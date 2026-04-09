import html
import re
from datetime import datetime

import httpx
from alice.tools.base import BaseTool, ToolResult

# RSS feeds: world + Philippines local
RSS_FEEDS = {
    "world": [
        "https://feeds.bbci.co.uk/news/world/rss.xml",
        "https://rss.cnn.com/rss/edition_world.rss",
    ],
    "local": [
        "https://www.rappler.com/feed/",
        "https://www.philstar.com/rss/headlines",
        "https://newsinfo.inquirer.net/feed",
    ],
    "tech": [
        "https://feeds.feedburner.com/TechCrunch/",
        "https://www.theverge.com/rss/index.xml",
    ],
}


def _strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


def _parse_rss(xml: str, max_items: int = 5) -> list[dict]:
    """Minimal RSS parser using regex (no lxml dependency)."""
    items = []
    for item in re.finditer(r"<item>(.*?)</item>", xml, re.DOTALL):
        block = item.group(1)
        title_m = re.search(r"<title>(.*?)</title>", block, re.DOTALL)
        link_m = re.search(r"<link>(.*?)</link>", block, re.DOTALL)
        if not title_m:
            continue
        items.append({
            "title": _strip_html(title_m.group(1)),
            "link": _strip_html(link_m.group(1)) if link_m else "",
        })
        if len(items) >= max_items:
            break
    return items


class NewsTool(BaseTool):
    name = "get_news"
    description = (
        "Fetch the latest news headlines. Categories: 'world', 'local' (Philippines), 'tech', 'all'."
    )
    parameters = {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "enum": ["world", "local", "tech", "all"],
                "description": "News category to fetch.",
            },
            "max_items": {
                "type": "integer",
                "description": "Max headlines per source (default 5).",
            },
        },
        "required": ["category"],
    }
    is_read_only = True

    async def execute(self, category: str = "all", max_items: int = 5, **_) -> ToolResult:
        if category == "all":
            feeds = RSS_FEEDS["world"][:1] + RSS_FEEDS["local"][:1]
        else:
            feeds = RSS_FEEDS.get(category, RSS_FEEDS["world"])

        all_headlines: list[str] = []

        async with httpx.AsyncClient(timeout=10.0) as client:
            for url in feeds:
                try:
                    response = await client.get(url, follow_redirects=True)
                    response.raise_for_status()
                    items = _parse_rss(response.text, max_items)
                    for item in items:
                        all_headlines.append(f"• {item['title']}")
                except Exception:
                    continue

        if not all_headlines:
            return ToolResult(
                success=False, output="",
                error="Could not fetch news. Check internet connection."
            )

        label = category.upper() if category != "all" else "LATEST"
        output = f"{label} NEWS ({datetime.now().strftime('%b %d, %Y')}):\n" + "\n".join(all_headlines)
        return ToolResult(success=True, output=output)
