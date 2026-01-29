#!/usr/bin/env python3
"""
Claude Drinking Bird - Auto-approves Claude Code permission prompts.

A background tool that monitors the screen for permission prompts and
automatically approves them when a Claude window is in focus.
"""

import os
import sys
import time
import signal
import threading
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
import subprocess

import pyautogui
from PIL import Image

# Try to import pynput for global hotkey support
try:
    from pynput import keyboard
    from pynput.keyboard import Key
    HAS_PYNPUT = True
except ImportError:
    HAS_PYNPUT = False
    print("Warning: pynput not available. Hotkey support disabled.")

# Try to import AppIndicator3 for Ubuntu top bar integration
try:
    import gi
    gi.require_version('Gtk', '3.0')
    gi.require_version('AppIndicator3', '0.1')
    from gi.repository import Gtk, AppIndicator3, GLib
    HAS_INDICATOR = True
except (ImportError, ValueError):
    HAS_INDICATOR = False
    print("Warning: AppIndicator3 not available. Running without system tray.")

# ============================================================================
# CONFIGURATION - Adjust these values as needed
# ============================================================================

# Timing configuration
SCAN_INTERVAL_MS = 500      # Check every 500ms
COOLDOWN_SECONDS = 1.0      # Wait 1 second after sending Enter

# Image matching
CONFIDENCE_THRESHOLD = 0.9  # Matching confidence (0.0 to 1.0)

# Hotkey configuration (set to None to disable hotkey)
# Modifiers: Key.cmd (Super), Key.shift, Key.ctrl, Key.alt
# Default: Super+Shift+A
if HAS_PYNPUT:
    HOTKEY_MODIFIERS = frozenset([Key.shift, Key.alt])  # Shift+Alt
    HOTKEY_KEY = 'y'
else:
    HOTKEY_MODIFIERS = None
    HOTKEY_KEY = None

# Reference images directory
CONFIG_DIR = Path.home() / ".config" / "claude-drinking-bird"
IMAGES_DIR = CONFIG_DIR / "reference_images"
CONFIG_FILE = CONFIG_DIR / "config.json"

# Claude window detection - window title prefix
CLAUDE_WINDOW_PREFIX = "✳"

# ============================================================================
# GLOBAL STATE
# ============================================================================

class AppState:
    """Global application state."""
    def __init__(self):
        self.running = True
        self.enabled = False  # Start in 'off' state
        self.paused = False  # True when Claude window not in focus
        self.last_approve_time = 0
        self.indicator = None
        self.status_item = None
        self.toggle_item = None  # Reference to toggle menu item
        self.capture_area_item = None
        self.custom_region = None  # (x, y, width, height) or None for focused window
        self.lock = threading.Lock()
        self.hotkey_listener = None
        self.current_keys = set()  # Currently pressed keys for hotkey detection

state = AppState()

# ============================================================================
# HOTKEY HANDLING
# ============================================================================

def toggle_enabled():
    """Toggle the enabled state. Called from menu or hotkey."""
    with state.lock:
        state.enabled = not state.enabled
        enabled = state.enabled

    status = "enabled" if enabled else "disabled"
    print(f"[{time.strftime('%H:%M:%S')}] Auto-approve {status}")

    # Update menu item if available
    if HAS_INDICATOR and state.toggle_item:
        def update_menu():
            state.toggle_item.set_label("Disable" if enabled else "Enable")
        GLib.idle_add(update_menu)

    update_indicator_icon()

def on_hotkey_press(key):
    """Handle key press for hotkey detection."""
    if not HOTKEY_MODIFIERS or not HOTKEY_KEY:
        return

    # Normalize the key
    try:
        # For regular character keys
        if hasattr(key, 'char') and key.char:
            state.current_keys.add(key.char.lower())
        else:
            # For special keys (shift, ctrl, etc.)
            state.current_keys.add(key)
    except AttributeError:
        state.current_keys.add(key)

    # Check if hotkey combination is pressed
    modifiers_pressed = HOTKEY_MODIFIERS.issubset(state.current_keys)
    key_pressed = HOTKEY_KEY.lower() in state.current_keys

    if modifiers_pressed and key_pressed:
        toggle_enabled()
        # Clear to prevent repeated triggers
        state.current_keys.clear()

def on_hotkey_release(key):
    """Handle key release for hotkey detection."""
    try:
        if hasattr(key, 'char') and key.char:
            state.current_keys.discard(key.char.lower())
        else:
            state.current_keys.discard(key)
    except AttributeError:
        state.current_keys.discard(key)

