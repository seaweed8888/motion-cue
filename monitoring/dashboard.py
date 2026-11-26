"""Native local IMU/model studio: python monitoring/dashboard.py."""
import argparse
from collections import deque
import json
import math
from pathlib import Path
import sys
import threading
import time

from PySide6.QtCore import QPointF, QRectF, QSettings, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QKeySequence, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient, QShortcut
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDoubleSpinBox, QFormLayout, QFrame, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from monitoring.event_router import Router
from monitoring.keyboard_output import Keyboard
from monitoring.local_broker import run_with_broker
from monitoring.live import FEATURE_VERSION, LABELS, ROOT, LiveMonitor
from monitoring.mqtt_listener import Listener


def text_label(text, name=""):
    label = QLabel(text)
    label.setObjectName(name)
    label.setWordWrap(True)
    return label


def style_state(widget, name, value):
    if widget.property(name) != value:
        widget.setProperty(name, value)
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()


class TiltView(QWidget):
    def __init__(self, clock=time.monotonic, source=None):
        super().__init__()
        self.clock = clock
        self.source = source
        self.setMinimumSize(260, 260)
        self.setAccessibleName("IMU gesture ball; follows movement and centers at rest")
        self.position = QPointF()
        self.target = QPointF()
        self.online = False
        self.trail = deque(maxlen=36)
        self.animation = QTimer(self)
        self.animation.setTimerType(Qt.TimerType.PreciseTimer)
        self.animation.timeout.connect(self.animate)
        self.animation.start(16)

    def set_motion(self, x, y, online):
        changed = self.online != online
        self.online = online
        if not online:
            self.trail.clear()
        self.target = QPointF(x, y) if online else QPointF()
        if changed:
            self.update()

    def animate(self):
        if self.source is not None:
            self.set_motion(*self.source())
        now = self.clock()
        had_trail = bool(self.trail)
        while self.trail and now-self.trail[0][1] >= .55:
            self.trail.popleft()
        delta = self.target-self.position
        if abs(delta.x()) + abs(delta.y()) > .0005:
            if self.online:
                self.trail.append((QPointF(self.position), now))
            self.position = QPointF(self.target)
            self.update()
        elif had_trail:
            self.update()

    def hideEvent(self, event):
        self.animation.stop()
        self.trail.clear()
        super().hideEvent(event)

    def showEvent(self, event):
        self.animation.start(16)
        super().showEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        area = QRectF(self.rect()).adjusted(12, 6, -12, -20)
        painter.setPen(Qt.PenStyle.NoPen)
        for spread, opacity in ((12, 2), (9, 3), (6, 4), (3, 5)):
            painter.setBrush(QColor(35, 42, 54, opacity))
            shadow = area.adjusted(-spread, -spread, spread, spread).translated(0, 7)
            painter.drawRoundedRect(shadow, 16+spread, 16+spread)
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawRoundedRect(area, 16, 16)
        center = area.center()
        radius = max(60., min(area.width(), area.height())*.33)
        well = QRadialGradient(center, radius)
        well.setColorAt(0, QColor("#F1F2F5"))
        well.setColorAt(1, QColor("#FFFFFF"))
        painter.setBrush(well)
        painter.drawEllipse(center, radius, radius)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for factor in (1., .66, .33):
            painter.setPen(QPen(QColor("#E0E2E7"), 1))
            painter.drawEllipse(center, radius*factor, radius*factor)
        painter.setPen(QPen(QColor("#D3D6DD"), 1, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(center.x()-radius-18, center.y()), QPointF(center.x()+radius+18, center.y()))
        painter.drawLine(QPointF(center.x(), center.y()-radius-18), QPointF(center.x(), center.y()+radius+18))
        painter.setPen(QColor("#686C74"))
        painter.setFont(QFont("Segoe UI", 10))
        painter.drawText(QRectF(area.left()+24, area.top()+20, area.width()-48, 24), "Gesture motion")
        painter.drawText(QRectF(area.left()+24, area.bottom()-38, area.width()-48, 24),
                         Qt.AlignmentFlag.AlignCenter, "Live movement  ·  Centers at rest")
        point = center + self.position*radius
        now = self.clock()
        trail = [*self.trail, (self.position, now)]
        left, right = [], []
        for index, (position, timestamp) in enumerate(trail):
            tangent = trail[min(index+1, len(trail)-1)][0]-trail[max(index-1, 0)][0]
            length = math.hypot(tangent.x(), tangent.y())
            if length < .00001:
                continue
            strength = max(0., 1-(now-timestamp)/.55)
            normal = QPointF(-tangent.y(), tangent.x())*((1+9*strength)/length)
            left.append(center+position*radius+normal)
            right.append(center+position*radius-normal)
        if len(left) > 1:
            ribbon = QPainterPath(left[0])
            for edge in [*left[1:], *reversed(right)]:
                ribbon.lineTo(edge)
            ribbon.closeSubpath()
            fade = max(0., 1-(now-self.trail[-1][1])/.55)
            gradient = QLinearGradient(left[0], left[-1])
            gradient.setColorAt(0, QColor(211, 82, 48, 0))
            gradient.setColorAt(1, QColor(211, 82, 48, round(70*fade)))
            painter.fillPath(ribbon, gradient)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(70, 45, 28, 14))
        painter.drawEllipse(point+QPointF(0, 7), 24, 24)
        gradient = QRadialGradient(point-QPointF(7, 9), 36)
        gradient.setColorAt(0, QColor("#F8B294" if self.online else "#DDE0E5"))
        gradient.setColorAt(.45, QColor("#D35230" if self.online else "#9298A2"))
        gradient.setColorAt(1, QColor("#B43718" if self.online else "#656C77"))
        painter.setBrush(gradient)
        painter.drawEllipse(point, 22, 22)
        painter.end()


