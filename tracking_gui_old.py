"""
tracking_gui.py
================
Desktop-Oberfläche für das Workspace-Tracking-System.

Ersteinrichtung ist bewusst auf ein einziges Feld reduziert: Name eingeben,
fertig. Die Kamera wird automatisch im Hintergrund erkannt (erste
gefundene Kamera wird genommen), alle anderen Parameter (Rotation,
Intervalle, Arbeits-/Nicht-Arbeits-Apps) bleiben auf sinnvollen
Standardwerten (siehe gui_settings.DEFAULTS). Wer das doch mal ändern
will, findet über "Einstellungen" den ausführlicheren Assistenten mit
Kamera-Auswahl -- im Normalfall muss den aber niemand öffnen.

Voraussetzungen (zusätzlich zu track_all.py):
    pip install matplotlib --break-system-packages
    sudo apt install python3-tk   # falls tkinter fehlt

Start:
    python3 tracking_gui.py

Muss im selben Ordner liegen wie track_all.py, db_client.py,
db_queries.py, camera_utils.py, gui_settings.py und db_config.json.
"""

import os
import re
import sys
import signal
import platform
import subprocess
import threading
import queue
import datetime
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.dates as mdates
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

import db_queries
import gui_settings
import camera_utils


OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
TRACK_ALL_PATH = os.path.join(OUTPUT_DIR, "track_all.py")

# ---------- Farbpalette (dark premium UI) ----------
COLOR_BG = "#0b1020"
COLOR_PANEL = "#121a2b"
COLOR_PANEL_ALT = "#182336"
COLOR_TEXT = "#eaf2ff"
COLOR_TEXT_MUTED = "#97a9c5"
COLOR_BORDER = "#24324d"
COLOR_WHITE = "#ffffff"
COLOR_ARBEIT = "#2fd38a"
COLOR_NICHT_ARBEIT = "#f5b75d"
COLOR_UNBEKANNT = "#8ea1b5"
COLOR_ERROR = "#ff6b6b"
COLOR_PRIMARY = "#5f7cff"
COLOR_PRIMARY_SOFT = "#1a2948"
COLOR_ACCENT = "#23c7b6"
COLOR_WARNING = "#f59e0b"

KATEGORIE_FARBEN = {"Arbeit": COLOR_ARBEIT, "Nicht-Arbeit": COLOR_NICHT_ARBEIT}


def kategorie_farbe(name):
    return KATEGORIE_FARBEN.get(name, COLOR_UNBEKANNT)


def _to_local_naive(dt):
    """Wandelt einen (meist tz-aware) Datenbank-Zeitstempel in ein lokales,
    tz-loses datetime um -- matplotlib.dates verarbeitet naive datetimes am
    zuverlässigsten."""
    if dt.tzinfo is not None:
        return dt.astimezone().replace(tzinfo=None)
    return dt


# ===========================================================
# Theme -- bewusst zurückhaltend, damit die App nativ wirkt
# ===========================================================

def apply_theme(root):
    root.configure(bg=COLOR_BG)
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("TFrame", background=COLOR_BG)
    style.configure("Card.TFrame", background=COLOR_PANEL, relief="flat")
    style.configure("TLabel", background=COLOR_BG, foreground=COLOR_TEXT)
    style.configure("Header.TLabel", background=COLOR_BG, foreground=COLOR_TEXT,
                     font=("Segoe UI", 12, "bold"))
    style.configure("Title.TLabel", background=COLOR_BG, foreground=COLOR_TEXT,
                     font=("Segoe UI", 16, "bold"))
    style.configure("Hero.TLabel", background=COLOR_BG, foreground=COLOR_TEXT,
                     font=("Segoe UI", 24, "bold"))
    style.configure("Muted.TLabel", background=COLOR_BG, foreground=COLOR_TEXT_MUTED)
    style.configure("Value.TLabel", background=COLOR_BG, foreground=COLOR_TEXT,
                     font=("Segoe UI", 14, "bold"))
    style.configure("BigValue.TLabel", background=COLOR_BG, foreground=COLOR_PRIMARY,
                     font=("Segoe UI", 20, "bold"))
    style.configure("TCheckbutton", background=COLOR_BG, foreground=COLOR_TEXT)
    style.configure("TRadiobutton", background=COLOR_BG, foreground=COLOR_TEXT)
    style.configure("TLabelframe", background=COLOR_BG)
    style.configure("TLabelframe.Label", background=COLOR_BG, foreground=COLOR_TEXT_MUTED,
                     font=("Segoe UI", 9, "bold"))
    style.configure("TNotebook", background=COLOR_BG, borderwidth=0)
    style.configure("TNotebook.Tab", padding=(18, 10), background="#121a2b", foreground=COLOR_TEXT_MUTED)
    style.map("TNotebook.Tab", background=[("selected", COLOR_PANEL_ALT)], foreground=[("selected", COLOR_TEXT)])
    style.configure("TButton", relief="flat", borderwidth=0, padding=(12, 9))
    style.map("TButton", background=[("active", "#6d85ff"), ("pressed", "#5574f5")], foreground=[("active", COLOR_WHITE), ("pressed", COLOR_WHITE)])
    style.configure("Big.TButton", font=("Segoe UI", 12, "bold"), padding=(18, 12), background=COLOR_PRIMARY, foreground=COLOR_WHITE)
    style.map("Big.TButton", background=[("active", "#761ae7"), ("pressed", "#5c14d9")], foreground=[("active", COLOR_WHITE), ("pressed", COLOR_WHITE)])
    style.configure("Secondary.TButton", font=("Segoe UI", 10, "bold"), padding=(10, 8), background=COLOR_PRIMARY_SOFT, foreground=COLOR_TEXT)
    style.map("Secondary.TButton", background=[("active", "#1e3357"), ("pressed", "#142848")], foreground=[("active", COLOR_TEXT), ("pressed", COLOR_TEXT)])
    style.configure("Treeview", rowheight=24, background=COLOR_PANEL, fieldbackground=COLOR_PANEL, foreground=COLOR_TEXT)
    style.configure("Treeview.Heading", background="#1b273d", foreground=COLOR_TEXT, font=("Segoe UI", 9, "bold"))
    style.map("Treeview", background=[("selected", COLOR_PRIMARY_SOFT)], foreground=[("selected", COLOR_TEXT)])


def style_axes(ax, fig):
    fig.patch.set_facecolor(COLOR_WHITE)
    ax.set_facecolor(COLOR_WHITE)
    for spine in ax.spines.values():
        spine.set_color(COLOR_BORDER)
    ax.tick_params(colors=COLOR_TEXT_MUTED, labelsize=8)
    ax.title.set_color(COLOR_TEXT)
    ax.xaxis.label.set_color(COLOR_TEXT_MUTED)
    ax.yaxis.label.set_color(COLOR_TEXT_MUTED)
    ax.grid(True, color="#e2e2e2", linewidth=0.7)