def start_hotkey_listener():
    """Start the global hotkey listener."""
    if not HAS_PYNPUT or not HOTKEY_MODIFIERS or not HOTKEY_KEY:
        return None

    listener = keyboard.Listener(
        on_press=on_hotkey_press,
        on_release=on_hotkey_release
    )
    listener.start()
    return listener

# ============================================================================
# CONFIGURATION FILE
# ============================================================================

def load_config() -> Dict[str, Any]:
    """Load configuration from file."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load config: {e}")
    return {}

def save_config(config: Dict[str, Any]):
    """Save configuration to file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not save config: {e}")

def load_custom_region():
    """Load custom scan region from config."""
    config = load_config()
    region = config.get('scan_region')
    if region and len(region) == 4:
        state.custom_region = tuple(region)
        print(f"Loaded custom scan region: {state.custom_region}")
    else:
        state.custom_region = None

# ============================================================================
# ICON GENERATION
# ============================================================================

def create_circle_icon(color: str, size: int = 22) -> str:
    """Create a circle icon and save it to config directory."""
    icons_dir = CONFIG_DIR / "icons"
    icons_dir.mkdir(parents=True, exist_ok=True)

    icon_path = icons_dir / f"circle_{color}.png"

    # Create a simple circle icon using PIL
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))

    # Draw a filled circle
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)

    colors = {
        'green': (76, 175, 80, 255),
        'yellow': (255, 193, 7, 255),
        'red': (244, 67, 54, 255),
    }

    fill_color = colors.get(color, colors['red'])

    # Draw circle with a slight border
    margin = 2
    draw.ellipse([margin, margin, size - margin - 1, size - margin - 1],
                 fill=fill_color, outline=(50, 50, 50, 255))

    img.save(str(icon_path))
    return str(icon_path)

def ensure_icons_exist():
    """Create all necessary icons."""
    for color in ['green', 'yellow', 'red']:
        create_circle_icon(color)

# ============================================================================
# REFERENCE IMAGE MANAGEMENT
# ============================================================================

def get_reference_images() -> List[Path]:
    """Get list of reference image paths."""
    if not IMAGES_DIR.exists():
        return []

    images = []
    for ext in ['*.png', '*.jpg', '*.jpeg', '*.bmp']:
        images.extend(IMAGES_DIR.glob(ext))

    return sorted(images)

def setup_reference_images():
    """Interactive setup for reference images."""
    print("\n" + "=" * 60)
    print("Claude Drinking Bird - First Run Setup")
    print("=" * 60)
    print("\nNo reference images found.")
    print(f"Reference images should be placed in: {IMAGES_DIR}")
    print("\nThese images are what the tool looks for on screen to auto-approve.")
    print("You can add multiple reference images for different button appearances.")

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    while True:
        print("\nOptions:")
        print("  1. Enter path to a reference image to copy")
        print("  2. Open the reference images folder")
        print("  3. Continue (after manually adding images)")
        print("  4. Exit")

        choice = input("\nChoice [1-4]: ").strip()

        if choice == '1':
            path = input("Enter path to reference image: ").strip()
            path = os.path.expanduser(path)

            if os.path.exists(path):
                import shutil
                dest = IMAGES_DIR / os.path.basename(path)
                shutil.copy(path, dest)
                print(f"Copied to: {dest}")
            else:
                print(f"File not found: {path}")

        elif choice == '2':
            subprocess.run(['xdg-open', str(IMAGES_DIR)], check=False)
            print(f"Opened: {IMAGES_DIR}")

        elif choice == '3':
            images = get_reference_images()
            if images:
                print(f"\nFound {len(images)} reference image(s):")
                for img in images:
                    print(f"  - {img.name}")
                return True
            else:
                print("\nNo images found yet. Please add at least one reference image.")

        elif choice == '4':
            return False

        else:
            print("Invalid choice.")

    return False

# ============================================================================
# SCREEN SCANNING
# ============================================================================

