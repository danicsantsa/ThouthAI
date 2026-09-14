# Workspace Tracking - Benutzerhandbuch

## 🎯 Was ist Workspace Tracking?

**Workspace Tracking** ist eine professionelle Desktop-Anwendung für Linux, Windows und macOS, die:

- ✅ Überwacht, an welchen Aufgaben Sie arbeiten
- ✅ Verfolgt, welche Anwendungen Sie nutzen  
- ✅ Erkennt Ihre Körperhaltung und Aktivitäten (per Webcam)
- ✅ Speichert alles lokal und optional in einer Datenbank
- ✅ Zeigt detaillierte Berichte und Statistiken

## 📥 Installation auf Linux

### Schnellinstallation (empfohlen)

```bash
cd ~/Workspace-Tracking  # oder: cd /pfad/zur/installation
chmod +x install.sh
./install.sh
```

Das Script installiert automatisch:
- Python 3 und alle erforderlichen Bibliotheken
- OpenCV (für Kamera)
- MediaPipe (für Pose/Gesicht/Hand-Erkennung)
- Desktop-Verknüpfung zum einfachen Starten

### Manuelle Installation

Falls der automatische Installer nicht funktioniert:

```bash
# 1. Installiere Systemabhängigkeiten
sudo apt-get install python3 python3-pip python3-tk

# 2. Erstelle Virtual Environment
python3 -m venv venv
source venv/bin/activate

# 3. Installiere Python-Pakete
pip install opencv-python mediapipe psycopg2-binary matplotlib numpy

# 4. Starte die App
python3 tracking_gui.py
```

## 🚀 Erste Schritte

### 1. Anwendung starten

Nach der Installation können Sie starten mit:

**Option A: Start-Script**
```bash
cd ~/Workspace-Tracking
./start.sh
```

**Option B: Vom Anwendungsmenü**
- Suchen Sie nach "Workspace Tracking" in Ihrer Anwendungsleiste
- Klicken Sie auf das Symbol zum Starten

**Option C: Terminal**
```bash
cd ~/Workspace-Tracking
source venv/bin/activate
python3 tracking_gui.py
```

### 2. Erstmaliges Setup

Beim ersten Start fragt die App nach Ihrem Namen:
1. **Name eingeben** (z.B. "Max Mustermann")
2. **Klick auf "Tracking starten"**
3. **Fertig!** 

Die Kamera und alle anderen Einstellungen werden automatisch konfiguriert.

## 💻 Wie man die App benutzt

### Hauptbildschirm - "Überwachung"

```
┌─────────────────────────────────────┐
│ ● Workspace Tracking               │  ← Navigationsleiste
│ [Überwachung] [Ergebnisse]          │
├─────────────────────────────────────┤
│                                     │
│  Workspace-Überwachung              │
│  Hallo, Max!                        │
│                                     │
│  Status: ● Bereit                   │
│  Erfassungszeit: 00:00:00            │
│                                     │
│  [▶ Aufnahme starten] [⏹ Stoppen]   │  ← Steuerknöpfe
│                                     │
│  Informationen                      │
│  Letzte Sitzung: Noch keine...      │
│  [Ergebnisse anzeigen]              │
│                                     │
│  Aktivitätslog                      │
│  [... aktuelle Meldungen ...]       │
│                                     │
└─────────────────────────────────────┘
```

### Bedienung

1. **Aufnahme starten**: Klick auf grünen Button "▶ Aufnahme starten"
   - Der Status wechselt zu "● Aufnahme läuft"
   - Die Zeit läuft hoch: HH:MM:SS
   - Die App erkennt automatisch Ihre Aktivitäten

2. **Während der Aufnahme**:
   - Die Kamera läuft im Hintergrund
   - App-Aktivitäten werden automatisch protokolliert
   - Pose/Gesicht/Hand-Erkennung läuft im Hintergrund

3. **Aufnahme stoppen**: Klick auf roten Button "⏹ Aufnahme stoppen"
   - Die Aufnahme wird sauber beendet
   - Alle Daten werden gespeichert
   - Aktivitätslog wird aktualisiert

4. **Ergebnisse anzeigen**: Klick auf Tab "Ergebnisse"
   - Zeigt Statistiken der letzten Aufnahmen
   - Detaillierte Auswertung pro Session

## ⚙️ Einstellungen anpassen

Die wichtigsten Einstellungen sind in `gui_settings.json` gespeichert:

