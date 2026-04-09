"""
Iron Man boot sequence — triggered by double clap.

Steps (as fast as possible):
  1. [parallel] Play Shoot To Thrill + launch preset apps
  2. [parallel] Fetch weather + fetch top news
  3. Build voice briefing from results
  4. Stream briefing to UI + speak via TTS

Deterministic — no LLM call, tools invoked directly.
"""

import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


async def run(broadcast) -> str:
    """
    Execute the Iron Man boot sequence.

    Args:
        broadcast: async callable(dict) — sends events to all UI clients.

    Returns:
        The briefing text that was spoken.
    """
    from alice.brain.language import get_language
    lang = get_language()

    await broadcast({"type": "status", "state": "thinking", "label": "Boot sequence…"})

    # ── Step 1: music + apps in parallel ────────────────────────────────
    music_task = asyncio.create_task(_play_music())
    apps_task  = asyncio.create_task(_launch_apps())
    await asyncio.gather(music_task, apps_task, return_exceptions=True)

    # ── Step 2: weather + news in parallel ───────────────────────────────
    weather_task = asyncio.create_task(_get_weather(lang))
    news_task    = asyncio.create_task(_get_news(lang))
    weather_text, news_text = await asyncio.gather(
        weather_task, news_task, return_exceptions=True
    )

    # ── Step 3: build briefing ───────────────────────────────────────────
    greeting = _greeting(lang)
    briefing = _assemble(greeting, weather_text, news_text, lang)

    # ── Step 4: stream to UI + speak ────────────────────────────────────
    await broadcast({"type": "status", "state": "speaking", "label": "Boot sequence…"})

    # Stream word-by-word so UI typing effect plays
    for word in briefing.split():
        await broadcast({"type": "token", "text": word + " "})
        await asyncio.sleep(0.02)
    await broadcast({"type": "done"})

    try:
        from alice.brain.tts import edge_tts as tts
        await tts.speak(briefing, language=lang)
    except Exception:
        logger.exception("Boot sequence TTS failed")

    await broadcast({"type": "status", "state": "idle", "label": "Ready"})
    return briefing


# ── Helpers ──────────────────────────────────────────────────────────────────

def _greeting(lang: str = "en") -> str:
    hour = datetime.now().hour
    if lang == "ja":
        if hour < 12:
            tod = "おはようございます"
        elif hour < 18:
            tod = "こんにちは"
        else:
            tod = "こんばんは"
        return f"{tod}、ボス。全システム起動完了。"
    else:
        if hour < 12:
            tod = "Good morning"
        elif hour < 18:
            tod = "Good afternoon"
        else:
            tod = "Good evening"
        return f"{tod}, boss. All systems online."


def _assemble(greeting: str, weather, news, lang: str = "en") -> str:
    parts = [greeting]

    if isinstance(weather, str) and weather:
        parts.append(weather)
    elif isinstance(weather, Exception):
        logger.warning("Weather fetch failed: %s", weather)

    if isinstance(news, str) and news:
        parts.append(news)
    elif isinstance(news, Exception):
        logger.warning("News fetch failed: %s", news)

    parts.append("何かお役に立てることはありますか？" if lang == "ja" else "How can I help you today?")
    return " ".join(parts)


async def _play_music() -> None:
    """Non-blocking — fires and forgets Windows shell command."""
    from alice.config import settings
    import subprocess
    from pathlib import Path

    path = settings.shoot_to_thrill_path
    if not path:
        logger.info("Boot: SHOOT_TO_THRILL_PATH not set — skipping music.")
        return
    p = Path(path)
    if not p.exists():
        logger.warning("Boot: music file not found: %s", path)
        return
    try:
        subprocess.Popen(["cmd", "/c", "start", "", str(p)], shell=False)
        logger.info("Boot: playing %s", p.name)
    except Exception:
        logger.exception("Boot: music playback failed")


async def _launch_apps() -> None:
    """Launch preset apps + tile windows."""
    import asyncio
    from alice.config import settings
    import subprocess

    app_names = [a.strip() for a in settings.preset_apps.split(",") if a.strip()]
    from alice.tools.apps import PRESET_EXECUTABLES
    for name in app_names:
        exe = PRESET_EXECUTABLES.get(name.lower(), name)
        try:
            subprocess.Popen(exe, shell=True)
            logger.info("Boot: launched %s", name)
        except Exception:
            logger.warning("Boot: failed to launch %s", name)

    # Brief pause so windows can open before tiling
    await asyncio.sleep(2.5)
    try:
        import ctypes
        user32 = ctypes.windll.user32
        taskbar = user32.FindWindowW("Shell_TrayWnd", None)
        if taskbar:
            user32.PostMessageW(taskbar, 0x0111, 0x273, 0)
            logger.info("Boot: windows tiled.")
    except Exception:
        logger.warning("Boot: window tiling failed")


async def _get_weather(lang: str = "en") -> str:
    """Return short weather summary string, or "" on failure."""
    from alice.config import settings
    if not settings.openweather_api_key:
        return ""
    try:
        import httpx
        url = "https://api.openweathermap.org/data/2.5/weather"
        location = f"{settings.weather_city},{settings.weather_country_code}"
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(url, params={
                "q": location,
                "appid": settings.openweather_api_key,
                "units": "metric",
            })
            r.raise_for_status()
            d = r.json()
        temp = d["main"]["temp"]
        cond = d["weather"][0]["description"]
        city = d.get("name", settings.weather_city)
        if lang == "ja":
            return f"{city}の現在の天気：{cond}、気温{temp:.0f}度です。"
        return f"Current weather in {city}: {cond}, {temp:.0f} degrees Celsius."
    except Exception as exc:
        logger.warning("Boot: weather fetch error: %s", exc)
        return ""


async def _get_news(lang: str = "en") -> str:
    """Return top 3 headlines as a short spoken sentence, or "" on failure."""
    try:
        import httpx, re, html as html_mod
        feed_url = "https://feeds.bbci.co.uk/news/world/rss.xml"
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(feed_url, headers={"User-Agent": "Alice/1.0"})
            r.raise_for_status()
            xml = r.text

        titles = []
        for m in re.finditer(r"<item>(.*?)</item>", xml, re.DOTALL):
            t = re.search(r"<title>(.*?)</title>", m.group(1), re.DOTALL)
            if t:
                raw = t.group(1).strip()
                # Unwrap CDATA if present
                cdata = re.match(r"<!\[CDATA\[(.*?)]]>", raw, re.DOTALL)
                title = cdata.group(1).strip() if cdata else html_mod.unescape(re.sub(r"<[^>]+>", "", raw)).strip()
                if title and len(title) > 5:
                    titles.append(title)
            if len(titles) >= 3:
                break

        if not titles:
            return ""
        headlines = ". ".join(titles)
        prefix = "トップニュース：" if lang == "ja" else "Top headlines: "
        return f"{prefix}{headlines}."
    except Exception as exc:
        logger.warning("Boot: news fetch error: %s", exc)
        return ""
