import os
from pathlib import Path

from alice.tools.base import BaseTool, ToolResult

# Safety: restrict operations to these root dirs by default
ALLOWED_ROOTS = [
    Path.home(),
    Path("D:/"),
    Path("C:/Users"),
]


def _is_allowed(path: Path) -> bool:
    for root in ALLOWED_ROOTS:
        try:
            path.resolve().relative_to(root.resolve())
            return True
        except ValueError:
            pass
    return False


class FileOpsTool(BaseTool):
    name = "file_ops"
    description = (
        "File system operations: list directory contents, read a text file, "
        "search for files by name pattern, get file size/info."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "read", "search", "info"],
                "description": "Operation to perform.",
            },
            "path": {
                "type": "string",
                "description": "File or directory path.",
            },
            "pattern": {
                "type": "string",
                "description": "Glob pattern for search (e.g. '*.pdf').",
            },
            "max_lines": {
                "type": "integer",
                "description": "Max lines to return when reading a file (default 100).",
            },
        },
        "required": ["action", "path"],
    }
    is_read_only = True

    async def execute(
        self,
        action: str,
        path: str = "",
        pattern: str = "*",
        max_lines: int = 100,
        **_,
    ) -> ToolResult:
        p = Path(path).expanduser()
        if not _is_allowed(p):
            return ToolResult(success=False, output="", error=f"Access denied: {path}")

        if action == "list":
            return self._list(p)
        if action == "read":
            return self._read(p, max_lines)
        if action == "search":
            return self._search(p, pattern)
        if action == "info":
            return self._info(p)
        return ToolResult(success=False, output="", error=f"Unknown action: {action}")

    def _list(self, p: Path) -> ToolResult:
        if not p.exists():
            return ToolResult(success=False, output="", error=f"Path not found: {p}")
        if p.is_file():
            return ToolResult(success=True, output=str(p))
        items = sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
        lines = [f"{'[DIR] ' if i.is_dir() else '      '}{i.name}" for i in items[:100]]
        return ToolResult(success=True, output="\n".join(lines) or "(empty directory)")

    def _read(self, p: Path, max_lines: int) -> ToolResult:
        if not p.is_file():
            return ToolResult(success=False, output="", error=f"Not a file: {p}")
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
            truncated = len(lines) > max_lines
            output = "\n".join(lines[:max_lines])
            if truncated:
                output += f"\n... (truncated, {len(lines)} total lines)"
            return ToolResult(success=True, output=output)
        except Exception as exc:
            return ToolResult(success=False, output="", error=str(exc))

    def _search(self, p: Path, pattern: str) -> ToolResult:
        if not p.exists():
            return ToolResult(success=False, output="", error=f"Path not found: {p}")
        results = list(p.rglob(pattern))[:50]
        if not results:
            return ToolResult(success=True, output=f"No files matching '{pattern}' in {p}.")
        lines = [str(r) for r in results]
        return ToolResult(success=True, output="\n".join(lines))

    def _info(self, p: Path) -> ToolResult:
        if not p.exists():
            return ToolResult(success=False, output="", error=f"Path not found: {p}")
        stat = p.stat()
        size = stat.st_size
        unit = "B"
        if size > 1e9:
            size /= 1e9; unit = "GB"
        elif size > 1e6:
            size /= 1e6; unit = "MB"
        elif size > 1e3:
            size /= 1e3; unit = "KB"
        info = (
            f"Name: {p.name}\n"
            f"Type: {'directory' if p.is_dir() else 'file'}\n"
            f"Size: {size:.1f} {unit}\n"
            f"Path: {p.resolve()}"
        )
        return ToolResult(success=True, output=info)
