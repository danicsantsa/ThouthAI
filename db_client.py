"""
Datenbank-Client für das Workspace-Tracking-System
=====================================================
Verbindet sich mit deiner Supabase/Postgres-Datenbank und stellt einfache
Funktionen bereit, die von activity_tracker.py und pose_face_hand_detection.py
genutzt werden können.

Voraussetzung:
    pip install psycopg2-binary --break-system-packages

Verbindungsdaten:
    Werden aus db_config.json gelesen (im selben Ordner). Falls die Datei
    nicht existiert, fragt dieses Modul beim ersten Import interaktiv danach
    und speichert sie für künftige Starts.

Die Verbindungs-URL findest du in Supabase unter:
    Project Settings -> Database -> Connection string -> "URI"
    (Format: postgresql://postgres:[PASSWORT]@[HOST]:5432/postgres)

Grundidee der Struktur:
    Jeder Tracking-Lauf (ein Skript-Start bis zum Beenden) ist eine eigene
    "recording_session". Alle Messungen (activity_log, pose_data, etc.) aus
    diesem Lauf hängen an dieser Session -- so lassen sich einzelne
    Tracking-Läufe später sauber trennen und vergleichen, auch über
    mehrere Geräte/Freunde hinweg.
"""

import json
import os
import sys
import platform

try:
    import psycopg2
    from psycopg2.extras import Json
except ImportError:
    print("psycopg2 ist nicht installiert.")
    print("Installieren mit: pip install psycopg2-binary --break-system-packages")
    sys.exit(1)


OUTPUT_DIR = os.environ.get("ATUM_DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
os.makedirs(OUTPUT_DIR, exist_ok=True)
RESOURCE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_CONFIG_FILE = os.path.join(OUTPUT_DIR, "db_config.json")
PACKAGED_DB_CONFIG_FILE = os.path.join(RESOURCE_DIR, "db_config.json")

# Global flag: ist die Datenbank verfügbar?
# Standardmäßig direkt mit Supabase verbunden, damit Daten sofort in die Cloud geschrieben werden.
# Nur ein explizites ATUM_USE_SUPABASE=0 oder false deaktiviert die Remote-DB.
DB_AVAILABLE = False
_CONNECTION_ERROR = None
_ATUM_USE_SUPABASE = os.environ.get("ATUM_USE_SUPABASE")
if _ATUM_USE_SUPABASE is None:
    USE_SUPABASE = True
else:
    USE_SUPABASE = _ATUM_USE_SUPABASE.strip().lower() not in {"0", "false", "no", "off"}


def _load_or_ask_connection_string():
    config_path = DB_CONFIG_FILE
    if not os.path.exists(config_path) and os.path.exists(PACKAGED_DB_CONFIG_FILE):
        config_path = PACKAGED_DB_CONFIG_FILE
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)["connection_string"]
    return None


def _normalize_connection_string(conn_str):
    """Supabase braucht explizit SSL; einige Netzwerke blockieren IPv6/5432 ohne TLS."""
    if not conn_str:
        return conn_str
    if "sslmode=" in conn_str:
        return conn_str
    separator = "&" if "?" in conn_str else "?"
    return f"{conn_str}{separator}sslmode=require"


def _connect_with_retry(conn_str, retries=3, timeout=5):
    """Versucht mehrere Verbindungen hintereinander, um kurzzeitige Supabase-Disconnects zu überwinden."""
    normalized_conn_str = _normalize_connection_string(conn_str)
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            conn = psycopg2.connect(
                normalized_conn_str,
                connect_timeout=timeout,
                sslmode="require",
                application_name="workspace_tracking",
            )
            return conn
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                print(f"[DB] Verbindungsversuch {attempt}/{retries} fehlgeschlagen, retry...", file=sys.stderr)
                continue
    raise last_error


