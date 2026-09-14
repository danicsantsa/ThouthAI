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
    QApplication, QDialog, QDialogButtonBox, QFormLayout, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox,
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
    "bg": "#0b1110", "surface": "#121b18", "surface_alt": "#182520",
    "text": "#e8f3ed", "muted": "#91aaa0", "border": "#294238",
    "primary": "#39d98a", "primary_dark": "#1aa968",
    "success": "#39d98a", "danger": "#ff6678", "warning": "#f2c14e",
}


def apply_theme(app):
    app.setStyleSheet(f"""
        QWidget {{ background: {COLORS['bg']}; color: {COLORS['text']};
                   font-family: 'Noto Sans', 'DejaVu Sans', sans-serif;
                   font-size: 10pt; }}
        QMainWindow, QDialog {{ background: {COLORS['bg']}; }}
        QPushButton {{ background: {COLORS['primary']}; color: #06100b; border: 0;
                       border-radius: 5px; padding: 9px 16px; font-weight: 700; }}
        QPushButton:hover {{ background: #63e6a5; }}
        QPushButton:disabled {{ background: #35483f; color: #789187; }}
        QLineEdit, QPlainTextEdit, QTableWidget {{ background: {COLORS['surface']};
            border: 1px solid {COLORS['border']}; border-radius: 5px; padding: 6px; }}
        QTableWidget {{ alternate-background-color: {COLORS['surface_alt']};
                        gridline-color: {COLORS['border']}; }}
        QHeaderView::section {{ background: #1d3028; color: {COLORS['muted']};
                                border: 0; padding: 8px; font-weight: 600; }}
        QTabBar::tab {{ background: {COLORS['surface']}; padding: 10px 18px; border: 0;
                        color: {COLORS['muted']}; }}
        QTabBar::tab:selected {{ color: {COLORS['primary']};
                                 border-bottom: 2px solid {COLORS['primary']}; }}
        #topBar, #sourcesSidebar {{ background: {COLORS['surface']};
                        border-bottom: 1px solid {COLORS['border']}; }}
        #sourcesSidebar {{ border-right: 1px solid {COLORS['border']};
                   border-bottom: 0; }}
        #metricCard {{ background: {COLORS['surface']};
                   border: 1px solid {COLORS['border']}; border-radius: 4px; }}
        QPushButton#secondaryButton {{ background: {COLORS['surface_alt']};
                   color: {COLORS['text']};
                           border: 1px solid {COLORS['border']}; }}
        QPushButton#secondaryButton:hover {{ border-color: {COLORS['primary']};
                             color: {COLORS['primary']}; }}
    """)


class TrackingProcess:
    """Manage the tracking worker without blocking the Qt event loop."""

    def __init__(self):
        self.proc = None
        self.output_queue = queue.Queue()
        self.session_id = None

    def is_running(self):
        return self.proc is not None and self.proc.poll() is None

    def start(self, settings):
        if self.is_running():
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
                   "--non-work-apps", settings["non_work_apps"]]
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
        threading.Thread(target=self._read_output, daemon=True).start()

    def _read_output(self):
        for line in self.proc.stdout:
            line = line.rstrip("\n")
            self.output_queue.put(line)
            match = SESSION_ID_PATTERN.search(line)
            if match:
                self.session_id = match.group(1)
        self.output_queue.put(None)

    def stop(self):
        if not self.is_running():
            return
        try:
            if platform.system() == "Windows":
                self.proc.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGINT)
        except Exception:
            self.proc.terminate()


