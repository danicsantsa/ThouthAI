#!/usr/bin/env bash
# Atum - Installation Script for macOS
# Downloads and installs Atum from DMG or builds from source

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

INSTALL_DIR="/Applications/Atum.app"
VERSION="${1:-latest}"

echo -e "${BLUE}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║         Atum - Activity Tracking Application               ║"
echo "║                   macOS Installer                          ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check macOS version
check_requirements() {
    echo -e "${YELLOW}Checking system requirements...${NC}"
    
    OS_VERSION=$(sw_vers -productVersion)
    MAJOR_VERSION=$(echo $OS_VERSION | cut -d. -f1)
    
    if [ "$MAJOR_VERSION" -lt 10 ]; then
        echo -e "${RED}✗ macOS 10.12+ required${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✓ macOS ${OS_VERSION}${NC}"
    
    # Check for Python
    if ! command -v python3 &> /dev/null; then
        echo -e "${YELLOW}Python 3 not found. Install from:${NC}"
        echo "  https://www.python.org/downloads/"
        exit 1
    fi
    
    echo -e "${GREEN}✓ Python available${NC}"
}

# Install from DMG
install_from_dmg() {
    echo -e "${BLUE}Downloading Atum DMG...${NC}"
    
    TEMP_DMG="/tmp/Atum_${VERSION}.dmg"
    curl -L "https://github.com/yourname/atum/releases/download/v${VERSION}/Atum_${VERSION}.dmg" \
        -o "$TEMP_DMG"
    
    echo -e "${BLUE}Mounting DMG...${NC}"
    hdiutil attach "$TEMP_DMG"
    
    echo -e "${BLUE}Installing...${NC}"
    cp -r "/Volumes/Atum/Atum.app" /Applications/
    
    echo -e "${BLUE}Cleaning up...${NC}"
    hdiutil detach "/Volumes/Atum"
    rm "$TEMP_DMG"
    
    echo -e "${GREEN}✓ Installed successfully${NC}"
}

# Install from source
install_from_source() {
    echo -e "${BLUE}Installing from source...${NC}"
    
    SOURCE_DIR="$HOME/atum-src"
    
    # Clone repository
    if [ -d "$SOURCE_DIR" ]; then
        cd "$SOURCE_DIR"
        git pull
    else
        git clone https://github.com/yourname/atum.git "$SOURCE_DIR"
        cd "$SOURCE_DIR"
    fi
    
    # Create virtual environment
    echo -e "${BLUE}Setting up Python environment...${NC}"
    python3 -m venv venv
    source venv/bin/activate
    
    # Install dependencies
    pip install --upgrade pip
    pip install -r requirements.txt
    
    # Create app wrapper
    echo -e "${BLUE}Creating macOS app...${NC}"
    
    mkdir -p "/Applications/Atum.app/Contents/MacOS"
    mkdir -p "/Applications/Atum.app/Contents/Resources"
    
    # Create launcher script
    cat > "/Applications/Atum.app/Contents/MacOS/Atum" << 'EOF'
#!/bin/bash
SOURCE_DIR="$HOME/atum-src"
cd "$SOURCE_DIR"
source venv/bin/activate
python3 atum.py
EOF
    chmod +x "/Applications/Atum.app/Contents/MacOS/Atum"
    
    # Create Info.plist
    cat > "/Applications/Atum.app/Contents/Info.plist" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>en</string>
    <key>CFBundleExecutable</key>
    <string>Atum</string>
    <key>CFBundleIdentifier</key>
    <string>com.atum.tracking</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>Atum</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleVersion</key>
    <string>1.0.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSHumanReadableCopyright</key>
    <string>Atum Project 2024</string>
    <key>NSPrincipalClass</key>
    <string>NSApplication</string>
</dict>
</plist>
EOF
    
    echo -e "${GREEN}✓ Installed from source${NC}"
}

# Main
main() {
    check_requirements
    
    if [ "$VERSION" == "source" ] || ! command -v curl &> /dev/null; then
        install_from_source
    else
        install_from_dmg
    fi
    
    echo -e "${GREEN}"
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║              ✓ Installation Complete!                      ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    echo -e "${BLUE}To launch Atum:${NC}"
    echo "  • Finder: Applications > Atum"
    echo "  • Spotlight: Cmd+Space, type 'Atum', press Enter"
    echo "  • Terminal: open /Applications/Atum.app"
}

main