def _test_connection():
    """Testet die Datenbankverbindung nur, wenn Supabase explizit aktiviert wurde."""
    global DB_AVAILABLE, _CONNECTION_ERROR

    if not USE_SUPABASE:
        DB_AVAILABLE = False
        _CONNECTION_ERROR = "Supabase deaktiviert (ATUM_USE_SUPABASE=0)"
        print("[DB] Offline-Modus aktiv - Supabase nicht verbunden", file=sys.stderr)
        return False

    conn_str = _load_or_ask_connection_string()
    if not conn_str:
        print("[DB] Warnung: Keine db_config.json - arbeite im Offline-Modus")
        DB_AVAILABLE = False
        return False

    try:
        print("[DB] Versuche Verbindung zur Datenbank...", file=sys.stderr)
        conn = _connect_with_retry(conn_str, retries=3, timeout=5)
        conn.close()
        DB_AVAILABLE = True
        _CONNECTION_ERROR = None
        print("[DB] ✓ Datenbank erreichbar", file=sys.stderr)
        return True
    except Exception as e:
        DB_AVAILABLE = False
        _CONNECTION_ERROR = str(e)
        print(f"[DB] ⚠ Datenbank NICHT erreichbar - arbeite OFFLINE", file=sys.stderr)
        print(f"[DB]   Fehler: {str(e)[:140]}", file=sys.stderr)
        print(f"[DB]   Daten werden lokal in CSV-Dateien gespeichert", file=sys.stderr)
        return False


def get_connection():
    """Öffnet eine neue Datenbankverbindung.
    Bei kurzzeitigen Verbindungsabbrüchen versucht das Modul automatisch erneut zu verbinden.
    """
    global DB_AVAILABLE, _CONNECTION_ERROR

    conn_str = _load_or_ask_connection_string()
    if not conn_str or not USE_SUPABASE:
        DB_AVAILABLE = False
        _CONNECTION_ERROR = "Supabase deaktiviert oder keine Verbindung konfiguriert"
        return None

    try:
        conn = _connect_with_retry(conn_str, retries=3, timeout=5)
        DB_AVAILABLE = True
        _CONNECTION_ERROR = None
        return conn
    except Exception as e:
        _CONNECTION_ERROR = str(e)
        DB_AVAILABLE = False
        print(f"[DB] Verbindung verloren: {str(e)[:140]}", file=sys.stderr)
        return None


# Teste Verbindung beim Import
_test_connection()


# ===========================================================
# Nutzer
# ===========================================================

def get_or_create_user(name):
    """Gibt die user_id für den angegebenen Namen zurück, legt den Nutzer
    bei Bedarf an. Im Offline-Modus wird eine lokale ID verwendet."""
    
    # Offline-Modus: nutze einfach einen Hash des Namens als ID
    if not DB_AVAILABLE:
        import hashlib
        user_id = hashlib.md5(name.encode()).hexdigest()[:8]
        print(f"[DB] Offline-Modus: User '{name}' -> ID {user_id}", file=sys.stderr)
        return user_id

    conn = get_connection()
    if not conn:
        import hashlib
        return hashlib.md5(name.encode()).hexdigest()[:8]
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("select id from users where name = %s", (name,))
                row = cur.fetchone()
                if row:
                    return row[0]
                cur.execute("insert into users (name) values (%s) returning id", (name,))
                user_id = cur.fetchone()[0]
                conn.commit()
                return user_id
    except Exception as exc:
        print(f"[DB] Fehler bei user create: {exc}", file=sys.stderr)
        import hashlib
        return hashlib.md5(name.encode()).hexdigest()[:8]


def get_or_create_device_user(device_name, display_name=None):
    """Löst die stabile Benutzeridentität über den Rechnernamen auf.

    Ein Rechner erhält genau eine users-Zeile; der Anzeigename bleibt optional.
    Die Migration in db_schema.sql ergänzt device_name für bestehende Datenbanken.
    """
    display_name = display_name or device_name
    if not DB_AVAILABLE:
        import hashlib
        return hashlib.md5(device_name.encode()).hexdigest()[:8]

    conn = get_connection()
    if not conn:
        import hashlib
        return hashlib.md5(device_name.encode()).hexdigest()[:8]
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("select id from users where device_name = %s", (device_name,))
                row = cur.fetchone()
                if row:
                    return row[0]
                cur.execute(
                    "insert into users (name, device_name) values (%s, %s) returning id",
                    (display_name, device_name),
                )
                user_id = cur.fetchone()[0]
                conn.commit()
                return user_id
    except Exception as exc:
        print(f"[DB] Geräteidentität konnte nicht angelegt werden: {exc}", file=sys.stderr)
        import hashlib
        return hashlib.md5(device_name.encode()).hexdigest()[:8]


