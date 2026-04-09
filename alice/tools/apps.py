"""Launch preset apps and arrange them side-by-side using Win32 API."""

import ctypes
import subprocess
import time
from alice.config import settings
from alice.tools.base import BaseTool, ToolResult

user32 = ctypes.windll.user32

# Mapping preset app names to executables
PRESET_EXECUTABLES: dict[str, str] = {
    "chrome": "chrome.exe",
    "spotify": "spotify.exe",
    "discord": "discord.exe",
    "steam": "steam.exe",
    "vlc": "vlc.exe",
    "vscode": "code.exe",
    "notepad": "notepad.exe",
    "explorer": "explorer.exe",
}


def _get_screen_size() -> tuple[int, int]:
    return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


class AppsTool(BaseTool):
    name = "launch_apps"
    description = (
        "Launch Chester's preset apps. Optionally arrange them side by side on screen. "
        "Use 'launch_preset' to open all configured apps, or 'launch_single' for one app."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["launch_preset", "launch_single", "tile_windows"],
                "description": "Action to perform.",
            },
            "app_name": {
                "type": "string",
                "description": "App name for launch_single (e.g. 'chrome', 'discord').",
            },
        },
        "required": ["action"],
    }
    is_read_only = False

    async def execute(self, action: str, app_name: str = "", **_) -> ToolResult:
        if action == "launch_preset":
            return self._launch_preset()
        if action == "launch_single":
            return self._launch_single(app_name)
        if action == "tile_windows":
            return self._tile_windows()
        return ToolResult(success=False, output="", error=f"Unknown action: {action}")

    def _launch_preset(self) -> ToolResult:
        app_names = [a.strip() for a in settings.preset_apps.split(",") if a.strip()]
        launched = []
        failed = []
        for name in app_names:
            exe = PRESET_EXECUTABLES.get(name.lower(), name)
            try:
                subprocess.Popen(exe, shell=True)
                launched.append(name)
            except Exception as exc:
                failed.append(f"{name} ({exc})")
        msg = f"Launched: {', '.join(launched)}." if launched else "No apps launched."
        if failed:
            msg += f" Failed: {', '.join(failed)}."
        return ToolResult(success=bool(launched), output=msg)

    def _launch_single(self, name: str) -> ToolResult:
        if not name:
            return ToolResult(success=False, output="", error="No app name provided.")
        exe = PRESET_EXECUTABLES.get(name.lower(), name)
        try:
            subprocess.Popen(exe, shell=True)
            return ToolResult(success=True, output=f"Launched {name}.")
        except Exception as exc:
            return ToolResult(success=False, output="", error=str(exc))

    def _tile_windows(self) -> ToolResult:
        """Tile all visible windows side-by-side (2 columns) using Win32."""
        try:
            screen_w, screen_h = _get_screen_size()
            col_w = screen_w // 2
            # Use Windows built-in tile functionality
            # WM_COMMAND 0x273 = tile vertically
            taskbar_hwnd = user32.FindWindowW("Shell_TrayWnd", None)
            if taskbar_hwnd:
                user32.PostMessageW(taskbar_hwnd, 0x0111, 0x273, 0)
                return ToolResult(success=True, output="Windows tiled side-by-side.")
            return ToolResult(success=False, output="", error="Taskbar not found.")
        except Exception as exc:
            return ToolResult(success=False, output="", error=str(exc))
