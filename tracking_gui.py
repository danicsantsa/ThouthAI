"""Qt desktop interface for the Atum workspace tracking application."""

from __future__ import annotations

import datetime
import csv
import json
import os
import platform
import queue
import re
import signal
import subprocess
import sys
import threading
from pathlib import Path

import cv2
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QFont, QImageReader, QPixmap
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPlainTextEdit, QPushButton, QStackedWidget, QTabBar, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget, QHeaderView, QFrame,
)

import db_queries
import gui_settings
import db_client

RESOURCE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.environ.get("ATUM_DATA_DIR", RESOURCE_DIR)
os.makedirs(OUTPUT_DIR, exist_ok=True)
TRACK_ALL_PATH = os.path.join(OUTPUT_DIR, "track_all.py")
VIDEO_OUTPUT_DIR = os.path.join(OUTPUT_DIR, "recorded_videos")
PREVIEW_IMAGE_PATH = os.path.join(OUTPUT_DIR, "camera_preview.png")
SESSION_ID_PATTERN = re.compile(r"session_id=([a-f0-9\-]+)")
COLORS = {
    "bg": "#14171c",
    "panel": "#1b1f26",
    "panel_raised": "#21262e",
    "line": "#2b313b",
    "text": "#eeece6",
    "muted": "#8d94a0",
    "text_faint": "#5c6470",
    "amber": "#d98e3f",
    "amber_dim": "rgba(217, 142, 63, 0.14)",
    "sage": "#7ea08f",
    "sage_dim": "rgba(126,160,143,0.14)",
    "danger": "#c26a5c",
    "warning": "#f2c14e",
    "primary": "#39d98a",
    "primary_dark": "#1aa968",
    "success": "#39d98a",
}
VALID_SESSION_MODES = ("standard", "focus", "hyperfocus")
SESSION_MODE_LABELS = {
    "standard": "Standard",
    "focus": "Fokus",
    "hyperfocus": "Hyperfokus",
}


def normalize_session_mode(mode):
    """Normalize and validate a session mode value for the app and worker."""
    if mode is None:
        return "standard"
    normalized = str(mode).strip().lower().replace("-", "").replace(" ", "")
    aliases = {
        "standard": "standard",
        "default": "standard",
        "focus": "focus",
        "fokus": "focus",
        "fokusmodus": "focus",
        "hyperfocus": "hyperfocus",
        "hyperfokus": "hyperfocus",
        "hyperfocusmodus": "hyperfocus",
    }
    if normalized in aliases:
        return aliases[normalized]
    return "standard" if normalized in ("", "standard") else normalized if normalized in VALID_SESSION_MODES else "standard"