def stat_row(parent, titel, spalte):
    frame = ttk.Frame(parent)
    frame.grid(row=0, column=spalte, sticky="w", padx=(0, 32))
    value_label = ttk.Label(frame, text="–", style="Value.TLabel")
    value_label.pack(anchor="w")
    ttk.Label(frame, text=titel, style="Muted.TLabel").pack(anchor="w")
    return value_label


# ===========================================================
# Prozess-Verwaltung für track_all.py
# ===========================================================

SESSION_ID_PATTERN = re.compile(r"Aufnahme-Sitzung gestartet:\s*(\S+)")


class TrackingProcess:
    def __init__(self):
        self.proc = None
        self.output_queue = queue.Queue()
        self.reader_thread = None
        self.session_id = None
        self.user_name = None

    def is_running(self):
        return self.proc is not None and self.proc.poll() is None

    def start(self, settings):
        if self.is_running():
            return
        cmd = [sys.executable, "-u", TRACK_ALL_PATH,
               "--user", settings["user"],
               "--camera", str(settings["camera"]),
               "--rotate", str(settings["rotate"]),
               "--check-interval", str(settings["check_interval"]),
               "--db-flush-interval", str(settings["db_flush_interval"]),
               "--work-apps", settings["work_apps"],
               "--non-work-apps", settings["non_work_apps"]]
        # Standard: keine eigene Kamera-Vorschau-Page öffnen; die Live-Anzeige bleibt in der App.
        if settings.get("device_name"):
            cmd += ["--device-name", settings["device_name"]]

        self.session_id = None
        self.user_name = settings["user"]

        popen_kwargs = dict(cwd=OUTPUT_DIR, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True, bufsize=1,
                             stdin=subprocess.DEVNULL)
        if platform.system() == "Windows":
            popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            popen_kwargs["preexec_fn"] = os.setsid

        self.proc = subprocess.Popen(cmd, **popen_kwargs)
        self.reader_thread = threading.Thread(target=self._read_output, daemon=True)
        self.reader_thread.start()

    def _read_output(self):
        for line in self.proc.stdout:
            self.output_queue.put(line.rstrip("\n"))
            match = SESSION_ID_PATTERN.search(line)
            if match:
                self.session_id = match.group(1)
        self.proc.stdout.close()
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


# ===========================================================
# Ersteinrichtung -- NUR der Name, alles andere ist Standard
# ===========================================================

class QuickSetupDialog(tk.Toplevel):
    """Minimale Ersteinrichtung: ein Feld (Name), ein Knopf. Die Kamera
    wird automatisch im Hintergrund erkannt (erste gefundene Kamera),
    alle übrigen Werte kommen unverändert aus gui_settings.DEFAULTS."""

    def __init__(self, parent, on_saved):
        super().__init__(parent)
        self.on_saved = on_saved
        self.title("Willkommen!")
        self.configure(bg=COLOR_BG)
        self.geometry("420x220")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", lambda: None)  # Ersteinrichtung nicht wegklicken

        pad = ttk.Frame(self, padding=24)
        pad.pack(fill="both", expand=True)

        ttk.Label(pad, text="Wie heißt du?", style="Title.TLabel").pack(anchor="w")
        ttk.Label(pad, text="Alles andere ist schon passend eingestellt.",
                  style="Muted.TLabel").pack(anchor="w", pady=(2, 16))

        self.user_var = tk.StringVar()
        entry = ttk.Entry(pad, textvariable=self.user_var, font=("Segoe UI", 12))
        entry.pack(fill="x")
        entry.focus_set()
        entry.bind("<Return>", lambda e: self._on_start())

        self.status_label = ttk.Label(pad, text="", style="Muted.TLabel")
        self.status_label.pack(anchor="w", pady=(10, 0))

        self.go_btn = ttk.Button(pad, text="Los geht's", command=self._on_start)
        self.go_btn.pack(anchor="e", pady=(16, 0))

    def _on_start(self):
        name = self.user_var.get().strip()
        if not name:
            messagebox.showwarning("Name fehlt", "Bitte einen Namen eingeben.")
            return

        self.go_btn.configure(state="disabled")
        self.status_label.configure(text="Kamera wird erkannt …")
        result_queue = queue.Queue()

        def worker():
            try:
                found = camera_utils.scan_cameras()
            except Exception:
                found = []
            result_queue.put(found)

        threading.Thread(target=worker, daemon=True).start()
        self.after(150, lambda: self._poll_scan(name, result_queue))

    def _poll_scan(self, name, result_queue):
        try:
            found = result_queue.get_nowait()
        except queue.Empty:
            self.after(150, lambda: self._poll_scan(name, result_queue))
            return

        camera_index = found[0][0] if found else gui_settings.DEFAULTS["camera"]
        new_settings = dict(gui_settings.DEFAULTS)
        new_settings["user"] = name
        new_settings["camera"] = camera_index
        saved = gui_settings.save_settings(new_settings)

        self.destroy()
        self.on_saved(saved)


# ===========================================================
# Erweiterte Einstellungen (optional, über "Einstellungen" erreichbar)
# ===========================================================

