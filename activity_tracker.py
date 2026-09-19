"""
Aktivitäts-Tracker
===================
Läuft im Hintergrund und protokolliert, welche App/welches Fenster gerade
aktiv ist. Ordnet jede App einer Kategorie zu (Arbeit / Nicht-Arbeit) und
schreibt zwei CSV-Dateien:

  - activity_log.csv   -> jede einzelne Messung (alle paar Sekunden), mit
                           20 Feldern: Zeitstempel, App, Fenstertitel,
                           Kategorie, PID, Fenster-ID, Workspace, Position/
                           Größe, Bildschirm, maximiert-Status, Leerlaufzeit,
                           Aktiv/Leerlauf-Status, App-Wechsel- und
                           Interaktionsfrequenz (jeweils letzte 5 Minuten)
  - activity_sessions.csv -> zusammengefasste Sitzungen pro App
                              (wann begonnen, wann beendet, wie lange)
  - inactivity_periods.csv -> erkannte Inaktivitätsperioden (Start, Ende,
                               Dauer, welche App/Kategorie währenddessen aktiv war)

Voraussetzung (einmalig, siehe GNOME Extensions Anleitung):
    Die GNOME-Erweiterung "Window Calls" muss installiert und aktiviert sein
    (https://extensions.gnome.org/extension/4724/window-calls/).
    Funktioniert damit auch unter Wayland, kein xdotool/Xorg mehr nötig.

Start (fragt beim allerersten Mal interaktiv nach deinen Arbeits-Apps,
merkt sich die Antwort danach in activity_config.json):
    python3 activity_tracker.py

Arbeits-Apps direkt ohne Nachfrage setzen:
    python3 activity_tracker.py --work-apps "code,firefox,libreoffice"

Gespeicherte Konfiguration neu abfragen:
    python3 activity_tracker.py --configure

Im Hintergrund laufen lassen (schließt Terminal, Skript läuft weiter):
    nohup python3 activity_tracker.py > tracker.log 2>&1 &

Beenden:
    Strg+C im Vordergrund, oder bei Hintergrund-Betrieb:
    pkill -f activity_tracker.py
"""

import csv
import json
import ast
import re
import argparse
import subprocess
import time
import datetime
import os
import sys
import platform
import shutil
from collections import deque

# ===========================================================
# KONFIGURATION -- hier anpassen
# ===========================================================

# Wie oft geprüft wird, welches Fenster aktiv ist (in Sekunden)
CHECK_INTERVAL = 3

# Ab wie vielen Sekunden ohne Eingabe gilt der Nutzer als "Leerlauf"
IDLE_THRESHOLD_SECONDS = 30

# Zeitfenster (in Sekunden) für die rollierenden Häufigkeits-Kennzahlen
# (Wechsel-/Interaktionsfrequenz werden jeweils für die letzten X Sekunden berechnet)
FREQUENZ_FENSTER_SEKUNDEN = 300  # 5 Minuten

# Vorschlags-Liste, falls du bei der Ersteinrichtung einfach Enter drückst.
# Kleinschreibung, Teilstrings reichen (z.B. "code" erfasst "Visual Studio Code")
DEFAULT_WORK_APPS = [
    "code", "vscode", "terminal", "gnome-terminal", "konsole",
    "libreoffice", "writer", "calc", "impress",
    "firefox", "chrome", "chromium",
    "gimp", "blender", "inkscape",
    "thunderbird", "outlook",
    "slack", "teams",
]

DEFAULT_NON_WORK_APPS = [
    "spotify", "steam", "discord", "netflix", "youtube",
]

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(OUTPUT_DIR, "activity_log.csv")
SESSION_FILE = os.path.join(OUTPUT_DIR, "activity_sessions.csv")
INACTIVITY_FILE = os.path.join(OUTPUT_DIR, "inactivity_periods.csv")
CONFIG_FILE = os.path.join(OUTPUT_DIR, "activity_config.json")


