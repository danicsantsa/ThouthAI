"""
Atum — Qt (PySide6) layout
-----------------------------------
Instrument-panel look, segmented mode selector, session timer, camera
signal strip, multi-app picker for Hyperfokus (as its own popup window),
transport controls, and live Supabase/backend status.

Run:
    pip install PySide6
    python capturesuite_qt.py
"""

import sys
import random
import os
from pathlib import Path
import gui_settings
import db_client
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QPushButton, QCheckBox, QFrame, QButtonGroup,
    QSizePolicy, QDialog, QDialogButtonBox, QScrollArea, QVBoxLayout,
)
from PySide6.QtGui import QFont


# ---------------------------------------------------------------------------
# Color tokens (mirrors the HTML redesign)
# ---------------------------------------------------------------------------
BG = "#14171c"
PANEL = "#1b1f26"
PANEL_RAISED = "#21262e"
LINE = "#2b313b"
TEXT = "#eeece6"
TEXT_MUTED = "#8d94a0"
TEXT_FAINT = "#5c6470"
AMBER = "#d98e3f"
AMBER_DIM = "rgba(217,142,63,40)"
SAGE = "#7ea08f"
SAGE_DIM = "rgba(126,160,143,40)"
DANGER = "#d66b5d"

MONO_FONT = "IBM Plex Mono, Consolas, monospace"
SANS_FONT = "IBM Plex Sans, Segoe UI, sans-serif"

STYLESHEET = f"""
QMainWindow, QWidget#root {{
    background: {BG};
}}
QLabel {{
    color: {TEXT};
    font-family: {SANS_FONT};
}}
QLabel#brandName {{
    font-size: 17px;
    font-weight: 600;
}}
QLabel#brandSub {{
    color: {TEXT_FAINT};
    font-size: 12px;
}}
QLabel#connLabel {{
    color: {TEXT_MUTED};
    font-size: 12px;
}}
QLabel#statusLabel {{
    color: {TEXT_MUTED};
    font-size: 11px;
}}
QLabel#statusGood {{
    color: {SAGE};
    font-size: 11px;
    font-weight: 600;
}}
QLabel#statusWarning {{
    color: {AMBER};
    font-size: 11px;
    font-weight: 600;
}}
QLabel#statusBad {{
    color: {DANGER};
    font-size: 11px;
    font-weight: 600;
}}
QFrame#topbar {{
    border-bottom: 1px solid {LINE};
}}
QFrame#statusStrip {{
    background: {PANEL_RAISED};
    border-top: 1px solid {LINE};
}}
QFrame#console {{
    background: {PANEL};
    border: 1px solid {LINE};
    border-radius: 10px;
}}
QPushButton#modeBtn {{
    background: transparent;
    border: none;
    border-bottom: 3px solid transparent;
    color: {TEXT_MUTED};
    font-family: {SANS_FONT};
    font-size: 13px;
    font-weight: 500;
    padding: 18px 10px 15px;
}}
QPushButton#modeBtn:checked {{
    color: {TEXT};
    border-bottom: 3px solid {AMBER};
    background: rgba(217, 142, 63, 10);
}}
QPushButton#modeBtn:hover {{
    color: {TEXT};
}}
QLabel#stateText {{
    color: {TEXT_MUTED};
    font-size: 13px;
}}
QLabel#sessionTag {{
    color: {TEXT_FAINT};
    font-size: 12px;
}}
QLabel#timerDisplay {{
    color: {TEXT};
    font-family: {MONO_FONT};
    font-size: 46px;
    font-weight: 500;
}}
QLabel#timerCaption {{
    color: {TEXT_FAINT};
    font-size: 12px;
}}
QFrame#signalBlock {{
    background: {PANEL_RAISED};
    border: 1px solid {LINE};
    border-radius: 8px;
}}
QFrame#hyperfocusHintBox {{
    background: rgba(217, 142, 63, 18);
    border: 1px solid {AMBER};
    border-radius: 10px;
}}
QLabel#fieldLabel {{
    color: {TEXT_MUTED};
    font-size: 12px;
}}
QLabel#hintLabel {{
    color: {TEXT_FAINT};
    font-size: 11.5px;
}}
QLabel#hyperfocusMessage {{
    color: {TEXT};
    font-size: 12.5px;
    font-weight: 500;
}}
QCheckBox#appCheck {{
    background: {PANEL_RAISED};
    border: 1px solid {LINE};
    border-radius: 7px;
    padding: 9px 10px;
    color: {TEXT};
    font-size: 13px;
}}
QCheckBox#appCheck:hover {{
    border: 1px solid {TEXT_FAINT};
}}
QCheckBox#appCheck::indicator {{
    width: 14px;
    height: 14px;
}}
QPushButton#transportBtn {{
    background: {PANEL_RAISED};
    border: 1px solid {LINE};
    border-radius: 7px;
    color: {TEXT};
    font-family: {SANS_FONT};
    font-size: 14px;
    font-weight: 500;
    padding: 12px 10px;
}}
QPushButton#transportBtn:hover {{
    border: 1px solid {TEXT_FAINT};
}}
QPushButton#transportBtn:disabled {{
    color: {TEXT_FAINT};
}}
QPushButton#transportBtnPrimary {{
    background: {AMBER};
    border: 1px solid {AMBER};
    border-radius: 7px;
    color: #201203;
    font-family: {SANS_FONT};
    font-size: 14px;
    font-weight: 600;
    padding: 12px 10px;
}}
QPushButton#transportBtnPrimary:disabled {{
    background: {PANEL_RAISED};
    border: 1px solid {LINE};
    color: {TEXT_FAINT};
}}
QLabel#footnote {{
    color: {TEXT_FAINT};
    font-size: 11.5px;
}}
"""


