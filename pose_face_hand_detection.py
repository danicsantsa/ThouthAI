import cv2                                  # OpenCV: liest Webcam-Bilder und zeigt Fenster an
import csv                                  # Zum Schreiben der Zahlen-Daten in Dateien
import platform                             # Um zu erkennen, auf welchem Betriebssystem wir laufen
import argparse                             # Um Kommandozeilen-Argumente wie --camera zu lesen
from collections import defaultdict         # Für einfaches Zählen der Berührungen
import mediapipe as mp                      # Die Bibliothek für Körper-/Gesichts-/Hand-Erkennung
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


# ===========================================================
# TEIL 0: Multi-OS Kamera-Funktion
# ===========================================================
def open_camera(index=0):
    """
    Öffnet die Kamera mit dem passenden Backend, je nachdem ob wir
    unter Windows, macOS oder Linux laufen. Fällt automatisch auf
    das Standard-Backend zurück, falls das spezifische nicht klappt.
    """
    system = platform.system()   # "Windows", "Darwin" (=macOS) oder "Linux"

    if system == "Windows":
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    elif system == "Darwin":
        cap = cv2.VideoCapture(index, cv2.CAP_AVFOUNDATION)
    else:  # Linux und alles andere
        cap = cv2.VideoCapture(index, cv2.CAP_V4L2)

    if not cap.isOpened():
        # Fallback: ohne explizites Backend versuchen
        cap = cv2.VideoCapture(index)

    return cap


def list_available_cameras(max_index=5):
    """Probiert Kameraindizes durch und gibt zurück, welche tatsächlich funktionieren."""
    available = []
    for i in range(max_index):
        cap = open_camera(i)
        if cap.isOpened():
            available.append(i)
            cap.release()
    return available

# ===========================================================
# TEIL 1: Die drei Erkennungs-Modelle vorbereiten
# ===========================================================

# --- Körper-Modell (Pose) einrichten ---
pose_options = vision.PoseLandmarkerOptions(
    base_options=python.BaseOptions(model_asset_path='pose_landmarker_lite.task'),
    running_mode=vision.RunningMode.VIDEO
)
pose_detector = vision.PoseLandmarker.create_from_options(pose_options)

# --- Gesichts-Modell (Face) einrichten ---
face_options = vision.FaceLandmarkerOptions(
    base_options=python.BaseOptions(model_asset_path='face_landmarker.task'),
    running_mode=vision.RunningMode.VIDEO,
    output_face_blendshapes=True
)
face_detector = vision.FaceLandmarker.create_from_options(face_options)

# --- Hand-Modell (Hand) einrichten ---
hand_options = vision.HandLandmarkerOptions(
    base_options=python.BaseOptions(model_asset_path='hand_landmarker.task'),
    running_mode=vision.RunningMode.VIDEO,
    num_hands=2                       # maximal 2 Hände gleichzeitig erkennen
)
hand_detector = vision.HandLandmarker.create_from_options(hand_options)

# --- Objekt-Modell (Object Detection) einrichten ---
# Nur Arbeitsplatz-relevante Objekte aus den 80 COCO-Klassen erkennen.
# Passe diese Liste einfach an, falls du andere/weitere Objekte brauchst.
WORKPLACE_OBJECTS = [
    'laptop', 'keyboard', 'mouse', 'tv', 'cell phone',
    'book', 'cup', 'chair', 'remote'
]

object_options = vision.ObjectDetectorOptions(
    base_options=python.BaseOptions(model_asset_path='efficientdet.tflite'),
    running_mode=vision.RunningMode.VIDEO,
    score_threshold=0.3,              # niedriger als vorher: mehr Treffer, auch unsicherere
    max_results=5,                    # maximal 5 Objekte pro Bild anzeigen
    category_allowlist=WORKPLACE_OBJECTS   # nur diese Klassen werden ueberhaupt erkannt
)
object_detector = vision.ObjectDetector.create_from_options(object_options)

