import ctypes
import ctypes.wintypes
import json
import os
import subprocess
import sys
import threading
import time

import psutil
import pystray
from PIL import Image, ImageDraw, ImageFont
from pypresence import Presence

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

APP_MAP = [
    ("nvim.exe",            "Editing",   "Neovim",            "coding"),
    ("Code.exe",            "Editing",   "VS Code",           "coding"),
    ("zed.exe",             "Editing",   "Zed",               "coding"),
    ("WindowsTerminal.exe", "Terminal",  "Windows Terminal",  "terminal"),
    ("powershell.exe",      "Terminal",  "PowerShell",        "terminal"),
    ("pwsh.exe",            "Terminal",  "PowerShell Core",   "terminal"),
    ("cmd.exe",             "Terminal",  "Command Prompt",    "terminal"),
    ("steam.exe",           "Gaming",    "Steam",             "steam"),
    ("Obsidian.exe",        "Writing",   "Obsidian",          "coding"),
    ("blender.exe",         "3D Work",   "Blender",           "coding"),
    ("firefox.exe",         "Browsing",  "Firefox",           "firefox"),
    ("librewolf.exe",       "Browsing",  "LibreWolf",         "firefox"),
    ("chrome.exe",          "Browsing",  "Chrome",            "firefox"),
]

DEFAULT_CONFIG = {
    "discord_app_id": "",
    "idle_detection": True,
    "idle_threshold_seconds": 300,
    "window_detection": True,
}

CONFIG_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "jellyrpc")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

POLL_SECS = 5
DEBOUNCE_COUNT = 2
RECONNECT_INTERVAL = 30

# ---------------------------------------------------------------------------
# Idle detection (Windows API)
# ---------------------------------------------------------------------------

class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.wintypes.UINT),
        ("dwTime", ctypes.wintypes.DWORD),
    ]


def get_idle_ms() -> int:
    lii = _LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(_LASTINPUTINFO)
    ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii))
    return ctypes.windll.kernel32.GetTickCount() - lii.dwTime


def is_idle(threshold_seconds: int) -> bool:
    return get_idle_ms() >= threshold_seconds * 1000


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_config() -> dict:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "w") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
        return dict(DEFAULT_CONFIG)
    with open(CONFIG_PATH, "r") as f:
        data = json.load(f)
    merged = dict(DEFAULT_CONFIG)
    merged.update(data)
    return merged


# ---------------------------------------------------------------------------
# Discord RPC manager
# ---------------------------------------------------------------------------

class RPCManager:
    def __init__(self, app_id: str):
        self.app_id = app_id
        self._rpc: Presence | None = None
        self.connected = False
        self._last_attempt = 0.0

    def ensure_connected(self) -> bool:
        if self.connected:
            return True
        if not self.app_id:
            return False
        now = time.monotonic()
        if now - self._last_attempt < RECONNECT_INTERVAL:
            return False
        self._last_attempt = now
        try:
            self._rpc = Presence(self.app_id)
            self._rpc.connect()
            self.connected = True
        except Exception:
            self.connected = False
        return self.connected

    def update(self, **kwargs) -> None:
        if not self.connected or self._rpc is None:
            return
        try:
            self._rpc.update(**kwargs)
        except Exception:
            self._mark_disconnected()

    def clear(self) -> None:
        if not self.connected or self._rpc is None:
            return
        try:
            self._rpc.clear()
        except Exception:
            self._mark_disconnected()

    def close(self) -> None:
        if self._rpc is not None:
            try:
                self._rpc.close()
            except Exception:
                pass
        self.connected = False

    def _mark_disconnected(self) -> None:
        self.connected = False
        try:
            if self._rpc:
                self._rpc.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Debounce
# ---------------------------------------------------------------------------

class DebounceState:
    def __init__(self, required: int = DEBOUNCE_COUNT):
        self._required = required
        self._candidate = None
        self._count = 0
        self.confirmed = None

    def feed(self, new_state) -> bool:
        if new_state == self._candidate:
            self._count += 1
        else:
            self._candidate = new_state
            self._count = 1
        if self._count >= self._required and new_state != self.confirmed:
            self.confirmed = new_state
            return True
        return False


# ---------------------------------------------------------------------------
# Process detection
# ---------------------------------------------------------------------------

_EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)


def _get_pids_with_visible_windows() -> set[int]:
    pids: set[int] = set()

    def _cb(hwnd, _):
        if ctypes.windll.user32.IsWindowVisible(hwnd):
            pid = ctypes.wintypes.DWORD()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            pids.add(pid.value)
        return True

    ctypes.windll.user32.EnumWindows(_EnumWindowsProc(_cb), 0)
    return pids


