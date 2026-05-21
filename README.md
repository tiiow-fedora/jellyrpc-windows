# jellyrpc-windows

Discord Rich Presence for Windows. Shows what app you're using in your Discord status.

Windows port of [jellyrpc](https://github.com/tiiow-fedora/jellyrpc).

![Discord presence example showing VS Code]

---

## Detected apps

| App | Status shown |
|-----|-------------|
| VS Code | Editing — VS Code |
| Neovim | Editing — Neovim |
| Zed | Editing — Zed |
| Windows Terminal | Terminal — Windows Terminal |
| PowerShell / pwsh | Terminal — PowerShell |
| Command Prompt | Terminal — Command Prompt |
| Steam | Gaming — Steam |
| Obsidian | Writing — Obsidian |
| GIMP | Editing — GIMP |
| Blender | 3D Work — Blender |
| Firefox | Browsing — Firefox |
| LibreWolf | Browsing — LibreWolf |
| Chrome | Browsing — Chrome |

Only apps with a **visible window** are detected — background processes are ignored.

---

## Setup

### 1. Get a Discord App ID

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications)
2. Click **New Application** and give it a name
3. Copy the **Application ID** from the General Information page

### 2. Install

```bat
install.bat
```

This installs dependencies and launches the app. No console window will appear.

### 3. Set your App ID

On first launch, the app creates a config file at:

```
%APPDATA%\jellyrpc\config.json
```

Right-click the tray icon → **Open Config Folder**, then edit `config.json`:

```json
{
  "discord_app_id": "YOUR_APP_ID_HERE",
  "idle_detection": true,
  "idle_threshold_seconds": 300,
  "window_detection": true
}
```

Restart the app after saving.

---

## Tray icon

Right-click the purple **J** icon in your system tray:

- **Open Config Folder** — opens the config directory in Explorer
- **Start with Windows** — toggle autostart on login
- **Quit** — exit the app

> Windows 11 may hide the tray icon by default. Go to taskbar settings and set jellyrpc to always show.

---

## Requirements

- Python 3.10+
- Discord desktop app

Dependencies (installed automatically by `install.bat`):

```
pypresence
psutil
pystray
Pillow
pywin32
```

---

## Running manually

```bat
pythonw jellyrpc.py
```

Use `pythonw` (not `python`) to run without a console window.