# --- Fertige "Bauplan-Listen" von MediaPipe laden (welche Punkte verbunden sind) ---
mp_pose_connections = mp.solutions.pose.POSE_CONNECTIONS
mp_face_connections = mp.solutions.face_mesh_connections.FACEMESH_TESSELATION
mp_hand_connections = mp.solutions.hands.HAND_CONNECTIONS

# ===========================================================
# TEIL 2: Die drei CSV-Ausgabedateien vorbereiten
# ===========================================================

# --- Datei für Körperdaten ---
pose_csv = open('pose_data.csv', mode='w', newline='')
pose_writer = csv.writer(pose_csv)
pose_header = ['timestamp']
for i in range(33):                         # 33 Körperpunkte
    pose_header += [f'x{i}', f'y{i}', f'z{i}', f'vis{i}']
pose_writer.writerow(pose_header)

# --- Datei für Gesichtsdaten (Blendshapes) ---
face_csv = open('face_data.csv', mode='w', newline='')
face_writer = csv.writer(face_csv)
face_header = ['timestamp']
face_header_written = False                 # Spaltennamen kommen erst beim ersten Ergebnis

# --- Datei für Handdaten ---
hand_csv = open('hand_data.csv', mode='w', newline='')
hand_writer = csv.writer(hand_csv)
hand_header = ['timestamp', 'hand_index', 'handedness']
for i in range(21):                         # 21 Handpunkte pro Hand
    hand_header += [f'x{i}', f'y{i}', f'z{i}']
hand_writer.writerow(hand_header)

# --- Datei für Objektdaten ---
object_csv = open('object_data.csv', mode='w', newline='')
object_writer = csv.writer(object_csv)
object_writer.writerow([
    'timestamp', 'object_index', 'category_name', 'score',
    'bbox_x', 'bbox_y', 'bbox_width', 'bbox_height',
    'horizontal_pos', 'relative_size', 'hand_nearby'
])


def is_hand_near_object(hand_points, bbox, margin=20):
    """Prüft, ob irgendein Handpunkt innerhalb (+Rand) der Objekt-Box liegt."""
    x1 = bbox.origin_x - margin
    y1 = bbox.origin_y - margin
    x2 = bbox.origin_x + bbox.width + margin
    y2 = bbox.origin_y + bbox.height + margin
    for (hx, hy) in hand_points:
        if x1 <= hx <= x2 and y1 <= hy <= y2:
            return True
    return False


def hand_touches_bodypart(hand_points, body_point, threshold=70):
    """Prüft, ob irgendein Handpunkt nah genug an einem Körperpunkt ist (Pixel-Abstand)."""
    bx, by = body_point
    for (hx, hy) in hand_points:
        distance = ((hx - bx) ** 2 + (hy - by) ** 2) ** 0.5
        if distance < threshold:
            return True
    return False


# --- Genaue Kopf-Regionen anhand fester Face-Mesh-Punkte (aus den 478 Gesichtspunkten) ---
# Diese Indizes sind bei MediaPipe Face Landmarker immer an derselben Stelle im Gesicht.
HEAD_REGIONS = {
    'Stirn':        10,
    'Nase':         4,
    'Mund':         13,
    'Kinn':         152,
    'Auge_Links':   33,
    'Auge_Rechts':  263,
    'Wange_Links':  234,
    'Wange_Rechts': 454,
    'Ohr_Links':    127,
    'Ohr_Rechts':   356,
}


# --- Datei für Hand-Körper-Berührungs-Ereignisse ---
touch_csv = open('touch_events.csv', mode='w', newline='')
touch_writer = csv.writer(touch_csv)
touch_writer.writerow(['timestamp', 'hand', 'body_part', 'event'])   # event: 'start' oder 'end'

