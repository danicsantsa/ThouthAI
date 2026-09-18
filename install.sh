#!/bin/bash
#
# Workspace Tracking - Linux Installation Script
# Moderne Desktop-Anwendung für Workspace-Überwachung
#
# Verwendung:
#   chmod +x install.sh
#   ./install.sh
#

set -e

echo ""
echo "╔════════════════════════════════════════════════════╗"
echo "║   Workspace Tracking - Linux Installation         ║"
echo "╚════════════════════════════════════════════════════╝"
echo ""

# Farben
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if running on Linux
if [[ ! "$OSTYPE" =~ ^linux ]]; then
    echo -e "${RED}✗ Dieses Script läuft nur auf Linux${NC}"
    exit 1
fi

INSTALL_DIR="$HOME/Workspace-Tracking"

echo -e "${BLUE}→ Installationsverzeichnis: $INSTALL_DIR${NC}"
echo ""

# Step 1: Check dependencies
echo -e "${YELLOW}Schritt 1: Überprüfe Abhängigkeiten...${NC}"

check_command() {
    if ! command -v $1 &> /dev/null; then
        echo -e "${RED}✗ $1 nicht gefunden${NC}"
        return 1
    fi
    echo -e "${GREEN}✓ $1 gefunden${NC}"
    return 0
}

deps_missing=0

check_command "python3" || deps_missing=1
check_command "pip3" || deps_missing=1

if [ $deps_missing -eq 1 ]; then
    echo ""
    echo -e "${YELLOW}Installiere fehlende Pakete...${NC}"
    sudo apt-get update
    sudo apt-get install -y python3 python3-pip python3-venv
fi

echo ""
echo -e "${YELLOW}Schritt 2: Erstelle Installationsverzeichnis...${NC}"

if [ -d "$INSTALL_DIR" ]; then
    echo -e "${YELLOW}Verzeichnis existiert bereits${NC}"
else
    mkdir -p "$INSTALL_DIR"
    echo -e "${GREEN}✓ Verzeichnis erstellt: $INSTALL_DIR${NC}"
fi

echo ""
echo -e "${YELLOW}Schritt 3: Kopiere Anwendungsdateien...${NC}"

# Copy main files
cp -v tracking_gui.py "$INSTALL_DIR/"
cp -v track_all.py "$INSTALL_DIR/"
cp -v gui_settings.py "$INSTALL_DIR/"
cp -v camera_utils.py "$INSTALL_DIR/"
cp -v db_client.py "$INSTALL_DIR/"
cp -v db_queries.py "$INSTALL_DIR/"
cp -v activity_tracker.py "$INSTALL_DIR/"
cp -v db_config.json "$INSTALL_DIR/"

# Copy model files
cp -v pose_landmarker_lite.task "$INSTALL_DIR/" 2>/dev/null || true
cp -v face_landmarker.task "$INSTALL_DIR/" 2>/dev/null || true
cp -v hand_landmarker.task "$INSTALL_DIR/" 2>/dev/null || true
cp -v efficientdet.tflite "$INSTALL_DIR/" 2>/dev/null || true

# Copy startup script
cp -v run_monitor_app.sh "$INSTALL_DIR/" 2>/dev/null || true
cp -v workspace-tracking-icon.png "$INSTALL_DIR/atum.png" 2>/dev/null || true

echo -e "${GREEN}✓ Dateien kopiert${NC}"

echo ""
echo -e "${YELLOW}Schritt 4: Erstelle Python Virtual Environment...${NC}"

cd "$INSTALL_DIR"

if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtual Environment erstellt${NC}"
else
    echo -e "${YELLOW}Virtual Environment existiert bereits${NC}"
fi

# Activate virtual environment
source venv/bin/activate

echo ""
echo -e "${YELLOW}Schritt 5: Installiere Python-Abhängigkeiten...${NC}"

# Install required packages
pip install --upgrade pip setuptools wheel > /dev/null

echo "  • Installing opencv-python..."
pip install opencv-python > /dev/null

echo "  • Installing mediapipe..."
pip install mediapipe > /dev/null

echo "  • Installing psycopg2-binary (Database)..."
pip install psycopg2-binary > /dev/null

echo "  • Installing PySide6..."
pip install PySide6 > /dev/null

echo "  • Installing numpy..."
pip install numpy > /dev/null

echo -e "${GREEN}✓ Alle Abhängigkeiten installiert${NC}"

echo ""
echo -e "${YELLOW}Schritt 6: Erstelle Desktop-Verknüpfung...${NC}"

# Create desktop launcher
DESKTOP_FILE="$HOME/.local/share/applications/workspace-tracking.desktop"
mkdir -p "$(dirname "$DESKTOP_FILE")"

cat > "$DESKTOP_FILE" << 'EOF'
[Desktop Entry]
Version=1.0
Type=Application
Name=Workspace Tracking
Comment=Überwachen Sie Ihre Arbeitsaufgaben und Aktivitäten
Exec=$HOME/Workspace-Tracking/start.sh
Icon=$HOME/Workspace-Tracking/atum.png
Terminal=false
Categories=Utility;Productivity;
EOF

echo -e "${GREEN}✓ Desktop-Verknüpfung erstellt${NC}"

echo ""
echo -e "${YELLOW}Schritt 7: Erstelle Start-Script...${NC}"

START_SCRIPT="$INSTALL_DIR/start.sh"

cat > "$START_SCRIPT" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
python3 capturesuite_qt_new.py
EOF

chmod +x "$START_SCRIPT"
echo -e "${GREEN}✓ Start-Script erstellt${NC}"

echo ""
echo "╔════════════════════════════════════════════════════╗"
echo "║              Installation abgeschlossen!           ║"
echo "╚════════════════════════════════════════════════════╝"
echo ""
echo -e "${GREEN}✓ Workspace Tracking ist installiert${NC}"
echo ""
echo -e "${BLUE}Startoptionen:${NC}"
echo ""
echo "1. Mit Startscript:"
echo -e "   ${GREEN}cd $INSTALL_DIR && ./start.sh${NC}"
echo ""
echo "2. Mit Python direkt:"
echo -e "   ${GREEN}cd $INSTALL_DIR && source venv/bin/activate && python3 capturesuite_qt_new.py${NC}"
echo ""
echo "3. Vom Anwendungsmenü:"
echo -e "   ${GREEN}Suche nach 'Workspace Tracking' im Menü${NC}"
echo ""
echo -e "${YELLOW}Erste Verwendung:${NC}"
echo "  1. Starten Sie die Anwendung"
echo "  2. Geben Sie Ihren Namen ein"
echo "  3. Klicken Sie auf 'Aufnahme starten'"
echo "  4. Alles Weitere läuft automatisch!"
echo ""
echo -e "${BLUE}Dokumentation:${NC}"
echo "  README.md im Installationsverzeichnis"
echo ""