class Dashboard(QWidget):
    task_finished = Signal(str, object)

    def __init__(self, router, monitor=None, settings=None):
        super().__init__()
        if router.keyboard.enabled:
            raise ValueError("The live testing dashboard requires keyboard output disabled")
        self.router = router
        self.monitor = monitor or LiveMonitor(router.device_id)
        self.settings = settings if settings is not None else QSettings("MotionCue", "Studio")
        self._jobs = set()
        self._closed = False
        self._close_after_save = False
        self.task_finished.connect(self.finish_task)
        self.setWindowTitle("Motion Cue — Live studio")
        self.resize(1440, 900)
        self.setMinimumSize(1050, 680)
        stylesheet = Path(__file__).with_name("desktop.qss").read_text()
        self.setStyleSheet(stylesheet.replace("@CHEVRON@", Path(__file__).with_name("chevron.svg").as_posix()))
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        body = QHBoxLayout()
        body.setSpacing(0)
        outer.addLayout(body, 1)
        left, left_layout = self.panel("sidebar", 292)
        self.sidebar = left
        body.addWidget(left)
        left_layout.addWidget(text_label("Model", "section"))
        self.models = QComboBox()
        self.models.setAccessibleName("Local trained model")
        self.models.currentIndexChanged.connect(self.load_selected_model)
        left_layout.addWidget(self.models)
        self.reload = QPushButton("Refresh model library")
        self.reload.setObjectName("quiet")
        self.reload.clicked.connect(self.refresh_models)
        left_layout.addWidget(self.reload, alignment=Qt.AlignmentFlag.AlignLeft)
        self.model_info = text_label("No model loaded. Add a trained .pkl to models/.", "modelState")
        left_layout.addWidget(self.model_info)
        self.divider(left_layout)
        left_layout.addWidget(text_label("Fine tuning", "section"))
        form = QFormLayout()
        form.setVerticalSpacing(12)
        self.threshold = self.spin(0, 1, .75, .05, "")
        self.acceleration = self.spin(.61, 10, 1.2, .1, " m/s²")
        self.rotation = self.spin(.36, 10, .7, .05, " rad/s")
        form.addRow("Confidence", self.threshold)
        form.addRow("Accel. onset", self.acceleration)
        form.addRow("Gyro onset", self.rotation)
        left_layout.addLayout(form)
        reset = QPushButton("Reset thresholds")
        reset.setObjectName("quiet")
        reset.clicked.connect(self.reset_thresholds)
        left_layout.addWidget(reset, alignment=Qt.AlignmentFlag.AlignLeft)
        self.divider(left_layout)
        left_layout.addWidget(text_label("Collect & label", "section"))
        self.user = QLineEdit(self.settings.value("user", ""))
        self.user.setPlaceholderText("User")
        self.user.setToolTip("User identifier, for example partner1")
        self.user.setAccessibleName("Recording user")
        self.session = QLineEdit(self.settings.value("session", ""))
        self.session.setPlaceholderText("Session")
        self.session.setToolTip("Recording session, for example day1")
        self.session.setAccessibleName("Recording session")
        identity = QHBoxLayout()
        identity.addWidget(self.user)
        identity.addWidget(self.session)
        left_layout.addLayout(identity)
        self.record_label = QComboBox()
        self.record_label.setAccessibleName("Gesture label for this recording")
        self.record_label.setToolTip("Record one gesture type per take; this label covers the entire recording.")
        for key, label in LABELS.items():
            self.record_label.addItem(label.replace("_", " ").capitalize(), int(key))
        left_layout.addWidget(self.record_label)
        row = QHBoxLayout()
        self.record = QPushButton("Record")
        self.record.setObjectName("primary")
        self.record.clicked.connect(self.start_recording)
        self.stop = QPushButton("Stop")
        self.stop.clicked.connect(self.stop_recording)
        row.addWidget(self.record)
        row.addWidget(self.stop)
        self.save = QPushButton("Save take")
        self.save.setObjectName("primary")
        self.save.clicked.connect(self.save_recording)
        self.discard = QPushButton("Discard")
        self.discard.setObjectName("quiet")
        self.discard.clicked.connect(self.discard_recording)
        row.addWidget(self.save)
        row.addWidget(self.discard)
        row.addStretch()
        left_layout.addLayout(row)
        self.capture_status = text_label("", "muted")
        left_layout.addWidget(self.capture_status)
        left_layout.addStretch()
        middle = QWidget()
        center = QVBoxLayout(middle)
        center.setContentsMargins(32, 28, 32, 24)
        center.setSpacing(12)
        title = QHBoxLayout()
        title.addStretch()
        self.signal = text_label("Waiting for device", "pill")
        title.addWidget(self.signal)
        center.addLayout(title)
        self.prediction = text_label("Idle", "prediction")
        self.prediction.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center.addWidget(self.prediction)
        self.prediction_info = text_label("Connect your controller to see live movement.", "muted")
        self.prediction_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center.addWidget(self.prediction_info)
        self.tilt = TiltView(source=self.motion_pose)
        center.addWidget(self.tilt, 1)
        self.angles = text_label("Roll  —      Pitch  —", "angles")
        self.angles.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center.addWidget(self.angles)
        center.addSpacing(10)
        center.addWidget(text_label("Recent predictions", "section"))
        self.history = text_label("", "muted")
        self.history.setMinimumHeight(52)
        center.addWidget(self.history)
        body.addWidget(middle, 1)
        right, right_layout = self.panel("health", 292)
        body.addWidget(right)
        right_layout.addWidget(text_label("Connection & health", "section"))
        right_layout.addWidget(text_label(router.device_id, "muted"))
        self.metrics = {}
        for group in (("MQTT Broker", "Controller", "Telemetry"),
                      ("Sample rate", "Expected rate", "Last sample", "Samples received"),
                      ("Data gaps", "Invalid batches", "Inference skips", "Device mode"),
                      ("Last gesture", "Confidence", "Feature version")):
            self.divider(right_layout)
            for name in group:
                line = QHBoxLayout()
                line.addWidget(text_label(name, "muted"))
                value = text_label("—", "metric")
                value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                line.addWidget(value)
                self.metrics[name] = value
                right_layout.addLayout(line)
        right_layout.addStretch()
        self.fullscreen_button = QPushButton("Fullscreen")
        self.fullscreen_button.setObjectName("quiet")
        self.fullscreen_button.setToolTip("Toggle fullscreen (F11). Esc returns to a window.")
        self.fullscreen_button.clicked.connect(self.toggle_fullscreen)
        right_layout.addWidget(self.fullscreen_button, alignment=Qt.AlignmentFlag.AlignRight)
        self.error = text_label("", "error")
        self.error.setContentsMargins(28, 6, 28, 6)
        self.error.setAccessibleName("Dashboard error")
        outer.addWidget(self.error)
        self.notice = text_label("", "muted")
        self.notice.setContentsMargins(28, 8, 28, 8)
        outer.addWidget(self.notice)
        QShortcut(QKeySequence("F11"), self, activated=self.toggle_fullscreen)
        QShortcut(QKeySequence("Escape"), self, activated=self.leave_fullscreen)
        self.models.addItem("Choose a model…", "")
        for key, control in (("confidence", self.threshold), ("acceleration", self.acceleration),
                             ("rotation", self.rotation)):
            try:
                control.setValue(float(self.settings.value(key, control.value())))
            except (ValueError, TypeError):
                pass
            control.valueChanged.connect(self.apply_thresholds)
        self.apply_thresholds()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(80)
        self.refresh()
        self.models.setFocus()
        self.refresh_models()

    def panel(self, name, width):
        scroll = QScrollArea()
        scroll.setObjectName(name)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFixedWidth(width)
        widget = QWidget()
        widget.setObjectName(name + "Content")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(8)
        scroll.setWidget(widget)
        return scroll, layout

    def divider(self, layout):
        line = QFrame()
        line.setObjectName("divider")
        line.setFixedHeight(1)
        layout.addSpacing(2)
        layout.addWidget(line)
        layout.addSpacing(2)

    def spin(self, low, high, value, step, suffix):
        control = QDoubleSpinBox()
        control.setRange(low, high)
        control.setSingleStep(step)
        control.setValue(value)
        control.setSuffix(suffix)
        control.setKeyboardTracking(False)
        control.setAlignment(Qt.AlignmentFlag.AlignRight)
        control.lineEdit().setTextMargins(8, 0, 8, 0)
        control.setToolTip("Laptop testing only. Type a value or use the up/down arrow keys to adjust.")
        control.setMinimumWidth(110)
        return control

    def refresh_models(self):
        if self._jobs & {"library", "model"}:
            return
        self.models.setEnabled(False)
        self.reload.setEnabled(False)
        self.run_task("library", lambda: sorted((ROOT / "models").rglob("*.pkl")))

    def populate_models(self, paths):
        selected = self.models.currentData() or self.settings.value("model", "")
        self.models.blockSignals(True)
        self.models.clear()
        self.models.addItem("Choose a model…", "")
        for path in paths:
            self.models.addItem(str(path.relative_to(ROOT / "models")), str(path))
        index = self.models.findData(selected)
        self.models.setCurrentIndex(max(0, index))
        self.models.blockSignals(False)
        self.load_selected_model()

    def load_selected_model(self):
        path = self.models.currentData()
        self.monitor.clear_model()
        if not path:
            self.model_info.setText("No model loaded. Add a trained .pkl to models/.")
            self.settings.setValue("model", "")
            return
        self.model_info.setText("Loading model…")
        self.models.setEnabled(False)
        self.reload.setEnabled(False)
        for control in (self.threshold, self.acceleration, self.rotation):
            control.setEnabled(False)
        self.run_task("model", lambda: self.monitor.read_model(path))

    def run_task(self, kind, action):
        if kind in self._jobs:
            return
        self._jobs.add(kind)

        def work():
            try:
                result = action()
            except Exception as exc:
                result = exc
            self.task_finished.emit(kind, result)

        threading.Thread(target=work, daemon=True).start()

    def finish_task(self, kind, result):
        self._jobs.discard(kind)
        if self._closed:
            return
        if kind in ("library", "model"):
            self.models.setEnabled(True)
            self.reload.setEnabled(True)
        if kind == "model":
            for control in (self.threshold, self.acceleration, self.rotation):
                control.setEnabled(True)
        if isinstance(result, Exception):
            self.error.setText(f"Could not {dict(library='scan models', model='load model', save='save take')[kind]}: {result}")
            if kind == "model":
                self.model_info.setText("Model could not be loaded. Choose another model.")
            self._close_after_save = False
        elif kind == "library":
            self.populate_models(result)
        elif kind == "model":
            previous = self.settings.value("model", "")
            confidence = self.threshold.value()
            self.monitor.install_model(result)
            self.threshold.setValue(confidence if str(result[0]) == previous else self.monitor.threshold)
            self.apply_thresholds()
            self.model_info.setText("Fixture model · test only" if self.monitor.synthetic_model
                                    else "Model ready · 4 classes · 55 features")
            self.settings.setValue("model", str(result[0]))
            self.error.clear()
        elif kind == "save":
            self.notice.setText(f"Saved {result.name} to data/raw/")
            self.error.clear()
            if self._close_after_save:
                self._close_after_save = False
                self.close()
                return
        self.refresh()

    def motion_pose(self):
        x, y, online = self.monitor.motion_pose()
        return x, y, online and self.router.broker

    def apply_thresholds(self):
        self.monitor.configure(self.threshold.value(), self.acceleration.value(), self.rotation.value())
        for key, control in (("confidence", self.threshold), ("acceleration", self.acceleration),
                             ("rotation", self.rotation)):
            self.settings.setValue(key, control.value())

    def reset_thresholds(self):
        self.threshold.setValue(self.monitor.default_threshold)
        self.acceleration.setValue(1.2)
        self.rotation.setValue(.7)

    def start_recording(self):
        try:
            self.monitor.start_recording(self.user.text(), self.session.text(), self.record_label.currentData())
            self.settings.setValue("user", self.user.text().strip())
            self.settings.setValue("session", self.session.text().strip())
            self.error.clear()
        except ValueError as exc:
            self.error.setText(str(exc))
        self.refresh()

    def stop_recording(self):
        self.monitor.stop_recording()
        self.refresh()

    def save_recording(self):
        self.run_task("save", self.monitor.save_recording)
        self.refresh()

    def discard_recording(self):
        self.monitor.discard_recording()
        self.notice.setText("Unsaved take discarded.")
        self.error.clear()
        self.refresh()

    def refresh(self):
        host, live = self.router.snapshot(), self.monitor.snapshot()
        if not host["broker"] and live["online"]:
            self.monitor.disconnected()
            live = self.monitor.snapshot()
        if self.sidebar.property("powered") != live["online"]:
            for widget in (self.sidebar, *self.sidebar.findChildren(QWidget)):
                style_state(widget, "powered", live["online"])
        style_state(self.model_info, "active", self.monitor.model is not None)
        self.signal.setText("Live telemetry" if live["online"] else "Waiting for device")
        style_state(self.signal, "live", live["online"])
        self.prediction.setText(live["prediction"])
        active_prediction = live["online"] and live["prediction"] not in ("Idle", "Other")
        style_state(self.prediction, "active", active_prediction)
        info = f"{live['confidence']:.0%} confidence" if active_prediction else ""
        self.prediction_info.setText(info)
        self.prediction_info.setVisible(bool(info))
        self.tilt.set_motion(*self.motion_pose())
        self.angles.setText(f"Roll  {live['roll']:+.1f}°      Pitch  {live['pitch']:+.1f}°"
                            if live["online"] else "Roll  —      Pitch  —")
        values = {"MQTT Broker": "Connected" if host["broker"] else "Offline",
                  "Controller": "Connected" if host["online"] else "Waiting",
                  "Telemetry": "Streaming" if live["online"] else "No signal",
                  "Sample rate": f"{live['rate']:.1f} Hz" if live["online"] else "—",
                  "Expected rate": f"{live['nominal']:g} Hz" if live["nominal"] else "—",
                  "Last sample": f"{live['age']:.1f}s ago" if live["age"] is not None else "—",
                  "Samples received": f"{live['total']:,}", "Data gaps": str(live["gaps"]),
                  "Invalid batches": str(live["invalid"]),
                  "Inference skips": str(live["inference_skips"]),
                  "Device mode": "Armed" if host["online"] and host["armed"] else "Disarmed",
                  "Last gesture": live["history"][0]["gesture"] if live["history"] else "—",
                  "Confidence": f"{live['confidence']:.0%}" if live["confidence"] is not None else "—",
                  "Feature version": str(FEATURE_VERSION)}
        for name, value in values.items():
            self.metrics[name].setText(value)
            accent = ((name in ("MQTT Broker", "Controller", "Telemetry", "Device mode")
                       and value in ("Connected", "Streaming", "Armed"))
                      or (name == "Sample rate" and live["online"])
                      or (name in ("Last gesture", "Confidence") and active_prediction))
            warning = name in ("Data gaps", "Invalid batches", "Inference skips") and value != "0"
            style_state(self.metrics[name], "accent", accent or warning)
        self.history.setText("\n".join(f"{item['time']}     {item['gesture']}     {item['confidence']:.0%}"
                                      for item in live["history"][:3])
                             or "")
        state = live["recording_state"]
        self.record.setVisible(state == "idle")
        self.stop.setVisible(state == "recording")
        self.save.setVisible(state == "review")
        self.discard.setVisible(state != "idle")
        self.record.setEnabled(state == "idle" and live["online"] and host["broker"])
        self.stop.setEnabled(state == "recording")
        self.save.setEnabled(state == "review" and "save" not in self._jobs and not live["recording_error"] and live["recording_count"] >= 3)
        self.discard.setEnabled(state != "idle" and "save" not in self._jobs)
        for control in (self.user, self.session, self.record_label):
            control.setEnabled(state == "idle")
        self.capture_status.setText("" if state == "idle" else
                                   f"{live['recording_count']:,} samples · {'Recording' if state == 'recording' else 'Review take'}")
        self.capture_status.setVisible(state != "idle")
        failure = host["error"] or live["recording_error"] or live["error"]
        if failure:
            self.error.setText(failure)
        self.error.setVisible(bool(self.error.text()))
        self.notice.setVisible(bool(self.notice.text()))
        self.fullscreen_button.setText("Exit fullscreen" if self.isFullScreen() else "Fullscreen")
        style_state(self.fullscreen_button, "active", self.isFullScreen())

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.leave_fullscreen()
        else:
            self._was_maximized = self.isMaximized()
            self.showFullScreen()
        self.refresh()

    def leave_fullscreen(self):
        if self.isFullScreen():
            self.showMaximized() if getattr(self, "_was_maximized", False) else self.showNormal()
            self.refresh()

    def closeEvent(self, event):
        if "save" in self._jobs:
            self._close_after_save = True
            event.ignore()
            return
        if self.monitor.recording is not None:
            self.monitor.stop_recording()
            result = QMessageBox.question(self, "Unsaved recording", "Save this labeled take before closing?",
                                          QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard |
                                          QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel)
            if result == QMessageBox.StandardButton.Cancel:
                event.ignore()
                self.refresh()
                return
            if result == QMessageBox.StandardButton.Save:
                self._close_after_save = True
                self.save_recording()
                event.ignore()
                return
            else:
                self.monitor.discard_recording()
        self.timer.stop()
        self.tilt.animation.stop()
        self._closed = True
        self.monitor.clear_model()
        self.settings.sync()
        event.accept()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Open the Motion Cue desktop IMU and model studio")
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("config.example.json"))
    args = parser.parse_args(argv)
    try:
        config = json.loads(args.config.read_text(encoding="utf-8"))
        router = Router(config["device_id"], Keyboard())
        monitor = LiveMonitor(config["device_id"])
        listener = Listener(config, router, telemetry=monitor.receive)
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        parser.error(str(exc))
    app = QApplication(sys.argv[:1])
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    window = Dashboard(router, monitor)
    worker = threading.Thread(target=run_with_broker, args=(config, listener), daemon=True)
    worker.start()
    try:
        window.showMaximized()
        return app.exec()
    finally:
        window.timer.stop()
        window.tilt.animation.stop()
        monitor.clear_model()
        listener.stop_event.set()
        worker.join()
        listener.close()


if __name__ == "__main__":
    sys.exit(main())