def detect_active_app():
    try:
        visible_pids = _get_pids_with_visible_windows()
        procs = {p.name(): p.pid for p in psutil.process_iter(["name", "pid"])
                 if p.pid in visible_pids}
    except Exception:
        return None, None

    for proc_name, activity, display_name, icon_key in APP_MAP:
        if proc_name in procs:
            return proc_name, (activity, display_name, icon_key)

    # GIMP version-independent detection
    for name in procs:
        if name.lower().startswith("gimp-"):
            return name, ("Editing", "GIMP", "coding")

    return None, None


# ---------------------------------------------------------------------------
# Presence updates
# ---------------------------------------------------------------------------

_start_time = int(time.time())


def apply_presence(rpc: RPCManager, state, info) -> None:
    if state is None:
        rpc.clear()
        return
    if state == "idle":
        rpc.update(state="Away from keyboard", large_image="idle", large_text="Idle")
        return
    activity, display_name, icon_key = info
    rpc.update(
        details=display_name,
        state=activity,
        start=_start_time,
        large_image=icon_key,
        large_text=display_name,
    )


# ---------------------------------------------------------------------------
# Tray icon image
# ---------------------------------------------------------------------------

def create_tray_image(size: int = 64) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([(2, 2), (size - 2, size - 2)], fill=(123, 47, 190, 255))

    font = ImageFont.load_default()
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", int(size * 0.55))
    except OSError:
        pass

    text = "J"
    bbox = draw.textbbox((0, 0), text, font=font)
    x = (size - (bbox[2] - bbox[0])) / 2 - bbox[0]
    y = (size - (bbox[3] - bbox[1])) / 2 - bbox[1]
    draw.text((x, y), text, fill=(255, 255, 255, 255), font=font)
    return img


# ---------------------------------------------------------------------------
# Autostart
# ---------------------------------------------------------------------------

def _startup_lnk_path() -> str:
    startup = os.path.join(
        os.environ.get("APPDATA", ""),
        "Microsoft", "Windows", "Start Menu", "Programs", "Startup",
    )
    return os.path.join(startup, "jellyrpc.lnk")


def is_autostart_enabled() -> bool:
    return os.path.exists(_startup_lnk_path())


def add_autostart() -> None:
    import win32com.client
    pythonw = sys.executable.replace("python.exe", "pythonw.exe")
    if not os.path.exists(pythonw):
        pythonw = sys.executable
    shell = win32com.client.Dispatch("WScript.Shell")
    lnk = shell.CreateShortcut(_startup_lnk_path())
    lnk.TargetPath = pythonw
    lnk.Arguments = f'"{os.path.abspath(__file__)}"'
    lnk.WorkingDirectory = os.path.dirname(os.path.abspath(__file__))
    lnk.Description = "JellyRPC Discord Rich Presence"
    lnk.save()


def remove_autostart() -> None:
    path = _startup_lnk_path()
    if os.path.exists(path):
        os.remove(path)


# ---------------------------------------------------------------------------
# Tray callbacks
# ---------------------------------------------------------------------------

def cb_open_config(icon, item) -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    subprocess.Popen(["explorer", CONFIG_DIR])


def cb_toggle_autostart(icon, item) -> None:
    if is_autostart_enabled():
        remove_autostart()
    else:
        add_autostart()


def cb_quit(icon, item, stop_event: threading.Event) -> None:
    stop_event.set()
    icon.stop()


# ---------------------------------------------------------------------------
# Polling loop (background thread)
# ---------------------------------------------------------------------------

def polling_loop(stop_event: threading.Event) -> None:
    config = load_config()
    rpc = RPCManager(config["discord_app_id"])
    debounce = DebounceState()

    while not stop_event.wait(timeout=POLL_SECS):
        if not rpc.ensure_connected():
            continue

        if config["idle_detection"] and is_idle(config["idle_threshold_seconds"]):
            new_state = "idle"
            info = None
        elif config["window_detection"]:
            proc_name, info = detect_active_app()
            new_state = proc_name
        else:
            new_state = None
            info = None

        if debounce.feed(new_state):
            apply_presence(rpc, debounce.confirmed, info)

    rpc.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    stop_event = threading.Event()

    bg = threading.Thread(target=polling_loop, args=(stop_event,), daemon=True)
    bg.start()

    image = create_tray_image()

    menu = pystray.Menu(
        pystray.MenuItem("jellyrpc", None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Open Config Folder", cb_open_config),
        pystray.MenuItem(
            "Start with Windows",
            lambda icon, item: cb_toggle_autostart(icon, item),
            checked=lambda item: is_autostart_enabled(),
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", lambda icon, item: cb_quit(icon, item, stop_event)),
    )

    icon = pystray.Icon("jellyrpc", image, "jellyrpc", menu)
    icon.run()

    bg.join(timeout=POLL_SECS + 1)


if __name__ == "__main__":
    main()