def get_focused_window_geometry() -> Optional[tuple]:
    """
    Get the geometry of the currently focused window.
    Returns (x, y, width, height) or None if unable to determine.
    """
    try:
        # Get the active window ID
        result = subprocess.run(
            ['xdotool', 'getactivewindow'],
            capture_output=True,
            text=True,
            timeout=1
        )
        if result.returncode != 0:
            return None

        window_id = result.stdout.strip()

        # Get window geometry
        result = subprocess.run(
            ['xdotool', 'getwindowgeometry', '--shell', window_id],
            capture_output=True,
            text=True,
            timeout=1
        )
        if result.returncode != 0:
            return None

        # Parse output like: X=100\nY=200\nWIDTH=800\nHEIGHT=600\n...
        geometry = {}
        for line in result.stdout.strip().split('\n'):
            if '=' in line:
                key, value = line.split('=', 1)
                geometry[key] = int(value)

        if all(k in geometry for k in ['X', 'Y', 'WIDTH', 'HEIGHT']):
            return (geometry['X'], geometry['Y'], geometry['WIDTH'], geometry['HEIGHT'])
        return None
    except Exception:
        return None


def is_claude_window_focused() -> Optional[bool]:
    """
    Check if a Claude Code window is currently focused.
    Returns True/False for definite answer, None if unable to determine.
    """
    try:
        # Use xdotool to get the active window title
        result = subprocess.run(
            ['xdotool', 'getactivewindow', 'getwindowname'],
            capture_output=True,
            text=True,
            timeout=1
        )
        if result.returncode == 0:
            title = result.stdout.strip()
            return title.startswith(CLAUDE_WINDOW_PREFIX)
        # Non-zero return code (e.g., no window focused) - treat as not focused
        return False
    except subprocess.TimeoutExpired:
        # Timeout - can't determine, return None
        return None
    except Exception:
        # Other error - can't determine, return None
        return None

def find_permission_prompt(reference_images: List[Path]) -> Optional[tuple]:
    """
    Search for any of the reference images in the focused window.
    Returns the center coordinates if found, None otherwise.
    """
    # Use custom region if set, otherwise use focused window geometry
    if state.custom_region:
        region = state.custom_region
    else:
        region = get_focused_window_geometry()

    for ref_image_path in reference_images:
        try:
            location = pyautogui.locateOnScreen(
                str(ref_image_path),
                confidence=CONFIDENCE_THRESHOLD,
                region=region
            )

            if location:
                center = pyautogui.center(location)
                return (center.x, center.y)

        except pyautogui.ImageNotFoundException:
            continue
        except Exception as e:
            print(f"Error scanning for {ref_image_path.name}: {e}")
            continue

    return None