class Dot(QFrame):
    """Small colored status dot."""

    def __init__(self, color: str, ring: str = None, size: int = 8):
        super().__init__()
        self.setFixedSize(size, size)
        style = f"background: {color}; border-radius: {size // 2}px;"
        self.setStyleSheet(style)


class AppCheck(QCheckBox):
    def __init__(self, name: str):
        super().__init__(name)
        self.setObjectName("appCheck")


class AppSelectionDialog(QDialog):
    """Small popup window for choosing which apps stay available in Hyperfokus."""

    DEFAULT_APP_NAMES = ["Notion", "VS Code", "Word", "PDF-Reader"]

    @staticmethod
    def _discover_apps():
        """Collect installed desktop apps from the local system."""
        seen = set()
        apps = []
        app_dirs = [
            Path.home() / ".local" / "share" / "applications",
            Path("/usr/share/applications"),
            Path("/var/lib/snapd/desktop/applications"),
        ]

        for app_dir in app_dirs:
            if not app_dir.exists():
                continue
            for desktop_file in sorted(app_dir.glob("*.desktop")):
                try:
                    content = desktop_file.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                for line in content.splitlines():
                    if not line.startswith("Name="):
                        continue
                    name = line.split("=", 1)[1].strip()
                    if not name or name in seen:
                        continue
                    seen.add(name)
                    apps.append(name)

        if apps:
            recent = [
                "VS Code", "Firefox", "Terminal", "Notion", "Chrome", "Files", "LibreOffice Writer",
                "Spotify", "Slack", "Microsoft Teams", "Discord"
            ]
            ordered = []
            for name in recent:
                if name in apps and name not in ordered:
                    ordered.append(name)
            for name in apps:
                if name not in ordered:
                    ordered.append(name)
            return ordered[:80]
        return list(AppSelectionDialog.DEFAULT_APP_NAMES)

    def __init__(self, parent=None, checked_apps=None):
        super().__init__(parent)
        self.setWindowTitle("Apps für Hyperfokus")
        self.setFixedWidth(360)
        self.setMinimumHeight(200)
        self.setStyleSheet(parent.styleSheet() if parent else "")

        checked_apps = checked_apps or set()
        app_names = self._discover_apps()

        self.setLayout(QVBoxLayout())
        layout = self.layout()
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(10)

        self.primary_checks = []
        self.checks = []

        primary_widget = QWidget()
        primary_grid = QGridLayout(primary_widget)
        primary_grid.setSpacing(8)
        for i, name in enumerate(app_names[:4]):
            cb = AppCheck(name)
            cb.setChecked(name in checked_apps)
            self.primary_checks.append(cb)
            self.checks.append(cb)
            primary_grid.addWidget(cb, i // 2, i % 2)
        layout.addWidget(primary_widget)

        if len(app_names) > 4:
            extra_label = QLabel("Weitere Apps")
            extra_label.setStyleSheet("color: #7f8c8d; font-size: 11px; font-weight: 600;")
            layout.addWidget(extra_label)

            scroll = QScrollArea(self)
            scroll.setWidgetResizable(True)
            scroll.setMinimumHeight(140)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

            extra_widget = QWidget()
            extra_grid = QGridLayout(extra_widget)
            extra_grid.setSpacing(8)
            for i, name in enumerate(app_names[4:]):
                cb = AppCheck(name)
                cb.setChecked(name in checked_apps)
                self.checks.append(cb)
                extra_grid.addWidget(cb, i // 2, i % 2)
            scroll.setWidget(extra_widget)
            layout.addWidget(scroll)

        buttons = QDialogButtonBox()
        done_btn = QPushButton("Fertig")
        done_btn.setObjectName("transportBtnPrimary")
        done_btn.clicked.connect(self.accept)
        buttons.addButton(done_btn, QDialogButtonBox.AcceptRole)
        layout.addWidget(buttons)

    def selected_apps(self):
        return [cb.text() for cb in self.checks if cb.isChecked()]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Atum")
        self.resize(680, 760)
        self.setStyleSheet(STYLESHEET)

        self.seconds = 0
        self.session_mode = "standard"
        self.selected_apps = []
        self.tracker = self._create_tracker()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.backend_timer = QTimer(self)
        self.backend_timer.timeout.connect(self._refresh_backend_status)
        self.backend_timer.start(4000)

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)

        outer = QVBoxLayout(root)
        outer.setContentsMargins(40, 32, 40, 40)
        outer.setSpacing(24)

        outer.addWidget(self._build_topbar())
        outer.addWidget(self._build_console())
        outer.addWidget(self._build_footnote())
        outer.addStretch(1)
        self._on_mode_changed("standard")

    # ------------------------------------------------------------------
    # Top bar: brand + connection status
    # ------------------------------------------------------------------
    def _build_topbar(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("topbar")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 18)

        brand_box = QHBoxLayout()
        brand_box.setSpacing(10)
        mark = Dot(AMBER, size=9)
        brand_box.addWidget(mark)
        name = QLabel("Atum")
        name.setObjectName("brandName")
        brand_box.addWidget(name)
        sub = QLabel("Learning Focus")
        sub.setObjectName("brandSub")
        brand_box.addWidget(sub)
        brand_widget = QWidget()
        brand_widget.setLayout(brand_box)
        layout.addWidget(brand_widget)
        layout.addStretch(1)

        return frame

    # ------------------------------------------------------------------
    # Console: mode selector + readout + transport controls
    # ------------------------------------------------------------------
    def _build_console(self) -> QWidget:
        console = QFrame()
        console.setObjectName("console")
        layout = QVBoxLayout(console)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_mode_selector())
        layout.addWidget(self._build_readout())
        layout.addWidget(self._build_transport())

        return console

    def _build_mode_selector(self) -> QWidget:
        wrap = QFrame()
        wrap.setStyleSheet(f"border-bottom: 1px solid {LINE};")
        layout = QHBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)

        # plain labels only — no subtitles under the mode names
        modes = [
            ("standard", "Standard"),
            ("focus", "Fokus"),
            ("hyperfocus", "Hyperfokus"),
        ]
        self.mode_buttons = {}
        for key, title in modes:
            btn = QPushButton(title)
            btn.setObjectName("modeBtn")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, k=key: self._on_mode_changed(k))
            self.mode_group.addButton(btn)
            self.mode_buttons[key] = btn
            layout.addWidget(btn, 1)

        self.mode_buttons["standard"].setChecked(True)
        self._on_mode_changed("standard")
        return wrap

    def _build_readout(self) -> QWidget:
        wrap = QWidget()
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(28, 26, 28, 20)
        layout.setSpacing(14)

        # state row
        state_row = QHBoxLayout()
        state_left = QHBoxLayout()
        state_left.setSpacing(8)
        self.state_dot = Dot(SAGE, size=7)
        state_left.addWidget(self.state_dot)
        self.state_text = QLabel("Bereit")
        self.state_text.setObjectName("stateText")
        state_left.addWidget(self.state_text)
        state_left_widget = QWidget()
        state_left_widget.setLayout(state_left)
        state_row.addWidget(state_left_widget)
        state_row.addStretch(1)
        self.session_tag = QLabel("Modus: Hyperfokus")
        self.session_tag.setObjectName("sessionTag")
        state_row.addWidget(self.session_tag)
        layout.addLayout(state_row)

        # timer
        self.timer_display = QLabel("00:00:00")
        self.timer_display.setObjectName("timerDisplay")
        layout.addWidget(self.timer_display)

        # signal block (camera activity) — no label text, just the bars,
        # which move only while a session is actively recording
        self.signal_block = self._build_signal_block()
        layout.addWidget(self.signal_block)

        # app picker (hyperfocus) — a button that opens its own window
        self.app_picker = self._build_app_picker()
        layout.addWidget(self.app_picker)

        self.hyperfocus_hint_box = self._build_hyperfocus_hint_box()
        self.hyperfocus_hint_box.setVisible(False)
        self.hyperfocus_message.setText("")

        return wrap

    def _build_signal_block(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("signalBlock")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(0)

        bars_row = QHBoxLayout()
        bars_row.setSpacing(3)
        self.signal_bars = []
        for i in range(24):
            bar = QFrame()
            bar.setFixedHeight(4)
            color = AMBER if (i + 1) % 4 == 0 else SAGE
            bar.setStyleSheet(f"background: {color}; border-radius: 1px;")
            bars_row.addWidget(bar)
            self.signal_bars.append(bar)
        layout.addLayout(bars_row)

        # only redraws bar heights while a session is actively recording
        self.signal_timer = QTimer(self)
        self.signal_timer.timeout.connect(self._animate_signal)

        return frame

    def _build_app_picker(self) -> QWidget:
        wrap = QWidget()
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(6)

        self.app_picker_btn = QPushButton("Hyperfokus-App")
        self.app_picker_btn.setObjectName("transportBtn")
        self.app_picker_btn.setCursor(Qt.PointingHandCursor)
        self.app_picker_btn.clicked.connect(self._open_app_dialog)
        layout.addWidget(self.app_picker_btn)

        self.app_hint = QLabel("")
        self.app_hint.setObjectName("hintLabel")
        self.app_hint.setWordWrap(True)
        layout.addWidget(self.app_hint)

        return wrap

    def _open_app_dialog(self):
        dialog = AppSelectionDialog(self, checked_apps=set(self.selected_apps))
        if dialog.exec() == QDialog.Accepted:
            self.selected_apps = dialog.selected_apps()
            self._update_app_hint()

    def _update_app_hint(self):
        if self.selected_apps:
            self.app_picker_btn.setText(
                self.selected_apps[0] if len(self.selected_apps) == 1
                else f"{len(self.selected_apps)} Apps"
            )
            self.app_hint.setText("")
        else:
            self.app_picker_btn.setText("Hyperfokus-App")
            self.app_hint.setText("")

    def _camera_observation_message(
        self,
        face_detected=True,
        looking_away=False,
        blink_detected=False,
        phone_use_count=0,
        distraction_count=0,
        fatigue_level=0,
    ):
        """Return a plain observation-based status message without coaching tips."""
        if phone_use_count >= 2 or distraction_count >= 3:
            return (
                "Handy-/Ablenkungsfrequenz erkannt: Mehrfaches Abweichen von der Arbeitsaufgabe. "
                "Konzentration derzeit reduziert."
            )

        if not face_detected:
            return (
                "Kamera: Kein Gesicht erkannt. Blickzustand derzeit nicht verlässlich."
            )

        if looking_away:
            return (
                "Kamera: Blick ist abgelenkt. Aufmerksamkeit derzeit außerhalb der Arbeitsfläche."
            )

        if blink_detected or fatigue_level >= 2:
            return (
                "Kamera: Müdigkeit / häufiges Blinzeln erkannt. Erhöhte Ermüdung sichtbar."
            )

        return (
            "Kamera: Blick stabil und fokussiert. Kein wesentlicher Ablenkungszustand erkannt."
        )

    def _build_hyperfocus_hint_box(self) -> QWidget:
        box = QFrame()
        box.setObjectName("hyperfocusHintBox")
        box.setVisible(False)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        title = QLabel("Hyperfokus-Tipp")
        title.setObjectName("fieldLabel")
        layout.addWidget(title)

        self.hyperfocus_message = QLabel(
            self._camera_observation_message(face_detected=True, looking_away=False, blink_detected=False)
        )
        self.hyperfocus_message.setObjectName("hyperfocusMessage")
        self.hyperfocus_message.setWordWrap(True)
        layout.addWidget(self.hyperfocus_message)

        return box

    def _build_transport(self) -> QWidget:
        wrap = QFrame()
        wrap.setStyleSheet(f"border-top: 1px solid {LINE};")
        layout = QHBoxLayout(wrap)
        layout.setContentsMargins(28, 18, 28, 24)
        layout.setSpacing(10)

        self.start_btn = QPushButton("▶  Start")
        self.start_btn.setObjectName("transportBtnPrimary")
        self.start_btn.setCursor(Qt.PointingHandCursor)
        self.start_btn.clicked.connect(self._on_start)

        self.pause_btn = QPushButton("❙❙  Pause")
        self.pause_btn.setObjectName("transportBtn")
        self.pause_btn.setCursor(Qt.PointingHandCursor)
        self.pause_btn.setEnabled(False)
        self.pause_btn.clicked.connect(self._on_pause)

        self.stop_btn = QPushButton("■  Stopp")
        self.stop_btn.setObjectName("transportBtn")
        self.stop_btn.setCursor(Qt.PointingHandCursor)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._on_stop)

        for btn in (self.start_btn, self.pause_btn, self.stop_btn):
            layout.addWidget(btn, 1)

        return wrap

    def _build_footnote(self) -> QWidget:
        row = QHBoxLayout()
        left = QLabel("Entwurf — Statusanzeigen sind zu Vorschauzwecken animiert")
        left.setObjectName("footnote")
        right = QLabel("v0.2")
        right.setObjectName("footnote")
        row.addWidget(left)
        row.addStretch(1)
        row.addWidget(right)
        wrap = QWidget()
        wrap.setLayout(row)
        return wrap

    def _create_tracker(self):
        try:
            from tracking_gui import TrackingProcess
            return TrackingProcess()
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Behaviour
    # ------------------------------------------------------------------
    def _refresh_backend_status(self):
        # Database status is intentionally hidden from the UI.
        return

    def _on_mode_changed(self, mode_key: str):
        normalised_key = str(mode_key).strip().lower().replace("-", "")
        if normalised_key in {"fokus", "focus"}:
            mode_key = "focus"
        elif normalised_key in {"hyperfokus", "hyperfocus"}:
            mode_key = "hyperfocus"
        else:
            mode_key = "standard"

        self.session_mode = mode_key
        labels = {"standard": "Standard", "focus": "Fokus", "hyperfocus": "Hyperfokus"}
        if hasattr(self, "session_tag"):
            self.session_tag.setText(f"Modus: {labels[mode_key]}")
        if hasattr(self, "app_picker"):
            self.app_picker.setVisible(mode_key == "hyperfocus")
        if hasattr(self, "hyperfocus_hint_box"):
            self.hyperfocus_hint_box.setVisible(False)
            self.hyperfocus_message.setText("")
        if hasattr(self, "signal_block"):
            self.signal_block.setVisible(mode_key != "standard")

        if hasattr(self, "mode_buttons") and mode_key in self.mode_buttons:
            for key, button in self.mode_buttons.items():
                button.setChecked(key == mode_key)

        if self.timer.isActive():
            self._on_stop()

    def _on_start(self):
        settings = gui_settings.load_settings()
        settings["user"] = settings.get("user") or "Atum User"
        settings["session_mode"] = self.session_mode
        settings["camera"] = settings.get("camera", 1)
        settings["rotate"] = settings.get("rotate", 0)
        settings["check_interval"] = settings.get("check_interval", 3)
        settings["db_flush_interval"] = settings.get("db_flush_interval", 2)
        settings["work_apps"] = settings.get("work_apps", "code")
        settings["non_work_apps"] = settings.get("non_work_apps", "spotify")
        if self.session_mode == "hyperfocus":
            settings["hyperfocus_app"] = self.selected_apps[0] if self.selected_apps else settings.get("hyperfocus_app", "")
        gui_settings.save_settings(settings)

        if self.tracker is None:
            self.tracker = self._create_tracker()

        if self.tracker is not None and self.session_mode != "standard":
            self.tracker.start(settings, mode=self.session_mode)

        self.timer.start(1000)
        self._set_dot(self.state_dot, AMBER)
        self.state_text.setText("Sitzung läuft")
        self.start_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.signal_timer.start(320)

    def _on_pause(self):
        if self.tracker is not None and self.tracker.is_running():
            self.tracker.pause()
        self.timer.stop()
        self._set_dot(self.state_dot, SAGE)
        self.state_text.setText("Pausiert")
        self.start_btn.setEnabled(True)
        self.start_btn.setText("▶  Fortsetzen")
        self.signal_timer.stop()
        self._reset_signal()

    def _on_stop(self):
        if self.tracker is not None:
            self.tracker.stop()
        self.timer.stop()
        self.seconds = 0
        self.timer_display.setText(self._format(self.seconds))
        self._set_dot(self.state_dot, SAGE)
        self.state_text.setText("Bereit")
        self.start_btn.setEnabled(True)
        self.start_btn.setText("▶  Start")
        self.pause_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.signal_timer.stop()
        self._reset_signal()

    def _animate_signal(self):
        for bar in self.signal_bars:
            bar.setFixedHeight(random.randint(6, 22))

    def _reset_signal(self):
        for bar in self.signal_bars:
            bar.setFixedHeight(4)

    def _tick(self):
        self.seconds += 1
        self.timer_display.setText(self._format(self.seconds))

    @staticmethod
    def _format(s: int) -> str:
        h, rem = divmod(s, 3600)
        m, sec = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{sec:02d}"

    @staticmethod
    def _set_dot(dot: Dot, color: str):
        size = dot.width()
        dot.setStyleSheet(f"background: {color}; border-radius: {size // 2}px;")


def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("IBM Plex Sans", 10))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()