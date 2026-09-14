# QUICK START - Workspace Tracking Installation

## 🎯 Das brauchst du wissen

Deine Software ist **fertig** und hat ein **neues professionelles Design**. Es sieht jetzt aus wie eine echte Business-Software - nicht mehr technisch und kompliziert.

## 🚀 Installation in 3 Schritten

### Schritt 1: Installer starten

```bash
chmod +x install.sh
./install.sh
```

**Dauer**: ~3-5 Minuten (je nach Internet)

Das Script installiert automatisch ALLES:
- Python 3 & Bibliotheken
- Kamera-Software (OpenCV)
- AI-Modelle (MediaPipe)
- Desktop-Verknüpfung

### Schritt 2: Erste Verwendung

Nach Installation:
```bash
# Option A: Einfach mit Start-Script
./start.sh

# Option B: Oder vom Desktop-Menü
# Suche nach "Workspace Tracking"
```

### Schritt 3: Setup

1. **Namen eingeben** (z.B. "Max Mustermann")
2. **Klick: Tracking starten**
3. **Fertig!** 🎉

Alles andere läuft automatisch im Hintergrund.

---

## 📊 Neues Design - Die Highlights

### Das neue Fenster sieht so aus:

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  ● Workspace Tracking                        ┃
┃  [Überwachung]  [Ergebnisse]                 ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

    Workspace-Überwachung
    Hallo, Max!

    ┌─────────────────────────────────┐
    │ Status: ● Bereit                │
    │ Erfassungszeit: 00:00:00        │
    │                                 │
    │ [▶ Aufnahme starten] [⏹ Stop]  │  ← Große, einfache Knöpfe
    └─────────────────────────────────┘

    ┌─────────────────────────────────┐
    │ Informationen                   │
    │ Letzte Sitzung: ...             │
    │ [Ergebnisse anzeigen]           │
    └─────────────────────────────────┘

    Aktivitätslog
    ┌─────────────────────────────────┐
    │ [Meldungen ...                  │
    └─────────────────────────────────┘
```

### Was ist anders?

| Alt | Neu |
|-----|-----|
| Dunkel, düster | Hell, sauber, professionell |
| Kleine Texte | Große, lesbare Texte |
| Viele bunte Farben | Professionelles Blau + Weiß |
| Verwirrende Anordnung | Klare Struktur mit Karten |
| Technisch wirkend | Sieht aus wie normale Software |

---

## 💻 Systemanforderungen

### Linux (empfohlen)
- Ubuntu 20.04+ oder ähnlich
- Webcam/Kamera (USB oder eingebaut)
- 2GB RAM minimum
- 500MB freier Speicherplatz

### Windows / macOS
- Python 3.8+ manuell installieren
- Dann: `pip install opencv-python mediapipe...` usw.
- Oder einfach auf Linux wechseln 😉

---

## 📁 Ordnerstruktur nach Installation

```
Workspace-Tracking/                ← Installationsordner
├── tracking_gui.py                ← Die App (neu mit professionellem Design!)
├── track_all.py                   ← Hintergrund-Worker
├── start.sh                        ← Start-Script
├── install.sh                      ← Installer
├── BENUTZERHANDBUCH.md            ← Ausführliche Hilfe (deutsch)
├── NEUES_DESIGN_INFO.md           ← Info zum neuen Design
├── gui_settings.json              ← Deine Einstellungen
├── venv/                           ← Python-Umgebung
├── pose_data.csv                  ← Gespeicherte Daten
├── activity_log.csv               ← Aktivitätslog
└── ... weitere Dateien
```

---

## 🎮 Wie man die App benutzt

### Aufnahme starten

1. App öffnen
2. Klick auf grünen Button: **▶ Aufnahme starten**
3. Arbeite normal weiter
4. Die App erfasst im Hintergrund automatisch alles

### Aufnahme stoppen

1. Klick auf roten Button: **⏹ Aufnahme stoppen**
2. Die Sitzung wird gespeichert
3. Du kannst jederzeit eine neue Aufnahme starten

### Ergebnisse ansehen

1. Klick auf Tab: **Ergebnisse**
2. Sieh deine Statistiken und Auswertungen
3. Zurück: Klick auf Tab **Überwachung**

---

## ⚙️ Erste Einstellungen

Die wichtigsten Einstellungen sind in `gui_settings.json`:

```json
{
  "user": "Dein Name",      ← Beim Setup eingegeben
  "camera": 1,              ← Kamera-Index (1 ist Standard auf Linux)
  "rotate": 0,              ← Bild drehen wenn nötig (0, 90, 180, 270)
  "check_interval": 1       ← Überprüfungsintervall in Sekunden
}
```

**Du brauchst das normalerweise nicht zu ändern!** Die Standard-Werte funktionieren prima.

---

## 🎥 Kamera funktioniert nicht?

Falls die Kamera nicht erkannt wird:

```bash
# Diagnose starten
python3 diagnose_camera.py
```

Das zeigt dir:
- Welche Kameras vorhanden sind
- Welche funktionieren
- Welche Nummer zu verwenden ist

Dann in `gui_settings.json` ändern:
```json
"camera": 1  ← Hier die richtige Nummer eintragen
```

---

## 📝 Wichtige Dateien

### Dokumentation (Deutsch)
- `BENUTZERHANDBUCH.md` - Ausführliches Handbuch
- `NEUES_DESIGN_INFO.md` - Info zum neuen Design

### Tests
```bash
# Alles testen
python3 test_integration.py

# Kamera testen
python3 diagnose_camera.py

# System-Check
python3 test_camera_integration.py
```

### Deine Daten
- `pose_data.csv` - Körperhaltung (30/Sekunde)
- `activity_log.csv` - App-Aktivitäten
- `gui_settings.json` - Deine Einstellungen

---

## ✅ Checkliste für die Installation

- [ ] `./install.sh` ausgeführt
- [ ] Keine Fehler während Installation
- [ ] App startet: `./start.sh` oder vom Menü
- [ ] Fenster sieht professionell und sauber aus ✨
- [ ] Namen eingegeben
- [ ] Test: Aufnahme starten & stoppen
- [ ] Ergebnisse-Tab ansehen

---

## 🆘 Häufige Probleme

### "Command not found: install.sh"
```bash
chmod +x install.sh  # Erst ausführbar machen
./install.sh         # Dann starten
```

### "X11 Display not set"
Du brauchst eine grafische Oberfläche. SSH-Sessions funktionieren nicht. Du brauchst physikalisch den Monitor oder X11-Forwarding.

### "python3-tk not found"
```bash
sudo apt-get install python3-tk
```

### Kamera wird nicht erkannt
```bash
python3 diagnose_camera.py  # Welche Kamera?
# Dann in gui_settings.json die Nummer anpassen
```

### "Permission denied" bei start.sh
```bash
chmod +x start.sh
```

---

## 🎨 Design-Vergleich

### ALT ❌ (Dunkel, kompliziert, technisch)
- Schwarzer Hintergrund (deprimierend)
- Viele Neon-Farben durcheinander
- Kleine, unklar Texte
- Schwer zu verstehen was man tun soll
- Sieht nach Hacker-Software aus 👨‍💻

### NEU ✅ (Hell, sauber, professionell)
- Weißer/heller Hintergrund (freundlich)
- Professionelle Farben (Blau, Grün, Rot)
- Große, klare Texte
- Sofort klar: "Start" grün, "Stop" rot
- Sieht aus wie normale Business-Software 💼

---

## 🚀 Los geht's!

### Kurz-Befehle:

```bash
# Installation
chmod +x install.sh && ./install.sh

# Start
./start.sh

# Tests
python3 test_integration.py

# Diagnose
python3 diagnose_camera.py
```

---

## 📞 Support

Wenn du Probleme hast:

1. **Logs prüfen** - Im Aktivitätslog (unten in der App)
2. **Tests starten** - `python3 test_integration.py`
3. **Manuell starten** - Terminal öffnen:
   ```bash
   cd ~/Workspace-Tracking
   source venv/bin/activate
   python3 tracking_gui.py
   ```
4. **Fehler anschauen** - Terminal zeigt alle Meldungen

---

## 🎉 Das war's!

Du hast jetzt eine professionelle, moderne Desktop-Anwendung für Workspace-Tracking mit:

✅ Sauberes, helles professionelles Design  
✅ Einfache, klare Bedienung  
✅ Automatische Kamera-Erkennung  
✅ Pose/Gesicht/Hand-Tracking im Hintergrund  
✅ Automatische Aktivitätserkennung  
✅ Lokale und optionale Cloud-Speicherung  

**Viel Erfolg!** 🚀

---

**Version**: 1.0  
**Stand**: September 2026  
**Status**: ✅ Produktionsreif  