def play_approval_sound():
    """Play a sound to indicate auto-approval."""
    try:
        # Try using paplay (PulseAudio) with system sounds
        sound_paths = [
            "/usr/share/sounds/freedesktop/stereo/complete.oga",
            "/usr/share/sounds/freedesktop/stereo/message.oga",
            "/usr/share/sounds/gnome/default/alerts/drip.ogg",
            "/usr/share/sounds/sound-icons/prompt.wav",
        ]

        for sound_path in sound_paths:
            if os.path.exists(sound_path):
                subprocess.Popen(
                    ['paplay', sound_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                return

        # Fallback: terminal bell
        print('\a', end='', flush=True)

    except Exception:
        # Silent fallback
        pass

def send_enter_key():
    """Send Enter keypress to approve the prompt."""
    pyautogui.press('enter')

def select_capture_area() -> Optional[tuple]:
    """
    Use slop to interactively select a screen region.
    Returns (x, y, width, height) or None if cancelled.
    """
    try:
        print(f"[{time.strftime('%H:%M:%S')}] Select capture area (click and drag to select, Esc to cancel)")
        # slop confirms on mouse release by default
        # -f: format string, -c: selection color (RGBA), -b: border width
        result = subprocess.run(
            ['slop', '-f', '%x %y %w %h', '-c', '0.3,0.5,0.8,0.4', '-b', '3'],
            capture_output=True,
            text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split()
            if len(parts) == 4:
                x, y, w, h = map(int, parts)
                if w > 10 and h > 10:  # Minimum size check
                    return (x, y, w, h)
        print(f"[{time.strftime('%H:%M:%S')}] Selection cancelled or invalid")
        return None
    except FileNotFoundError:
        print(f"[{time.strftime('%H:%M:%S')}] Error: slop not installed. Run: sudo apt install slop")
        return None
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] Error selecting area: {e}")
        return None

# ============================================================================
# INDICATOR (SYSTEM TRAY)
# ============================================================================

def update_indicator_icon():
    """Update the indicator icon based on current state."""
    if not HAS_INDICATOR or not state.indicator:
        return

    # Capture state NOW before scheduling GTK update (fixes race condition)
    with state.lock:
        enabled = state.enabled
        paused = state.paused

    # Determine color and status text based on captured state
    if not enabled:
        color = 'red'
        status_text = "Status: Disabled"
    elif paused:
        color = 'yellow'
        status_text = "Status: Paused (Claude not focused)"
    else:
        color = 'green'
        status_text = "Status: Active"

    def do_update(color=color, status_text=status_text):
        icon_path = str(CONFIG_DIR / "icons" / f"circle_{color}.png")
        state.indicator.set_icon_full(icon_path, f"Claude Drinking Bird - {color}")

        if state.status_item:
            state.status_item.set_label(status_text)

    GLib.idle_add(do_update)

def on_toggle_clicked(_):
    """Handle toggle on/off from menu."""
    toggle_enabled()

def on_quit_clicked(_):
    """Handle quit button."""
    print(f"\n[{time.strftime('%H:%M:%S')}] Exiting...")
    state.running = False
    if HAS_INDICATOR:
        Gtk.main_quit()

def on_set_capture_area_clicked(_):
    """Handle set capture area button."""
    # Temporarily disable scanning
    was_enabled = state.enabled
    with state.lock:
        state.enabled = False
    update_indicator_icon()

    # Run slop in a separate thread to not block GTK
    def do_selection():
        region = select_capture_area()
        if region:
            state.custom_region = region
            # Save to config
            config = load_config()
            config['scan_region'] = list(region)
            save_config(config)
            print(f"[{time.strftime('%H:%M:%S')}] Capture area set to: {region}")
            # Update menu item
            GLib.idle_add(update_capture_area_menu)
        else:
            print(f"[{time.strftime('%H:%M:%S')}] Capture area unchanged")

        # Restore previous enabled state
        with state.lock:
            state.enabled = was_enabled
        GLib.idle_add(update_indicator_icon)

    thread = threading.Thread(target=do_selection, daemon=True)
    thread.start()

def on_reset_capture_area_clicked(_):
    """Handle reset capture area button."""
    state.custom_region = None
    config = load_config()
    if 'scan_region' in config:
        del config['scan_region']
        save_config(config)
    print(f"[{time.strftime('%H:%M:%S')}] Capture area reset to default")
    update_capture_area_menu()

def update_capture_area_menu():
    """Update the capture area menu item text."""
    if state.capture_area_item:
        if state.custom_region:
            x, y, w, h = state.custom_region
            state.capture_area_item.set_label(f"Capture Area: {w}x{h} at ({x},{y})")
        else:
            state.capture_area_item.set_label("Capture Area: Default")

def create_indicator():
    """Create the AppIndicator for the system tray."""
    if not HAS_INDICATOR:
        return None

    ensure_icons_exist()

    icon_path = str(CONFIG_DIR / "icons" / "circle_red.png")

    indicator = AppIndicator3.Indicator.new(
        "claude-drinking-bird",
        icon_path,
        AppIndicator3.IndicatorCategory.APPLICATION_STATUS
    )

    indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
    indicator.set_title("Claude Drinking Bird")

    # Create menu
    menu = Gtk.Menu()

    # Status item (non-clickable)
    status_item = Gtk.MenuItem(label="Status: Disabled")
    status_item.set_sensitive(False)
    menu.append(status_item)
    state.status_item = status_item

    # Separator
    menu.append(Gtk.SeparatorMenuItem())

    # Toggle item
    toggle_item = Gtk.MenuItem(label="Enable")
    toggle_item.connect("activate", on_toggle_clicked)
    menu.append(toggle_item)
    state.toggle_item = toggle_item

    # Separator
    menu.append(Gtk.SeparatorMenuItem())

    # Capture area info (non-clickable)
    capture_area_item = Gtk.MenuItem(label="Capture Area: Default")
    capture_area_item.set_sensitive(False)
    menu.append(capture_area_item)
    state.capture_area_item = capture_area_item

    # Set capture area
    set_area_item = Gtk.MenuItem(label="Set Custom Area...")
    set_area_item.connect("activate", on_set_capture_area_clicked)
    menu.append(set_area_item)

    # Reset capture area
    reset_area_item = Gtk.MenuItem(label="Reset to Default")
    reset_area_item.connect("activate", on_reset_capture_area_clicked)
    menu.append(reset_area_item)

    # Separator
    menu.append(Gtk.SeparatorMenuItem())

    # Quit item
    quit_item = Gtk.MenuItem(label="Exit")
    quit_item.connect("activate", on_quit_clicked)
    menu.append(quit_item)

    menu.show_all()
    indicator.set_menu(menu)

    return indicator

# ============================================================================
# MAIN LOOP
# ============================================================================

def scanner_loop(reference_images: List[Path]):
    """Main scanning loop running in a background thread."""
    print(f"[{time.strftime('%H:%M:%S')}] Scanner started (disabled by default)")
    print(f"  - Monitoring {len(reference_images)} reference image(s)")
    print(f"  - Scan interval: {SCAN_INTERVAL_MS}ms")
    print(f"  - Confidence threshold: {CONFIDENCE_THRESHOLD}")
    print(f"  - Cooldown: {COOLDOWN_SECONDS}s")

    if state.custom_region:
        x, y, w, h = state.custom_region
        print(f"  - Scan area: custom region {w}x{h} at ({x},{y})")
    else:
        print(f"  - Scan area: focused window")

    print(f"\nClick the system tray icon to enable. Press Ctrl+C to exit.\n")

    while state.running:
        try:
            with state.lock:
                enabled = state.enabled

            if not enabled:
                time.sleep(SCAN_INTERVAL_MS / 1000)
                continue

            # Check if Claude window is focused
            claude_focused = is_claude_window_focused()

            with state.lock:
                was_paused = state.paused
                # Only update pause state if we got a definite answer
                # If None (couldn't determine), keep previous state
                if claude_focused is not None:
                    state.paused = not claude_focused

            # Update icon if pause state changed
            if was_paused != state.paused:
                if state.paused:
                    print(f"[{time.strftime('%H:%M:%S')}] Paused - Claude window not in focus")
                else:
                    print(f"[{time.strftime('%H:%M:%S')}] Resumed - Claude window focused")
                update_indicator_icon()

            if state.paused:
                time.sleep(SCAN_INTERVAL_MS / 1000)
                continue

            # Check cooldown
            current_time = time.time()
            if current_time - state.last_approve_time < COOLDOWN_SECONDS:
                time.sleep(SCAN_INTERVAL_MS / 1000)
                continue

            # Scan for permission prompt
            location = find_permission_prompt(reference_images)

            if location:
                print(f"[{time.strftime('%H:%M:%S')}] Permission prompt detected at {location}")

                # Send Enter to approve
                send_enter_key()

                print(f"[{time.strftime('%H:%M:%S')}] AUTO-APPROVED! Sent Enter key")
                play_approval_sound()

                state.last_approve_time = time.time()

                # Wait for cooldown before next scan
                time.sleep(COOLDOWN_SECONDS)
            else:
                time.sleep(SCAN_INTERVAL_MS / 1000)

        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] Scanner error: {e}")
            time.sleep(1)

def main():
    """Main entry point."""
    print("Claude Drinking Bird")
    print("=" * 40)

    # Ensure config directory exists
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # Load saved configuration
    load_custom_region()

    # Check for reference images
    reference_images = get_reference_images()

    if not reference_images:
        if not setup_reference_images():
            print("Setup cancelled. Exiting.")
            sys.exit(1)

        reference_images = get_reference_images()

        if not reference_images:
            print("No reference images configured. Exiting.")
            sys.exit(1)

    print(f"\nLoaded {len(reference_images)} reference image(s):")
    for img in reference_images:
        print(f"  - {img.name}")

    # Set up signal handler for graceful shutdown
    def signal_handler(sig, frame):
        print(f"\n[{time.strftime('%H:%M:%S')}] Received interrupt signal")
        state.running = False
        if HAS_INDICATOR:
            GLib.idle_add(Gtk.main_quit)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create indicator
    if HAS_INDICATOR:
        state.indicator = create_indicator()
        # Update capture area display if custom region loaded
        if state.custom_region:
            update_capture_area_menu()

    # Start hotkey listener
    if HAS_PYNPUT and HOTKEY_MODIFIERS and HOTKEY_KEY:
        state.hotkey_listener = start_hotkey_listener()
        print(f"\nHotkey: Shift+Alt+{HOTKEY_KEY.upper()} to toggle on/off")
    else:
        print("\nHotkey: disabled (pynput not available)")

    # Start scanner thread
    scanner_thread = threading.Thread(target=scanner_loop, args=(reference_images,), daemon=True)
    scanner_thread.start()

    # Run GTK main loop (or simple loop if no indicator)
    if HAS_INDICATOR:
        try:
            Gtk.main()
        except KeyboardInterrupt:
            pass
    else:
        try:
            while state.running:
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass

    state.running = False
    print(f"\n[{time.strftime('%H:%M:%S')}] Goodbye!")

if __name__ == "__main__":
    main()
