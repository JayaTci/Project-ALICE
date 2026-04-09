"""
Quick tool tests — run without GROQ_API_KEY needed.
Usage: py -3.14 scripts/test_tools.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from alice.tools.system_info import SystemInfoTool
from alice.tools.file_ops import FileOpsTool
from alice.tools.news import NewsTool


async def main() -> None:
    print("=== System Info ===")
    tool = SystemInfoTool()
    result = await tool.execute(query="all")
    print(result.output)

    print("\n=== File List (home dir) ===")
    ftool = FileOpsTool()
    result = await ftool.execute(action="list", path=str(Path.home()))
    print(result.output[:500])

    print("\n=== Latest News (local PH) ===")
    ntool = NewsTool()
    result = await ntool.execute(category="local", max_items=3)
    if result.success:
        print(result.output)
    else:
        print(f"News error: {result.error}")


if __name__ == "__main__":
    asyncio.run(main())