# ===========================================================
# Aufnahme-Sitzungen (ein Tracking-Lauf = eine recording_session)
# ===========================================================

def start_recording_session(user_id, device_name=None, notes=None):
    """Beim Start eines Tracking-Skripts aufrufen. Gibt die neue
    recording_session_id zurück, die dann bei allen folgenden Insert-Aufrufen
    mitgegeben wird. Im Offline-Modus wird eine lokale ID verwendet."""
    device_name = device_name or platform.node()
    
    # Offline-Modus: nutze UUID
    if not DB_AVAILABLE:
        import uuid
        session_id = str(uuid.uuid4())[:8]
        print(f"[DB] Offline-Modus: Session -> {session_id}", file=sys.stderr)
        return session_id
    
    conn = get_connection()
    if not conn:
        import uuid
        session_id = str(uuid.uuid4())[:8]
        return session_id
    
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    insert into recording_sessions (user_id, device_name, notes)
                    values (%s, %s, %s) returning id
                """, (user_id, device_name, notes))
                session_id = cur.fetchone()[0]
                conn.commit()
                return session_id
    except Exception as e:
        print(f"[DB] Fehler bei session create: {e}", file=sys.stderr)
        import uuid
        session_id = str(uuid.uuid4())[:8]
        return session_id


def ensure_table_exists(table_name, create_sql):
    """Creates a missing table on the fly so newer app code can still run against older Supabase schemas."""
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT to_regclass(%s)", (table_name,))
                exists = cur.fetchone()[0] is not None
                if not exists:
                    cur.execute(create_sql)
                    conn.commit()
                    print(f"[DB] Tabelle {table_name} wurde automatisch angelegt.", file=sys.stderr)
        return True
    except Exception as e:
        print(f"[DB] Fehler beim Prüfen/Anlegen von {table_name}: {e}", file=sys.stderr)
        return False


def insert_session_mode(user_id, recording_session_id, mode, started_at=None, ended_at=None, notes=None):
    """Speichert den gewählten Modus einer Sitzung in der Datenbank."""
    mode = (mode or "standard").strip().lower()
    if mode not in {"standard", "focus", "hyperfocus"}:
        mode = "standard"
    if not DB_AVAILABLE:
        return None
    ensure_table_exists(
        "session_modes",
        """
        create table if not exists session_modes (
            id bigserial primary key,
            user_id uuid references users(id) on delete cascade,
            recording_session_id uuid references recording_sessions(id) on delete cascade,
            mode text not null check (mode in ('standard', 'focus', 'hyperfocus')),
            started_at timestamptz not null default now(),
            ended_at timestamptz,
            notes text
        )
        """,
    )
    conn = get_connection()
    if not conn:
        return None
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    insert into session_modes (user_id, recording_session_id, mode, started_at, ended_at, notes)
                    values (%s, %s, %s, %s, %s, %s)
                """, (user_id, recording_session_id, mode, started_at or __import__("datetime").datetime.now(), ended_at, notes))
                conn.commit()
    except Exception as e:
        print(f"[DB] Fehler beim Speichern des Session-Modus: {e}", file=sys.stderr)
    return None


def end_recording_session(recording_session_id):
    """Beim Beenden des Tracking-Skripts (z.B. im Strg+C-Handler) aufrufen.
    Im Offline-Modus ist das ein No-Op."""
    if not DB_AVAILABLE:
        print(f"[DB] Offline-Modus: Session {recording_session_id} beendet", file=sys.stderr)
        return
    
    conn = get_connection()
    if not conn:
        return
    
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    update recording_sessions set ended_at = now()
                    where id = %s
                """, (recording_session_id,))
                conn.commit()
    except Exception as e:
        print(f"[DB] Fehler bei session end: {e}", file=sys.stderr)


# ===========================================================
# App-Katalog & pro-Nutzer Kategorisierung
# (ersetzt die alten losen JSON-Listen aus activity_config.json)
# ===========================================================

def get_or_create_application(wm_class, anzeige_name=None, vorgeschlagene_kategorie="Unbekannt"):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("select id from applications where wm_class = %s", (wm_class,))
            row = cur.fetchone()
            if row:
                return row[0]
            cur.execute("""
                insert into applications (wm_class, anzeige_name, vorgeschlagene_kategorie)
                values (%s, %s, %s) returning id
            """, (wm_class, anzeige_name or wm_class, vorgeschlagene_kategorie))
            app_id = cur.fetchone()[0]
            conn.commit()
            return app_id


def set_user_app_kategorie(user_id, wm_class, kategorie):
    """Legt fest, dass diese App für DIESEN Nutzer als 'Arbeit'/'Nicht-Arbeit' gilt."""
    application_id = get_or_create_application(wm_class)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                insert into user_app_kategorie (user_id, application_id, kategorie)
                values (%s, %s, %s)
                on conflict (user_id, application_id) do update
                set kategorie = excluded.kategorie
            """, (user_id, application_id, kategorie))
            conn.commit()