def activity_tracking_available():
    """True only on Linux systems with GNOME accessibility tools active."""
    if platform.system() != "Linux":
        return False
    if shutil.which("gdbus") is None:
        return False
    try:
        proc = subprocess.run(
            [
                "gdbus", "call", "--session",
                "--dest", "org.gnome.Shell",
                "--object-path", "/org/gnome/Shell/Extensions/Windows",
                "--method", "org.gnome.Shell.Extensions.Windows.List",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2,
            check=False,
        )
        return proc.returncode == 0
    except Exception:
        return False


def load_or_create_config(reconfigure=False, cli_work_apps=None, cli_non_work_apps=None):
    """
    Lädt die Arbeit/Nicht-Arbeit-Listen aus activity_config.json.
    Falls die Datei nicht existiert, oder --configure angegeben wurde,
    wird interaktiv beim Start danach gefragt. Über --work-apps /
    --non-work-apps lässt sich das auch ganz ohne Nachfrage direkt setzen.
    """
    if cli_work_apps is not None:
        work_apps = [a.strip().lower() for a in cli_work_apps.split(",") if a.strip()]
        non_work_apps = (
            [a.strip().lower() for a in cli_non_work_apps.split(",") if a.strip()]
            if cli_non_work_apps else DEFAULT_NON_WORK_APPS
        )
        save_config(work_apps, non_work_apps)
        return work_apps, non_work_apps

    if os.path.exists(CONFIG_FILE) and not reconfigure:
        with open(CONFIG_FILE, "r") as f:
            cfg = json.load(f)
        print(f"Geladene Arbeits-Apps: {', '.join(cfg['work_apps'])}")
        return cfg["work_apps"], cfg["non_work_apps"]

    # Ersteinrichtung oder Neu-Konfiguration: interaktiv abfragen
    print("Welche Apps zählen für dich als 'Arbeit'?")
    print(f"(kommagetrennt, z.B. code,firefox,libreoffice -- Enter für Standard-Liste)")
    print(f"Standard wäre: {', '.join(DEFAULT_WORK_APPS)}")
    work_input = input("> ").strip()
    work_apps = (
        [a.strip().lower() for a in work_input.split(",") if a.strip()]
        if work_input else DEFAULT_WORK_APPS
    )

    print("\nWelche Apps zählen explizit als 'Nicht-Arbeit'?")
    print(f"(kommagetrennt -- Enter für Standard-Liste: {', '.join(DEFAULT_NON_WORK_APPS)})")
    non_work_input = input("> ").strip()
    non_work_apps = (
        [a.strip().lower() for a in non_work_input.split(",") if a.strip()]
        if non_work_input else DEFAULT_NON_WORK_APPS
    )

    save_config(work_apps, non_work_apps)
    return work_apps, non_work_apps


def save_config(work_apps, non_work_apps):
    with open(CONFIG_FILE, "w") as f:
        json.dump({"work_apps": work_apps, "non_work_apps": non_work_apps}, f, indent=2)
    print(f"Konfiguration gespeichert in {CONFIG_FILE}\n")


# ===========================================================
# Hilfsfunktionen
# ===========================================================

def _gdbus_call(object_path, method, *args):
    """Kleiner Helfer: ruft eine D-Bus-Methode über gdbus auf und gibt die
    rohe Textausgabe zurück (oder None bei Fehler)."""
    try:
        cmd = ["gdbus", "call", "--session",
               "--dest", "org.gnome.Shell",
               "--object-path", object_path,
               "--method", method]
        cmd.extend(str(a) for a in args)
        return subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return None


def get_active_window_info():
    """
    Fragt über D-Bus (GNOME-Erweiterung "Window Calls") ausführliche Infos
    zum aktuell aktiven Fenster ab: Position, Größe, Bildschirm, Status, etc.
    Funktioniert unter Wayland und Xorg gleichermaßen.
    Gibt ein Dictionary zurück, oder None bei Fehler (z.B. Erweiterung nicht
    installiert/aktiviert, kein Fenster fokussiert).
    """
    if not activity_tracking_available():
        return None

    list_output = _gdbus_call("/org/gnome/Shell/Extensions/Windows",
                               "org.gnome.Shell.Extensions.Windows.List")
    if list_output is None:
        return None

    try:
        windows = json.loads(ast.literal_eval(list_output)[0])
    except Exception:
        return None

    focused = next((w for w in windows if w.get("focus")), None)
    if focused is None:
        return None

    info = {
        "app_name": focused.get("wm_class", "unbekannt"),
        "wm_class_instance": focused.get("wm_class_instance", ""),
        "fenster_titel": focused.get("title", ""),
        "pid": focused.get("pid", ""),
        "window_id": focused.get("id", ""),
        "workspace": focused.get("workspace", ""),
        "frame_type": focused.get("frame_type", ""),
        "window_type": focused.get("window_type", ""),
        # Standardwerte, falls der Details()-Aufruf unten fehlschlägt
        "fenster_breite": "", "fenster_hoehe": "",
        "fenster_x": "", "fenster_y": "",
        "maximiert": "", "monitor": "",
    }

    # Zusätzliche Geometrie-/Status-Details per Details()-Aufruf nachladen
    details_output = _gdbus_call("/org/gnome/Shell/Extensions/Windows",
                                  "org.gnome.Shell.Extensions.Windows.Details",
                                  f"uint32:{info['window_id']}")
    if details_output is not None:
        try:
            details = json.loads(ast.literal_eval(details_output)[0])
            info["fenster_breite"] = details.get("width", "")
            info["fenster_hoehe"] = details.get("height", "")
            info["fenster_x"] = details.get("x", "")
            info["fenster_y"] = details.get("y", "")
            info["maximiert"] = details.get("maximized", "")
            info["monitor"] = details.get("monitor", "")
        except Exception:
            pass  # Geometrie ist ein Bonus, kein Abbruchgrund

    return info


def get_idle_seconds():
    """
    Fragt über GNOME's Idle-Monitor ab, wie viele Sekunden seit der letzten
    Maus-/Tastatureingabe vergangen sind. Funktioniert unter Wayland und
    Xorg gleichermaßen. Gibt None zurück, falls nicht verfügbar.
    """
    if not activity_tracking_available():
        return None
    try:
        cmd = ["gdbus", "call", "--session",
               "--dest", "org.gnome.Mutter.IdleMonitor",
               "--object-path", "/org/gnome/Mutter/IdleMonitor/Core",
               "--method", "org.gnome.Mutter.IdleMonitor.GetIdletime"]
        output = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode().strip()
        match = re.search(r"(\d+)", output)
        return round(int(match.group(1)) / 1000, 1) if match else None
    except Exception:
        return None


def classify(app_name, title, work_apps, non_work_apps):
    """
    Ordnet eine App/Fenster einer Kategorie zu: 'Arbeit', 'Nicht-Arbeit',
    oder 'Unbekannt', falls sie in keiner Liste vorkommt.
    """
    combined = f"{app_name} {title}".lower()

    for keyword in non_work_apps:
        if keyword in combined:
            return "Nicht-Arbeit"

    for keyword in work_apps:
        if keyword in combined:
            return "Arbeit"

    return "Unbekannt"


def ensure_csv_headers():
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w", newline="") as f:
            csv.writer(f).writerow([
                "timestamp", "app_name", "wm_class_instance", "fenster_titel",
                "kategorie", "pid", "window_id", "workspace",
                "fenster_breite", "fenster_hoehe", "fenster_x", "fenster_y",
                "maximiert", "monitor", "frame_type", "window_type",
                "leerlauf_sekunden", "status",
                "wechsel_letzte_5min", "interaktionen_letzte_5min",
            ])

    if not os.path.exists(SESSION_FILE):
        with open(SESSION_FILE, "w", newline="") as f:
            csv.writer(f).writerow(
                ["app_name", "kategorie", "start", "ende", "dauer_sekunden"]
            )

    if not os.path.exists(INACTIVITY_FILE):
        with open(INACTIVITY_FILE, "w", newline="") as f:
            csv.writer(f).writerow(
                ["start", "ende", "dauer_sekunden", "app_dabei", "kategorie_dabei"]
            )


def write_session(app_name, kategorie, start_time, end_time):
    duration = round((end_time - start_time).total_seconds(), 1)
    with open(SESSION_FILE, "a", newline="") as f:
        csv.writer(f).writerow([
            app_name, kategorie,
            start_time.strftime("%Y-%m-%d %H:%M:%S"),
            end_time.strftime("%Y-%m-%d %H:%M:%S"),
            duration
        ])


def write_inactivity_period(start_time, end_time, app_dabei, kategorie_dabei):
    duration = round((end_time - start_time).total_seconds(), 1)
    with open(INACTIVITY_FILE, "a", newline="") as f:
        csv.writer(f).writerow([
            start_time.strftime("%Y-%m-%d %H:%M:%S"),
            end_time.strftime("%Y-%m-%d %H:%M:%S"),
            duration, app_dabei, kategorie_dabei
        ])


# ===========================================================
# Hauptschleife
# ===========================================================

def main():
    parser = argparse.ArgumentParser(description="Aktivitäts-Tracker")
    parser.add_argument("--configure", action="store_true",
                         help="Fragt die Arbeit/Nicht-Arbeit-Listen neu ab, auch wenn schon eine Konfiguration existiert")
    parser.add_argument("--work-apps", type=str, default=None,
                         help="Kommagetrennte Liste, z.B. 'code,firefox,libreoffice' -- setzt direkt ohne Nachfrage")
    parser.add_argument("--non-work-apps", type=str, default=None,
                         help="Kommagetrennte Liste, z.B. 'spotify,steam' -- nur zusammen mit --work-apps nutzbar")
    args = parser.parse_args()

    if not activity_tracking_available():
        print("Aktivitäts-Tracking ist auf diesem System nicht verfügbar.")
        print("Das Projekt läuft weiterhin mit Kamera- und CSV-Tracking, aber ohne GNOME-Fenster-Monitoring.")
        if platform.system() != "Linux":
            print(f"Betriebssystem erkannt: {platform.system()} -> Fenster-/Idle-Tracking wird übersprungen.")
        else:
            print("Ist die GNOME-Erweiterung 'Window Calls' installiert und aktiviert?")
            print("-> https://extensions.gnome.org/extension/4724/window-calls/")
            print("Test manuell mit: gdbus call --session --dest org.gnome.Shell "
                  "--object-path /org/gnome/Shell/Extensions/Windows "
                  "--method org.gnome.Shell.Extensions.Windows.List")
        return

    # Kurzer Selbsttest, ob die Window-Calls-Erweiterung erreichbar ist
    if get_active_window_info() is None:
        print("Konnte kein aktives Fenster auslesen.")
        print("Ist die GNOME-Erweiterung 'Window Calls' installiert und aktiviert?")
        print("-> https://extensions.gnome.org/extension/4724/window-calls/")
        print("Test manuell mit: gdbus call --session --dest org.gnome.Shell "
              "--object-path /org/gnome/Shell/Extensions/Windows "
              "--method org.gnome.Shell.Extensions.Windows.List")
        return

    work_apps, non_work_apps = load_or_create_config(
        reconfigure=args.configure,
        cli_work_apps=args.work_apps,
        cli_non_work_apps=args.non_work_apps,
    )

    ensure_csv_headers()
    print(f"Aktivitäts-Tracker gestartet. Prüfe alle {CHECK_INTERVAL} Sekunden.")
    print(f"Log-Datei:            {LOG_FILE}")
    print(f"Sitzungs-Datei:       {SESSION_FILE}")
    print(f"Inaktivitäts-Datei:   {INACTIVITY_FILE}")
    print("Beenden mit Strg+C.")

    current_app = None
    current_category = None
    session_start = None

    # Für die rollierenden Häufigkeits-Kennzahlen: Zeitstempel der letzten
    # App-Wechsel bzw. erkannten Interaktionen (nur die letzten X Sekunden
    # werden behalten, siehe FREQUENZ_FENSTER_SEKUNDEN)
    wechsel_zeitpunkte = deque()
    interaktions_zeitpunkte = deque()
    vorheriger_leerlauf = None

    # Für die Erkennung von Inaktivitätsperioden (Start/Ende)
    ist_inaktiv = False
    inaktiv_seit = None
    inaktiv_app = None
    inaktiv_kategorie = None

    try:
        while True:
            info = get_active_window_info()
            now = datetime.datetime.now()

            if info is not None:
                kategorie = classify(info["app_name"], info["fenster_titel"],
                                      work_apps, non_work_apps)
                leerlauf = get_idle_seconds()
                status = "Leerlauf" if (leerlauf is not None and leerlauf >= IDLE_THRESHOLD_SECONDS) else "Aktiv"

                # --- Interaktion erkennen: ist der Leerlauf-Wert seit der letzten
                # Messung zurückgesprungen? Dann gab es zwischendurch eine Eingabe. ---
                if (leerlauf is not None and vorheriger_leerlauf is not None
                        and leerlauf < vorheriger_leerlauf):
                    interaktions_zeitpunkte.append(now)
                vorheriger_leerlauf = leerlauf

                # alte Einträge außerhalb des Zeitfensters verwerfen
                grenze = now - datetime.timedelta(seconds=FREQUENZ_FENSTER_SEKUNDEN)
                while wechsel_zeitpunkte and wechsel_zeitpunkte[0] < grenze:
                    wechsel_zeitpunkte.popleft()
                while interaktions_zeitpunkte and interaktions_zeitpunkte[0] < grenze:
                    interaktions_zeitpunkte.popleft()

                # Jede einzelne Messung wird geloggt, mit allen Detail-Feldern
                with open(LOG_FILE, "a", newline="") as f:
                    csv.writer(f).writerow([
                        now.strftime("%Y-%m-%d %H:%M:%S"),
                        info["app_name"], info["wm_class_instance"], info["fenster_titel"],
                        kategorie, info["pid"], info["window_id"], info["workspace"],
                        info["fenster_breite"], info["fenster_hoehe"],
                        info["fenster_x"], info["fenster_y"],
                        info["maximiert"], info["monitor"],
                        info["frame_type"], info["window_type"],
                        leerlauf, status,
                        len(wechsel_zeitpunkte), len(interaktions_zeitpunkte),
                    ])

                # Sitzungs-Logik: hat sich die aktive App geändert?
                if info["app_name"] != current_app:
                    if current_app is not None:
                        # vorherige Sitzung abschließen und speichern
                        write_session(current_app, current_category, session_start, now)
                        wechsel_zeitpunkte.append(now)

                    # neue Sitzung beginnt
                    current_app = info["app_name"]
                    current_category = kategorie
                    session_start = now

                # --- Inaktivitätsperiode erkennen (Start/Ende, wie touch_events) ---
                if status == "Leerlauf" and not ist_inaktiv:
                    # Inaktivität beginnt gerade jetzt -- der eigentliche Start liegt
                    # aber schon 'leerlauf' Sekunden in der Vergangenheit
                    ist_inaktiv = True
                    inaktiv_seit = now - datetime.timedelta(seconds=leerlauf)
                    inaktiv_app = info["app_name"]
                    inaktiv_kategorie = kategorie

                elif status == "Aktiv" and ist_inaktiv:
                    # Inaktivität endet gerade
                    write_inactivity_period(inaktiv_seit, now, inaktiv_app, inaktiv_kategorie)
                    ist_inaktiv = False

            time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        # letzte offene Sitzung / Inaktivitätsperiode beim Beenden noch sauber abschließen
        jetzt = datetime.datetime.now()
        if current_app is not None:
            write_session(current_app, current_category, session_start, jetzt)
        if ist_inaktiv:
            write_inactivity_period(inaktiv_seit, jetzt, inaktiv_app, inaktiv_kategorie)
        print("\nTracker beendet. Letzte Sitzung/Inaktivitätsperiode gespeichert.")


if __name__ == "__main__":
    main()
