#!/bin/bash
#
# Claude Drinking Bird - Installation Script
# Installs dependencies and sets up the application for Ubuntu
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$HOME/.local/share/claude-drinking-bird"
BIN_DIR="$HOME/.local/bin"
CONFIG_DIR="$HOME/.config/claude-drinking-bird"
AUTOSTART_DIR="$HOME/.config/autostart"

echo "======================================"
echo "Claude Drinking Bird - Installer"
echo "======================================"
echo ""

# Check if running on Ubuntu/Debian
if ! command -v apt &> /dev/null; then
    echo "Warning: This installer is designed for Ubuntu/Debian systems."
    echo "You may need to install dependencies manually on other systems."
fi

# Install system dependencies
echo "[1/4] Installing system dependencies..."
sudo apt update
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-gi \
    gir1.2-appindicator3-0.1 \
    libgirepository1.0-dev \
    scrot \
    xdotool \
    slop \
    pulseaudio-utils

# Create installation directory
echo ""
echo "[2/4] Creating directories..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$BIN_DIR"
mkdir -p "$CONFIG_DIR/reference_images"
mkdir -p "$AUTOSTART_DIR"

# Copy application files
echo ""
echo "[3/4] Copying application files..."
cp "$SCRIPT_DIR/claude_drinking_bird.py" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/requirements.txt" "$INSTALL_DIR/"

# Copy reference images if they exist in the source directory
if [[ -d "$SCRIPT_DIR/reference-images" ]]; then
    echo "     Copying bundled reference images..."
    cp "$SCRIPT_DIR/reference-images/"*.png "$CONFIG_DIR/reference_images/" 2>/dev/null || true
    cp "$SCRIPT_DIR/reference-images/"*.jpg "$CONFIG_DIR/reference_images/" 2>/dev/null || true
fi

# Create virtual environment and install Python dependencies
echo ""
echo "[4/4] Setting up Python environment..."
# Use --system-site-packages to access system-installed python3-gi
python3 -m venv --system-site-packages "$INSTALL_DIR/venv"
source "$INSTALL_DIR/venv/bin/activate"
pip install --upgrade pip
pip install -r "$INSTALL_DIR/requirements.txt"
deactivate

# Create launcher script
echo ""
echo "Creating launcher scripts..."
cat > "$BIN_DIR/claude-drinking-bird" << 'EOF'
#!/bin/bash
INSTALL_DIR="$HOME/.local/share/claude-drinking-bird"
source "$INSTALL_DIR/venv/bin/activate"
exec python3 "$INSTALL_DIR/claude_drinking_bird.py" "$@"
EOF
chmod +x "$BIN_DIR/claude-drinking-bird"

# Copy autostart helper script
cp "$SCRIPT_DIR/claude-drinking-bird-autostart" "$BIN_DIR/"
chmod +x "$BIN_DIR/claude-drinking-bird-autostart"

# Create desktop entry for app launcher
mkdir -p "$HOME/.local/share/applications"
cat > "$HOME/.local/share/applications/claude-drinking-bird.desktop" << EOF
[Desktop Entry]
Type=Application
Name=Claude Drinking Bird
Comment=Auto-approve Claude Code permission prompts
Exec=$BIN_DIR/claude-drinking-bird
Icon=utilities-terminal
Terminal=false
Categories=Utility;Development;
StartupNotify=false
EOF

# Create autostart entry (disabled by default)
cat > "$AUTOSTART_DIR/claude-drinking-bird.desktop" << EOF
[Desktop Entry]
Type=Application
Name=Claude Drinking Bird
Comment=Auto-approve Claude Code permission prompts
Exec=$BIN_DIR/claude-drinking-bird
Icon=utilities-terminal
Terminal=false
Categories=Utility;Development;
StartupNotify=false
X-GNOME-Autostart-enabled=false
EOF

echo ""
echo "======================================"
echo "Installation Complete!"
echo "======================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Add reference images:"
echo "   Place screenshots of the 'Yes' button in:"
echo "   $CONFIG_DIR/reference_images/"
echo ""
echo "2. Run the application:"
echo "   claude-drinking-bird"
echo ""
echo "3. To enable autostart on boot:"
echo "   claude-drinking-bird-autostart enable"
echo ""
echo "Note: Make sure $BIN_DIR is in your PATH."
echo "      Add this to your ~/.bashrc if needed:"
echo "      export PATH=\"\$HOME/.local/bin:\$PATH\""
echo ""
