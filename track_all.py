"""
track_all.py
============
Kombiniertes Tracking: startet Kamera-Erkennung (Pose/Face/Hand/Object) UND
Aktivitäts-Tracking (aktive App/Fenster) als EINEN Prozess, unter EINER
gemeinsamen recording_session in der Datenbank. Ein Start, ein Stop.

Schreibt weiterhin alle bekannten CSV-Dateien (wie bisher, als Backup/
Offline-Kopie) UND zusätzlich in die Supabase/Postgres-Datenbank.

Wichtig zur Performance:
    Kamera-Daten fallen mit ~30 Bildern/Sekunde an. Statt bei jeder
    einzelnen Zeile eine neue Datenbankverbindung zu öffnen (das würde die
    Verbindungsgrenze von Supabase sprengen), sammelt dieses Skript Zeilen
    kurz im Speicher und schreibt sie alle paar Sekunden gebündelt weg
    (siehe Klasse DBWriter unten, Standard: alle 2 Sekunden).

Start:
    python3 track_all.py --user Danic
    python3 track_all.py --user Freund1 --camera 2 --rotate 90

Beenden:
    'q' im Kamera-Fenster drücken, ODER Strg+C im Terminal.
    Beides beendet sauber: letzte Sitzung/Inaktivitätsperiode wird
    geschrieben, verbleibende gepufferte DB-Zeilen werden geflusht,
    recording_session wird als beendet markiert.

Voraussetzung:
    - db_client.py und db_config.json im selben Ordner (siehe SETUP.md)
    - GNOME-Erweiterung "Window Calls" für die Aktivitäts-Erkennung
      (https://extensions.gnome.org/extension/4724/window-calls/)
"""

import csv
import json
import os
import sys
import time
import argparse
import threading
import datetime
import platform
from collections import defaultdict

import cv2

try:
    import mediapipe as mp
    if not hasattr(mp, "solutions"):
        raise AttributeError("MediaPipe solution API not available")
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision
except Exception as exc:
    print("[Setup] Inkompatible MediaPipe-Installation erkannt.")
    print("[Setup] Dieses Projekt benötigt die MediaPipe-Lösung-API (mp.solutions).")
    print("[Setup] Bitte ausführen: . myenv/bin/activate && python -m pip install --upgrade 'mediapipe==0.10.14'")
    raise SystemExit(1) from exc

from psycopg2.extras import Json, execute_values

import db_client
import activity_tracker as at  # wiederverwendete Hilfsfunktionen (D-Bus, Klassifizierung, Konfiguration)
from session_mode_logic import evaluate_session_mode


RESOURCE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.environ.get("ATUM_DATA_DIR", RESOURCE_DIR)
os.makedirs(OUTPUT_DIR, exist_ok=True)
PREVIEW_IMAGE_PATH = os.path.join(OUTPUT_DIR, "camera_preview.png")
VIDEO_OUTPUT_DIR = os.path.join(OUTPUT_DIR, "recorded_videos")
DEFAULT_CAMERA_INDEX = 1 if platform.system() == "Linux" else 0


# ===========================================================
# TEIL 0: Gebündelter Datenbank-Schreiber (DBWriter)
# ===========================================================

# Spaltenreihenfolge pro Tabelle -- muss zur Reihenfolge der Werte passen,
# die camera_worker/activity_worker beim Aufruf von db_writer.add(...) übergeben.
TABLE_COLUMNS = {
    "pose_data": (
        "user_id", "recording_session_id", "t_ms", "landmarks",
    ),
    "face_data": (
        "user_id", "recording_session_id", "t_ms", "blendshapes",
    ),
    "hand_data": (
        "user_id", "recording_session_id", "t_ms",
        "hand_index", "handedness", "landmarks",
    ),
    "object_detections": (
        "user_id", "recording_session_id", "t_ms", "object_index",
        "category_name", "score", "bbox_x", "bbox_y", "bbox_width",
        "bbox_height", "horizontal_pos", "relative_size", "hand_nearby",
    ),
    "touch_events": (
        "user_id", "recording_session_id", "t_ms",
        "hand", "body_part", "event",
    ),
    "activity_log": (
        "user_id", "recording_session_id", "t_ms", "timestamp", "app_name",
        "wm_class_instance", "fenster_titel", "kategorie", "pid",
        "window_id", "workspace", "fenster_breite", "fenster_hoehe",
        "fenster_x", "fenster_y", "maximiert", "monitor", "frame_type",
        "window_type", "leerlauf_sekunden", "status",
        "wechsel_letzte_5min", "interaktionen_letzte_5min",
    ),
}