def apply_theme(app):
    app.setStyleSheet(f"""
        QWidget {{ background: {COLORS['bg']}; color: {COLORS['text']};
                   font-family: 'Noto Sans', 'DejaVu Sans', sans-serif;
                   font-size: 10pt; }}
        QMainWindow, QDialog {{ background: {COLORS['bg']}; }}
        QPushButton {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 {COLORS['primary']}, stop:1 {COLORS['primary_dark']});
                       color: #06100b; border: 0; border-radius: 8px;
                       padding: 10px 18px; font-weight: 700; min-height: 42px;
                       min-width: 170px; }}
        QPushButton:hover {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #63e6a5, stop:1 {COLORS['primary']}); }}
        QPushButton:disabled {{ background: #2a3a35; color: #7d9188; }}
        QLineEdit, QPlainTextEdit, QTableWidget {{ background: {COLORS['panel']};
            border: 1px solid {COLORS['line']}; border-radius: 8px; padding: 6px; }}
        QTableWidget {{ alternate-background-color: {COLORS['panel_raised']};
                        gridline-color: {COLORS['line']}; }}
        QHeaderView::section {{ background: #1d3028; color: {COLORS['muted']};
                                border: 0; padding: 8px; font-weight: 600; }}
        QTabBar::tab {{ background: {COLORS['panel']}; padding: 10px 18px; border: 0;
                        color: {COLORS['muted']}; }}
        QTabBar::tab:selected {{ color: {COLORS['primary']};
                                 border-bottom: 2px solid {COLORS['primary']}; }}
        #topBar {{ background: {COLORS['panel']}; border: 1px solid {COLORS['line']};
                   border-radius: 12px; margin: 12px 12px 0 12px; }}
        #consolePanel {{ background: {COLORS['panel']}; border: 1px solid {COLORS['line']};
                       border-radius: 10px; }}
        #modeStrip {{ border-bottom: 1px solid {COLORS['line']}; }}
        #modeButton {{ background: transparent; color: {COLORS['muted']}; border: 0; border-radius: 0;
                      padding: 15px 12px 13px; min-height: 0; min-width: 0; font-weight: 500; }}
        #modeButton:hover {{ background: rgba(255,255,255,0.02); color: {COLORS['text']}; }}
        #modeButton:selected, #modeButton:checked {{ background: transparent; color: {COLORS['text']}; }}
        #statusCard {{ background: {COLORS['panel']}; border: 1px solid {COLORS['line']};
                      border-radius: 10px; min-height: 260px; }}
        #readoutPanel {{ background: {COLORS['panel']}; border: 0; padding: 0; }}
        #signalPanel {{ background: {COLORS['panel_raised']}; border: 1px solid {COLORS['line']};
                       border-radius: 8px; padding: 16px 18px; }}
        #modeButton.active {{ color: {COLORS['text']}; border-bottom: 2px solid {COLORS['amber']}; }}
        #statusCard QPushButton {{ min-width: 120px; }}
        QComboBox {{ background: {COLORS['panel_raised']}; color: {COLORS['text']};
                    border: 1px solid {COLORS['line']}; border-radius: 7px;
                    padding: 11px 14px; min-height: 42px; }}
        QComboBox::drop-down {{ border: 0; background: transparent; }}
        QComboBox QAbstractItemView {{ background: {COLORS['panel_raised']}; color: {COLORS['text']};
                                     border: 1px solid {COLORS['line']}; selection-background-color: rgba(217,142,63,0.18); }}
        #mainPanel {{ background: transparent; border: 0; }}
        #metricCard {{ background: {COLORS['panel']}; border: 1px solid {COLORS['line']}; border-radius: 10px; }}
        QPushButton#secondaryButton {{ background: {COLORS['panel_raised']};
                   color: {COLORS['text']}; border: 1px solid {COLORS['line']}; }}
        QPushButton#secondaryButton:hover {{ border-color: {COLORS['primary']};
                             color: {COLORS['primary']}; }}
        QLabel {{ color: {COLORS['text']}; }}
    """)


class TrackingProcess:
    """Manage the tracking worker without blocking the Qt event loop."""

    def __init__(self):
        self.proc = None
        self.output_queue = queue.Queue()
        self.session_id = None
        self.state = "idle"
        self.mode = "standard"

    def is_running(self):
        return self.proc is not None and self.proc.poll() is None and self.state == "running"

    def is_paused(self):
        return self.proc is not None and self.proc.poll() is None and self.state == "paused"

    def start(self, settings, mode=None):
        self.mode = normalize_session_mode(mode or settings.get("session_mode") or self.mode)
        if self.mode == "standard":
            self.state = "idle"
            self.proc = None
            self.session_id = None
            return
        if self.is_running():
            return
        if self.proc is not None and self.proc.poll() is None:
            self.resume()
            return
        if getattr(sys, "frozen", False):
            command = [sys.executable, "--worker"]
        else:
            command = [sys.executable, "-u", os.path.join(RESOURCE_DIR, "atum.py"), "--worker"]
        command += [
                   "--user", settings["user"], "--camera", str(settings["camera"]),
                   "--rotate", str(settings["rotate"]),
                   "--check-interval", str(settings["check_interval"]),
                   "--db-flush-interval", str(settings["db_flush_interval"]),
                   "--work-apps", settings["work_apps"],
                   "--non-work-apps", settings["non_work_apps"],
                   "--session-mode", self.mode]
        if self.mode == "hyperfocus" and settings.get("hyperfocus_app"):
            command += ["--hyperfocus-app", settings["hyperfocus_app"]]
        if settings.get("device_name"):
            command += ["--device-name", settings["device_name"]]
        self.session_id = None
        options = dict(cwd=OUTPUT_DIR, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, text=True, bufsize=1,
                       stdin=subprocess.DEVNULL)
        if platform.system() == "Windows":
            options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            options["preexec_fn"] = os.setsid
        self.proc = subprocess.Popen(command, **options)
        self.state = "running"
        threading.Thread(target=self._read_output, daemon=True).start()

    def pause(self):
        if self.proc is None or self.proc.poll() is not None or self.state != "running":
            return False
        try:
            if platform.system() in ("Linux", "Darwin"):
                os.killpg(os.getpgid(self.proc.pid), signal.SIGSTOP)
            else:
                return False
        except Exception:
            return False
        self.state = "paused"
        return True

    def resume(self):
        if self.proc is None or self.proc.poll() is not None or self.state != "paused":
            return False
        try:
            if platform.system() in ("Linux", "Darwin"):
                os.killpg(os.getpgid(self.proc.pid), signal.SIGCONT)
            else:
                return False
        except Exception:
            return False
        self.state = "running"
        return True

    def _read_output(self):
        try:
            if self.proc is None or self.proc.stdout is None:
                self.output_queue.put(None)
                return
            for line in self.proc.stdout:
                line = line.rstrip("\n")
                self.output_queue.put(line)
                match = SESSION_ID_PATTERN.search(line)
                if match:
                    self.session_id = match.group(1)
        finally:
            if self.proc is not None and self.proc.stdout is not None:
                self.proc.stdout.close()
            self.output_queue.put(None)

    def stop(self):
        if self.proc is None:
            self.state = "idle"
            return
        if self.proc.poll() is not None:
            if self.proc.stdout is not None:
                self.proc.stdout.close()
            self.proc = None
            self.state = "idle"
            return
        try:
            if platform.system() == "Windows":
                self.proc.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGINT)
        except Exception:
            self.proc.terminate()
        self.state = "stopped"
        try:
            self.proc.wait(timeout=8)
        except Exception:
            pass
        if self.proc.stdout is not None:
            self.proc.stdout.close()
        self.proc = None
        self.state = "idle"


