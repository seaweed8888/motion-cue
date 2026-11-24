"""Native studio checks. No real keyboard events or hardware are used."""
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QSettings, QTimer
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QMessageBox, QScrollArea
from monitoring import dashboard
from monitoring.event_router import Router
from monitoring.live import LiveMonitor
from .test_event_routing import Keyboard
from .test_live import telemetry


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def settings(tmp_path):
    return QSettings(str(tmp_path/"studio.ini"), QSettings.Format.IniFormat)


def wait_until(app, predicate, timeout=3):
    deadline = time.monotonic()+timeout
    while not predicate() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.001)
    assert predicate()


def test_offline_and_error_states(app, settings):
    router = Router("test", Keyboard())
    window = dashboard.Dashboard(router, settings=settings)
    try:
        window.show()
        app.processEvents()
        assert window.threshold.lineEdit().width() > 50
        assert window.prediction.text() == "Idle"
        assert window.findChild(QFrame, "header") is None
        assert window.findChild(QScrollArea, "sidebar").width() == window.findChild(QScrollArea, "health").width()
        assert window.notice.isHidden() and window.capture_status.isHidden()
        copy = " ".join(label.text().lower() for label in window.findChildren(QLabel))
        for filler in ("ready when you are", "ready to record", "movement stays local", "no presentation keys are sent"):
            assert filler not in copy
        assert window.metrics["Broker"].text() == "Offline"
        assert not window.record.isEnabled() and not window.save.isEnabled()
        assert window.stop.isHidden() and window.save.isHidden() and window.discard.isHidden()
        router.connection(False, error="MQTT worker stopped: startup failed")
        window.refresh()
        assert "startup failed" in window.error.text()
        assert not window.record.isEnabled()
    finally:
        window.close()


def test_tilt_labeled_recording_and_settings(app, settings, tmp_path, monkeypatch):
    router = Router("test", Keyboard())
    router.connection(True)
    live = LiveMonitor("test")
    live.receive(telemetry([[t, 0, 9.81, 9.81, 0, 0, 0] for t in (0, .01, .02)]))
    window = dashboard.Dashboard(router, live, settings)
    try:
        assert window.record.isEnabled()
        assert window.metrics["Telemetry"].text() == "Streaming"
        assert window.tilt.target.x() == pytest.approx(1)
        window.user.setText("one")
        window.session.setText("day1")
        window.record_label.setCurrentIndex(2)
        window.record.click()
        assert not window.record_label.isEnabled() and window.stop.isEnabled()
        assert window.record.isHidden() and not window.stop.isHidden() and not window.discard.isHidden()
        live.receive(telemetry([[t, 0, 0, 9.81, 0, 0, 0] for t in (.03, .04, .05)]))
        window.stop.click()
        assert window.save.isEnabled() and "3 samples" in window.capture_status.text()
        assert window.stop.isHidden() and not window.save.isHidden()
        save = live.save_recording
        monkeypatch.setattr(live, "save_recording", lambda: save(tmp_path))
        window.save.click()
        wait_until(app, lambda: "save" not in window._jobs)
        assert len(list(tmp_path.glob("recording-*.json"))) == 1
        assert not window.save.isEnabled() and window.user.isEnabled()
        window.acceleration.setValue(2.)
        window.threshold.setValue(.9)
        assert live.threshold == .9 and live.acceleration_onset == 2.
        assert float(settings.value("confidence")) == .9
        window.toggle_fullscreen()
        assert window.isFullScreen()
        assert window.fullscreen_button.property("active") is True
        window.leave_fullscreen()
        assert not window.isFullScreen()
        assert window.fullscreen_button.property("active") is False
    finally:
        window.monitor.discard_recording()
        window.close()
    restored = dashboard.Dashboard(router, settings=settings)
    assert restored.threshold.value() == .9
    assert restored.acceleration.value() == 2.
    restored.close()


def test_unsaved_close_can_cancel_or_discard(app, settings, monkeypatch):
    router = Router("test", Keyboard())
    router.connection(True)
    live = LiveMonitor("test")
    live.receive(telemetry())
    live.start_recording("one", "day1", 1)
    window = dashboard.Dashboard(router, live, settings)
    window.show()
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Cancel)
    assert not window.close()
    assert live.recording is not None
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Discard)
    assert window.close()
    assert live.recording is None


