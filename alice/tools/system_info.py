import platform
from datetime import datetime

import psutil
from alice.tools.base import BaseTool, ToolResult


class SystemInfoTool(BaseTool):
    name = "get_system_info"
    description = (
        "Get system information: current time/date, CPU usage, RAM usage, "
        "disk storage, OS details, running process count."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "enum": ["time", "date", "datetime", "cpu", "ram", "disk", "os", "all"],
                "description": "What system info to retrieve.",
            }
        },
        "required": ["query"],
    }
    is_read_only = True

    async def execute(self, query: str = "all", **_) -> ToolResult:
        now = datetime.now()
        info: dict[str, str] = {}

        if query in ("time", "datetime", "all"):
            info["time"] = now.strftime("%I:%M %p")
        if query in ("date", "datetime", "all"):
            info["date"] = now.strftime("%A, %B %d, %Y")
        if query in ("cpu", "all"):
            info["cpu_percent"] = f"{psutil.cpu_percent(interval=0.5)}%"
            info["cpu_cores"] = str(psutil.cpu_count(logical=True))
        if query in ("ram", "all"):
            vm = psutil.virtual_memory()
            info["ram_used"] = f"{vm.used / 1e9:.1f} GB"
            info["ram_total"] = f"{vm.total / 1e9:.1f} GB"
            info["ram_percent"] = f"{vm.percent}%"
        if query in ("disk", "all"):
            du = psutil.disk_usage("C:/")
            info["disk_used"] = f"{du.used / 1e9:.1f} GB"
            info["disk_total"] = f"{du.total / 1e9:.1f} GB"
            info["disk_free"] = f"{du.free / 1e9:.1f} GB"
            info["disk_percent"] = f"{du.percent}%"
        if query in ("os", "all"):
            info["os"] = f"{platform.system()} {platform.release()}"
            info["machine"] = platform.node()

        lines = [f"{k}: {v}" for k, v in info.items()]
        return ToolResult(success=True, output="\n".join(lines))
