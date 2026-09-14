#!/usr/bin/env bash
"""
Atum - Automated Installation Script for Linux
Downloads and installs Atum from releases or builds from source
"""

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

INSTALL_DIR="${1:-$HOME/.local/opt/atum}"
VERSION="${2:-latest}"

echo -e "${BLUE}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║         Atum - Activity Tracking Application               ║"
echo "║                  Linux Installer                           ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check system requirements
check_requirements() {
    echo -e "${YELLOW}Checking system requirements...${NC}"
    
    # Check for Python 3.8+
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}✗ Python 3 is not installed${NC}"
        echo "  Install with: sudo apt install python3 python3-pip python3-venv"
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    echo -e "${GREEN}✓ Python ${PYTHON_VERSION}${NC}"
    
    # Check for required system packages
    echo -e "${YELLOW}Checking system dependencies...${NC}"
    MISSING_DEPS=""
    
    if [ -n "$MISSING_DEPS" ]; then
        echo -e "${YELLOW}Missing system dependencies: $MISSING_DEPS${NC}"
        echo -e "${BLUE}Installing with apt...${NC}"
        sudo apt-get update
        sudo apt-get install -y $MISSING_DEPS
    fi
    
    echo -e "${GREEN}✓ System requirements met${NC}"
}

# Download or build
install_atum() {
    echo -e "${BLUE}Installing Atum...${NC}"
    
    mkdir -p "$INSTALL_DIR"
    
    # Option 1: Use .deb if available
    if command -v dpkg &> /dev/null && [ "$VERSION" != "latest-source" ]; then
        echo -e "${BLUE}Installing from Debian package...${NC}"
        curl -L "https://github.com/yourname/atum/releases/download/v${VERSION}/atum_${VERSION}_amd64.deb" \
            -o /tmp/atum.deb
        sudo dpkg -i /tmp/atum.deb
        rm /tmp/atum.deb
        return
    fi
    
    # Option 2: Use AppImage if available
    if [ "$VERSION" != "latest-source" ] && [ -z "$FORCE_SOURCE" ]; then
        echo -e "${BLUE}Downloading AppImage...${NC}"
        curl -L "https://github.com/yourname/atum/releases/download/v${VERSION}/Atum_${VERSION}.AppImage" \
            -o "$INSTALL_DIR/atum"
        chmod +x "$INSTALL_DIR/atum"
        
        # Create symlink in PATH
        mkdir -p "$HOME/.local/bin"
        ln -sf "$INSTALL_DIR/atum" "$HOME/.local/bin/atum"
        
        echo -e "${GREEN}✓ AppImage installed${NC}"
        return
    fi
    
    # Option 3: Install from source
    echo -e "${BLUE}Installing from source...${NC}"
    
    # Clone or update repository
    if [ -d "$INSTALL_DIR/.git" ]; then
        cd "$INSTALL_DIR"
        git pull origin main
    else
        git clone https://github.com/yourname/atum.git "$INSTALL_DIR" 2>/dev/null || \
            git clone https://github.com/yourname/atum.git "$INSTALL_DIR"
    fi
    
    cd "$INSTALL_DIR"
    
    # Create virtual environment
    echo -e "${BLUE}Setting up Python environment...${NC}"
    python3 -m venv venv
    source venv/bin/activate
    
    # Install dependencies
    echo -e "${BLUE}Installing Python dependencies...${NC}"
    pip install --upgrade pip
    pip install -r requirements.txt
    
    # Create launcher script
    create_launcher
    
    echo -e "${GREEN}✓ Installed from source${NC}"
}

# Create desktop launcher
create_launcher() {
    echo -e "${BLUE}Creating desktop launcher...${NC}"
    
    DESKTOP_FILE="$HOME/.local/share/applications/atum.desktop"
    mkdir -p "$(dirname "$DESKTOP_FILE")"
    
    cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Type=Application
Name=Atum
Comment=Activity Tracking Application
Exec=$HOME/.local/bin/atum
Icon=$INSTALL_DIR/atum.png
Terminal=false
Categories=Utility;
EOF
    
    # Create launcher script
    mkdir -p "$HOME/.local/bin"
    cat > "$HOME/.local/bin/atum" << EOF
#!/usr/bin/env bash
cd "$INSTALL_DIR"
source venv/bin/activate
python3 atum.py
EOF
    chmod +x "$HOME/.local/bin/atum"
    if [ -f "$INSTALL_DIR/workspace-tracking-icon.png" ]; then
        cp "$INSTALL_DIR/workspace-tracking-icon.png" "$INSTALL_DIR/atum.png"
    fi
    
    echo -e "${GREEN}✓ Desktop launcher created${NC}"
}

# Main flow
main() {
    check_requirements
    install_atum
    
    echo -e "${GREEN}"
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║              ✓ Installation Complete!                      ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    echo -e "${BLUE}To launch Atum:${NC}"
    echo "  • Command line: ${GREEN}atum${NC}"
    echo "  • Application menu: Search for ${GREEN}Atum${NC}"
    echo "  • Desktop shortcut: Double-click ${GREEN}Atum${NC}"
    
    echo -e "\n${BLUE}Uninstall:${NC}"
    echo "  sudo apt remove atum  # If installed via .deb"
    echo "  rm -rf $INSTALL_DIR  # If installed from source"
}

main