def load_user_app_kategorien(user_id):
    """Gibt {wm_class: kategorie} für alle bekannten Apps dieses Nutzers zurück."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                select a.wm_class, uak.kategorie
                from user_app_kategorie uak
                join applications a on a.id = uak.application_id
                where uak.user_id = %s
            """, (user_id,))
            return dict(cur.fetchall())


# ===========================================================
# Tasks
# ===========================================================

def start_task(user_id, recording_session_id, name):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                insert into tasks (user_id, recording_session_id, name, started_at, status)
                values (%s, %s, %s, now(), 'offen') returning id
            """, (user_id, recording_session_id, name))
            task_id = cur.fetchone()[0]
            conn.commit()
            return task_id


def finish_task(task_id, status="erledigt"):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                update tasks set ended_at = now(), status = %s where id = %s
            """, (status, task_id))
            conn.commit()


# ===========================================================
# Umgebungsdaten (Temperatur, Lärm, etc.)
# ===========================================================

def insert_environment_reading(user_id, recording_session_id, timestamp,
                                temperatur_celsius=None, laerm_dezibel=None,
                                luftfeuchtigkeit_prozent=None, helligkeit_lux=None,
                                sonstige=None):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                insert into environment_readings
                    (user_id, recording_session_id, timestamp, temperatur_celsius,
                     laerm_dezibel, luftfeuchtigkeit_prozent, helligkeit_lux, sonstige)
                values (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (user_id, recording_session_id, timestamp, temperatur_celsius,
                  laerm_dezibel, luftfeuchtigkeit_prozent, helligkeit_lux,
                  Json(sonstige) if sonstige is not None else None))
            conn.commit()


# ===========================================================
# Fokus-/Produktivitäts-Scores (für spätere Modell-Ausgaben)
# ===========================================================

def insert_focus_score(user_id, recording_session_id, zeitfenster_start, zeitfenster_ende,
                        fokus_score=None, produktivitaet_score=None, quelle="heuristik"):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                insert into focus_scores
                    (user_id, recording_session_id, zeitfenster_start, zeitfenster_ende,
                     fokus_score, produktivitaet_score, quelle)
                values (%s, %s, %s, %s, %s, %s, %s)
            """, (user_id, recording_session_id, zeitfenster_start, zeitfenster_ende,
                  fokus_score, produktivitaet_score, quelle))
            conn.commit()


# ===========================================================
# Rohdaten aus activity_tracker.py
# ===========================================================

def insert_activity_log(user_id, recording_session_id, row: dict):
    """row enthält dieselben Felder wie eine Zeile in activity_log.csv."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                insert into activity_log (
                    user_id, recording_session_id, timestamp, app_name, wm_class_instance,
                    fenster_titel, kategorie, pid, window_id, workspace, fenster_breite,
                    fenster_hoehe, fenster_x, fenster_y, maximiert, monitor, frame_type,
                    window_type, leerlauf_sekunden, status, wechsel_letzte_5min,
                    interaktionen_letzte_5min
                ) values (
                    %(user_id)s, %(recording_session_id)s, %(timestamp)s, %(app_name)s,
                    %(wm_class_instance)s, %(fenster_titel)s, %(kategorie)s, %(pid)s,
                    %(window_id)s, %(workspace)s, %(fenster_breite)s, %(fenster_hoehe)s,
                    %(fenster_x)s, %(fenster_y)s, %(maximiert)s, %(monitor)s, %(frame_type)s,
                    %(window_type)s, %(leerlauf_sekunden)s, %(status)s, %(wechsel_letzte_5min)s,
                    %(interaktionen_letzte_5min)s
                )
            """, {**row, "user_id": user_id, "recording_session_id": recording_session_id})
            conn.commit()


def insert_session(user_id, recording_session_id, app_name, kategorie,
                    start_zeit, end_zeit, dauer_sekunden):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                insert into activity_sessions
                    (user_id, recording_session_id, app_name, kategorie,
                     start_zeit, end_zeit, dauer_sekunden)
                values (%s, %s, %s, %s, %s, %s, %s)
            """, (user_id, recording_session_id, app_name, kategorie,
                  start_zeit, end_zeit, dauer_sekunden))
            conn.commit()


