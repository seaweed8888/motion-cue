import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import secrets
import threading
import time
from .event_router import Router
from .keyboard_output import Keyboard, KEYS
from .mqtt_listener import Listener

WEB = Path(__file__).parent / "web"


def make_handler(router):
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, code, data, mime="application/json"):
            payload = json.dumps(data).encode() if mime == "application/json" else data
            self.send_response(code)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(payload)

        def valid_host(self):
            return self.headers.get("Host") in (f"localhost:{self.server.server_port}",
                                                  f"127.0.0.1:{self.server.server_port}")

        def do_GET(self):
            if not self.valid_host():
                return self.reply(403, {"error": "Invalid host"})
            if self.path == "/favicon.ico":
                return self.reply(204, b"", "image/x-icon")
            if self.path == "/api/state":
                return self.reply(200, dict(router.snapshot(), token=token, keys=list(KEYS)))
            if self.path == "/api/stream":
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                try:
                    while True:
                        self.wfile.write(("data: " + json.dumps(router.snapshot()) + "\n\n").encode())
                        self.wfile.flush()
                        time.sleep(0.4)
                except (ConnectionError, OSError):
                    return
            assets = {"/": ("index.html", "text/html; charset=utf-8"),
                      "/styles.css": ("styles.css", "text/css"),
                      "/app.js": ("app.js", "text/javascript")}
            if self.path not in assets:
                return self.reply(404, {"error": "Not found"})
            name, mime = assets[self.path]
            self.reply(200, (WEB / name).read_bytes(), mime)

        def do_POST(self):
            if not self.valid_host() or self.headers.get("X-MotionLink-Token") != token:
                return self.reply(403, {"error": "Invalid request token"})
            try:
                length = int(self.headers.get("Content-Length", 0))
                if not 0 < length <= 4096:
                    raise ValueError("Invalid body length")
                body = json.loads(self.rfile.read(length))
                if self.path == "/api/mode":
                    router.command(body["armed"])
                elif self.path == "/api/mappings":
                    router.remap(body)
                else:
                    return self.reply(404, {"error": "Not found"})
                self.reply(200, router.snapshot())
            except (ValueError, KeyError, TypeError) as exc:
                self.reply(400, {"error": str(exc)})
    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="monitoring/config.example.json")
    parser.add_argument("--enable-keyboard", action="store_true")
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())
    router = Router(config["device_id"], Keyboard(args.enable_keyboard))
    listener = Listener(config, router)
    threading.Thread(target=listener.run, daemon=True).start()
    server = ThreadingHTTPServer(("127.0.0.1", config.get("web_port", 8765)), make_handler(router))
    print(f"Dashboard: http://127.0.0.1:{server.server_port} (keyboard {'ON' if args.enable_keyboard else 'dry-run'})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        listener.close()
        server.server_close()


if __name__ == "__main__":
    main()