class QuickSetupDialog(QDialog):
    def __init__(self, parent=None, on_saved=None):
        super().__init__(parent)
        self.on_saved = on_saved
        self.setWindowTitle("Willkommen bei Workspace Tracking")
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
        self._start_time = None
        self._video_duration_cache = {}
        self._invalid_videos = set()
        self._preview_mtime = None
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
        top_layout.setContentsMargins(16, 10, 16, 10)
        brand = QLabel("▣  CaptureSuite — Datenerfassung")
        brand.setFont(QFont("Noto Sans", 11, QFont.Weight.DemiBold))
        top_layout.addWidget(brand)
        top_layout.addStretch()
        self.connection_status = QLabel("●  TLS gesichert")
        self.connection_status.setStyleSheet(f"color: {COLORS['success']};")
        top_layout.addWidget(self.connection_status)
        layout.addWidget(top_bar)

        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        sidebar = self._build_sources_sidebar()
        content_layout.addWidget(sidebar)

        main = QWidget()
        main_layout = QVBoxLayout(main)
        main_layout.setContentsMargins(16, 16, 16, 10)
        main_layout.setSpacing(12)
        main_layout.addWidget(self._section_label("Neue Erfassung"))

        capture = QHBoxLayout()
        capture.setSpacing(16)
        self.preview = QLabel("▣\n\nKamera 01")
        preview = self.preview
        preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview.setMinimumSize(190, 142)
        preview.setStyleSheet("background: #050807; color: #6f8a7d; border: 1px solid #294238; border-radius: 5px;")
        capture.addWidget(preview)

        control = QWidget()
        control_layout = QVBoxLayout(control)
        control_layout.setContentsMargins(0, 0, 0, 0)
        self.status_indicator = QLabel("● Bereit")
        self.status_indicator.setStyleSheet(f"color: {COLORS['success']}; font-weight: 600")
        self.elapsed_time = QLabel("00:00:00")
        self.elapsed_time.setFont(QFont("Noto Sans Mono", 20, QFont.Weight.Bold))
        buttons = QHBoxLayout()
        self.start_btn = QPushButton("●  Start")
        self.stop_btn = QPushButton("■  Stop")
        self.stop_btn.setEnabled(False)
        self.start_btn.clicked.connect(self._on_start)
        self.stop_btn.clicked.connect(self._on_stop)
        buttons.addWidget(self.start_btn)
        buttons.addWidget(self.stop_btn)
        control_layout.addWidget(QLabel("Aufnahmedauer"))
        control_layout.addWidget(self.elapsed_time)
        control_layout.addWidget(self.status_indicator)
        control_layout.addLayout(buttons)
        control_layout.addStretch()
        capture.addWidget(control, 1)
        main_layout.addLayout(capture)
        main_layout.addWidget(self._build_metric_cards())
        records_header = QHBoxLayout()
        records_header.addWidget(self._section_label("Erfasste Datensätze"))
        records_header.addStretch()
        export_btn = QPushButton("↓  Als CSV exportieren")
        export_btn.setObjectName("secondaryButton")
        export_btn.clicked.connect(self._export_records)
        records_header.addWidget(export_btn)
        main_layout.addLayout(records_header)
        self.records = QTableWidget(0, 5)
        self.records.setHorizontalHeaderLabels(("Video", "Aufgenommen", "Größe", "Dauer", "Sync"))
        self.records.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.records.verticalHeader().setVisible(False)
        self.records.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        main_layout.addWidget(self.records, 1)
        content_layout.addWidget(main, 1)
        layout.addWidget(content, 1)

        self.last_session = QLabel()
        self.last_session.setVisible(False)
        self.output_text = QPlainTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setVisible(False)

        status_bar = QWidget()
        status_layout = QHBoxLayout(status_bar)
        status_layout.setContentsMargins(16, 8, 16, 8)
        self.local_count = QLabel("▣  0 Datensätze lokal")
        status_layout.addWidget(self.local_count)
        self.supabase_status = QLabel()
        status_layout.addWidget(self.supabase_status)
        status_layout.addStretch()
        status_layout.addWidget(QLabel("Angemeldet als lokaler Benutzer"))
        layout.addWidget(status_bar)
        self._refresh_video_list()

    def _section_label(self, text):
        label = QLabel(text)
        label.setFont(QFont("Noto Sans", 11, QFont.Weight.DemiBold))
        return label

    def _build_sources_sidebar(self):
        sidebar = QWidget()
        sidebar.setObjectName("sourcesSidebar")
        sidebar.setFixedWidth(190)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(10, 14, 10, 14)
        layout.addWidget(QLabel("Hardware-Quellen"))
        for name, active in (("▣  Kamera 01", True), ("♨  Temperatur", False),
                     ("⌖  GPS", False), ("⚖  Waage", False)):
            source = QLabel(f"{name}     {'●' if active else '○'}")
            source.setStyleSheet(f"padding: 7px; color: {COLORS['text'] if active else COLORS['muted']};")
            layout.addWidget(source)
        add_source = QPushButton("＋  Quelle hinzufügen")
        add_source.setObjectName("secondaryButton")
        add_source.clicked.connect(lambda: self.output_text.appendPlainText("Quelle hinzufügen: noch nicht konfiguriert"))
        layout.addWidget(add_source)
        layout.addStretch()
        return sidebar

    def _build_metric_cards(self):
        cards = QWidget()
        grid = QGridLayout(cards)
        grid.setContentsMargins(0, 0, 0, 0)
        for column, (name, value) in enumerate((("Temperatur", "Nicht angeschlossen"),
                              ("GPS", "Nicht angeschlossen"),
                                                  ("Waage", "—"))):
            card = QFrame()
            card.setObjectName("metricCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(10, 8, 10, 8)
            card_layout.addWidget(QLabel(name))
            value_label = QLabel(value)
            value_label.setFont(QFont("Noto Sans Mono", 11, QFont.Weight.DemiBold))
            card_layout.addWidget(value_label)
            grid.addWidget(card, 0, column)
        return cards

    def _export_records(self):
        self.output_text.appendPlainText("CSV-Export ist für die lokalen Datensätze vorbereitet.")

    def _refresh_video_list(self):
        video_dir = Path(VIDEO_OUTPUT_DIR)
        videos = sorted(
            (path for path in video_dir.glob("*.mp4")
             if not path.name.endswith(".part.mp4")),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        ) if video_dir.exists() else []
        self.records.setRowCount(len(videos))
        for row, video in enumerate(videos):
            info = video.stat()
            metadata = self._load_video_metadata(video)
            duration_seconds = metadata.get("duration_seconds")
            if duration_seconds is None:
                duration_seconds = self._read_video_duration(video)
            values = (
                video.name,
                datetime.datetime.fromtimestamp(info.st_mtime).strftime("%d.%m %H:%M"),
                f"{info.st_size / 1024 / 1024:.1f} MB",
                self._format_duration(duration_seconds),
                "●" if db_client.DB_AVAILABLE else "○",
            )
            for column, value in enumerate(values):
                self.records.setItem(row, column, QTableWidgetItem(value))
        self.local_count.setText(f"▣  {len(videos)} Videos lokal")
        if db_client.DB_AVAILABLE:
            self.supabase_status.setText("☁  Supabase verbunden")
            self.supabase_status.setStyleSheet(f"color: {COLORS['success']};")
            self.connection_status.setText("●  Supabase verbunden")
            self.connection_status.setStyleSheet(f"color: {COLORS['success']};")
        else:
            self.supabase_status.setText("☁  Supabase nicht verbunden")
            self.supabase_status.setStyleSheet(f"color: {COLORS['danger']};")
            self.connection_status.setText("●  Supabase nicht verbunden")
            self.connection_status.setStyleSheet(f"color: {COLORS['danger']};")

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
        try:
            preview_mtime = os.path.getmtime(PREVIEW_IMAGE_PATH)
        except OSError:
            preview_mtime = None

        if preview_mtime is not None and preview_mtime != self._preview_mtime:
            reader = QImageReader(PREVIEW_IMAGE_PATH)
            reader.setAutoTransform(True)
            image = reader.read()
            if not image.isNull():
                pixmap = QPixmap.fromImage(image)
                self.preview.setPixmap(pixmap.scaled(
                    self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation))
                self.preview.setText("")
                self._preview_mtime = preview_mtime
        elif not self.is_tracking():
            self.preview.setPixmap(QPixmap())
            self.preview.setText("▣\n\nKamera 01")

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

    def is_tracking(self):
        return self.tracker.is_running()

    def _on_start(self):
        settings = gui_settings.load_settings()
        if not settings.get("user"):
            QMessageBox.warning(self, "Setup erforderlich", "Bitte geben Sie zuerst Ihren Namen ein.")
            return
        try:
            self.tracker.start(settings)
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.status_indicator.setText("● Kamera und MediaPipe werden gestartet ...")
            self.status_indicator.setStyleSheet(f"color: {COLORS['success']}; font-weight: 600")
            self._start_time = datetime.datetime.now()
            if self.on_state_changed:
                self.on_state_changed(settings["user"], None, True)
        except Exception as exc:
            QMessageBox.critical(self, "Fehler", f"Konnte Aufnahme nicht starten: {exc}")

    def _on_stop(self):
        self.tracker.stop()
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_indicator.setText("● Bereit")
        self.status_indicator.setStyleSheet(f"color: {COLORS['success']}; font-weight: 600")
        self._start_time = None
        if self.on_state_changed:
            self.on_state_changed("", self.tracker.session_id, False)

    def _poll(self):
        try:
            while True:
                line = self.tracker.output_queue.get_nowait()
                if line is None:
                    break
                self.output_text.appendPlainText(line)
        except queue.Empty:
            pass
        if self._start_time and self.tracker.proc is not None and not self.is_tracking():
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.status_indicator.setText("● Kamera/MediaPipe wurde beendet - keine Preview")
            self.status_indicator.setStyleSheet(f"color: {COLORS['danger']}; font-weight: 600")
            self._start_time = None
        if self._start_time:
            seconds = int((datetime.datetime.now() - self._start_time).total_seconds())
            hours, remainder = divmod(seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            self.elapsed_time.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
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
        self.setWindowTitle("Workspace Tracking")
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
    print("[App] Starte Workspace Tracking GUI...", file=sys.stderr)
    app = QApplication.instance() or QApplication(sys.argv)
    apply_theme(app)
    window = App()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