class QuickSetupDialog(QDialog):
    def __init__(self, parent=None, on_saved=None):
        super().__init__(parent)
        self.on_saved = on_saved
        self.setWindowTitle("Willkommen bei Atum")
        self.setModal(True)
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        title = QLabel("Erste Einrichtung")
        title.setFont(QFont("Noto Sans", 18, QFont.Weight.Bold))
        layout.addWidget(title)
        layout.addWidget(QLabel("Geben Sie Ihren Namen ein, um zu beginnen"))
        form = QFormLayout()
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Ihr Name")
        form.addRow("Name:", self.name_input)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self._save)
        layout.addWidget(buttons)
        self.name_input.returnPressed.connect(self._save)
        self.name_input.setFocus()

    def _save(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Name erforderlich", "Bitte geben Sie einen Namen ein.")
            return
        settings = gui_settings.load_settings()
        settings["user"] = name
        gui_settings.save_settings(settings)
        if self.on_saved:
            self.on_saved(settings)
        self.accept()


class HomeTab(QWidget):
    """Main tracking control view."""

    def __init__(self, parent=None, on_state_changed=None, on_open_dashboard=None):
        super().__init__(parent)
        self.on_state_changed = on_state_changed
        self.on_open_dashboard = on_open_dashboard
        self.tracker = TrackingProcess()
        self.session_mode = normalize_session_mode(gui_settings.load_settings().get("session_mode"))
        self._start_time = None
        self._elapsed_before_pause = 0
        self._session_started_at = None
        self._video_duration_cache = {}
        self._invalid_videos = set()
        self._preview_mtime = None
        self._focus_status_message = ""
        self.hyperfocus_app_combo = None
        self._build_ui()
        self._load_settings_into_header()
        self._show_last_session_summary()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._poll)
        self.timer.start(500)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        top_bar = QWidget()
        top_bar.setObjectName("topBar")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(18, 9, 18, 9)
        brand = QLabel("Atum")
        brand.setFont(QFont("Noto Sans", 10, QFont.Weight.DemiBold))
        brand.setStyleSheet(f"color: {COLORS['text']}; letter-spacing: 0.4px;")
        top_layout.addWidget(brand)
        top_layout.addStretch()
        self.connection_status = QLabel("●  TLS")
        self.connection_status.setStyleSheet(f"color: {COLORS['success']}; font-weight: 600; font-size: 9pt;")
        top_layout.addWidget(self.connection_status)
        layout.addWidget(top_bar)

        console = QWidget()
        console.setObjectName("consolePanel")
        console_layout = QVBoxLayout(console)
        console_layout.setContentsMargins(0, 0, 0, 0)
        console_layout.setSpacing(0)

        mode_row = QWidget()
        mode_row.setObjectName("modeStrip")
        mode_layout = QHBoxLayout(mode_row)
        mode_layout.setContentsMargins(0, 0, 0, 0)
        mode_layout.setSpacing(0)
        self.mode_buttons = {}
        for mode_name, label in (("standard", "Standard"), ("focus", "Fokus"), ("hyperfocus", "Hyperfokus")):
            button = QPushButton(label)
            button.setObjectName("modeButton")
            button.setCheckable(True)
            button.setProperty("mode", mode_name)
            button.clicked.connect(lambda checked, value=mode_name: self._set_session_mode(value))
            self.mode_buttons[mode_name] = button
            mode_layout.addWidget(button)

        readout = QWidget()
        readout.setObjectName("readoutPanel")
        readout_layout = QVBoxLayout(readout)
        readout_layout.setContentsMargins(28, 28, 28, 18)
        readout_layout.setSpacing(12)

        state_row = QHBoxLayout()
        self.status_indicator = QLabel("Bereit")
        self.status_indicator.setStyleSheet(f"color: {COLORS['success']}; font-weight: 700; font-size: 13px;")
        state_row.addWidget(self.status_indicator)
        state_row.addStretch()
        self.mode_label = QLabel(f"Modus: {SESSION_MODE_LABELS[self.session_mode]}")
        self.mode_label.setStyleSheet(f"color: {COLORS['muted']}; font-size: 12px;")
        state_row.addWidget(self.mode_label)
        readout_layout.addLayout(state_row)

        self.elapsed_time = QLabel("00:00:00")
        self.elapsed_time.setFont(QFont("Noto Sans Mono", 30, QFont.Weight.Bold))
        self.elapsed_time.setStyleSheet("color: #eeece6; letter-spacing: 0.01em;")
        readout_layout.addWidget(self.elapsed_time)

        timer_caption = QLabel("Läuft ohne festes Zeitlimit — du bestimmst die Dauer")
        timer_caption.setStyleSheet(f"color: {COLORS['text_faint']}; font-size: 12px;")
        readout_layout.addWidget(timer_caption)

        self.signal_panel = QWidget()
        self.signal_panel.setObjectName("signalPanel")
        signal_layout = QVBoxLayout(self.signal_panel)
        signal_layout.setContentsMargins(0, 0, 0, 0)
        signal_head = QHBoxLayout()
        signal_title = QLabel("Kamera-Signal")
        signal_title.setStyleSheet(f"color: {COLORS['muted']}; font-size: 12px;")
        self.signal_value = QLabel("bereit")
        self.signal_value.setStyleSheet(f"color: {COLORS['text']}; font-size: 12px;")
        signal_head.addWidget(signal_title)
        signal_head.addStretch()
        signal_head.addWidget(self.signal_value)
        signal_layout.addLayout(signal_head)

        bars = QWidget()
        bars_layout = QHBoxLayout(bars)
        bars_layout.setContentsMargins(0, 0, 0, 0)
        bars_layout.setSpacing(3)
        for idx in range(28):
            bar = QWidget()
            bar.setFixedHeight(26)
            bar.setStyleSheet(f"background: {COLORS['sage']}; border-radius: 1px; opacity: {0.5 if idx % 4 else 0.9};")
            bars_layout.addWidget(bar)
        signal_layout.addWidget(bars)
        readout_layout.addWidget(self.signal_panel)

        self.focus_status = QLabel("Fokusstatus: normal")
        self.focus_status.setStyleSheet(f"color: {COLORS['muted']}; font-size: 12px;")
        readout_layout.addWidget(self.focus_status)

        self.hyperfocus_label = QLabel("Erlaubte App im Hyperfokus")
        self.hyperfocus_label.setVisible(False)
        self.hyperfocus_label.setStyleSheet(f"color: {COLORS['muted']}; font-size: 12px;")
        readout_layout.addWidget(self.hyperfocus_label)

        self.hyperfocus_app_combo = QComboBox()
        self.hyperfocus_app_combo.setVisible(False)
        self.hyperfocus_app_combo.currentTextChanged.connect(self._on_hyperfocus_app_changed)
        readout_layout.addWidget(self.hyperfocus_app_combo)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        self.start_btn = QPushButton("Start")
        self.pause_btn = QPushButton("Pause")
        self.stop_btn = QPushButton("Stop")
        self.pause_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.start_btn.setMinimumWidth(120)
        self.pause_btn.setMinimumWidth(120)
        self.stop_btn.setMinimumWidth(120)
        self.start_btn.clicked.connect(self._on_start)
        self.pause_btn.clicked.connect(self._on_pause)
        self.stop_btn.clicked.connect(self._on_stop)
        buttons.addWidget(self.start_btn)
        buttons.addWidget(self.pause_btn)
        buttons.addWidget(self.stop_btn)
        readout_layout.addLayout(buttons)

        self._populate_hyperfocus_apps()
        self._update_focus_status_display()
        self._refresh_session_mode_buttons()
        self._sync_session_controls()

        console_layout.addWidget(mode_row)
        console_layout.addWidget(readout)
        layout.addWidget(console, 1)

        self.last_session = QLabel()
        self.last_session.setVisible(False)
        self.output_text = QPlainTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setVisible(False)

        status_bar = QWidget()
        status_layout = QHBoxLayout(status_bar)
        status_layout.setContentsMargins(16, 8, 16, 8)
        self.local_count = QLabel("▣  0 Datensätze lokal")
        self.local_count.setVisible(False)
        status_layout.addWidget(self.local_count)
        status_layout.addStretch()
        status_layout.addWidget(QLabel("Angemeldet als lokaler Benutzer"))
        layout.addWidget(status_bar)
        self._refresh_video_list()

    def _section_label(self, text):
        label = QLabel(text)
        label.setFont(QFont("Noto Sans", 11, QFont.Weight.DemiBold))
        return label

    def _refresh_video_list(self):
        # Database status is intentionally hidden from the UI.
        return

    def _load_video_metadata(self, video):
        metadata_path = video.with_suffix(".json")
        if not metadata_path.exists():
            return {}
        try:
            with metadata_path.open("r", encoding="utf-8") as metadata_file:
                return json.load(metadata_file)
        except (OSError, ValueError):
            return {}

    @staticmethod
    def _format_duration(seconds):
        if seconds is None:
            return "—"
        total_seconds = max(0, int(round(float(seconds))))
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def _read_video_duration(self, video):
        cache_key = str(video)
        if cache_key in self._video_duration_cache:
            return self._video_duration_cache[cache_key]
        capture = cv2.VideoCapture(str(video))
        try:
            fps = capture.get(cv2.CAP_PROP_FPS)
            frames = capture.get(cv2.CAP_PROP_FRAME_COUNT)
            if fps and fps > 0 and frames >= 0:
                duration = frames / fps
                self._video_duration_cache[cache_key] = duration
                return duration
        finally:
            capture.release()
        self._video_duration_cache[cache_key] = None
        return None

    def _refresh_preview(self):
        return

    def _load_settings_into_header(self):
        pass

    def _show_last_session_summary(self):
        user = gui_settings.load_settings().get("user", "")
        summary = "Letzte Sitzung: Noch keine Aufnahmen"
        if user:
            try:
                records = db_queries.session_records_for_user(user, limit=1)
                if records:
                    record = records[0]
                    summary = f"Letzte Sitzung: {record.get('start_time', '')} ({record.get('duration', 0)} Minuten)"
            except Exception:
                pass
        self.last_session.setText(summary)

    def _elapsed_seconds(self):
        if self._session_started_at is not None:
            return self._elapsed_before_pause + int((datetime.datetime.now() - self._session_started_at).total_seconds())
        return self._elapsed_before_pause

    def _update_focus_status_display(self, override_message=None):
        if override_message:
            text = f"Fokusstatus: {override_message}"
            self.focus_status.setText(text)
            self.focus_status.setStyleSheet(f"color: {COLORS['warning']}; font-size: 9pt;")
            return

        if self.session_mode == "standard":
            text = "Fokusstatus: normal"
            color = COLORS["muted"]
        elif self.session_mode == "focus":
            text = "Fokusstatus: aktiv"
            color = COLORS["primary"]
        else:
            text = "Fokusstatus: Hyperfocus aktiv"
            color = COLORS["warning"]
        self.focus_status.setText(text)
        self.focus_status.setStyleSheet(f"color: {color}; font-size: 9pt;")

    def _populate_hyperfocus_apps(self):
        if self.hyperfocus_app_combo is None:
            return
        settings = gui_settings.load_settings()
        apps = [item.strip() for item in str(settings.get("work_apps", "")).split(",") if item.strip()]
        if not apps:
            apps = ["code", "firefox", "chrome", "terminal", "slack"]
        self.hyperfocus_app_combo.blockSignals(True)
        self.hyperfocus_app_combo.clear()
        self.hyperfocus_app_combo.addItem("Bitte App wählen", "")
        for app in apps:
            self.hyperfocus_app_combo.addItem(app, app)
        current = settings.get("hyperfocus_app", "")
        if current:
            index = self.hyperfocus_app_combo.findData(current)
            if index >= 0:
                self.hyperfocus_app_combo.setCurrentIndex(index)
        self.hyperfocus_app_combo.blockSignals(False)
        self._sync_hyperfocus_controls()

    def _sync_hyperfocus_controls(self):
        if self.hyperfocus_app_combo is None:
            return
        is_hyperfocus = self.session_mode == "hyperfocus"
        self.hyperfocus_label.setVisible(is_hyperfocus)
        self.hyperfocus_app_combo.setVisible(is_hyperfocus)

    def _on_hyperfocus_app_changed(self, value):
        if not value:
            return
        settings = gui_settings.load_settings()
        settings["hyperfocus_app"] = value
        gui_settings.save_settings(settings)

    def _refresh_session_mode_buttons(self):
        for mode_name, button in self.mode_buttons.items():
            is_selected = mode_name == self.session_mode
            button.setChecked(is_selected)
            if is_selected:
                button.setStyleSheet(
                    "background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #63e6a5, stop:1 #39d98a); "
                    "color: #06100b; border: 0; border-radius: 8px; padding: 8px 12px; font-weight: 700;"
                )
            else:
                button.setStyleSheet(
                    "background: #182520; color: #e8f3ed; border: 1px solid #294238; border-radius: 8px; "
                    "padding: 8px 12px; font-weight: 600;"
                )
        self.mode_label.setText(f"Modus: {SESSION_MODE_LABELS[self.session_mode]}")
        self._sync_hyperfocus_controls()
        self._update_focus_status_display()
        if hasattr(self, "signal_panel"):
            self.signal_panel.setVisible(self.session_mode == "standard")

    def _set_session_mode(self, mode):
        self.session_mode = normalize_session_mode(mode)
        settings = gui_settings.load_settings()
        settings["session_mode"] = self.session_mode
        gui_settings.save_settings(settings)
        self._refresh_session_mode_buttons()
        if hasattr(self, "signal_panel"):
            self.signal_panel.setVisible(self.session_mode == "standard")
        if self.tracker is not None:
            self.tracker.mode = self.session_mode

    def _sync_session_controls(self):
        self.mode_label.setText(f"Modus: {SESSION_MODE_LABELS[self.session_mode]}")
        if hasattr(self, "signal_panel"):
            self.signal_panel.setVisible(self.session_mode == "standard")
        if self.tracker.is_running():
            self.start_btn.setEnabled(False)
            self.pause_btn.setEnabled(True)
            self.pause_btn.setText("Pause")
            self.stop_btn.setEnabled(True)
            self.status_indicator.setText("● Aufnahme läuft")
            self.status_indicator.setStyleSheet(f"color: {COLORS['success']}; font-weight: 600")
            self._update_focus_status_display(self._focus_status_message or None)
            return
        if self.tracker.is_paused():
            self.start_btn.setEnabled(False)
            self.pause_btn.setEnabled(True)
            self.pause_btn.setText("Resume")
            self.stop_btn.setEnabled(True)
            self.status_indicator.setText("● Pausiert")
            self.status_indicator.setStyleSheet(f"color: {COLORS['warning']}; font-weight: 600")
            self._update_focus_status_display(self._focus_status_message or None)
            return
        self.start_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setText("Pause")
        self.stop_btn.setEnabled(False)
        self.status_indicator.setText("● Bereit")
        self.status_indicator.setStyleSheet(f"color: {COLORS['success']}; font-weight: 600")
        self._update_focus_status_display()

    def is_tracking(self):
        return self.tracker.is_running() or self.tracker.is_paused()

    def _on_start(self):
        settings = gui_settings.load_settings()
        if not settings.get("user"):
            QMessageBox.warning(self, "Setup erforderlich", "Bitte geben Sie zuerst Ihren Namen ein.")
            return
        settings["session_mode"] = self.session_mode
        gui_settings.save_settings(settings)
        try:
            if self.session_mode == "hyperfocus":
                selected_app = self.hyperfocus_app_combo.currentData() if self.hyperfocus_app_combo is not None else ""
                settings["hyperfocus_app"] = selected_app or settings.get("hyperfocus_app", "")
                gui_settings.save_settings(settings)
            if self.tracker.is_paused():
                self.tracker.resume()
                self._session_started_at = datetime.datetime.now()
            else:
                self.tracker.start(settings, mode=self.session_mode)
                self._session_started_at = datetime.datetime.now()
                self._elapsed_before_pause = 0
            self._sync_session_controls()
            if self.on_state_changed:
                self.on_state_changed(settings["user"], None, True)
        except Exception as exc:
            QMessageBox.critical(self, "Fehler", f"Konnte Aufnahme nicht starten: {exc}")

    def _on_pause(self):
        if self.tracker.is_paused():
            if self.tracker.resume():
                self._session_started_at = datetime.datetime.now()
                self._sync_session_controls()
                if self.on_state_changed:
                    self.on_state_changed("", self.tracker.session_id, True)
            return
        if self.tracker.pause():
            self._elapsed_before_pause = self._elapsed_seconds()
            self._session_started_at = None
            self._sync_session_controls()
            if self.on_state_changed:
                self.on_state_changed("", self.tracker.session_id, False)

    def _on_stop(self):
        self.tracker.stop()
        self._elapsed_before_pause = 0
        self._session_started_at = None
        self._sync_session_controls()
        if self.on_state_changed:
            self.on_state_changed("", self.tracker.session_id, False)

    def _poll(self):
        try:
            while True:
                line = self.tracker.output_queue.get_nowait()
                if line is None:
                    break
                self.output_text.appendPlainText(line)
                if "[Fokus]" in line:
                    self._focus_status_message = line.split("[Fokus]", 1)[1].strip()
                    self._update_focus_status_display("Ablenkung erkannt")
                elif self._focus_status_message:
                    self._focus_status_message = ""
                    self._update_focus_status_display()
        except queue.Empty:
            pass
        if self.tracker.proc is not None and self.tracker.proc.poll() is not None and self.tracker.state != "idle":
            self.tracker.state = "idle"
            self._elapsed_before_pause = 0
            self._session_started_at = None
            self._focus_status_message = ""
            self._sync_session_controls()
        if self.tracker.is_running() and self._session_started_at is not None:
            seconds = self._elapsed_seconds()
            hours, remainder = divmod(seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            self.elapsed_time.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
        elif not self.tracker.is_running() and not self.tracker.is_paused():
            self.elapsed_time.setText("00:00:00")
        self._refresh_preview()
        self._refresh_video_list()

    def request_stop_for_shutdown(self):
        if self.is_tracking():
            self._on_stop()


class DashboardTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        header = QHBoxLayout()
        title = QLabel("MediaPipe AI — Erkennungsergebnisse")
        title.setFont(QFont("Noto Sans", 22, QFont.Weight.Bold))
        header.addWidget(title)
        header.addStretch()
        refresh_button = QPushButton("↻  Aktualisieren")
        refresh_button.setObjectName("secondaryButton")
        refresh_button.clicked.connect(self.refresh_results)
        header.addWidget(refresh_button)
        layout.addLayout(header)
        layout.addWidget(QLabel("Lokale Auswertung der tatsächlich aufgezeichneten MediaPipe-Daten."))

        self.session_label = QLabel("Letzte Aufnahme: noch keine Daten")
        self.session_label.setStyleSheet(f"color: {COLORS['muted']};")
        layout.addWidget(self.session_label)

        self.results = QTableWidget(0, 4)
        self.results.setHorizontalHeaderLabels(("Erkennung", "Ausgabe", "Frames / Events", "Modellstatus"))
        self.results.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.results.verticalHeader().setVisible(False)
        self.results.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.results, 1)

        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet(f"color: {COLORS['muted']};")
        layout.addWidget(self.info_label)
        self.refresh_results()
        layout.addStretch()

    def ensure_loaded(self):
        self.refresh_results()

    def notify_recording_state(self, user_name, session_id, running):
        if not running:
            self.refresh_results()

    def select_user_and_session(self, user_name, session_id):
        self.refresh_results()

    def refresh_results(self):
        detections = (
            ("Pose", "Körper-Landmarks", "pose_data.csv", "pose_landmarker_lite.task"),
            ("Gesicht", "Gesichts-Landmarks / Blendshapes", "face_data.csv", "face_landmarker.task"),
            ("Hände", "Hand-Landmarks", "hand_data.csv", "hand_landmarker.task"),
            ("Objekte", "Arbeitsplatz-Objekte", "object_data.csv", "efficientdet.tflite"),
            ("Berührungen", "Hand-Körper-Ereignisse", "touch_events.csv", "Pose + Hand Landmarker"),
        )
        self.results.setRowCount(len(detections))
        total_events = 0
        for row, (name, output, data_file, model_file) in enumerate(detections):
            data_path = Path(OUTPUT_DIR) / data_file
            model_path = Path(RESOURCE_DIR) / model_file
            count = self._data_rows(data_path)
            total_events += count
            status = "verfügbar" if model_path.exists() else "fehlt"
            values = (name, output, str(count), status)
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 3:
                    item.setForeground(Qt.GlobalColor.darkGreen if status == "verfügbar"
                                       else Qt.GlobalColor.red)
                self.results.setItem(row, column, item)
        self.session_label.setText(
            f"Letzte lokale Auswertung: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
        )
        self.info_label.setText(
            f"Gesamt: {total_events} gespeicherte Frames/Events. "
            "Pose, Gesicht und Hände werden mit MediaPipe Landmarks erkannt; "
            "Objekte werden über den Arbeitsplatz-Objektdetektor erfasst."
        )

    @staticmethod
    def _data_rows(path):
        if not path.exists():
            return 0
        try:
            with path.open("r", encoding="utf-8", newline="") as data_file:
                return max(0, sum(1 for _ in csv.reader(data_file)) - 1)
        except (OSError, csv.Error):
            return 0