def insert_inactivity_period(user_id, recording_session_id, start_zeit, end_zeit,
                              dauer_sekunden, app_dabei, kategorie_dabei):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                insert into inactivity_periods
                    (user_id, recording_session_id, start_zeit, end_zeit,
                     dauer_sekunden, app_dabei, kategorie_dabei)
                values (%s, %s, %s, %s, %s, %s, %s)
            """, (user_id, recording_session_id, start_zeit, end_zeit,
                  dauer_sekunden, app_dabei, kategorie_dabei))
            conn.commit()


def insert_touch_event(user_id, recording_session_id, timestamp_ms, hand, body_part, event):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                insert into touch_events
                    (user_id, recording_session_id, t_ms, hand, body_part, event)
                values (%s, %s, %s, %s, %s, %s)
            """, (user_id, recording_session_id, timestamp_ms, hand, body_part, event))
            conn.commit()


def insert_object_detection(user_id, recording_session_id, timestamp_ms, object_index,
                             category_name, score, bbox_x, bbox_y, bbox_width, bbox_height,
                             horizontal_pos, relative_size, hand_nearby):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                insert into object_detections
                    (user_id, recording_session_id, t_ms, object_index, category_name,
                     score, bbox_x, bbox_y, bbox_width, bbox_height,
                     horizontal_pos, relative_size, hand_nearby)
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (user_id, recording_session_id, timestamp_ms, object_index, category_name,
                  score, bbox_x, bbox_y, bbox_width, bbox_height,
                  horizontal_pos, relative_size, hand_nearby))
            conn.commit()


def insert_pose_data(user_id, recording_session_id, timestamp_ms, landmarks):
    """landmarks: Liste von Dicts, z.B. [{'i':0,'x':..,'y':..,'z':..,'vis':..}, ...]"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                insert into pose_data (user_id, recording_session_id, t_ms, landmarks)
                values (%s, %s, %s, %s)
            """, (user_id, recording_session_id, timestamp_ms, Json(landmarks)))
            conn.commit()


def insert_face_data(user_id, recording_session_id, timestamp_ms, blendshapes):
    """blendshapes: Dict, z.B. {'mouthSmileLeft': 0.12, 'eyeBlinkLeft': 0.87, ...}"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                insert into face_data (user_id, recording_session_id, t_ms, blendshapes)
                values (%s, %s, %s, %s)
            """, (user_id, recording_session_id, timestamp_ms, Json(blendshapes)))
            conn.commit()


def insert_hand_data(user_id, recording_session_id, timestamp_ms, hand_index, handedness, landmarks):
    """landmarks: Liste von Dicts, z.B. [{'i':0,'x':..,'y':..,'z':..}, ...]"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                insert into hand_data
                    (user_id, recording_session_id, t_ms, hand_index, handedness, landmarks)
                values (%s, %s, %s, %s, %s, %s)
            """, (user_id, recording_session_id, timestamp_ms, hand_index, handedness, Json(landmarks)))
            conn.commit()


if __name__ == "__main__":
    # Kleiner Selbsttest: Verbindung aufbauen, Test-Nutzer + Test-Session anlegen
    print("Teste Datenbankverbindung...")
    test_user_id = get_or_create_user("verbindungstest")
    print(f"Nutzer OK, ID: {test_user_id}")
    test_session_id = start_recording_session(test_user_id, notes="Verbindungstest")
    print(f"Aufnahme-Sitzung angelegt, ID: {test_session_id}")
    end_recording_session(test_session_id)
    print("Erfolgreich verbunden, Sitzung wieder beendet.")