class SetupWizard(tk.Toplevel):
    """Dreiseitiger Assistent für alle, die die automatisch erkannten
    Werte doch mal ändern wollen: Name -> Kamera -> Erweitert. Wird nicht
    automatisch gezeigt, nur über den Knopf 'Einstellungen'."""

    def __init__(self, parent, on_saved):
        super().__init__(parent)
        self.on_saved = on_saved
        self.settings = gui_settings.load_settings()
        self.thumb_image = None
        self.found_cameras = {}
        self.page_index = 0

        self.title("Einstellungen")
        self.configure(bg=COLOR_BG)
        self.geometry("640x580")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

        self._build_shell()
        self._build_page_name()
        self._build_page_camera()
        self._build_page_advanced()
        self.pages = [self.page_name, self.page_camera, self.page_advanced]
        self._show_page(0)
        self._start_scan()

    def _build_shell(self):
        ttk.Label(self, text="Einstellungen", style="Header.TLabel"
                  ).pack(anchor="w", padx=20, pady=(16, 4))

        self.body = ttk.Frame(self, padding=(20, 4))
        self.body.pack(fill="both", expand=True)

        ttk.Separator(self).pack(fill="x", side="bottom")
        footer = ttk.Frame(self, padding=(20, 12))
        footer.pack(fill="x", side="bottom")
        self.back_btn = ttk.Button(footer, text="Zurück", command=self._go_back)
        self.back_btn.pack(side="left")
        self.next_btn = ttk.Button(footer, text="Weiter", command=self._go_next)
        self.next_btn.pack(side="right")
        ttk.Button(footer, text="Abbrechen", command=self._on_cancel).pack(side="right", padx=(0, 10))

    def _show_page(self, index):
        for page in getattr(self, "pages", []):
            page.pack_forget()
        self.page_index = index
        self.pages[index].pack(fill="both", expand=True)
        self.back_btn.configure(state="normal" if index > 0 else "disabled")
        self.next_btn.configure(text="Speichern" if index == len(self.pages) - 1 else "Weiter")

    def _go_back(self):
        if self.page_index > 0:
            self._show_page(self.page_index - 1)

    def _go_next(self):
        if self.page_index == 0 and not self.user_var.get().strip():
            messagebox.showwarning("Name fehlt", "Bitte einen Namen eingeben.")
            return
        if self.page_index < len(self.pages) - 1:
            self._show_page(self.page_index + 1)
        else:
            self._on_save()

    def _on_cancel(self):
        self.destroy()

    def _build_page_name(self):
        page = ttk.Frame(self.body)
        self.page_name = page
        ttk.Label(page, text="Name", style="Title.TLabel").pack(anchor="w", pady=(10, 16))
        self.user_var = tk.StringVar(value=self.settings["user"])
        user_combo = ttk.Combobox(page, textvariable=self.user_var, width=32)
        try:
            user_combo["values"] = [name for (_id, name) in db_queries.list_users()]
        except Exception:
            pass
        user_combo.pack(anchor="w")

    def _build_page_camera(self):
        page = ttk.Frame(self.body)
        self.page_camera = page
        ttk.Label(page, text="Kamera", style="Title.TLabel").pack(anchor="w", pady=(10, 4))

        scan_row = ttk.Frame(page)
        scan_row.pack(fill="x", pady=(0, 12))
        self.scan_btn = ttk.Button(scan_row, text="Kameras suchen", command=self._start_scan)
        self.scan_btn.pack(side="left")
        self.scan_status = ttk.Label(scan_row, text="", style="Muted.TLabel")
        self.scan_status.pack(side="left", padx=(10, 0))

        content = ttk.Frame(page)
        content.pack(fill="x")

        left = ttk.Frame(content)
        left.pack(side="left", anchor="n", fill="y")
        ttk.Label(left, text="Gefundene Kameras", style="Muted.TLabel").pack(anchor="w", pady=(0, 6))
        self.camera_var = tk.IntVar(value=self.settings["camera"])
        self.radio_container = ttk.Frame(left)
        self.radio_container.pack(anchor="w")

        manual_row = ttk.Frame(left)
        manual_row.pack(anchor="w", pady=(14, 0))
        ttk.Radiobutton(manual_row, text="Andere (Index):", variable=self.camera_var,
                         value=-1, command=self._on_manual_selected).pack(side="left")
        self.manual_index_var = tk.IntVar(value=self.settings["camera"])
        ttk.Spinbox(manual_row, from_=0, to=9, width=4, textvariable=self.manual_index_var,
                     command=self._on_manual_selected).pack(side="left", padx=(6, 0))

        right = ttk.Frame(content, padding=(24, 0, 0, 0))
        right.pack(side="left", anchor="n")
        ttk.Label(right, text="Vorschau", style="Muted.TLabel").pack(anchor="w", pady=(0, 6))
        self.preview_label = tk.Label(right, bg=COLOR_WHITE, width=26, height=10,
                                       text="(noch keine Vorschau)", fg=COLOR_TEXT_MUTED)
        self.preview_label.pack(anchor="w")

        rotate_row = ttk.Frame(right)
        rotate_row.pack(anchor="w", pady=(10, 0))
        ttk.Label(rotate_row, text="Bild gedreht?").pack(side="left")
        ttk.Button(rotate_row, text="⟲ 90°", command=lambda: self._rotate(-90)).pack(side="left", padx=(8, 4))
        ttk.Button(rotate_row, text="⟳ 90°", command=lambda: self._rotate(90)).pack(side="left")

    def _build_page_advanced(self):
        page = ttk.Frame(self.body)
        self.page_advanced = page
        ttk.Label(page, text="Erweitert", style="Title.TLabel").pack(anchor="w", pady=(10, 16))

        grid = ttk.Frame(page)
        grid.pack(fill="x")
        grid.columnconfigure(1, weight=1)

        ttk.Label(grid, text="Geräte-Name").grid(row=0, column=0, sticky="w", pady=6)
        self.device_var = tk.StringVar(value=self.settings["device_name"])
        ttk.Entry(grid, textvariable=self.device_var).grid(row=0, column=1, sticky="ew", pady=6)

        ttk.Label(grid, text="Zählt als Arbeit").grid(row=1, column=0, sticky="w", pady=6)
        self.work_apps_var = tk.StringVar(value=self.settings["work_apps"])
        ttk.Entry(grid, textvariable=self.work_apps_var).grid(row=1, column=1, sticky="ew", pady=6)

        ttk.Label(grid, text="Zählt nicht als Arbeit").grid(row=2, column=0, sticky="w", pady=6)
        self.non_work_apps_var = tk.StringVar(value=self.settings["non_work_apps"])
        ttk.Entry(grid, textvariable=self.non_work_apps_var).grid(row=2, column=1, sticky="ew", pady=6)

        ttk.Label(grid, text="Prüf-Intervall (s)").grid(row=3, column=0, sticky="w", pady=6)
        self.check_interval_var = tk.DoubleVar(value=self.settings["check_interval"])
        ttk.Spinbox(grid, from_=0.5, to=30, increment=0.5, width=8,
                    textvariable=self.check_interval_var).grid(row=3, column=1, sticky="w", pady=6)

        ttk.Label(grid, text="DB-Schreib-Intervall (s)").grid(row=4, column=0, sticky="w", pady=6)
        self.db_flush_var = tk.DoubleVar(value=self.settings["db_flush_interval"])
        ttk.Spinbox(grid, from_=0.5, to=30, increment=0.5, width=8,
                    textvariable=self.db_flush_var).grid(row=4, column=1, sticky="w", pady=6)

    def _start_scan(self):
        self.scan_btn.configure(state="disabled")
        self.scan_status.configure(text="Suche läuft, einen Moment …")
        result_queue = queue.Queue()

        def worker():
            try:
                found = camera_utils.scan_cameras()
            except Exception as e:
                result_queue.put(("error", str(e)))
                return
            result_queue.put(("ok", found))

        threading.Thread(target=worker, daemon=True).start()
        self._poll_scan(result_queue)

    def _poll_scan(self, result_queue):
        try:
            status, payload = result_queue.get_nowait()
        except queue.Empty:
            self.after(150, lambda: self._poll_scan(result_queue))
            return

        self.scan_btn.configure(state="normal")
        if status == "error":
            self.scan_status.configure(text=f"Fehler bei der Suche ({payload})")
            return
        if not payload:
            self.scan_status.configure(text="Keine Kamera gefunden -- rechts Index manuell eintragen.")
            return

        self.scan_status.configure(text=f"{len(payload)} Kamera(s) gefunden.")
        self.found_cameras = dict(payload)
        self._render_radios()

    def _render_radios(self):
        for widget in self.radio_container.winfo_children():
            widget.destroy()
        for index in sorted(self.found_cameras.keys()):
            ttk.Radiobutton(self.radio_container, text=f"Kamera {index}", variable=self.camera_var,
                             value=index, command=self._on_camera_selected).pack(anchor="w", pady=2)
        if self.camera_var.get() in self.found_cameras:
            self._update_preview(self.camera_var.get())
        elif self.found_cameras:
            first_index = sorted(self.found_cameras.keys())[0]
            self.camera_var.set(first_index)
            self._update_preview(first_index)

    def _on_camera_selected(self):
        self._update_preview(self.camera_var.get())

    def _on_manual_selected(self):
        self.camera_var.set(-1)
        idx = self.manual_index_var.get()
        if idx in self.found_cameras:
            self._update_preview(idx)
        else:
            self.preview_label.configure(image="", text="(keine Vorschau für diesen Index)")

    def _update_preview(self, index):
        frame = self.found_cameras.get(index)
        if frame is None:
            return
        rotate = getattr(self, "_preview_rotate", self.settings["rotate"])
        ppm = camera_utils.frame_to_ppm_bytes(frame, max_width=220, rotate=rotate)
        self.thumb_image = tk.PhotoImage(data=ppm, format="PPM")
        self.preview_label.configure(image=self.thumb_image, text="", width=0, height=0)

    def _rotate(self, delta):
        current = getattr(self, "_preview_rotate", self.settings["rotate"])
        self._preview_rotate = (current + delta) % 360
        selected = self.camera_var.get()
        if selected in self.found_cameras:
            self._update_preview(selected)

    def _selected_camera_index(self):
        if self.camera_var.get() == -1:
            return self.manual_index_var.get()
        return self.camera_var.get()

    def _on_save(self):
        name = self.user_var.get().strip()
        if not name:
            messagebox.showwarning("Name fehlt", "Bitte einen Namen eingeben.")
            self._show_page(0)
            return

        new_settings = {
            "user": name,
            "camera": self._selected_camera_index(),
            "rotate": getattr(self, "_preview_rotate", self.settings["rotate"]),
            "device_name": self.device_var.get().strip(),
            "work_apps": self.work_apps_var.get().strip() or gui_settings.DEFAULTS["work_apps"],
            "non_work_apps": self.non_work_apps_var.get().strip() or gui_settings.DEFAULTS["non_work_apps"],
            "check_interval": self.check_interval_var.get(),
            "db_flush_interval": self.db_flush_var.get(),
        }
        saved = gui_settings.save_settings(new_settings)
        self.destroy()
        self.on_saved(saved)