class DBWriter:
    """Sammelt Zeilen für mehrere Tabellen und schreibt sie alle
    `flush_interval` Sekunden gebündelt in einem Rutsch in die Datenbank.
    Bei Verbindungsproblemen wird eine Warnung ausgegeben, aber das
    Tracking (inkl. CSV-Schreiben) läuft trotzdem ungestört weiter --
    die Datenbank ist ein "Zusatz", kein kritischer Pfad."""

    def __init__(self, flush_interval=2.0):
        self.flush_interval = flush_interval
        self.buffers = {table: [] for table in TABLE_COLUMNS}
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.conn = None
        self._warned = False
        self._connect()
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def _connect(self):
        try:
            self.conn = db_client.get_connection()
            self._warned = False
        except Exception as e:
            self.conn = None
            if not self._warned:
                print(f"[DB] Keine Verbindung ({e}). Tracking läuft weiter, "
                      f"nur CSV wird geschrieben, bis die Verbindung wieder klappt.")
                self._warned = True

    def add(self, table, row):
        """row: Tuple in der Reihenfolge von TABLE_COLUMNS[table] (ohne id)."""
        with self.lock:
            self.buffers[table].append(row)

    def _loop(self):
        while not self.stop_event.wait(self.flush_interval):
            self.flush()

    def flush(self):
        with self.lock:
            pending = {t: rows for t, rows in self.buffers.items() if rows}
            for t in pending:
                self.buffers[t] = []

        if not pending:
            return

        if self.conn is None:
            self._connect()
        if self.conn is None:
            return  # weiterhin keine Verbindung -- Daten sind verloren, CSV hat sie aber

        try:
            with self.conn.cursor() as cur:
                for table, rows in pending.items():
                    cols = TABLE_COLUMNS[table]
                    sql = f"insert into {table} ({', '.join(cols)}) values %s"
                    execute_values(cur, sql, rows)
            self.conn.commit()
        except Exception as e:
            print(f"[DB] Schreibfehler beim Bündel-Insert ({e}). "
                  f"Verbindung wird neu aufgebaut, Daten dieses Batches gehen verloren "
                  f"(stehen aber weiter in den CSV-Dateien).")
            try:
                self.conn.rollback()
                self.conn.close()
            except Exception:
                pass
            self.conn = None

    def stop(self):
        self.stop_event.set()
        self.thread.join(timeout=10)
        self.flush()
        if self.conn is not None:
            try:
                self.conn.close()
            except Exception:
                pass


def _none_if_empty(value):
    """GNOME/Window-Calls liefert manche Felder gelegentlich als leeren
    String statt Zahl/None -- für DB-Spalten vom Typ integer/boolean muss
    daraus None werden (CSV verträgt '', Postgres nicht)."""
    return None if value == "" else value


# ===========================================================
# TEIL 1: Kamera-Worker (Pose + Face + Hand + Object + Touch)
#          -- läuft im HAUPT-Thread (OpenCV-Fenster brauchen das)
# ===========================================================

def open_camera(index=None):
    if index is None:
        index = DEFAULT_CAMERA_INDEX
    system = platform.system()
    if system == "Windows":
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    elif system == "Darwin":
        cap = cv2.VideoCapture(index, cv2.CAP_AVFOUNDATION)
    else:
        cap = cv2.VideoCapture(index, cv2.CAP_V4L2)
    if not cap.isOpened():
        cap = cv2.VideoCapture(index)
    return cap


def list_available_cameras(max_index=5):
    """Gibt alle verfügbaren Kameraindizes zurück, die tatsächlich Frames liefern."""
    available = []
    for i in range(max_index):
        cap = open_camera(i)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret and frame is not None:
                available.append(i)
            cap.release()
    return available


def is_hand_near_object(hand_points, bbox, margin=20):
    x1 = bbox.origin_x - margin
    y1 = bbox.origin_y - margin
    x2 = bbox.origin_x + bbox.width + margin
    y2 = bbox.origin_y + bbox.height + margin
    for (hx, hy) in hand_points:
        if x1 <= hx <= x2 and y1 <= hy <= y2:
            return True
    return False


def hand_touches_bodypart(hand_points, body_point, threshold=70):
    bx, by = body_point
    for (hx, hy) in hand_points:
        distance = ((hx - bx) ** 2 + (hy - by) ** 2) ** 0.5
        if distance < threshold:
            return True
    return False


HEAD_REGIONS = {
    "Stirn": 10, "Nase": 4, "Mund": 13, "Kinn": 152,
    "Auge_Links": 33, "Auge_Rechts": 263,
    "Wange_Links": 234, "Wange_Rechts": 454,
    "Ohr_Links": 127, "Ohr_Rechts": 356,
}

WORKPLACE_OBJECTS = [
    "laptop", "keyboard", "mouse", "tv", "cell phone",
    "book", "cup", "chair", "remote",
]


