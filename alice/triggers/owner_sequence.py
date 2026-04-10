"""
Owner PIN welcome sequence — triggered when Chester enters the owner PIN.

Steps (all news fetched in parallel):
  1. Personal welcome to Chester with current time + date
  2. International headlines (BBC World, top 3)
  3. Philippine local news (Rappler → Inquirer fallback, top 3)
  4. Tagum City news (Google News search, top 3)

No LLM call — deterministic, fast.
"""

import asyncio
import html as html_mod
import logging
import re
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)


async def run(broadcast) -> str:
    """
    Run the owner welcome sequence.

    Args:
        broadcast: async callable(dict) — sends events to all UI clients.

    Returns:
        The full briefing text that was spoken.
    """
    from alice.brain.language import get_language
    lang = get_language()

    await broadcast({"type": "status", "state": "thinking", "label": "Owner verified…"})

    # ── Fetch all news in parallel ───────────────────────────────────────
    intl_task  = asyncio.create_task(_fetch_international())
    ph_task    = asyncio.create_task(_fetch_philippine())
    tagum_task = asyncio.create_task(_fetch_tagum())

    intl_news, ph_news, tagum_news = await asyncio.gather(
        intl_task, ph_task, tagum_task, return_exceptions=True
    )

    # ── Build briefing ───────────────────────────────────────────────────
    now      = datetime.now()
    time_str = now.strftime("%I:%M %p").lstrip("0")        # e.g. "2:45 PM"
    day_str  = now.strftime("%A, %B %d, %Y")               # e.g. "Thursday, April 10, 2026"

    parts: list[str] = []

    # Personal greeting
    hour = now.hour
    if hour < 12:
        tod = "Good morning"
    elif hour < 18:
        tod = "Good afternoon"
    else:
        tod = "Good evening"

    parts.append(
        f"Identity confirmed. {tod}, boss. Welcome back. "
        f"It's {time_str} on {day_str}. "
        f"All systems are online. Here is your briefing."
    )

    # International news
    if isinstance(intl_news, list) and intl_news:
        headlines = ". ".join(intl_news)
        parts.append(f"International headlines: {headlines}.")
    else:
        parts.append("International news is unavailable at the moment.")

    # Philippine news
    if isinstance(ph_news, list) and ph_news:
        headlines = ". ".join(ph_news)
        parts.append(f"Philippine news: {headlines}.")
    else:
        parts.append("Philippine news is unavailable at the moment.")

    # Tagum City news
    if isinstance(tagum_news, list) and tagum_news:
        headlines = ". ".join(tagum_news)
        parts.append(f"Tagum City updates: {headlines}.")
    else:
        parts.append("No recent Tagum City updates found.")

    parts.append("That is all for now. How can I assist you today, boss?")

    briefing = " ".join(parts)

    # ── Stream to UI word-by-word ────────────────────────────────────────
    await broadcast({"type": "status", "state": "speaking", "label": "Welcome briefing…"})
    for word in briefing.split():
        await broadcast({"type": "token", "text": word + " "})
        await asyncio.sleep(0.02)
    await broadcast({"type": "done"})

    # ── TTS ──────────────────────────────────────────────────────────────
    try:
        from alice.brain.tts import edge_tts as tts
        await tts.speak(briefing, language=lang)
    except Exception:
        logger.exception("Owner sequence TTS failed")

    await broadcast({"type": "status", "state": "idle", "label": "Ready"})
    return briefing


# ── RSS helpers ──────────────────────────────────────────────────────────────

def _parse_titles(xml: str, max_items: int = 3) -> list[str]:
    """Extract titles from RSS <item> or Atom <entry> blocks."""
    titles: list[str] = []

    # RSS 2.0 items
    blocks = re.findall(r"<item>(.*?)</item>", xml, re.DOTALL)
    # Fallback: Atom entries (Google News new format)
    if not blocks:
        blocks = re.findall(r"<entry>(.*?)</entry>", xml, re.DOTALL)

    for block in blocks:
        t = re.search(r"<title[^>]*>(.*?)</title>", block, re.DOTALL)
        if not t:
            continue
        raw = t.group(1).strip()
        cdata = re.match(r"<!\[CDATA\[(.*?)]]>", raw, re.DOTALL)
        title = (
            cdata.group(1).strip() if cdata
            else html_mod.unescape(re.sub(r"<[^>]+>", "", raw)).strip()
        )
        if title and len(title) > 8:
            titles.append(title)
        if len(titles) >= max_items:
            break

    return titles


async def _fetch_rss(url: str, max_items: int = 3) -> list[str]:
    async with httpx.AsyncClient(
        timeout=8.0,
        headers={"User-Agent": "Mozilla/5.0 Alice/1.0"},
        follow_redirects=True,
    ) as client:
        r = await client.get(url)
        r.raise_for_status()
        return _parse_titles(r.text, max_items)


async def _fetch_international() -> list[str]:
    """BBC World News top 3."""
    try:
        return await _fetch_rss("https://feeds.bbci.co.uk/news/world/rss.xml")
    except Exception as exc:
        logger.warning("Owner seq: international news error: %s", exc)
        return []


async def _fetch_philippine() -> list[str]:
    """Philippine news — Rappler with Inquirer fallback."""
    for url in [
        "https://www.rappler.com/feed/",
        "https://newsinfo.inquirer.net/feed",
        "https://www.philstar.com/rss/headlines",
    ]:
        try:
            items = await _fetch_rss(url)
            if items:
                return items
        except Exception:
            continue
    logger.warning("Owner seq: all Philippine news sources failed")
    return []


async def _fetch_tagum() -> list[str]:
    """Tagum City news via Google News RSS search."""
    url = "https://news.google.com/rss/search?q=Tagum+City&hl=en-PH&gl=PH&ceid=PH:en"
    try:
        return await _fetch_rss(url)
    except Exception as exc:
        logger.warning("Owner seq: Tagum City news error: %s", exc)
        return []
