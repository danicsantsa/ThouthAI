"""
CaptureSuite — Qt (PySide6) layout
-----------------------------------
Rebuilds the CaptureSuite redesign (instrument-panel look, segmented
mode selector, session timer, camera signal strip, multi-app picker
for Hyperfocus, transport controls) as a native Qt window.

Run:
    pip install PySide6
    python capturesuite_qt.py
"""

import sys
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QPushButton, QCheckBox, QFrame, QButtonGroup,
)


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
SAGE = "#7ea08f"
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
QFrame#topbar {{
    border-bottom: 1px solid {LINE};
}}
QFrame#console {{
    background: {PANEL};
    border: 1px solid {LINE};
    border-radius: 10px;
}}
QPushButton#modeBtn {{
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    color: {TEXT_MUTED};
    font-family: {SANS_FONT};
    font-size: 13px;
    font-weight: 500;
    padding: 14px 10px;
}}
QPushButton#modeBtn:checked {{
    color: {TEXT};
    border-bottom: 2px solid {AMBER};
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
QLabel#signalTitle {{
    color: {TEXT_MUTED};
    font-size: 12px;
}}
QLabel#signalValue {{
    color: {TEXT};
    font-family: {MONO_FONT};
    font-size: 12px;
}}
QLabel#fieldLabel {{
    color: {TEXT_MUTED};
    font-size: 12px;
}}
QLabel#hintLabel {{
    color: {TEXT_FAINT};
    font-size: 11.5px;
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

    def __init__(self, color: str, size: int = 8):
        super().__init__()
        self.setFixedSize(size, size)
        self.setStyleSheet(f"background: {color}; border-radius: {size // 2}px;")


