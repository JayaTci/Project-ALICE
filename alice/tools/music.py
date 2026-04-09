import subprocess
from pathlib import Path

from alice.config import settings
from alice.tools.base import BaseTool, ToolResult


class MusicTool(BaseTool):
    name = "music_control"
    description = (
        "Play a music file or the configured 'Shoot To Thrill' track. "
        "Action: 'play_shoot_to_thrill' plays the Iron Man activation track. "
        "'play_file' plays a specific audio file path."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["play_shoot_to_thrill", "play_file"],
                "description": "Music action to perform.",
            },
            "file_path": {
                "type": "string",
                "description": "Path to audio file (for play_file action).",
            },
        },
        "required": ["action"],
    }
    is_read_only = False

    async def execute(self, action: str, file_path: str = "", **_) -> ToolResult:
        if action == "play_shoot_to_thrill":
            path = settings.shoot_to_thrill_path
            if not path:
                return ToolResult(
                    success=False, output="",
                    error="SHOOT_TO_THRILL_PATH not configured in .env."
                )
            return self._play(path)

        if action == "play_file":
            if not file_path:
                return ToolResult(success=False, output="", error="No file path provided.")
            return self._play(file_path)

        return ToolResult(success=False, output="", error=f"Unknown action: {action}")

    def _play(self, path: str) -> ToolResult:
        p = Path(path)
        if not p.exists():
            return ToolResult(success=False, output="", error=f"File not found: {path}")
        try:
            # Use Windows default media player via shell
            subprocess.Popen(["cmd", "/c", "start", "", str(p)], shell=False)
            return ToolResult(success=True, output=f"Playing: {p.name}")
        except Exception as exc:
            return ToolResult(success=False, output="", error=str(exc))