def test_enabled_keyboard_is_refused(app, settings):
    keyboard = Keyboard()
    keyboard.enabled = True
    with pytest.raises(ValueError, match="keyboard output disabled"):
        dashboard.Dashboard(Router("test", keyboard), settings=settings)


def test_tilt_trail_fades_and_clears_on_disconnect(app):
    now = [0.]
    view = dashboard.TiltView(clock=lambda: now[0])
    view.show()
    view.animation.stop()
    try:
        view.set_tilt(30, 15, True)
        for _ in range(20):
            now[0] += .016
            view.animate()
        assert view.trail and view.position.x() > 0
        assert view.position == view.target
        assert all(now[0]-timestamp < .55 for _, timestamp in view.trail)
        for _ in range(120):
            now[0] += .016
            view.animate()
        assert not view.trail
        view.set_tilt(-30, 0, True)
        view.animate()
        assert view.trail
        view.set_tilt(0, 0, False)
        assert not view.trail and view.target.isNull()
    finally:
        view.close()


def test_gray_off_orange_on_resets_after_timeout(app, settings):
    now = [100.]
    router = Router("test", Keyboard())
    live = LiveMonitor("test", clock=lambda: now[0])
    window = dashboard.Dashboard(router, live, settings)
    window.show()
    app.processEvents()
    try:
        idle_color = window.prediction.palette().color(QPalette.ColorRole.WindowText)
        off_surface = window.sidebar.widget().palette().color(QPalette.ColorRole.Window)
        assert window.sidebar.property("powered") is False
        assert not window.tilt.online
        router.connection(True)
        live.receive(telemetry())
        live.prediction, live.confidence, live.predicted_at = "Swipe right", .9, now[0]
        live.history.appendleft(dict(gesture="Swipe right", confidence=.9, time="12:00:00"))
        window.refresh()
        assert window.sidebar.property("powered") is True and window.tilt.online
        assert window.signal.property("live") is True
        assert window.prediction.palette().color(QPalette.ColorRole.WindowText) != idle_color
        assert window.sidebar.widget().palette().color(QPalette.ColorRole.Window) != off_surface
        assert window.metrics["Sample rate"].property("accent") is True
        now[0] += 2
        window.refresh()
        assert window.sidebar.property("powered") is False and not window.tilt.online
        assert window.signal.property("live") is False
        assert window.prediction.palette().color(QPalette.ColorRole.WindowText) == idle_color
        assert window.sidebar.widget().palette().color(QPalette.ColorRole.Window) == off_surface
        assert window.metrics["Sample rate"].property("accent") is False
    finally:
        window.close()


def test_main_starts_maximized_and_stops_listener(app, settings, monkeypatch, tmp_path):
    class Listener:
        def __init__(self, config, router, telemetry=None):
            self.stop_event = threading.Event()
            self.closed = False
            self.router = router
            assert callable(telemetry)
            listeners.append(self)

        def run(self):
            self.stop_event.wait()

        def close(self):
            self.closed = True
            self.stop_event.set()

    listeners = []
    broker_starts = []

    def run_with_broker(config, listener):
        broker_starts.append(config["broker"])
        listener.run()

    monkeypatch.setattr(dashboard, "run_with_broker", run_with_broker)
    monkeypatch.setattr(dashboard, "Listener", Listener)
    monkeypatch.setattr(dashboard, "QApplication", lambda args: app)
    monkeypatch.setattr(dashboard, "QSettings", lambda *args: settings)
    monkeypatch.chdir(tmp_path)
    maximized = []

    def exit_app():
        maximized.append(any(widget.isMaximized() and not widget.isFullScreen()
                             for widget in app.topLevelWidgets()))
        app.quit()

    QTimer.singleShot(50, exit_app)
    assert dashboard.main([]) == 0
    assert maximized == [True] and listeners[0].closed
    assert broker_starts == ["127.0.0.1"]
    assert not listeners[0].router.keyboard.enabled
    for widget in app.topLevelWidgets():
        widget.close()


