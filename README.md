# Claude Drinking Bird

A background tool that automatically approves Claude Code permission prompts for situations where --dangerously-skip-permissions is not available for some reason.

![catfix-funny](https://github.com/user-attachments/assets/dcd4a1c8-525f-45b6-b0ec-6b278ca4bf63)

## Features

- **Auto-approval**: Detects permission prompts and sends Enter key to approve
- **System tray integration**: Shows status in Ubuntu top bar
  - 🟢 Green: Active and scanning
  - 🟡 Yellow: Paused (Claude window not focused)
  - 🔴 Red: Disabled
- **Safety features**:
  - Only activates when a Claude window is in focus (title starts with ✳)
  - Configurable confidence threshold (default 0.9)
  - Cooldown between approvals to prevent rapid-fire
- **Multiple reference images**: Support for different themes etc
- **Audio feedback**: Plays a sound when auto-approving
- **Optimized scanning**: By default scans only within the focused window bounds, with option to set a custom fixed region

## Installation

### Quick Install (Ubuntu)

```bash
# Clone or download this repository
cd claude-drinking-bird

# Run the installer
chmod +x install.sh
./install.sh
```

### Manual Installation

1. **Install system dependencies:**

```bash
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
```

2. **Create a virtual environment and install Python packages:**

```bash
# Use --system-site-packages to access system-installed python3-gi
python3 -m venv --system-site-packages venv
source venv/bin/activate
pip install -r requirements.txt
```

3. **Run the application:**

```bash
python3 claude_drinking_bird.py
```

## Setup Reference Images

On first run, you'll be prompted to provide reference images. These are screenshots of the button/element that should trigger auto-approval.

1. Take a screenshot of the "Yes" or approval button in Claude Code
2. Crop it to just the button
3. Save it to: `~/.config/claude-drinking-bird/reference_images/`

You can add multiple reference images for different themes or button states.

**Tip**: Use a tool like `gnome-screenshot -a` to capture a specific area.

## Usage

### Starting the Application

```bash
claude-drinking-bird
```

### System Tray Controls

Click the circle icon in the top bar to access:
- **Status**: Shows current state (Active/Paused/Disabled)
- **Enable/Disable**: Toggle auto-approval on/off
- **Capture Area**: Shows current scan region (default: focused window)
- **Set Custom Area...**: Click and drag to select a custom fixed scan region
- **Reset to Default**: Restore scanning within the focused window bounds
- **Exit**: Completely close the application

## Enable Autostart on Boot

### Option 1: Using the helper script

```bash
# Enable autostart
claude-drinking-bird-autostart enable

# Disable autostart
claude-drinking-bird-autostart disable

# Check status
claude-drinking-bird-autostart status
```

### Option 2: Using GNOME Tweaks

1. Install GNOME Tweaks: `sudo apt install gnome-tweaks`
2. Open GNOME Tweaks
3. Go to "Startup Applications"
4. Enable "Claude Drinking Bird"

### Option 3: Manual Edit

Edit `~/.config/autostart/claude-drinking-bird.desktop` and change:
```
X-GNOME-Autostart-enabled=false
```
to:
```
X-GNOME-Autostart-enabled=true
```

## Configuration

Edit the configuration variables at the top of `claude_drinking_bird.py`:

```python
# Timing
SCAN_INTERVAL_MS = 500      # Check every 500ms
COOLDOWN_SECONDS = 1.0      # Wait after approval

# Matching
CONFIDENCE_THRESHOLD = 0.9  # Image matching confidence
```

### Scan Area Behavior

By default, the tool scans only within the bounds of the currently focused window. This reduces CPU usage and prevents false positives from other applications.

You can set a custom fixed scan region via the system tray menu ("Set Custom Area..."). This is useful if:
- You want to scan a specific portion of the screen regardless of window position
- The focused window detection isn't working correctly for your setup

Custom regions are saved to `~/.config/claude-drinking-bird/config.json` and persist across restarts.

## Troubleshooting

### Application doesn't start

1. Ensure all dependencies are installed
2. Check if `~/.local/bin` is in your PATH:
   ```bash
   echo $PATH | grep -q "$HOME/.local/bin" || echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
   source ~/.bashrc
   ```

### Not detecting prompts

1. Verify reference images are in `~/.config/claude-drinking-bird/reference_images/`
2. Try lowering `CONFIDENCE_THRESHOLD` (e.g., 0.8)
3. Ensure the Claude window is focused (the tool only scans within the focused window by default)
4. If using a custom scan area, verify it covers where the button appears
5. Take a new screenshot of the button at your current resolution/scaling

### System tray icon not showing

1. Install the AppIndicator extension for GNOME:
   ```bash
   sudo apt install gnome-shell-extension-appindicator
   ```
2. Enable it using GNOME Extensions app or Tweaks
3. Log out and log back in

### High CPU usage

1. Increase `SCAN_INTERVAL_MS` (e.g., 1000 for 1 second)
2. Use the default scan behavior (focused window only) rather than a custom full-screen region

## Uninstall

```bash
# Remove installed files
rm -rf ~/.local/share/claude-drinking-bird
rm -f ~/.local/bin/claude-drinking-bird
rm -f ~/.local/bin/claude-drinking-bird-autostart
rm -f ~/.local/share/applications/claude-drinking-bird.desktop
rm -f ~/.config/autostart/claude-drinking-bird.desktop

# Optionally remove configuration (keeps your reference images)
rm -rf ~/.config/claude-drinking-bird
```

## License

MIT License - Use at your own risk.

## Disclaimer

This tool automatically approves permission prompts. Use responsibly and understand the security implications of auto-approving actions.