class App(QMainWindow):
    """Main Qt window. Kept as ``App`` for integration compatibility."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Atum")
        self.resize(900, 700)
        self.setMinimumSize(800, 600)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        self.tabs = QTabBar()
        self.tabs.addTab("Überwachung")
        self.tabs.addTab("Ergebnisse")
        self.tabs.currentChanged.connect(self._show_tab)
        layout.addWidget(self.tabs)
        self.stack = QStackedWidget()
        self.home_tab = HomeTab(self, on_state_changed=self._on_recording_state_changed)
        self.dashboard_tab = DashboardTab(self)
        self.stack.addWidget(self.home_tab)
        self.stack.addWidget(self.dashboard_tab)
        layout.addWidget(self.stack, 1)
        self._maybe_first_run_setup()

    def _show_tab(self, index):
        self.stack.setCurrentIndex(index)

    def _on_recording_state_changed(self, user_name, session_id, running):
        self.dashboard_tab.notify_recording_state(user_name, session_id, running)

    def _maybe_first_run_setup(self):
        settings = gui_settings.load_settings()
        if not gui_settings.has_settings() or not settings.get("user"):
            dialog = QuickSetupDialog(self, on_saved=self._on_first_run_saved)
            dialog.exec()

    def _on_first_run_saved(self, settings):
        self.home_tab._load_settings_into_header()
        self.home_tab._show_last_session_summary()

    def closeEvent(self, event):
        if self.home_tab.is_tracking():
            answer = QMessageBox.question(
                self, "Aufnahme läuft noch",
                "Es läuft gerade eine Aufnahme. Wirklich beenden?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.home_tab.request_stop_for_shutdown()
        event.accept()


def main():
    from capturesuite_qt_new import QApplication, QFont, MainWindow

    app = QApplication.instance() or QApplication(sys.argv)
    app.setFont(QFont("IBM Plex Sans", 10))
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