touch_state = {}                     # merkt sich pro (Hand, Körperteil), ob GERADE berührt wird
touch_counts = defaultdict(int)      # zählt, wie oft jede Kombination berührt wurde (nur "start"-Momente)
first_touch_time = {}                # Zeitpunkt der allerersten Berührung pro Kombination
last_touch_time = {}                 # Zeitpunkt der letzten Berührung pro Kombination


# ===========================================================
# TEIL 3: Webcam öffnen (multi-OS: Windows / macOS / Linux)
# ===========================================================

# --- Kommandozeilen-Argument lesen, damit man die Kamera beim Start wählen kann ---
# Beispiel: python3 pose_face_hand_detection.py --camera 2   (für DroidCam auf /dev/video2)
parser = argparse.ArgumentParser()
parser.add_argument('--camera', type=int, default=0,
                     help='Kamera-Index, z.B. 0 für eingebaute Webcam, 2 für DroidCam (/dev/video2)')
parser.add_argument('--rotate', type=int, default=0, choices=[0, 90, 180, 270],
                     help='Bild um X Grad drehen, z.B. 90 wenn das Handy hochkant gehalten wird')
args = parser.parse_args()

cap = open_camera(args.camera)
print(f"Verwende Kamera-Index {args.camera} (/dev/video{args.camera})")

if not cap.isOpened():
    print("Fehler: Kamera konnte nicht geöffnet werden.")
    print("Prüfe: Ist eine Kamera angeschlossen? Ist sie von einem anderen Programm belegt?")
    if platform.system() == "Darwin":
        print("Auf macOS: Systemeinstellungen -> Datenschutz & Sicherheit -> Kamera prüfen.")
    print("Verfügbare Kameraindizes:", list_available_cameras())
    exit(1)

# Auflösung/Framerate einheitlich setzen, damit es auf allen Systemen gleich aussieht
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
cap.set(cv2.CAP_PROP_FPS, 30)

frame_timestamp = 0                         # Zähler in Millisekunden, wächst mit jedem Bild