```json
{
  "user": "Ihr Name",
  "camera": 1,           // Kamera-Index (0, 1, 2, ...)
  "rotate": 0,           // Bild drehen: 0, 90, 180, 270
  "check_interval": 1,   // Sekunden zwischen Aktivitätsüberprüfungen
  "work_apps": "code,firefox,libreoffice",
  "non_work_apps": "chrome,spotify,vlc"
}
```

## 🎥 Kamera-Probleme?

### Kamera wird nicht erkannt

Führen Sie das Diagnose-Script aus:
```bash
python3 diagnose_camera.py
```

Das zeigt:
- Welche Kameras angeschlossen sind
- Welche funktionieren
- Welche Indizes zu nutzen sind

### Kamera 0 funktioniert nicht

Das ist normal auf Linux. Die App versucht automatisch Kamera 1 oder 2.

Sie können aber auch manuell einstellen:
1. Öffnen Sie `gui_settings.json`
2. Ändern Sie `"camera": 1` auf z.B. `"camera": 2`
3. Starten Sie die App neu

## 📊 Datennutzung

### Lokale Speicherung (offline)

Alle Daten werden lokal in CSV-Dateien gespeichert:
- `pose_data.csv` - Körperhaltung (30/Sekunde)
- `face_data.csv` - Gesichtspunkte
- `hand_data.csv` - Hand-Positionen
- `activity_log.csv` - App-Aktivitäten

Diese Dateien sind immer lokal verfügbar, auch ohne Internetverbindung.

### Optionale Cloud-Speicherung

Wenn eine Datenbank konfiguriert ist:
- Daten werden zusätzlich in PostgreSQL/Supabase gespeichert
- Sie können von jedem Gerät auf die Ergebnisse zugreifen

## 🔧 Häufige Probleme

| Problem | Lösung |
|---------|--------|
| App startet nicht | Stellen Sie sicher, dass python3-tk installiert ist: `sudo apt-get install python3-tk` |
| Kamera wird nicht erkannt | Führen Sie `python3 diagnose_camera.py` aus |
| "X11 Display" Fehler | Sie benötigen eine grafische Benutzeroberfläche (X11). SSH-Sessions funktionieren nicht. |
| App ist zu langsam | Reduzieren Sie `check_interval` in `gui_settings.json` |
| Datenbank-Fehler | Das ist OK - App funktioniert auch ohne Datenbank (CSV-Speicherung) |

## 📝 Dateien & Struktur

```
~/Workspace-Tracking/
├── tracking_gui.py           ← Hauptanwendung
├── track_all.py              ← Hintergrund-Worker
├── gui_settings.py           ← Einstellungen
├── gui_settings.json         ← Ihre Konfiguration
├── db_config.json            ← Datenbankeinstellungen
├── *.task & *.tflite         ← AI-Modelle
├── venv/                     ← Python-Umgebung
├── start.sh                  ← Start-Script
└── *.csv                     ← Gespeicherte Daten
```

## 💡 Tipps zur Benutzung

1. **Regelmäßig starten**: Nutzen Sie die App täglich, um aussagekräftige Daten zu sammeln
2. **Kamera-Position**: Positionieren Sie die Webcam auf Augenhöhe für beste Ergebnisse
3. **Gutes Licht**: Die Pose-Erkennung funktioniert besser mit ausreichend Beleuchtung
4. **Lange Sessions**: Längere Aufnahmesitzungen (>1 Stunde) liefern bessere Statistiken

## 🆘 Support & Fehlerberichte

Wenn Sie Probleme haben:

1. **Logs prüfen**: Das Aktivitätslog in der App zeigt oft die Fehlermeldung
2. **Test starten**: 
   ```bash
   python3 test_integration.py    # Testet alle Komponenten
   python3 diagnose_camera.py     # Testet Kamera
   ```
3. **Terminal-Ausgabe**: Starten Sie aus dem Terminal, um Fehlermeldungen zu sehen:
   ```bash
   cd ~/Workspace-Tracking
   source venv/bin/activate
   python3 tracking_gui.py    # Zeigt alle Meldungen
   ```

## 📄 Lizenz & Datenschutz

- ✅ Diese Software speichert Daten lokal auf Ihrem Computer
- ✅ Keine Daten werden ohne Ihre Erlaubnis übertragen
- ✅ Sie haben Zugriff auf alle gesammelten Daten (CSV-Dateien)
- ✅ Sie können jederzeit alle Daten löschen

---

**Version**: 1.0  
**Zuletzt aktualisiert**: September 2026  
**Plattform**: Linux, Windows, macOS