class AppCheck(QCheckBox):
    def __init__(self, name: str):
        super().__init__(name)
        self.setObjectName("appCheck")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CaptureSuite — Workspace Tracking")
        self.resize(680, 760)
        self.setStyleSheet(STYLESHEET)

        self.seconds = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)

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

    def _build_topbar(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("topbar")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 18)

        brand_box = QHBoxLayout()
        brand_box.setSpacing(10)
        brand_box.addWidget(Dot(AMBER, size=9))

        name = QLabel("CaptureSuite")
        name.setObjectName("brandName")
        brand_box.addWidget(name)

        sub = QLabel("Workspace Tracking")
        sub.setObjectName("brandSub")
        brand_box.addWidget(sub)

        brand_widget = QWidget()
        brand_widget.setLayout(brand_box)
        layout.addWidget(brand_widget)
        layout.addStretch(1)

        conn_box = QHBoxLayout()
        conn_box.setSpacing(7)
        conn_box.addWidget(Dot(SAGE, size=6))
        conn_label = QLabel("Supabase verbunden")
        conn_label.setObjectName("connLabel")
        conn_box.addWidget(conn_label)

        conn_widget = QWidget()
        conn_widget.setLayout(conn_box)
        layout.addWidget(conn_widget)

        return frame

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

        modes = [
            ("standard", "Standard", "Nur Sitzung"),
            ("fokus", "Fokus", "Kamera-Erkennung"),
            ("hyperfokus", "Hyperfokus", "Mehrere Apps erlaubt"),
        ]
        self.mode_buttons = {}
        for key, title, desc in modes:
            btn = QPushButton(f"{title}\n{desc}")
            btn.setObjectName("modeBtn")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, k=key: self._on_mode_changed(k))
            self.mode_group.addButton(btn)
            self.mode_buttons[key] = btn
            layout.addWidget(btn, 1)

        self.mode_buttons["hyperfokus"].setChecked(True)
        return wrap

    def _build_readout(self) -> QWidget:
        wrap = QWidget()
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(28, 26, 28, 20)
        layout.setSpacing(14)

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

        self.timer_display = QLabel("00:00:00")
        self.timer_display.setObjectName("timerDisplay")
        layout.addWidget(self.timer_display)

        caption = QLabel("Läuft ohne festes Zeitlimit — du bestimmst die Dauer")
        caption.setObjectName("timerCaption")
        layout.addWidget(caption)

        self.signal_block = self._build_signal_block()
        layout.addWidget(self.signal_block)

        self.app_picker = self._build_app_picker()
        layout.addWidget(self.app_picker)

        return wrap

    def _build_signal_block(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("signalBlock")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        head = QHBoxLayout()
        title = QLabel("Kamera-Signal")
        title.setObjectName("signalTitle")
        head.addWidget(title)
        head.addStretch(1)
        self.signal_value = QLabel("bereit")
        self.signal_value.setObjectName("signalValue")
        head.addWidget(self.signal_value)
        layout.addLayout(head)

        bars_row = QHBoxLayout()
        bars_row.setSpacing(3)
        import random
        for i in range(24):
            bar = QFrame()
            height = random.randint(10, 22)
            color = AMBER if (i + 1) % 4 == 0 else SAGE
            bar.setFixedHeight(height)
            bar.setStyleSheet(f"background: {color}; border-radius: 1px;")
            bars_row.addWidget(bar)
        layout.addLayout(bars_row)

        return frame

    def _build_app_picker(self) -> QWidget:
        wrap = QWidget()
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(8)

        label = QLabel("Erlaubte Apps im Hyperfokus")
        label.setObjectName("fieldLabel")
        layout.addWidget(label)

        grid = QGridLayout()
        grid.setSpacing(8)
        app_names = ["Notion", "VS Code", "Word", "PDF-Reader"]
        self.app_checks = []
        for i, app_name in enumerate(app_names):
            cb = AppCheck(app_name)
            cb.stateChanged.connect(self._update_app_hint)
            self.app_checks.append(cb)
            grid.addWidget(cb, i // 2, i % 2)
        layout.addLayout(grid)

        self.app_hint = QLabel(
            "Während des Hyperfokus bleiben nur die ausgewählten Apps "
            "zugänglich. Alle anderen Benachrichtigungen werden stummgeschaltet."
        )
        self.app_hint.setObjectName("hintLabel")
        self.app_hint.setWordWrap(True)
        layout.addWidget(self.app_hint)

        return wrap

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

    def _on_mode_changed(self, mode_key: str):
        labels = {"standard": "Standard", "fokus": "Fokus", "hyperfokus": "Hyperfokus"}
        self.session_tag.setText(f"Modus: {labels[mode_key]}")
        self.app_picker.setVisible(mode_key == "hyperfokus")
        self.signal_block.setVisible(mode_key != "standard")

    def _update_app_hint(self):
        chosen = [cb.text() for cb in self.app_checks if cb.isChecked()]
        if chosen:
            self.app_hint.setText(
                "Erlaubt: " + ", ".join(chosen) +
                ". Alle anderen Apps und Benachrichtigungen werden während der Sitzung blockiert."
            )
        else:
            self.app_hint.setText(
                "Während des Hyperfokus bleiben nur die ausgewählten Apps "
                "zugänglich. Alle anderen Benachrichtigungen werden stummgeschaltet."
            )

    def _on_start(self):
        self.timer.start(1000)
        self._set_dot(self.state_dot, AMBER)
        self.state_text.setText("Sitzung läuft")
        self.start_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)

    def _on_pause(self):
        self.timer.stop()
        self._set_dot(self.state_dot, SAGE)
        self.state_text.setText("Pausiert")
        self.start_btn.setEnabled(True)
        self.start_btn.setText("▶  Fortsetzen")

    def _on_stop(self):
        self.timer.stop()
        self.seconds = 0
        self.timer_display.setText(self._format(self.seconds))
        self._set_dot(self.state_dot, SAGE)
        self.state_text.setText("Bereit")
        self.start_btn.setEnabled(True)
        self.start_btn.setText("▶  Start")
        self.pause_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)

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
    app.setFont(__import__("PySide6.QtGui", fromlist=["QFont"]).QFont("IBM Plex Sans", 10))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