def camera_worker(user_id, session_id, db_writer, stop_event, args, results, runtime_state):
    """Läuft im Hauptthread. Füllt `results` (dict) am Ende mit den
    Touch-Zusammenfassungsdaten, damit main() sie nach dem Join ausgeben kann."""

    try:
        if os.path.exists(PREVIEW_IMAGE_PATH):
            os.remove(PREVIEW_IMAGE_PATH)
    except OSError:
        pass

    pose_options = vision.PoseLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path=os.path.join(RESOURCE_DIR, "pose_landmarker_lite.task")),
        running_mode=vision.RunningMode.VIDEO,
    )
    pose_detector = vision.PoseLandmarker.create_from_options(pose_options)

    face_options = vision.FaceLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path=os.path.join(RESOURCE_DIR, "face_landmarker.task")),
        running_mode=vision.RunningMode.VIDEO,
        output_face_blendshapes=True,
    )
    face_detector = vision.FaceLandmarker.create_from_options(face_options)

    hand_options = vision.HandLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path=os.path.join(RESOURCE_DIR, "hand_landmarker.task")),
        running_mode=vision.RunningMode.VIDEO,
        num_hands=2,
    )
    hand_detector = vision.HandLandmarker.create_from_options(hand_options)

    object_options = vision.ObjectDetectorOptions(
        base_options=python.BaseOptions(model_asset_path=os.path.join(RESOURCE_DIR, "efficientdet.tflite")),
        running_mode=vision.RunningMode.VIDEO,
        score_threshold=0.3,
        max_results=5,
        category_allowlist=WORKPLACE_OBJECTS,
    )
    object_detector = vision.ObjectDetector.create_from_options(object_options)

    mp_pose_connections = mp.solutions.pose.POSE_CONNECTIONS
    mp_face_connections = mp.solutions.face_mesh_connections.FACEMESH_TESSELATION
    mp_hand_connections = mp.solutions.hands.HAND_CONNECTIONS

    pose_csv = open(os.path.join(OUTPUT_DIR, "pose_data.csv"), mode="w", newline="")
    pose_writer = csv.writer(pose_csv)
    pose_header = ["timestamp"]
    for i in range(33):
        pose_header += [f"x{i}", f"y{i}", f"z{i}", f"vis{i}"]
    pose_writer.writerow(pose_header)

    face_csv = open(os.path.join(OUTPUT_DIR, "face_data.csv"), mode="w", newline="")
    face_writer = csv.writer(face_csv)
    face_header = ["timestamp"]
    face_header_written = False

    hand_csv = open(os.path.join(OUTPUT_DIR, "hand_data.csv"), mode="w", newline="")
    hand_writer = csv.writer(hand_csv)
    hand_header = ["timestamp", "hand_index", "handedness"]
    for i in range(21):
        hand_header += [f"x{i}", f"y{i}", f"z{i}"]
    hand_writer.writerow(hand_header)

    object_csv = open(os.path.join(OUTPUT_DIR, "object_data.csv"), mode="w", newline="")
    object_writer = csv.writer(object_csv)
    object_writer.writerow([
        "timestamp", "object_index", "category_name", "score",
        "bbox_x", "bbox_y", "bbox_width", "bbox_height",
        "horizontal_pos", "relative_size", "hand_nearby",
    ])

    touch_csv = open(os.path.join(OUTPUT_DIR, "touch_events.csv"), mode="w", newline="")
    touch_writer = csv.writer(touch_csv)
    touch_writer.writerow(["timestamp", "hand", "body_part", "event"])

    touch_state = {}
    touch_counts = defaultdict(int)
    first_touch_time = {}
    last_touch_time = {}

    cap = open_camera(args.camera)
    print(f"Versuche Kamera-Index {args.camera} (/dev/video{args.camera})...")

    # Teste, ob wir ein echtes Frame bekommen
    ret, test_frame = cap.read()
    if not ret or test_frame is None:
        print(f"  ⚠️  Kamera {args.camera} funktioniert nicht oder liefert keine Frames.")
        cap.release()
        
        print("  → Suche nach verfügbaren Kameras...")
        available = list_available_cameras(max_index=10)
        
        if not available:
            print("\n❌ FEHLER: Keine funktionierende Kamera gefunden!")
            print("\nMögliche Lösungen:")
            print("  1. Ist die Kamera angeschlossen?")
            print("  2. Ist sie von anderem Programm belegt (Chrome, OBS, Zoom)?")
            print("  3. Auf Linux: ls -la /dev/video*")
            print("  4. Auf macOS: Systemeinstellungen -> Datenschutz")
            print("\nDiagnose: python diagnose_camera.py")
            stop_event.set()
            return
        
        print(f"  ✓ Verfügbare Kameras: {available}")
        new_camera_index = available[0]
        print(f"  → Nutze Kamera {new_camera_index}")
        args.camera = new_camera_index
        cap = open_camera(args.camera)
    else:
        cap.release()
        cap = open_camera(args.camera)
    
    print(f"Verwende Kamera-Index {args.camera} (/dev/video{args.camera})")
    
    if not cap.isOpened():
        print("❌ Fehler: Kamera konnte nicht geöffnet werden.")
        stop_event.set()
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FPS, 30)
    os.makedirs(VIDEO_OUTPUT_DIR, exist_ok=True)
    final_video_path = os.path.join(VIDEO_OUTPUT_DIR, f"{session_id}.mp4")
    video_path = final_video_path + ".part.mp4"
    video_writer = None

    frame_timestamp = 0
    preview_every_ms = 200
    last_preview_timestamp = -preview_every_ms

    def write_preview(frame):
        try:
            preview = cv2.resize(
                frame,
                (640, max(1, int(frame.shape[0] * (640 / max(frame.shape[1], 1))))),
            )
            ok, buffer = cv2.imencode(".png", preview)
            if ok:
                tmp_path = PREVIEW_IMAGE_PATH + ".tmp"
                with open(tmp_path, "wb") as preview_file:
                    preview_file.write(buffer.tobytes())
                os.replace(tmp_path, PREVIEW_IMAGE_PATH)
                return True
        except Exception as exc:
            print(f"[Preview] Konnte Kamerabild nicht schreiben: {exc}")
        return False

    try:
        while cap.isOpened() and not stop_event.is_set():
            ret, frame = cap.read()
            if not ret:
                break

            if args.rotate == 90:
                frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
            elif args.rotate == 180:
                frame = cv2.rotate(frame, cv2.ROTATE_180)
            elif args.rotate == 270:
                frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

            # Sofort ein Kamerabild zeigen, auch während MediaPipe noch rechnet.
            if frame_timestamp == 0:
                write_preview(frame)

            if video_writer is None:
                height, width = frame.shape[:2]
                video_writer = cv2.VideoWriter(
                    video_path,
                    cv2.VideoWriter_fourcc(*"mp4v"),
                    30.0,
                    (width, height),
                )
                if not video_writer.isOpened():
                    print(f"[Video] Konnte {video_path} nicht öffnen.")
                    video_writer = None

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

            pose_result = pose_detector.detect_for_video(mp_image, frame_timestamp)
            face_result = face_detector.detect_for_video(mp_image, frame_timestamp)
            hand_result = hand_detector.detect_for_video(mp_image, frame_timestamp)
            object_result = object_detector.detect_for_video(mp_image, frame_timestamp)

            # --- Körper ---
            pose_points = None
            if pose_result.pose_landmarks:
                landmarks = pose_result.pose_landmarks[0]
                points = []
                for lm in landmarks:
                    x = int(lm.x * frame.shape[1])
                    y = int(lm.y * frame.shape[0])
                    points.append((x, y))
                pose_points = points

                for connection in mp_pose_connections:
                    start_idx, end_idx = connection
                    cv2.line(frame, points[start_idx], points[end_idx], (0, 255, 0), 2)
                for (x, y) in points:
                    cv2.circle(frame, (x, y), 3, (0, 255, 0), -1)

                row = [frame_timestamp]
                landmark_dicts = []
                for i, lm in enumerate(landmarks):
                    row += [lm.x, lm.y, lm.z, lm.visibility]
                    landmark_dicts.append({"i": i, "x": lm.x, "y": lm.y, "z": lm.z, "vis": lm.visibility})
                pose_writer.writerow(row)
                db_writer.add("pose_data", (user_id, session_id, frame_timestamp, Json(landmark_dicts)))

            # --- Gesicht ---
            face_points = None
            if face_result.face_landmarks:
                landmarks = face_result.face_landmarks[0]
                points = []
                for lm in landmarks:
                    x = int(lm.x * frame.shape[1])
                    y = int(lm.y * frame.shape[0])
                    points.append((x, y))
                face_points = points

                for connection in mp_face_connections:
                    start_idx, end_idx = connection
                    cv2.line(frame, points[start_idx], points[end_idx], (255, 255, 0), 1)
                for (x, y) in points:
                    cv2.circle(frame, (x, y), 1, (255, 0, 0), -1)

                if face_result.face_blendshapes:
                    blendshapes = face_result.face_blendshapes[0]

                    if not face_header_written:
                        for b in blendshapes:
                            face_header.append(b.category_name)
                        face_writer.writerow(face_header)
                        face_header_written = True

                    row = [frame_timestamp]
                    blendshape_dict = {}
                    for b in blendshapes:
                        row.append(b.score)
                        blendshape_dict[b.category_name] = b.score
                    face_writer.writerow(row)
                    db_writer.add("face_data", (user_id, session_id, frame_timestamp, Json(blendshape_dict)))

            # --- Hände ---
            all_hand_points = []
            if hand_result.hand_landmarks:
                for hand_idx, landmarks in enumerate(hand_result.hand_landmarks):
                    handedness = hand_result.handedness[hand_idx][0].category_name

                    points = []
                    for lm in landmarks:
                        x = int(lm.x * frame.shape[1])
                        y = int(lm.y * frame.shape[0])
                        points.append((x, y))
                    all_hand_points.extend(points)

                    for connection in mp_hand_connections:
                        start_idx, end_idx = connection
                        cv2.line(frame, points[start_idx], points[end_idx], (0, 0, 255), 2)
                    for (x, y) in points:
                        cv2.circle(frame, (x, y), 3, (0, 0, 255), -1)

                    wrist_x, wrist_y = points[0]
                    cv2.putText(frame, handedness, (wrist_x, wrist_y - 20),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

                    row = [frame_timestamp, hand_idx, handedness]
                    landmark_dicts = []
                    for i, lm in enumerate(landmarks):
                        row += [lm.x, lm.y, lm.z]
                        landmark_dicts.append({"i": i, "x": lm.x, "y": lm.y, "z": lm.z})
                    hand_writer.writerow(row)
                    db_writer.add("hand_data", (user_id, session_id, frame_timestamp,
                                                 hand_idx, handedness, Json(landmark_dicts)))

                    # --- Hand-Körper-Berührung ---
                    body_parts = {}
                    if face_points is not None:
                        for region_name, landmark_idx in HEAD_REGIONS.items():
                            body_parts[region_name] = (face_points[landmark_idx], 40)
                    elif pose_points is not None:
                        body_parts["Kopf"] = (pose_points[0], 70)

                    if pose_points is not None:
                        body_parts["Brust"] = (
                            ((pose_points[11][0] + pose_points[12][0]) // 2,
                             (pose_points[11][1] + pose_points[12][1]) // 2), 70)
                        body_parts["Bauch"] = (
                            ((pose_points[23][0] + pose_points[24][0]) // 2,
                             (pose_points[23][1] + pose_points[24][1]) // 2), 70)

                    for part_name, (body_point, threshold) in body_parts.items():
                        key = f"{handedness}_{part_name}"
                        touching = hand_touches_bodypart(points, body_point, threshold=threshold)
                        was_touching = touch_state.get(key, False)

                        if touching and not was_touching:
                            touch_counts[key] += 1
                            if key not in first_touch_time:
                                first_touch_time[key] = frame_timestamp
                            last_touch_time[key] = frame_timestamp
                            touch_writer.writerow([frame_timestamp, handedness, part_name, "start"])
                            db_writer.add("touch_events", (user_id, session_id, frame_timestamp,
                                                            handedness, part_name, "start"))
                        elif not touching and was_touching:
                            touch_writer.writerow([frame_timestamp, handedness, part_name, "end"])
                            db_writer.add("touch_events", (user_id, session_id, frame_timestamp,
                                                            handedness, part_name, "end"))

                        touch_state[key] = touching

            # --- Objekte ---
            if object_result.detections:
                frame_width = frame.shape[1]
                frame_height = frame.shape[0]

                for obj_idx, detection in enumerate(object_result.detections):
                    bbox = detection.bounding_box
                    category = detection.categories[0]
                    x, y, w, h = bbox.origin_x, bbox.origin_y, bbox.width, bbox.height

                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 255), 2)
                    label = f"{category.category_name} ({category.score:.2f})"
                    cv2.putText(frame, label, (x, y - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

                    center_x = x + w / 2
                    if center_x < frame_width / 3:
                        horizontal_pos = "links"
                    elif center_x < 2 * frame_width / 3:
                        horizontal_pos = "mitte"
                    else:
                        horizontal_pos = "rechts"

                    relative_size = (w * h) / (frame_width * frame_height)
                    hand_nearby = is_hand_near_object(all_hand_points, bbox)
                    if hand_nearby:
                        cv2.putText(frame, "in Benutzung", (x, y + h + 20),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)

                    category_name = category.category_name.lower()
                    if "cell phone" in category_name or "phone" in category_name:
                        runtime_state["phone_detected"] = True
                    row = [frame_timestamp, obj_idx, category.category_name, category.score,
                           x, y, w, h, horizontal_pos, relative_size, hand_nearby]
                    object_writer.writerow(row)
                    db_writer.add("object_detections", (
                        user_id, session_id, frame_timestamp, obj_idx, category.category_name,
                        float(category.score), x, y, w, h, horizontal_pos, relative_size, bool(hand_nearby),
                    ))

            if video_writer is not None:
                video_writer.write(frame)

            if frame_timestamp - last_preview_timestamp >= preview_every_ms:
                if write_preview(frame):
                    last_preview_timestamp = frame_timestamp

            frame_timestamp += 33

            if args.preview_window:
                cv2.imshow("Pose + Face + Hand + Object Detection", frame)
                if cv2.waitKey(5) & 0xFF == ord("q"):
                    break
    finally:
        cap.release()
        if video_writer is not None:
            video_writer.release()
        if os.path.exists(video_path) and os.path.getsize(video_path) > 0:
            try:
                os.replace(video_path, final_video_path)
            except OSError as exc:
                print(f"[Video] Konnte Aufnahme nicht abschließen: {exc}")
        if args.preview_window:
            cv2.destroyAllWindows()
        pose_csv.close()
        face_csv.close()
        hand_csv.close()
        object_csv.close()
        touch_csv.close()
        # signalisiert dem Aktivitäts-Thread, dass Schluss ist (falls Kamera zuerst endet)
        stop_event.set()

        total_minutes = frame_timestamp / 1000 / 60 if frame_timestamp > 0 else 0
        metadata_path = os.path.splitext(final_video_path)[0] + ".json"
        try:
            with open(metadata_path, "w", encoding="utf-8") as metadata_file:
                json.dump({
                    "video": os.path.basename(video_path),
                    "duration_seconds": round(frame_timestamp / 1000, 2),
                    "recorded_at": datetime.datetime.now().isoformat(timespec="seconds"),
                }, metadata_file, indent=2, ensure_ascii=False)
        except OSError as exc:
            print(f"[Video] Konnte Metadaten nicht speichern: {exc}")
        results["touch_counts"] = touch_counts
        results["first_touch_time"] = first_touch_time
        results["last_touch_time"] = last_touch_time
        results["total_minutes"] = total_minutes

        if touch_counts:
            with open(os.path.join(OUTPUT_DIR, "touch_summary.csv"), mode="w", newline="") as summary_csv:
                summary_writer = csv.writer(summary_csv)
                summary_writer.writerow(["hand_bodypart", "anzahl", "erste_beruehrung_ms",
                                          "letzte_beruehrung_ms", "pro_minute"])
                for key, count in touch_counts.items():
                    per_minute = count / total_minutes if total_minutes > 0 else 0
                    summary_writer.writerow([key, count, first_touch_time[key],
                                              last_touch_time[key], round(per_minute, 2)])


# ===========================================================
# TEIL 2: Aktivitäts-Worker (aktive App/Fenster)
#          -- läuft in einem Hintergrund-Thread
#          (nutzt Hilfsfunktionen aus activity_tracker.py wieder)
# ===========================================================

def activity_worker(user_id, session_id, db_writer, stop_event, args, session_clock, runtime_state):
    if not at.activity_tracking_available():
        print("[Aktivität] Fenster-/Idle-Tracking ist auf diesem System nicht verfügbar.")
        print("[Aktivität] Betriebssystem/Plattform wird als Nicht-Linux oder ohne GNOME-Integration erkannt.")
        print("[Aktivität] Aktivitäts-Tracking wird übersprungen, Kamera-Tracking läuft weiter.")
        return

    if at.get_active_window_info() is None:
        print("[Aktivität] Konnte kein aktives Fenster auslesen.")
        print("[Aktivität] Ist die GNOME-Erweiterung 'Window Calls' installiert und aktiviert?")
        print("[Aktivität] -> https://extensions.gnome.org/extension/4724/window-calls/")
        print("[Aktivität] Aktivitäts-Tracking wird übersprungen, Kamera-Tracking läuft weiter.")
        return

    work_apps, non_work_apps = at.load_or_create_config(
        reconfigure=args.configure,
        cli_work_apps=args.work_apps,
        cli_non_work_apps=args.non_work_apps,
    )
    at.ensure_csv_headers()

    print(f"[Aktivität] Gestartet. Prüfe alle {args.check_interval} Sekunden.")

    current_app = None
    current_category = None
    session_start = None
    focus_state = {"alert": False, "last_alert": None}

    from collections import deque
    wechsel_zeitpunkte = deque()
    interaktions_zeitpunkte = deque()
    vorheriger_leerlauf = None

    ist_inaktiv = False
    inaktiv_seit = None
    inaktiv_app = None
    inaktiv_kategorie = None

    while not stop_event.is_set():
        info = at.get_active_window_info()
        now = datetime.datetime.now()

        if info is not None:
            kategorie = at.classify(info["app_name"], info["fenster_titel"], work_apps, non_work_apps)
            leerlauf = at.get_idle_seconds()
            status = "Leerlauf" if (leerlauf is not None and leerlauf >= at.IDLE_THRESHOLD_SECONDS) else "Aktiv"

            if args.session_mode == "hyperfocus" and args.hyperfocus_app:
                at.enforce_hyperfocus_app(info["app_name"], args.hyperfocus_app)

            mode_eval = evaluate_session_mode(
                args.session_mode,
                kategorie,
                leerlauf,
                info["app_name"],
                allowed_app=args.hyperfocus_app,
                phone_detected=runtime_state.get("phone_detected", False),
            )
            if mode_eval["alert"]:
                if focus_state["last_alert"] is None or (now - focus_state["last_alert"]).total_seconds() >= 20:
                    print(f"[Fokus] {args.session_mode}: {mode_eval['reason']} | {mode_eval['recommendation']}")
                    focus_state["last_alert"] = now
                focus_state["alert"] = True
            else:
                focus_state["alert"] = False

            if (leerlauf is not None and vorheriger_leerlauf is not None
                    and leerlauf < vorheriger_leerlauf):
                interaktions_zeitpunkte.append(now)
            vorheriger_leerlauf = leerlauf

            grenze = now - datetime.timedelta(seconds=at.FREQUENZ_FENSTER_SEKUNDEN)
            while wechsel_zeitpunkte and wechsel_zeitpunkte[0] < grenze:
                wechsel_zeitpunkte.popleft()
            while interaktions_zeitpunkte and interaktions_zeitpunkte[0] < grenze:
                interaktions_zeitpunkte.popleft()

            row = [
                now.strftime("%Y-%m-%d %H:%M:%S"),
                info["app_name"], info["wm_class_instance"], info["fenster_titel"],
                kategorie, info["pid"], info["window_id"], info["workspace"],
                info["fenster_breite"], info["fenster_hoehe"],
                info["fenster_x"], info["fenster_y"],
                info["maximiert"], info["monitor"],
                info["frame_type"], info["window_type"],
                leerlauf, status,
                len(wechsel_zeitpunkte), len(interaktions_zeitpunkte),
            ]
            with open(at.LOG_FILE, "a", newline="") as f:
                csv.writer(f).writerow(row)

            db_writer.add("activity_log", (
                user_id, session_id, int((time.monotonic() - session_clock) * 1000), now,
                info["app_name"], info["wm_class_instance"], info["fenster_titel"], kategorie,
                _none_if_empty(info["pid"]), _none_if_empty(info["window_id"]), _none_if_empty(info["workspace"]),
                _none_if_empty(info["fenster_breite"]), _none_if_empty(info["fenster_hoehe"]),
                _none_if_empty(info["fenster_x"]), _none_if_empty(info["fenster_y"]),
                _none_if_empty(info["maximiert"]), _none_if_empty(info["monitor"]),
                _none_if_empty(info["frame_type"]), _none_if_empty(info["window_type"]),
                leerlauf, status, len(wechsel_zeitpunkte), len(interaktions_zeitpunkte),
            ))

            if info["app_name"] != current_app:
                if current_app is not None:
                    at.write_session(current_app, current_category, session_start, now)
                    try:
                        db_client.insert_session(user_id, session_id, current_app, current_category,
                                                  session_start, now,
                                                  round((now - session_start).total_seconds(), 1))
                    except Exception as e:
                        print(f"[DB] Konnte Sitzungswechsel nicht schreiben ({e}), steht aber in CSV.")
                    wechsel_zeitpunkte.append(now)
                current_app = info["app_name"]
                current_category = kategorie
                session_start = now

            if status == "Leerlauf" and not ist_inaktiv:
                ist_inaktiv = True
                inaktiv_seit = now - datetime.timedelta(seconds=leerlauf)
                inaktiv_app = info["app_name"]
                inaktiv_kategorie = kategorie
            elif status == "Aktiv" and ist_inaktiv:
                at.write_inactivity_period(inaktiv_seit, now, inaktiv_app, inaktiv_kategorie)
                try:
                    db_client.insert_inactivity_period(
                        user_id, session_id, inaktiv_seit, now,
                        round((now - inaktiv_seit).total_seconds(), 1),
                        inaktiv_app, inaktiv_kategorie)
                except Exception as e:
                    print(f"[DB] Konnte Inaktivitätsperiode nicht schreiben ({e}), steht aber in CSV.")
                ist_inaktiv = False

        stop_event.wait(args.check_interval)

    # sauberer Abschluss beim Beenden
    jetzt = datetime.datetime.now()
    if current_app is not None:
        at.write_session(current_app, current_category, session_start, jetzt)
        try:
            db_client.insert_session(user_id, session_id, current_app, current_category,
                                      session_start, jetzt,
                                      round((jetzt - session_start).total_seconds(), 1))
        except Exception as e:
            print(f"[DB] Konnte letzte Sitzung nicht schreiben ({e}), steht aber in CSV.")
    if ist_inaktiv:
        at.write_inactivity_period(inaktiv_seit, jetzt, inaktiv_app, inaktiv_kategorie)
        try:
            db_client.insert_inactivity_period(
                user_id, session_id, inaktiv_seit, jetzt,
                round((jetzt - inaktiv_seit).total_seconds(), 1),
                inaktiv_app, inaktiv_kategorie)
        except Exception as e:
            print(f"[DB] Konnte letzte Inaktivitätsperiode nicht schreiben ({e}), steht aber in CSV.")

    print("[Aktivität] Beendet. Letzte Sitzung/Inaktivitätsperiode gespeichert.")


# ===========================================================
# TEIL 3: main() -- startet beide Worker unter einer gemeinsamen Sitzung
# ===========================================================

def parse_args():
    parser = argparse.ArgumentParser(description="Kombiniertes Kamera- + Aktivitäts-Tracking")
    parser.add_argument("--user", type=str, required=True,
                         help="Name der Test-Person, z.B. --user Danic (wird in der DB angelegt, falls neu)")
    parser.add_argument("--camera", type=int, default=DEFAULT_CAMERA_INDEX,
                         help="Kamera-Index, z.B. 1 für die primäre Linux-Kamera, 2 für DroidCam")
    parser.add_argument("--rotate", type=int, default=0, choices=[0, 90, 180, 270],
                         help="Bild um X Grad drehen")
    parser.add_argument("--configure", action="store_true",
                         help="Fragt die Arbeit/Nicht-Arbeit-App-Listen neu ab")
    parser.add_argument("--work-apps", type=str, default=None,
                         help="Kommagetrennte Liste, z.B. 'code,firefox,libreoffice'")
    parser.add_argument("--non-work-apps", type=str, default=None,
                         help="Kommagetrennte Liste, z.B. 'spotify,steam'")
    parser.add_argument("--check-interval", type=float, default=3.0,
                         help="Wie oft die aktive App geprüft wird, in Sekunden (Standard: 3)")
    parser.add_argument("--db-flush-interval", type=float, default=2.0,
                         help="Wie oft gepufferte Daten in die DB geschrieben werden, in Sekunden (Standard: 2)")
    parser.add_argument("--device-name", type=str, default=None,
                         help="Name für dieses Gerät in der DB (Standard: Hostname)")
    parser.add_argument("--session-mode", type=str, default="standard",
                         choices=["standard", "focus", "hyperfocus"],
                         help="Aktiver Arbeitsmodus der Sitzung: standard, focus oder hyperfocus")
    parser.add_argument("--hyperfocus-app", type=str, default="",
                         help="Erlaubte Einzel-App im Hyperfocus-Modus, z.B. code, firefox oder chrome")
    parser.add_argument("--preview-window", action="store_true",
                         help="Zeigt zusätzlich ein eigenes OpenCV-Fenster an; standardmäßig deaktiviert, damit die App keine neue Kamera-Preview-Page öffnet.")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.session_mode == "standard":
        print("[Modus] Standard-Modus: Kamera und MediaPipe sind deaktiviert.")
        return

    print("Verbinde mit Datenbank...")
    device_name = args.device_name or platform.node()
    try:
        user_id = db_client.get_or_create_device_user(device_name, display_name=args.user)
    except Exception as e:
        print(f"Konnte keine Verbindung zur Datenbank herstellen: {e}")
        print("Prüfe db_config.json und deine Internetverbindung. Abbruch.")
        sys.exit(1)
    print(f"Nutzer: {args.user}  (ID: {user_id})")
    print(f"[Modus] Sitzung läuft im Modus: {args.session_mode}")

    session_clock = time.monotonic()
    session_id = db_client.start_recording_session(
        user_id, device_name=device_name,
        notes=f"track_all.py::{args.session_mode}")
    db_client.insert_session_mode(user_id, session_id, args.session_mode, notes=f"track_all.py::{args.session_mode}")
    print(f"Aufnahme-Sitzung gestartet: {session_id}")

    db_writer = DBWriter(flush_interval=args.db_flush_interval)
    stop_event = threading.Event()
    results = {}
    runtime_state = {"phone_detected": False}

    activity_thread = threading.Thread(
        target=activity_worker,
        args=(user_id, session_id, db_writer, stop_event, args, session_clock, runtime_state),
        daemon=True,
    )
    activity_thread.start()

    try:
        # Kamera-Loop läuft im Hauptthread (OpenCV-Fenster brauchen das)
        camera_worker(user_id, session_id, db_writer, stop_event, args, results, runtime_state)
    except KeyboardInterrupt:
        print("\nStrg+C erkannt, beende sauber...")
    finally:
        stop_event.set()
        activity_thread.join(timeout=15)
        db_writer.stop()
        try:
            db_client.end_recording_session(session_id)
        except Exception as e:
            print(f"[DB] Konnte Sitzung nicht als beendet markieren ({e}).")
        print(f"\nAufnahme-Sitzung beendet: {session_id}")

        touch_counts = results.get("touch_counts", {})
        total_minutes = results.get("total_minutes", 0)
        print("\n=== Zusammenfassung Hand-Körper-Berührungen ===")
        if not touch_counts:
            print("Keine Berührungen erkannt.")
        else:
            first_touch_time = results["first_touch_time"]
            last_touch_time = results["last_touch_time"]
            for key, count in touch_counts.items():
                per_minute = count / total_minutes if total_minutes > 0 else 0
                print(f"{key}: {count}x berührt "
                      f"(erste: {first_touch_time[key]} ms, letzte: {last_touch_time[key]} ms, "
                      f"~{per_minute:.1f}x pro Minute)")
            print(f"\nGesamtdauer: {total_minutes:.1f} Minuten")
        print("Details in touch_events.csv, Zusammenfassung in touch_summary.csv "
              "(zusätzlich alles in der Datenbank unter dieser Aufnahme-Sitzung).")


if __name__ == "__main__":
    main()