# ===========================================================
# Tab 1: Start
# ===========================================================

class HomeTab(ttk.Frame):
    def __init__(self, parent, on_state_changed, on_open_dashboard):
        super().__init__(parent, padding=24)
        self.on_state_changed = on_state_changed
        self.on_open_dashboard = on_open_dashboard
        self.tracker = TrackingProcess()
        self._start_time = None
        self._announced_running = False

        self._build_ui()
        self._load_settings_into_header()
        self._show_last_session_summary()
        self._poll_output()
        self._poll_preview()
        self._tick_elapsed()

    def _build_ui(self):
        shell = tk.Frame(self, bg="#1b2432")
        shell.pack(fill="both", expand=True, padx=6, pady=0)

        top_bar = tk.Frame(shell, bg="#1d232d", height=40)
        top_bar.pack(fill="x")
        top_bar.pack_propagate(False)

        left_clock = tk.Label(top_bar, text="1. Sep 12:52", bg="#1d232d", fg="#dfeaf8",
                             font=("Segoe UI", 10, "bold"), anchor="w")
        left_clock.place(x=8, y=8)

        title = tk.Label(top_bar, text="Workspace-Tracking", bg="#1d232d", fg="#eef5ff",
                         font=("Segoe UI", 14, "bold"))
        title.place(relx=0.5, y=8, anchor="n")

        system_icons = tk.Label(top_bar, text="◔  ◲  ⨯", bg="#1d232d", fg="#dfeaf8",
                                font=("Segoe UI", 10, "bold"))
        system_icons.place(relx=0.98, y=8, anchor="ne")

        tab_bar = tk.Frame(shell, bg="#1b2432", height=56)
        tab_bar.pack(fill="x")
        tab_bar.pack_propagate(False)

        self.tab_buttons = {}
        self.tab_buttons["home"] = tk.Button(tab_bar, text="Steuerung", bg="#3a7fe9", fg="white",
                                             bd=0, height=1, padx=16, pady=8,
                                             font=("Segoe UI", 10, "bold"),
                                             command=lambda: self.on_state_changed if False else None)
        self.tab_buttons["home"].place(x=10, y=10, width=110, height=28)

        self.tab_buttons["dashboard"] = tk.Button(tab_bar, text="Auswertung", bg="#2c3746", fg="#dfeaf8",
                                                  bd=0, height=1, padx=16, pady=8,
                                                  font=("Segoe UI", 10, "bold"),
                                                  command=lambda: self.on_state_changed if False else None)
        self.tab_buttons["dashboard"].place(x=130, y=10, width=110, height=28)

        content = tk.Frame(shell, bg="#1b2432")
        content.pack(fill="both", expand=True, pady=(0, 8))

        hero = tk.Frame(content, bg="#2a3540", highlightbackground="#37475f", highlightthickness=1)
        hero.pack(fill="x", pady=(10, 18))

        left = tk.Frame(hero, bg="#0f1a2d")
        left.pack(side="left", fill="both", expand=True, padx=24, pady=20)
        tk.Label(left, text="Hallo, Danic!", bg="#0f1a2d", fg=COLOR_TEXT,
                 font=("Segoe UI", 29, "bold"), anchor="w").pack(anchor="w")
        tk.Label(left, text="Überwachung & Motion Capture", bg="#0f1a2d", fg="#93a9c6",
                 font=("Segoe UI", 12), anchor="w").pack(anchor="w", pady=(8, 6))
        tk.Label(left, text="Computeraktivität + Körper-, Hand- und Gesichtserkennung in einem System.",
                 bg="#0f1a2d", fg="#dfe9ff", font=("Segoe UI", 16, "bold"), justify="left",
                 wraplength=860, anchor="w").pack(anchor="w", pady=(0, 12))

        status_row = tk.Frame(left, bg="#0f1a2d")
        status_row.pack(anchor="w", pady=(4, 14))
        self.status_dot = tk.Label(status_row, text="●", fg="#2fd38a", bg="#0f1a2d", font=("Segoe UI", 12, "bold"))
        self.status_dot.pack(side="left")
        self.status_label = tk.Label(status_row, text="Bereit.", bg="#0f1a2d", fg="#95a9c1",
                                     font=("Segoe UI", 10))
        self.status_label.pack(side="left", padx=(8, 0))
        self.elapsed_label = tk.Label(left, text="", bg="#0f1a2d", fg="#5f7cff",
                                      font=("Segoe UI", 18, "bold"), anchor="w")
        self.elapsed_label.pack(anchor="w")

        right = tk.Frame(hero, bg="#0f1a2d")
        right.pack(side="right", fill="y", padx=20, pady=20)
        self.toggle_btn = ttk.Button(right, text="Aufnahme starten", style="Big.TButton", command=self._on_toggle)
        self.toggle_btn.pack(anchor="e")

        cards = tk.Frame(content, bg=COLOR_BG)
        cards.pack(fill="x", pady=(0, 18))
        for idx, label in enumerate([("Kamera", "Live"), ("Computer", "Monitoring"), ("Motion", "Pose + Face + Hand")]):
            card = tk.Frame(cards, bg="#121a2b", highlightbackground="#2b3a52", highlightthickness=1)
            card.grid(row=0, column=idx, sticky="ew", padx=(0 if idx == 0 else 10, 0), pady=16)
            card.grid_columnconfigure(0, weight=1)
            card.grid_rowconfigure(0, weight=1)
            card.grid_propagate(False)
            card.configure(padx=18, pady=16)
            tk.Label(card, text=label[0], bg="#121a2b", fg="#97a9c5", font=("Segoe UI", 11)).pack(anchor="w")
            tk.Label(card, text=label[1], bg="#121a2b", fg=COLOR_TEXT, font=("Segoe UI", 20, "bold")).pack(anchor="w", pady=(5, 0))
        cards.columnconfigure(0, weight=1)
        cards.columnconfigure(1, weight=1)
        cards.columnconfigure(2, weight=1)

        preview = tk.Frame(content, bg="#121a2b", highlightbackground="#2b3a52", highlightthickness=1)
        preview.pack(fill="both", expand=False)
        preview.grid_columnconfigure(0, weight=1)
        preview.grid_columnconfigure(1, weight=0)

        tk.Label(preview, text="LIVE PREVIEW", bg="#121a2b", fg="#4edcc4", font=("Segoe UI", 10, "bold"),
                 anchor="w", padx=18, pady=12).grid(row=0, column=0, columnspan=2, sticky="ew")

        preview_img_frame = tk.Frame(preview, bg="#121a2b")
        preview_img_frame.grid(row=1, column=0, sticky="nsew", padx=(18, 10), pady=(0, 18))
        self.preview_image = tk.Label(preview_img_frame, bg="#101827", width=52, height=16, compound="center",
                                     relief="solid", borderwidth=1, font=("Segoe UI", 11))
        self.preview_image.pack(fill="both", expand=True)

        status_info = tk.Frame(preview, bg="#121a2b")
        status_info.grid(row=1, column=1, sticky="nsew", padx=(0, 18), pady=(0, 18))
        status_info.grid_propagate(False)
        status_info.configure(padx=18, pady=12)
        tk.Label(status_info, text="Status", bg="#121a2b", fg="#97a9c5", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.preview_label = tk.Label(status_info, text="Kamera-Status: bereit\n\nMotion Capture: standby\n\nComputer-Tracking: bereit",
                                     bg="#121a2b", fg=COLOR_TEXT, justify="left", font=("Segoe UI", 10),
                                     anchor="nw", padx=4, pady=8)
        self.preview_label.pack(anchor="w", fill="both", expand=True)

        self.system_status = tk.Label(content, text="System: bereit für Aufnahme", bg=COLOR_BG, fg="#97a9c5",
                                      font=("Segoe UI", 10), anchor="w", pady=14)
        self.system_status.pack(fill="x", anchor="w")

        self.details_visible = tk.BooleanVar(value=False)
        options = ttk.Frame(self)
        options.pack(fill="x", pady=(0, 10))
        ttk.Checkbutton(options, text="Technisches Protokoll anzeigen", variable=self.details_visible,
                         command=self._toggle_details).pack(anchor="w")

        self.log_text = scrolledtext.ScrolledText(
            self, bg=COLOR_PANEL, fg=COLOR_TEXT, insertbackground=COLOR_TEXT,
            font=("Consolas", 9), relief="solid", borderwidth=1, wrap="word",
            height=8, state="disabled")

        ttk.Separator(self).pack(fill="x", pady=(12, 14))
        self.summary_frame = ttk.Frame(self)
        self.summary_frame.pack(fill="x")

    def _toggle_details(self):
        if self.details_visible.get():
            self.log_text.pack(fill="both", expand=True, pady=(10, 0))
        else:
            self.log_text.pack_forget()

    def _load_settings_into_header(self):
        settings = gui_settings.load_settings()
        name = settings.get("user")
        label_text = f"Hallo, {name}!" if name else "Hallo!"
        if hasattr(self, "hello_label"):
            self.hello_label.configure(text=label_text)
        else:
            pass

    def _open_settings(self):
        SetupWizard(self.winfo_toplevel(), on_saved=self._on_settings_saved)

    def _on_settings_saved(self, settings):
        self._load_settings_into_header()
        self._show_last_session_summary()

    def _on_toggle(self):
        if self.tracker.is_running():
            self._on_stop()
        else:
            self._on_start()

    def _on_start(self):
        settings = gui_settings.load_settings()
        if not settings.get("user"):
            messagebox.showinfo("Kurz einrichten", "Bitte zuerst den Namen einrichten.")
            self._open_settings()
            return

        for widget in self.summary_frame.winfo_children():
            widget.destroy()
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

        try:
            self.tracker.start(settings)
        except Exception as e:
            messagebox.showerror("Start fehlgeschlagen", str(e))
            return

        self._start_time = datetime.datetime.now()
        self._announced_running = False
        self.toggle_btn.configure(text="Aufnahme beenden", state="normal")
        self.status_label.configure(text="Aufnahme läuft …")
        self.status_dot.configure(fg="#f5b75d")
        self.preview_label.configure(text="Kamera-Status: aktiv\nMotion Capture: live\nComputer-Tracking: online")
        self.system_status.configure(text="System: Live-Tracking aktiv")

    def _on_stop(self):
        self.toggle_btn.configure(state="disabled")
        self.status_label.configure(text="Wird beendet, einen Moment …")
        self.tracker.stop()

    def _log(self, line):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _poll_preview(self):
        preview_path = os.path.join(os.path.dirname(__file__), "camera_preview.png")
        if os.path.exists(preview_path):
            try:
                import PIL.Image, PIL.ImageTk
                with PIL.Image.open(preview_path) as pil_image:
                    pil_image.verify()
                with PIL.Image.open(preview_path) as pil_image:
                    pil_image.thumbnail((440, 248), PIL.Image.Resampling.LANCZOS)
                    photo = PIL.ImageTk.PhotoImage(pil_image)
                    self.preview_image.configure(image=photo, text="")
                    self.preview_image.image = photo
            except Exception:
                try:
                    os.remove(preview_path)
                except OSError:
                    pass
                self.preview_image.configure(text="(Keine Vorschau verfügbar)", image="")
                self.after(250, self._poll_preview)
                return
        self.after(250, self._poll_preview)

    def _poll_output(self):
        try:
            while True:
                item = self.tracker.output_queue.get_nowait()
                if item is None:
                    self._on_process_ended()
                else:
                    self._log(item)
                    if not self._announced_running and self.tracker.session_id:
                        self._announced_running = True
                        self.on_state_changed(self.tracker.user_name, self.tracker.session_id, True)
        except queue.Empty:
            pass
        self.after(100, self._poll_output)

    def _on_process_ended(self):
        returncode = self.tracker.proc.returncode if self.tracker.proc else None
        self._start_time = None
        self.elapsed_label.configure(text="")
        self.toggle_btn.configure(text="Aufnahme starten", state="normal")

        if returncode == 0:
            self.status_label.configure(text="Fertig! Hier ist deine Zusammenfassung:")
            self.status_dot.configure(fg="#2fd38a")
            self.preview_label.configure(text="Kamera-Status: bereit\nMotion Capture: standby\nComputer-Tracking: abgeschlossen")
            self.system_status.configure(text="System: bereit für neue Aufnahme")
        else:
            self.status_label.configure(text=f"Beendet (Exit-Code {returncode}) -- Details unten prüfen.")
            self.status_dot.configure(fg="#ff6b6b")
            self.preview_label.configure(text="Kamera-Status: beendet\nMotion Capture: stop\nComputer-Tracking: beendet")
            self.system_status.configure(text="System: beendet mit Hinweis")

        if self.tracker.session_id:
            self.on_state_changed(self.tracker.user_name, self.tracker.session_id, False)
            self._render_session_summary(self.tracker.user_name, self.tracker.session_id)

    def _tick_elapsed(self):
        if self._start_time is not None:
            delta = datetime.datetime.now() - self._start_time
            total = int(delta.total_seconds())
            h, rest = divmod(total, 3600)
            m, s = divmod(rest, 60)
            self.elapsed_label.configure(text=f"{h:02d}:{m:02d}:{s:02d}")
        self.after(1000, self._tick_elapsed)

    def _show_last_session_summary(self):
        settings = gui_settings.load_settings()
        if not settings.get("user"):
            return
        try:
            users = dict((name, uid) for (uid, name) in db_queries.list_users())
            user_id = users.get(settings["user"])
            if user_id is None:
                return
            sessions = db_queries.list_sessions(user_id, limit=1)
        except Exception:
            return
        if not sessions:
            return
        session_id = sessions[0][0]
        self._render_session_summary(settings["user"], session_id, title="Deine letzte Aufnahme")

    def _render_session_summary(self, user_name, session_id, title="Zusammenfassung"):
        for widget in self.summary_frame.winfo_children():
            widget.destroy()
        try:
            overview = db_queries.get_session_overview(session_id)
        except Exception:
            return

        ttk.Label(self.summary_frame, text=title, style="Muted.TLabel").pack(anchor="w", pady=(0, 10))
        row = ttk.Frame(self.summary_frame)
        row.pack(anchor="w")
        v1 = stat_row(row, "Gesamtdauer", 0)
        v1.configure(text=db_queries.format_dauer(overview["dauer_gesamt"]))
        v2 = stat_row(row, "Aktiv", 1)
        v2.configure(text=db_queries.format_dauer(overview["dauer_aktiv"]))
        v3 = stat_row(row, "App-Wechsel", 2)
        v3.configure(text=str(overview["anzahl_wechsel"]))

        ttk.Button(self.summary_frame, text="Vollständige Auswertung öffnen",
                   command=lambda: self.on_open_dashboard(user_name, session_id)
                   ).pack(anchor="w", pady=(14, 0))

    def request_stop_for_shutdown(self):
        self.tracker.stop()

    def is_tracking(self):
        return self.tracker.is_running()


# ===========================================================
# Tab 2: Auswertung
# ===========================================================

class DashboardTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, padding=20)
        self._user_ids_by_name = {}
        self._session_ids_by_label = {}
        self._current_session_id = None
        self._running_session_id = None
        self._live_job = None
        self._auto_selected_once = False
        self._build_ui()

    def _build_ui(self):
        self.rowconfigure(3, weight=1)
        self.columnconfigure(0, weight=1)

        top = ttk.Frame(self, padding=(0, 0, 0, 12))
        top.grid(row=0, column=0, sticky="ew")

        ttk.Label(top, text="Nutzer").pack(side="left")
        self.user_var = tk.StringVar()
        self.user_combo = ttk.Combobox(top, textvariable=self.user_var, state="readonly", width=18)
        self.user_combo.pack(side="left", padx=(6, 16))
        self.user_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_sessions())

        ttk.Label(top, text="Sitzung").pack(side="left")
        self.session_var = tk.StringVar()
        self.session_combo = ttk.Combobox(top, textvariable=self.session_var, state="readonly", width=42)
        self.session_combo.pack(side="left", padx=(6, 16))
        self.session_combo.bind("<<ComboboxSelected>>", lambda e: self._load_session())

        ttk.Button(top, text="Aktualisieren", style="Secondary.TButton", command=self._load_session).pack(side="left")

        self.live_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text="Live-Aktualisierung", variable=self.live_var,
                         command=self._toggle_live).pack(side="left", padx=(16, 0))

        kpi_row = ttk.Frame(self)
        kpi_row.grid(row=1, column=0, sticky="ew", pady=(0, 18))
        for idx, label in enumerate([("Gesamtdauer", "Gesamt"), ("Aktiv", "Aktiv"), ("Leerlauf", "Leerlauf"), ("App-Wechsel", "Wechsel")]):
            card = ttk.Frame(kpi_row, padding=(14, 12))
            card.grid(row=0, column=idx, sticky="ew", padx=(0 if idx == 0 else 10, 0))
            card.configure(style="Card.TFrame")
            ttk.Label(card, text=label[0], style="Muted.TLabel").pack(anchor="w")
            value = ttk.Label(card, text="–", style="BigValue.TLabel")
            value.pack(anchor="w", pady=(4, 0))
            setattr(self, f"val_{label[1].lower()}", value)
        kpi_row.columnconfigure(0, weight=1)
        kpi_row.columnconfigure(1, weight=1)
        kpi_row.columnconfigure(2, weight=1)
        kpi_row.columnconfigure(3, weight=1)

        charts_row = ttk.Frame(self)
        charts_row.grid(row=2, column=0, sticky="ew", pady=(0, 14))
        charts_row.columnconfigure(0, weight=1)
        charts_row.columnconfigure(1, weight=2)

        self.fig_pie = Figure(figsize=(3.4, 3.0), dpi=100)
        self.ax_pie = self.fig_pie.add_subplot(111)
        self.canvas_pie = FigureCanvasTkAgg(self.fig_pie, master=charts_row)
        self.canvas_pie.get_tk_widget().grid(row=0, column=0, sticky="ew", padx=(0, 10))

        self.fig_bar = Figure(figsize=(6.4, 3.0), dpi=100)
        self.ax_bar = self.fig_bar.add_subplot(111)
        self.canvas_bar = FigureCanvasTkAgg(self.fig_bar, master=charts_row)
        self.canvas_bar.get_tk_widget().grid(row=0, column=1, sticky="ew")

        bottom = ttk.Frame(self)
        bottom.grid(row=3, column=0, sticky="nsew")
        bottom.columnconfigure(0, weight=1)
        bottom.rowconfigure(1, weight=1)

        ttk.Label(bottom, text="Zeitstrahl (letzte App-Wechsel)", style="Muted.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 4))
        self.fig_timeline = Figure(figsize=(10, 2.2), dpi=100)
        self.ax_timeline = self.fig_timeline.add_subplot(111)
        self.canvas_timeline = FigureCanvasTkAgg(self.fig_timeline, master=bottom)
        self.canvas_timeline.get_tk_widget().grid(row=1, column=0, sticky="ew", pady=(0, 14))

        tables_row = ttk.Frame(bottom)
        tables_row.grid(row=2, column=0, sticky="nsew")
        tables_row.columnconfigure(0, weight=1)
        tables_row.columnconfigure(1, weight=1)

        touch_frame = ttk.Frame(tables_row)
        touch_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        ttk.Label(touch_frame, text="Hand-Körper-Berührungen", style="Muted.TLabel").pack(anchor="w", pady=(0, 4))
        self.touch_tree = ttk.Treeview(
            touch_frame, columns=("hand", "stelle", "anzahl", "pro_min"), show="headings", height=6)
        for col, text, width in [("hand", "Hand", 80), ("stelle", "Körperstelle", 120),
                                  ("anzahl", "Anzahl", 70), ("pro_min", "pro Min.", 70)]:
            self.touch_tree.heading(col, text=text)
            self.touch_tree.column(col, width=width, anchor="center")
        self.touch_tree.pack(fill="both", expand=True)

        obj_frame = ttk.Frame(tables_row)
        obj_frame.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        ttk.Label(obj_frame, text="Meist erkannte Objekte", style="Muted.TLabel").pack(anchor="w", pady=(0, 4))
        self.obj_tree = ttk.Treeview(obj_frame, columns=("objekt", "sichtbar"), show="headings", height=6)
        self.obj_tree.heading("objekt", text="Objekt")
        self.obj_tree.heading("sichtbar", text="≈ sichtbar")
        self.obj_tree.column("objekt", width=140, anchor="w")
        self.obj_tree.column("sichtbar", width=100, anchor="center")
        self.obj_tree.pack(fill="both", expand=True)

    def ensure_loaded(self):
        if self._auto_selected_once:
            return
        self._auto_selected_once = True
        self._refresh_users()
        settings = gui_settings.load_settings()
        if settings.get("user") and settings["user"] in self._user_ids_by_name:
            self.user_var.set(settings["user"])
            self._refresh_sessions()

    def _refresh_users(self):
        try:
            users = db_queries.list_users()
        except Exception as e:
            messagebox.showerror("Datenbank", f"Nutzerliste konnte nicht geladen werden:\n{e}")
            return
        self._user_ids_by_name = {name: uid for (uid, name) in users}
        self.user_combo["values"] = list(self._user_ids_by_name.keys())
        if users and not self.user_var.get():
            self.user_var.set(users[0][1])
            self._refresh_sessions()

    def _refresh_sessions(self):
        user_id = self._user_ids_by_name.get(self.user_var.get())
        if user_id is None:
            return
        try:
            sessions = db_queries.list_sessions(user_id)
        except Exception as e:
            messagebox.showerror("Datenbank", f"Sitzungen konnten nicht geladen werden:\n{e}")
            return

        self._session_ids_by_label = {}
        labels = []
        for (sid, device, started, ended, dauer, notes) in sessions:
            status = "läuft noch" if ended is None else db_queries.format_dauer(dauer)
            label = f"{started.strftime('%d.%m.%Y %H:%M')} · {device or '?'} · {status}"
            self._session_ids_by_label[label] = sid
            labels.append(label)

        self.session_combo["values"] = labels
        if labels:
            self.session_combo.current(0)
            self._load_session()
        else:
            self.session_combo.set("")

    def select_user_and_session(self, user_name, session_id):
        self._auto_selected_once = True
        if user_name not in self._user_ids_by_name:
            self._refresh_users()
        if user_name in self._user_ids_by_name:
            self.user_var.set(user_name)
            self._refresh_sessions()
            for label, sid in self._session_ids_by_label.items():
                if sid == session_id:
                    self.session_var.set(label)
                    break
            self._load_session()

    def notify_recording_state(self, user_name, session_id, running):
        self._running_session_id = session_id if running else None
        if self._current_session_id == session_id:
            self.live_var.set(running)
            self._toggle_live()
            if not running:
                self._load_session()

    def _load_session(self):
        label = self.session_var.get()
        session_id = self._session_ids_by_label.get(label)
        if session_id is None:
            return
        self._current_session_id = session_id

        try:
            overview = db_queries.get_session_overview(session_id)
            kategorien = db_queries.get_kategorie_breakdown(session_id)
            top_apps = db_queries.get_top_apps(session_id)
            timeline = db_queries.get_timeline(session_id)
            touches = db_queries.get_touch_summary(session_id)
            objects = db_queries.get_object_summary(session_id)
        except Exception as e:
            messagebox.showerror("Datenbank", f"Sitzungsdaten konnten nicht geladen werden:\n{e}")
            return

        self.val_gesamt.configure(text=db_queries.format_dauer(overview["dauer_gesamt"]))
        self.val_aktiv.configure(text=db_queries.format_dauer(overview["dauer_aktiv"]))
        self.val_leerlauf.configure(text=db_queries.format_dauer(overview["dauer_leerlauf"]))
        self.val_wechsel.configure(text=str(overview["anzahl_wechsel"]))

        self._draw_pie(kategorien)
        self._draw_bar(top_apps)
        self._draw_timeline(timeline)
        self._fill_touch_table(touches, overview["dauer_gesamt"])
        self._fill_object_table(objects)

    def _draw_pie(self, kategorien):
        self.ax_pie.clear()
        style_axes(self.ax_pie, self.fig_pie)
        if not kategorien:
            self.ax_pie.text(0.5, 0.5, "Keine Daten", ha="center", va="center", color=COLOR_TEXT_MUTED)
        else:
            labels = [k for (k, _d) in kategorien]
            values = [float(d) for (_k, d) in kategorien]
            colors = [kategorie_farbe(k) for k in labels]
            self.ax_pie.pie(values, labels=labels, colors=colors, autopct="%1.0f%%",
                             textprops={"color": COLOR_TEXT, "fontsize": 8},
                             wedgeprops={"edgecolor": COLOR_WHITE, "linewidth": 1.5})
        self.ax_pie.set_title("Arbeit vs. Nicht-Arbeit", fontsize=10)
        self.fig_pie.tight_layout()
        self.canvas_pie.draw()

    def _draw_bar(self, top_apps):
        self.ax_bar.clear()
        style_axes(self.ax_bar, self.fig_bar)
        if not top_apps:
            self.ax_bar.text(0.5, 0.5, "Keine Daten", ha="center", va="center", color=COLOR_TEXT_MUTED)
        else:
            names = [a or "?" for (a, _k, _d) in top_apps][::-1]
            minutes = [float(d) / 60.0 for (_a, _k, d) in top_apps][::-1]
            colors = [kategorie_farbe(k) for (_a, k, _d) in top_apps][::-1]
            self.ax_bar.barh(names, minutes, color=colors)
            self.ax_bar.set_xlabel("Minuten")
        self.ax_bar.set_title("Meistgenutzte Apps", fontsize=10)
        self.fig_bar.tight_layout()
        self.canvas_bar.draw()

    def _draw_timeline(self, timeline):
        self.ax_timeline.clear()
        style_axes(self.ax_timeline, self.fig_timeline)
        if not timeline:
            self.ax_timeline.text(0.5, 0.5, "Keine Daten", ha="center", va="center", color=COLOR_TEXT_MUTED)
            self.fig_timeline.tight_layout()
            self.canvas_timeline.draw()
            return

        rows = timeline[-60:]
        for (app, kategorie, start, end) in rows:
            start_local = _to_local_naive(start)
            end_local = _to_local_naive(end) if end else _to_local_naive(datetime.datetime.now())
            start_num = mdates.date2num(start_local)
            end_num = mdates.date2num(end_local)
            self.ax_timeline.barh(0, end_num - start_num, left=start_num, height=0.6,
                                   color=kategorie_farbe(kategorie))

        self.ax_timeline.xaxis_date()
        self.ax_timeline.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        self.ax_timeline.set_yticks([])
        self.ax_timeline.set_title(
            f"{len(rows)} von {len(timeline)} App-Wechseln" if len(timeline) > len(rows) else "App-Wechsel",
            fontsize=10)
        self.fig_timeline.tight_layout()
        self.canvas_timeline.draw()

    def _fill_touch_table(self, touches, dauer_gesamt):
        self.touch_tree.delete(*self.touch_tree.get_children())
        minuten = dauer_gesamt / 60.0 if dauer_gesamt else 0
        for (hand, teil, anzahl, _erste, _letzte) in touches:
            pro_min = anzahl / minuten if minuten > 0 else 0
            self.touch_tree.insert("", "end", values=(hand, teil, anzahl, f"{pro_min:.1f}"))

    def _fill_object_table(self, objects):
        self.obj_tree.delete(*self.obj_tree.get_children())
        for (name, frames) in objects:
            sekunden = frames * 0.033
            self.obj_tree.insert("", "end", values=(name, db_queries.format_dauer(sekunden)))

    def _toggle_live(self):
        if self.live_var.get():
            self._live_tick()
        elif self._live_job is not None:
            self.after_cancel(self._live_job)
            self._live_job = None

    def _live_tick(self):
        self._load_session()
        self._live_job = self.after(5000, self._live_tick)


# ===========================================================
# Hauptfenster
# ===========================================================

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Workspace-Tracking")
        self.geometry("1440x900")
        self.minsize(1100, 760)
        self.configure(bg="#1b2432")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        apply_theme(self)
        self.withdraw()

        self.tab_frame = tk.Frame(self, bg="#1b2432", height=52)
        self.tab_frame.pack(fill="x", padx=10, pady=(10, 0))
        self.tab_frame.pack_propagate(False)

        self.tab_buttons = {}
        self.tab_buttons["home"] = tk.Button(
            self.tab_frame, text="Steuerung", bg="#3a7fe9", fg="white",
            bd=0, padx=18, pady=8, font=("Segoe UI", 10, "bold"),
            command=lambda: self._show_tab("home"))
        self.tab_buttons["dashboard"] = tk.Button(
            self.tab_frame, text="Auswertung", bg="#2c3746", fg="#dfeaf8",
            bd=0, padx=18, pady=8, font=("Segoe UI", 10, "bold"),
            command=lambda: self._show_tab("dashboard"))
        self.tab_buttons["home"].pack(side="left")
        self.tab_buttons["dashboard"].pack(side="left", padx=(8, 0))

        self.dashboard_tab = DashboardTab(self)
        self.home_tab = HomeTab(self, on_state_changed=self._on_recording_state_changed,
                                 on_open_dashboard=self._go_to_results)

        self.dashboard_tab.pack_forget()
        self.home_tab.pack(fill="both", expand=True)

        self.notebook = self
        self._current_tab = "home"
        self._show_tab("home")

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(50, self._maybe_first_run_setup)

    def _show_tab(self, name):
        self._current_tab = name
        for key, btn in self.tab_buttons.items():
            if key == name:
                btn.configure(bg="#3a7fe9", fg="white")
            else:
                btn.configure(bg="#2c3746", fg="#dfeaf8")

        if name == "home":
            self.home_tab.pack(fill="both", expand=True)
            self.dashboard_tab.pack_forget()
        else:
            self.home_tab.pack_forget()
            self.dashboard_tab.pack(fill="both", expand=True)
            self.dashboard_tab.ensure_loaded()

    def select(self, tab):
        if tab is self.dashboard_tab:
            self._show_tab("dashboard")
        else:
            self._show_tab("home")

    def _on_tab_changed(self, event=None):
        if self._current_tab == "dashboard":
            self.dashboard_tab.ensure_loaded()

    def _on_recording_state_changed(self, user_name, session_id, running):
        self.dashboard_tab.notify_recording_state(user_name, session_id, running)

    def _go_to_results(self, user_name, session_id):
        self.dashboard_tab.select_user_and_session(user_name, session_id)
        self._show_tab("dashboard")

    def _maybe_first_run_setup(self):
        if not gui_settings.has_settings() or not gui_settings.load_settings().get("user"):
            self.deiconify()
            QuickSetupDialog(self, on_saved=self._on_first_run_saved)
        else:
            self.deiconify()

    def _on_first_run_saved(self, settings):
        self.home_tab._load_settings_into_header()
        self.home_tab._show_last_session_summary()

    def _on_close(self):
        if self.home_tab.is_tracking():
            if not messagebox.askyesno(
                    "Aufnahme läuft noch",
                    "Es läuft gerade eine Aufnahme. Wirklich beenden?\n"
                    "Die aktuelle Sitzung wird sauber gestoppt, das kann kurz dauern."):
                return
            self.home_tab.request_stop_for_shutdown()
        self.destroy()


def main():
    print("[Main] Starting application...", file=sys.stderr)
    if not os.path.exists(TRACK_ALL_PATH):
        print(f"Warnung: {TRACK_ALL_PATH} nicht gefunden. "
              f"track_all.py muss im selben Ordner liegen wie diese Datei.")

    try:
        print("[Main] Initializing App class...", file=sys.stderr)
        app = App()
        print("[Main] App initialized, starting mainloop...", file=sys.stderr)
        app.mainloop()
        print("[Main] Mainloop finished", file=sys.stderr)
        return 0
    except Exception as exc:
        print(f"[App] FATAL STARTUP ERROR: {exc}", file=sys.stderr)
        try:
            error_root = tk.Tk()
            error_root.withdraw()
            messagebox.showerror(
                "Atum konnte nicht gestartet werden",
                "Beim Start der Anwendung ist ein Fehler aufgetreten.\n\n"
                f"Details: {exc}\n\nBitte die Konsole prüfen und die App neu starten."
            )
            error_root.update()
            error_root.destroy()
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())