@pytest.mark.parametrize("module", [False, True])
def test_launch_help(module):
    root = Path(__file__).resolve().parents[1]
    command = ["-m", "monitoring.dashboard"] if module else ["dashboard.py"]
    result = subprocess.run([sys.executable, *command, "--help"],
                            cwd=root if module else root/"monitoring",
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert "--config" in result.stdout and "--enable-keyboard" not in result.stdout


def test_bad_config_exits_before_opening_window(tmp_path, capsys):
    config = tmp_path/"bad.json"
    config.write_text('{"device_id":"test"}')
    with pytest.raises(SystemExit) as error:
        dashboard.main(["--config", str(config)])
    assert error.value.code == 2
    assert "broker must be" in capsys.readouterr().err


def test_ball_reads_latest_pose_without_waiting_for_health_refresh(app, settings):
    router = Router("test", Keyboard())
    router.connection(True)
    now = [100.]
    live = LiveMonitor("test", clock=lambda: now[0])
    window = dashboard.Dashboard(router, live, settings)
    window.timer.stop()
    try:
        live.receive(telemetry([[t, 0, 9.81, 9.81, 0, 0, 0] for t in (0, .01, .02)]))
        window.tilt.animate()
        assert window.tilt.position.x() == pytest.approx(1)
        assert window.tilt.online
        assert window.metrics["Telemetry"].text() == "No signal"
        now[0] += 2
        window.tilt.animate()
        assert not window.tilt.online and window.tilt.position.isNull()
        assert not window.tilt.trail
    finally:
        window.close()


def test_model_loading_leaves_ui_responsive(app, settings, monkeypatch, tmp_path):
    router = Router("test", Keyboard())
    router.connection(True)
    live = LiveMonitor("test")
    window = dashboard.Dashboard(router, live, settings)
    wait_until(app, lambda: not window._jobs)
    started, release = threading.Event(), threading.Event()
    path = tmp_path/"fixture.pkl"

    def read(path):
        started.set()
        assert release.wait(3)
        return Path(path), dict(model=object(), synthetic=True), .85

    monkeypatch.setattr(live, "read_model", read)
    try:
        window.models.addItem("Fixture", str(path))
        window.models.setCurrentIndex(1)
        assert started.wait(2)
        assert window.model_info.text() == "Loading model…"
        assert not window.models.isEnabled() and not window.threshold.isEnabled()
        live.receive(telemetry([[t, 0, 9.81, 9.81, 0, 0, 0] for t in (0, .01, .02)]))
        window.tilt.animate()
        assert window.tilt.position.x() == pytest.approx(1)
        app.processEvents()
    finally:
        release.set()
        wait_until(app, lambda: "model" not in window._jobs)
        window.close()
    assert live.model is None  # Closing invalidates in-flight inference.
    assert window.threshold.value() == .85
    assert window.models.isEnabled()


def test_failed_async_save_keeps_take_and_cancels_deferred_close(app, settings, monkeypatch):
    router = Router("test", Keyboard())
    router.connection(True)
    live = LiveMonitor("test")
    live.receive(telemetry())
    live.start_recording("one", "day1", 1)
    live.receive(telemetry([[t, 0, 0, 9.81, 0, 0, 0] for t in (.03, .04, .05)]))
    live.stop_recording()
    window = dashboard.Dashboard(router, live, settings)
    started, release = threading.Event(), threading.Event()

    def fail():
        started.set()
        assert release.wait(3)
        raise OSError("disk full")

    monkeypatch.setattr(live, "save_recording", fail)
    window.show()
    try:
        window.save_recording()
        assert started.wait(2)
        assert not window.save.isEnabled() and not window.discard.isEnabled()
        assert not window.close()
        assert window._close_after_save
        release.set()
        wait_until(app, lambda: "save" not in window._jobs)
        assert "disk full" in window.error.text()
        assert live.recording is not None and window.isVisible()
        assert not window._close_after_save and window.save.isEnabled()
    finally:
        release.set()
        live.discard_recording()
        window.close()
