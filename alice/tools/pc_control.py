import ctypes
import subprocess
import logging

import psutil
from alice.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)

# Common app name → executable mapping for Windows
APP_MAP: dict[str, str] = {
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "firefox": "firefox.exe",
    "discord": "discord.exe",
    "spotify": "spotify.exe",
    "notepad": "notepad.exe",
    "explorer": "explorer.exe",
    "file explorer": "explorer.exe",
    "task manager": "taskmgr.exe",
    "cmd": "cmd.exe",
    "terminal": "wt.exe",
    "vs code": "code.exe",
    "vscode": "code.exe",
    "steam": "steam.exe",
    "vlc": "vlc.exe",
}


class PCControlTool(BaseTool):
    name = "pc_control"
    description = (
        "Control the PC: open an application, close a running process, "
        "adjust system volume, or lock the screen."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["open_app", "close_app", "set_volume", "lock_screen", "list_running"],
                "description": "Action to perform.",
            },
            "app_name": {
                "type": "string",
                "description": "App name (for open_app / close_app). E.g. 'chrome', 'discord'.",
            },
            "volume": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
                "description": "Volume level 0-100 (for set_volume).",
            },
        },
        "required": ["action"],
    }
    is_read_only = False
    requires_confirmation = False

    async def execute(self, action: str, app_name: str = "", volume: int = 50, **_) -> ToolResult:
        if action == "open_app":
            return self._open_app(app_name)
        if action == "close_app":
            return self._close_app(app_name)
        if action == "set_volume":
            return self._set_volume(volume)
        if action == "lock_screen":
            return self._lock_screen()
        if action == "list_running":
            return self._list_running()
        return ToolResult(success=False, output="", error=f"Unknown action: {action}")

    def _open_app(self, name: str) -> ToolResult:
        if not name:
            return ToolResult(success=False, output="", error="No app name provided.")
        exe = APP_MAP.get(name.lower(), name)
        try:
            subprocess.Popen(exe, shell=True)
            return ToolResult(success=True, output=f"Opened {name}.")
        except Exception as exc:
            return ToolResult(success=False, output="", error=str(exc))

    def _close_app(self, name: str) -> ToolResult:
        if not name:
            return ToolResult(success=False, output="", error="No app name provided.")
        exe = APP_MAP.get(name.lower(), name)
        killed = []
        for proc in psutil.process_iter(["name", "pid"]):
            if proc.info["name"] and exe.lower() in proc.info["name"].lower():
                try:
                    proc.kill()
                    killed.append(proc.info["name"])
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        if killed:
            return ToolResult(success=True, output=f"Closed: {', '.join(killed)}.")
        return ToolResult(success=False, output="", error=f"No running process found for '{name}'.")

    def _set_volume(self, level: int) -> ToolResult:
        # Windows volume via nircmd (if available) or ctypes
        try:
            # Try nircmd first (lightweight Windows util)
            subprocess.run(
                ["nircmd.exe", "setsysvolume", str(int(level / 100 * 65535))],
                check=True, capture_output=True,
            )
            return ToolResult(success=True, output=f"Volume set to {level}%.")
        except FileNotFoundError:
            pass
        # Fallback: PowerShell
        try:
            script = f"[audio]::Volume = {level / 100}"
            subprocess.run(
                ["powershell", "-Command",
                 f"$obj = New-Object -ComObject WScript.Shell; "
                 f"$obj.SendKeys([char]174 * {max(0, 50 - level)})"],
                capture_output=True, timeout=5,
            )
            return ToolResult(success=True, output=f"Volume adjusted toward {level}%.")
        except Exception as exc:
            return ToolResult(success=False, output="", error=f"Volume control failed: {exc}")

    def _lock_screen(self) -> ToolResult:
        try:
            ctypes.windll.user32.LockWorkStation()
            return ToolResult(success=True, output="Screen locked.")
        except Exception as exc:
            return ToolResult(success=False, output="", error=str(exc))

    def _list_running(self) -> ToolResult:
        names = sorted(
            {p.info["name"] for p in psutil.process_iter(["name"]) if p.info["name"]},
            key=str.lower,
        )
        return ToolResult(success=True, output="\n".join(names[:50]))
