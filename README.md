# jellyrpc-windows

Discord Rich Presence for Windows — window detection and idle state.

Windows port of [jellyrpc](https://github.com/tiiow-fedora/jellyrpc). Runs as a system tray app with no console window.

## How it works

```
Discord ← pypresence IPC ← jellyrpc.py
                               ├── idle > 5 min?              → "Away from keyboard"
                               └── visible window in APP_MAP  → show app activity
```

App detection uses `psutil` in priority order — editor beats terminal, terminal beats browser. Only apps with a **visible window** are detected; background processes are ignored. Edit `APP_MAP` in `jellyrpc.py` to add or reorder apps.

## Install

```bat
git clone https://github.com/tiiow-fedora/jellyrpc-windows
cd jellyrpc-windows
install.bat
```

Then fill in your config — right-click the tray icon → **Open Config Folder**, then edit `config.json`:

```json
{
  "discord_app_id": "YOUR_DISCORD_APP_ID",
  "idle_detection": true,
  "idle_threshold_seconds": 300,
  "window_detection": true
}
```

Restart the app after saving (right-click tray → **Quit**, then run `pythonw jellyrpc.py` again).

### Getting a Discord App ID

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications)
2. New Application → name it whatever you want shown in Discord (e.g. "Windows")
3. Copy the Application ID from the General Information page

### Uploading Rich Presence Art Assets

jellyrpc uses named image keys for each activity. You must upload the icons manually in your browser — this cannot be automated.

**Steps:**

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications) and open your application
2. Click **Rich Presence** → **Art Assets** in the left sidebar
3. Upload each PNG with the exact key name listed below

| Key name (must match exactly) | Used for |
|-------------------------------|----------|
| `coding` | VS Code, Neovim, Zed, Obsidian, GIMP, Blender |
| `terminal` | Windows Terminal, PowerShell, cmd |
| `steam` | Steam |
| `firefox` | Firefox, LibreWolf, Chrome |
| `idle` | Idle state |

The key names must match exactly — they map directly to the `large_image` values in `APP_MAP`.

### Dependencies

| Package | Purpose |
|---------|---------|
| `pypresence` | Discord IPC |
| `psutil` | Process and window detection |
| `pystray` | System tray icon |
| `Pillow` | Tray icon rendering |
| `pywin32` | Windows API (idle detection, autostart) |

`install.bat` installs all of these automatically via pip.

## Config

`%APPDATA%\jellyrpc\config.json`:

| Key | Default | Description |
|-----|---------|-------------|
| `discord_app_id` | `""` | **Required.** Your Discord application ID. |
| `idle_detection` | `true` | Show "Away from keyboard" after idle threshold. |
| `idle_threshold_seconds` | `300` | Seconds of inactivity before idle state. |
| `window_detection` | `true` | Show current app activity. |

## Adding apps

Edit `APP_MAP` in `jellyrpc.py`:

```python
("Code.exe",   "Editing",  "VS Code", "coding"),
("steam.exe",  "Gaming",   "Steam",   "steam"),
```

Fields: `(process .exe name, state line, details line, large_image key)`. Priority order — put higher-priority entries first. Use the exact `.exe` name as shown in Task Manager.

## Autostart

Right-click the tray icon → **Start with Windows** to toggle. This adds or removes a shortcut in your Startup folder (`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup`).

> Windows 11 may hide the tray icon. Go to taskbar settings and set jellyrpc to always show.

## Update

```bat
git pull
install.bat
```

## Uninstall

1. Right-click tray icon → **Start with Windows** (uncheck if enabled) → **Quit**
2. Delete the `jellyrpc-windows` folder
3. Delete `%APPDATA%\jellyrpc` (your config)
