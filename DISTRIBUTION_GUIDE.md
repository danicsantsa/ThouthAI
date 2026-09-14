# Atum: Bau- und Installationsplan

Dieser Plan ist fuer die Weitergabe an Personen gedacht, die keine Python- oder Computerkenntnisse haben.

## 1. Was die Nutzer bekommen

Fuer jede Plattform gibt es genau ein eigenes Paket:

| System | Datei fuer Nutzer | Installation |
|---|---|---|
| Windows | `Atum_1.0.0_installer.exe` | Doppelklick, Installieren |
| macOS | `Atum_1.0.0.dmg` | Atum nach Applications ziehen |
| Linux | `Atum_1.0.0.AppImage` | Doppelklick nach `Ausfuehrbar` |

Die Nutzer brauchen nicht:

- Python
- pip
- PySide6
- MediaPipe
- ein Terminal
- eine manuelle Konfiguration

## 2. Einmaliger Bau durch den Herausgeber

Der Build muss auf dem jeweiligen Betriebssystem ausgefuehrt werden.

### Linux

```bash
source myenv/bin/activate
python build/build.py
```

Ergebnis: Linux-Build in `dist/`.

### Windows

1. Projektordner auf einen Windows-Rechner kopieren.
2. Python 3.11 installieren.
3. Eingabeaufforderung im Projektordner oeffnen.
4. Abhaengigkeiten installieren:

```bat
py -m venv myenv
myenv\Scripts\activate
python -m pip install -r requirements.txt
python build\build.py
```

5. Falls NSIS installiert ist, wird zusaetzlich der Windows-Installer gebaut.

Ergebnis: `Atum_1.0.0_installer.exe`.

### macOS

1. Projektordner auf einen Mac kopieren.
2. Python 3.11 installieren.
3. Terminal im Projektordner oeffnen.
4. Abhaengigkeiten installieren:

```bash
python3 -m venv myenv
source myenv/bin/activate
python -m pip install -r requirements.txt
python build/build.py
```

Ergebnis: `Atum.app` und `Atum_1.0.0.dmg`.

Fuer Apple-Silicon-Macs und Intel-Macs sollten getrennte Builds erstellt werden.

## 3. Installation fuer normale Nutzer

### Windows

1. `Atum_1.0.0_installer.exe` herunterladen.
2. Datei doppelt anklicken.
3. Auf `Installieren` klicken.
4. Atum im Startmenue oder auf dem Desktop oeffnen.
5. Beim ersten Start den Kamera-Zugriff erlauben.

Wenn Windows eine Sicherheitsmeldung zeigt: Nur bei einem von dir signierten oder vertrauenswuerdigen Installer auf `Weitere Informationen` und danach `Trotzdem ausfuehren` klicken.

### macOS

1. `Atum_1.0.0.dmg` herunterladen.
2. DMG doppelt anklicken.
3. Das Atum-Symbol in `Applications` ziehen.
4. Atum aus `Applications` starten.
5. Den Kamera-Zugriff erlauben.

Wenn macOS die App blockiert: Atum im Finder mit der rechten Maustaste anklicken und `Oeffnen` waehlen.

Kamera-Berechtigung findet man unter:

`System Settings > Privacy & Security > Camera > Atum`

### Linux

1. `Atum_1.0.0.AppImage` herunterladen.
2. Rechtsklick auf die Datei und `Eigenschaften` oeffnen.
3. Unter `Berechtigungen` die Option `Datei als Programm ausfuehren` aktivieren.
4. Die Datei doppelt anklicken.

Alternativ kann der Herausgeber ein `.deb`-Paket anbieten.

## 4. Erster Start

Der Nutzer muss nur:

1. Atum oeffnen.
2. Den Namen eingeben.
3. Kamera-Zugriff erlauben.
4. `Start` klicken.
5. Sich im Kamera-Preview pruefen.
6. Zum Beenden `Stop` klicken.

Atum erstellt automatisch:

- die lokale Videoaufnahme
- die MediaPipe-Daten fuer Pose, Gesicht und Haende
- die lokale Auswertung
- die Supabase-Session, wenn die Verbindung verfuegbar ist

## 5. Vor dem Verteilen testen

Auf jedem Betriebssystem einen Testrechner ohne Entwicklungsumgebung verwenden.

### Pflicht-Test

- Installer startet ohne Python.
- Atum-Logo ist im Startmenue/Desktop sichtbar.
- Anwendung startet ohne Terminal.
- Kamera-Berechtigung funktioniert.
- Eigenes Bild erscheint im Preview.
- Pose-, Gesichts- und Handmarkierungen erscheinen.
- Aufnahme startet und stoppt.
- MP4-Datei wird gespeichert.
- Dauer der MP4 erscheint in der Tabelle.
- Ergebnisse-Tab zeigt MediaPipe-Daten.
- Supabase-Status zeigt gruen bei Verbindung.
- Supabase-Status zeigt rot ohne Verbindung.
- Anwendung beendet sich ohne Fehlermeldung.

## 6. Supabase und Sicherheit

Die aktuelle portable Version enthaelt `db_config.json`, damit Nutzer nichts konfigurieren muessen. Dieses Paket darf nur an Personen verteilt werden, die diese Supabase-Verbindung verwenden duerfen.

Vor einer oeffentlichen Verteilung sollten in Supabase unbedingt Row Level Security, eingeschraenkte Datenbankrechte und getrennte Produktionszugangsdaten eingerichtet werden. Ein direkt eingebettetes Datenbankpasswort ist fuer eine oeffentliche App nicht geeignet.

## 7. Release-Ordner

Fuer Nutzer sollten nur diese Dateien veroeffentlicht werden:

```text
release/
  Atum_1.0.0_installer.exe
  Atum_1.0.0.dmg
  Atum_1.0.0.AppImage
  INSTALLATION_DE.md
```

Nicht verteilen:

- Projektquellcode
- virtuelle Umgebungen
- Build-Zwischendateien
- private Testdaten
- private Entwicklungslogs

## 8. Support-Text fuer Nutzer

> Bitte Atum installieren, starten und den Kamera-Zugriff erlauben. Danach den Namen eingeben und auf Start klicken. Wenn kein Bild erscheint, Atum beenden, die Kamera-Berechtigung im Betriebssystem aktivieren und Atum erneut starten.
