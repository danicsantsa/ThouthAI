import cv2                                  # OpenCV: liest Webcam-Bilder und zeigt Fenster an
import csv                                  # Zum Schreiben der Zahlen-Daten in Dateien
import platform                             # Um zu erkennen, auf welchem Betriebssystem wir laufen
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

# ===========================================================
# TEIL 3: Webcam öffnen (multi-OS: Windows / macOS / Linux)
# ===========================================================
cap = open_camera(0)                        # 0 = die Standard-Webcam des Computers

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

    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

    # --- Alle drei Modelle auf demselben Bild laufen lassen ---
    pose_result = pose_detector.detect_for_video(mp_image, frame_timestamp)
    face_result = face_detector.detect_for_video(mp_image, frame_timestamp)
    hand_result = hand_detector.detect_for_video(mp_image, frame_timestamp)

    # -----------------------------------------------------
    # 4a) KÖRPER: zeichnen und in CSV speichern
    # -----------------------------------------------------
    if pose_result.pose_landmarks:
        landmarks = pose_result.pose_landmarks[0]

        points = []
        for lm in landmarks:
            x = int(lm.x * frame.shape[1])
            y = int(lm.y * frame.shape[0])
            points.append((x, y))

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
    if face_result.face_landmarks:
        landmarks = face_result.face_landmarks[0]

        points = []
        for lm in landmarks:
            x = int(lm.x * frame.shape[1])
            y = int(lm.y * frame.shape[0])
            points.append((x, y))

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

    # -----------------------------------------------------
    # 4d) Zeit weiterzählen und Bild anzeigen
    # -----------------------------------------------------
    frame_timestamp += 33      # ca. 30 Bilder/Sekunde

    cv2.imshow('Pose + Face + Hand Detection', frame)

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
