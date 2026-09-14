"""
db_queries.py
=============
Lese-Abfragen (SELECT) für die Auswertungs-Oberfläche (tracking_gui.py).

db_client.py enthält bewusst nur Schreib-Funktionen (INSERT/UPDATE) für die
Tracking-Skripte. Hier kommen die Lese-Abfragen dazu, die das Dashboard
braucht -- als eigenes Modul, damit db_client.py unangetastet bleibt.

Hinweis zu Verbindungen:
    db_client.get_connection() liefert eine neue psycopg2-Verbindung.
    `with connection as conn:` committet zwar automatisch, schließt die
    Verbindung aber NICHT (das ist psycopg2-Verhalten, kein Bug hier).
    Ein Dashboard fragt potenziell oft und wiederholt ab, deshalb schließen
    alle Funktionen hier ihre Verbindung explizit in einem finally-Block.
"""

import datetime

import db_client


def _fetchall(sql, params=None):
    """Führt eine SELECT-Abfrage aus, gibt alle Zeilen zurück und schließt
    die Verbindung danach sauber wieder."""
    conn = db_client.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.fetchall()
    finally:
        conn.close()


def _fetchone(sql, params=None):
    conn = db_client.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.fetchone()
    finally:
        conn.close()


# ===========================================================
# Nutzer
# ===========================================================

def list_users():
    """Gibt [(id, name), ...] zurück, alphabetisch sortiert."""
    return _fetchall("select id, name from users order by name")


# ===========================================================
# Aufnahme-Sitzungen
# ===========================================================

def list_sessions(user_id, limit=100):
    """Gibt die letzten Aufnahme-Sitzungen eines Nutzers zurück, neueste
    zuerst. Jede Zeile: (id, device_name, started_at, ended_at,
    dauer_sekunden, notes)."""
    return _fetchall("""
        select id, device_name, started_at, ended_at,
               extract(epoch from (coalesce(ended_at, now()) - started_at)) as dauer_sekunden,
               notes
        from recording_sessions
        where user_id = %s
        order by started_at desc
        limit %s
    """, (user_id, limit))


def get_running_session(user_id):
    """Gibt die aktuell laufende Sitzung eines Nutzers zurück (ended_at ist
    noch nicht gesetzt), oder None. Nützlich, falls die GUI neu gestartet
    wird, während track_all.py noch im Terminal läuft."""
    return _fetchone("""
        select id, device_name, started_at
        from recording_sessions
        where user_id = %s and ended_at is null
        order by started_at desc
        limit 1
    """, (user_id,))


def get_session_overview(session_id):
    """Kennzahlen einer einzelnen Sitzung: Gesamtdauer, Leerlauf, Aktiv-Zeit,
    Anzahl App-Wechsel. Gibt ein dict zurück."""
    total_row = _fetchone("""
        select extract(epoch from (coalesce(ended_at, now()) - started_at))
        from recording_sessions where id = %s
    """, (session_id,))
    dauer_gesamt = float(total_row[0]) if total_row and total_row[0] is not None else 0.0

    idle_row = _fetchone("""
        select coalesce(sum(dauer_sekunden), 0)
        from inactivity_periods where recording_session_id = %s
    """, (session_id,))
    dauer_leerlauf = float(idle_row[0]) if idle_row else 0.0

    wechsel_row = _fetchone("""
        select count(*) from activity_sessions where recording_session_id = %s
    """, (session_id,))
    anzahl_wechsel = wechsel_row[0] if wechsel_row else 0

    dauer_aktiv = max(dauer_gesamt - dauer_leerlauf, 0.0)

    return {
        "dauer_gesamt": dauer_gesamt,
        "dauer_leerlauf": dauer_leerlauf,
        "dauer_aktiv": dauer_aktiv,
        "anzahl_wechsel": anzahl_wechsel,
    }


def get_kategorie_breakdown(session_id):
    """[(kategorie, dauer_sekunden), ...] -- Basis für das Arbeit/Nicht-
    Arbeit-Kreisdiagramm."""
    return _fetchall("""
        select coalesce(kategorie, 'Unbekannt') as kategorie, sum(dauer_sekunden) as dauer
        from activity_sessions
        where recording_session_id = %s
        group by kategorie
        order by dauer desc
    """, (session_id,))


def get_top_apps(session_id, limit=8):
    """[(app_name, kategorie, dauer_sekunden), ...] -- meistgenutzte Apps
    nach Gesamtzeit in dieser Sitzung."""
    return _fetchall("""
        select app_name, coalesce(kategorie, 'Unbekannt') as kategorie, sum(dauer_sekunden) as dauer
        from activity_sessions
        where recording_session_id = %s
        group by app_name, kategorie
        order by dauer desc
        limit %s
    """, (session_id, limit))


def get_timeline(session_id):
    """[(app_name, kategorie, start_zeit, end_zeit), ...] in zeitlicher
    Reihenfolge -- Basis für das Zeitstrahl-/Gantt-Diagramm."""
    return _fetchall("""
        select app_name, coalesce(kategorie, 'Unbekannt') as kategorie, start_zeit, end_zeit
        from activity_sessions
        where recording_session_id = %s
        order by start_zeit asc
    """, (session_id,))


def get_touch_summary(session_id):
    """[(hand, body_part, anzahl, erste_ms, letzte_ms), ...]. Gezählt werden
    nur 'start'-Events, damit jede Berührung genau einmal zählt (ein
    'start' + ein 'end' pro Berührung)."""
    return _fetchall("""
        select hand, body_part, count(*) as anzahl,
               min(t_ms) as erste_ms, max(t_ms) as letzte_ms
        from touch_events
        where recording_session_id = %s and event = 'start'
        group by hand, body_part
        order by anzahl desc
    """, (session_id,))


def get_object_summary(session_id, limit=8):
    """[(category_name, anzahl_frames), ...]. Jede Zeile in
    object_detections ist eine Erkennung pro Frame (~33ms), die Anzahl ist
    also ein grober Proxy für 'wie lange sichtbar', nicht die Anzahl
    einzelner Objekte."""
    return _fetchall("""
        select category_name, count(*) as anzahl_frames
        from object_detections
        where recording_session_id = %s
        group by category_name
        order by anzahl_frames desc
        limit %s
    """, (session_id, limit))


def format_dauer(sekunden):
    """Formatiert Sekunden als 'Xh Ym' bzw. 'Ym Zs' für kurze Dauern."""
    if sekunden is None:
        return "–"
    sekunden = int(round(sekunden))
    stunden, rest = divmod(sekunden, 3600)
    minuten, sek = divmod(rest, 60)
    if stunden > 0:
        return f"{stunden}h {minuten:02d}m"
    if minuten > 0:
        return f"{minuten}m {sek:02d}s"
    return f"{sek}s"