# ===========================================================
# TEIL 4: Hauptschleife -- läuft einmal pro Kamerabild
# ===========================================================
while cap.isOpened():
    ret, frame = cap.read()                 # ein einzelnes Bild von der Webcam holen
    if not ret:
        break

    # Bild drehen, falls die Kamera falsch orientiert ist (z.B. Handy im Hochformat)
    if args.rotate == 90:
        frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
    elif args.rotate == 180:
        frame = cv2.rotate(frame, cv2.ROTATE_180)
    elif args.rotate == 270:
        frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

    # --- Alle drei Modelle auf demselben Bild laufen lassen ---
    pose_result = pose_detector.detect_for_video(mp_image, frame_timestamp)
    face_result = face_detector.detect_for_video(mp_image, frame_timestamp)
    hand_result = hand_detector.detect_for_video(mp_image, frame_timestamp)
    object_result = object_detector.detect_for_video(mp_image, frame_timestamp)

    # -----------------------------------------------------
    # 4a) KÖRPER: zeichnen und in CSV speichern
    # -----------------------------------------------------
    pose_points = None   # wird gleich befüllt, falls ein Körper erkannt wurde (für Hand-Körper-Check)

    if pose_result.pose_landmarks:
        landmarks = pose_result.pose_landmarks[0]

        points = []
        for lm in landmarks:
            x = int(lm.x * frame.shape[1])
            y = int(lm.y * frame.shape[0])
            points.append((x, y))

        pose_points = points   # merken für die Hand-Körper-Berührungsprüfung weiter unten

        for connection in mp_pose_connections:
            start_idx, end_idx = connection
            cv2.line(frame, points[start_idx], points[end_idx], (0, 255, 0), 2)   # grün

        for (x, y) in points:
            cv2.circle(frame, (x, y), 3, (0, 255, 0), -1)

        row = [frame_timestamp]
        for lm in landmarks:
            row += [lm.x, lm.y, lm.z, lm.visibility]
        pose_writer.writerow(row)

    # -----------------------------------------------------
    # 4b) GESICHT: zeichnen und in CSV speichern
    # -----------------------------------------------------
    face_points = None   # wird gleich befüllt, falls ein Gesicht erkannt wurde (für Hand-Kopf-Check)

    if face_result.face_landmarks:
        landmarks = face_result.face_landmarks[0]

        points = []
        for lm in landmarks:
            x = int(lm.x * frame.shape[1])
            y = int(lm.y * frame.shape[0])
            points.append((x, y))

        face_points = points   # merken für die Hand-Kopf-Berührungsprüfung weiter unten

        for connection in mp_face_connections:
            start_idx, end_idx = connection
            cv2.line(frame, points[start_idx], points[end_idx], (255, 255, 0), 1)  # türkis

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
            for b in blendshapes:
                row.append(b.score)
            face_writer.writerow(row)

    # -----------------------------------------------------
    # 4c) HÄNDE: zeichnen und in CSV speichern
    # -----------------------------------------------------
    all_hand_points = []   # sammelt alle Handpunkte aller erkannten Hände (für Objekt-Interaktion)

    if hand_result.hand_landmarks:
        # für jede erkannte Hand (bis zu 2) einzeln durchgehen
        for hand_idx, landmarks in enumerate(hand_result.hand_landmarks):
            # "Left" oder "Right" -- MediaPipe erkennt das aus Sicht der Kamera
            handedness = hand_result.handedness[hand_idx][0].category_name

            points = []
            for lm in landmarks:
                x = int(lm.x * frame.shape[1])
                y = int(lm.y * frame.shape[0])
                points.append((x, y))

            all_hand_points.extend(points)   # für die Objekt-Interaktions-Prüfung merken

            for connection in mp_hand_connections:
                start_idx, end_idx = connection
                cv2.line(frame, points[start_idx], points[end_idx], (0, 0, 255), 2)  # rot

            for (x, y) in points:
                cv2.circle(frame, (x, y), 3, (0, 0, 255), -1)

            # Handedness (Links/Rechts) neben der Hand einblenden
            wrist_x, wrist_y = points[0]     # Punkt 0 = Handgelenk
            cv2.putText(frame, handedness, (wrist_x, wrist_y - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

            row = [frame_timestamp, hand_idx, handedness]
            for lm in landmarks:
                row += [lm.x, lm.y, lm.z]
            hand_writer.writerow(row)

            # --- Hand-Körper-Beziehung: berührt diese Hand gerade Kopf/Brust/Bauch? ---
            body_parts = {}   # name -> (Punkt, Schwellenwert in Pixel)

            # präzise Kopf-Regionen, falls ein Gesicht erkannt wurde (Mund, Augen, Stirn, ...)
            if face_points is not None:
                for region_name, landmark_idx in HEAD_REGIONS.items():
                    body_parts[region_name] = (
                        face_points[landmark_idx],
                        40                                    # kleinerer Schwellenwert: Kopf ist kompakter
                    )
            elif pose_points is not None:
                # Fallback, falls kein Gesicht erkannt wird (z.B. Kopf abgewandt), aber der Körper schon
                body_parts['Kopf'] = (pose_points[0], 70)

            # grobe Körperregionen, unabhängig vom Gesicht
            if pose_points is not None:
                body_parts['Brust'] = (
                    ((pose_points[11][0] + pose_points[12][0]) // 2,
                     (pose_points[11][1] + pose_points[12][1]) // 2),
                    70
                )
                body_parts['Bauch'] = (
                    ((pose_points[23][0] + pose_points[24][0]) // 2,
                     (pose_points[23][1] + pose_points[24][1]) // 2),
                    70
                )

            for part_name, (body_point, threshold) in body_parts.items():
                key = f"{handedness}_{part_name}"
                touching = hand_touches_bodypart(points, body_point, threshold=threshold)

                was_touching = touch_state.get(key, False)

                if touching and not was_touching:
                    # neue Berührung beginnt gerade jetzt
                    touch_counts[key] += 1
                    if key not in first_touch_time:
                        first_touch_time[key] = frame_timestamp
                    last_touch_time[key] = frame_timestamp
                    touch_writer.writerow([frame_timestamp, handedness, part_name, 'start'])

                elif not touching and was_touching:
                    # Berührung endet gerade
                    touch_writer.writerow([frame_timestamp, handedness, part_name, 'end'])

                touch_state[key] = touching

    # -----------------------------------------------------
    # 4d) OBJEKTE: zeichnen und in CSV speichern
    # -----------------------------------------------------
    if object_result.detections:
        frame_width = frame.shape[1]
        frame_height = frame.shape[0]

        for obj_idx, detection in enumerate(object_result.detections):
            bbox = detection.bounding_box
            category = detection.categories[0]
            x, y, w, h = bbox.origin_x, bbox.origin_y, bbox.width, bbox.height

            # Rechteck um das erkannte Objekt zeichnen
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 255), 2)   # gelb

            # Klassenname + Sicherheit als Text darüber
            label = f"{category.category_name} ({category.score:.2f})"
            cv2.putText(frame, label, (x, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

            # grobe Position im Bild (links/mitte/rechts)
            center_x = x + w / 2
            if center_x < frame_width / 3:
                horizontal_pos = "links"
            elif center_x < 2 * frame_width / 3:
                horizontal_pos = "mitte"
            else:
                horizontal_pos = "rechts"

            # grobe Größenschätzung relativ zum Bild (größer = näher an der Kamera)
            relative_size = (w * h) / (frame_width * frame_height)

            # prüfen, ob eine Hand gerade in der Nähe/auf dem Objekt liegt
            hand_nearby = is_hand_near_object(all_hand_points, bbox)
            if hand_nearby:
                cv2.putText(frame, "in Benutzung", (x, y + h + 20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)

            row = [
                frame_timestamp, obj_idx, category.category_name, category.score,
                x, y, w, h, horizontal_pos, relative_size, hand_nearby
            ]
            object_writer.writerow(row)

    # -----------------------------------------------------
    # 4e) Zeit weiterzählen und Bild anzeigen
    # -----------------------------------------------------
    frame_timestamp += 33      # ca. 30 Bilder/Sekunde

    cv2.imshow('Pose + Face + Hand + Object Detection', frame)

    if cv2.waitKey(5) & 0xFF == ord('q'):
        break

# ===========================================================
# TEIL 5: Aufräumen, sobald die Schleife vorbei ist
# ===========================================================
cap.release()
cv2.destroyAllWindows()
pose_csv.close()
face_csv.close()
hand_csv.close()
object_csv.close()
touch_csv.close()

# --- Zusammenfassung: wie oft wurde was berührt, und wie häufig pro Minute ---
total_minutes = frame_timestamp / 1000 / 60 if frame_timestamp > 0 else 0

print("\n=== Zusammenfassung Hand-Körper-Berührungen ===")
if not touch_counts:
    print("Keine Berührungen erkannt.")
else:
    with open('touch_summary.csv', mode='w', newline='') as summary_csv:
        summary_writer = csv.writer(summary_csv)
        summary_writer.writerow(['hand_bodypart', 'anzahl', 'erste_beruehrung_ms',
                                  'letzte_beruehrung_ms', 'pro_minute'])

        for key, count in touch_counts.items():
            per_minute = count / total_minutes if total_minutes > 0 else 0
            print(f"{key}: {count}x berührt "
                  f"(erste: {first_touch_time[key]} ms, letzte: {last_touch_time[key]} ms, "
                  f"~{per_minute:.1f}x pro Minute)")
            summary_writer.writerow([key, count, first_touch_time[key],
                                      last_touch_time[key], round(per_minute, 2)])

    print(f"\nGesamtdauer: {total_minutes:.1f} Minuten")
    print("Details in touch_events.csv (jede einzelne Berührung), "
          "Zusammenfassung in touch_summary.csv")
