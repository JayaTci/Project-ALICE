"""
Startup health check — Phase 10.

Validates config, connectivity, and optional features.
Prints clear warnings for missing or misconfigured items.
Does NOT crash on non-critical failures — Alice degrades gracefully.
"""

import sys
import logging

logger = logging.getLogger(__name__)

_WARN  = "[WARN ]"
_OK    = "[ OK  ]"
_FAIL  = "[FAIL ]"
_INFO  = "[INFO ]"


def run_health_check(verbose: bool = True) -> bool:
    """
    Run all checks. Returns True if Alice can start, False if a critical
    dependency is missing.
    """
    from alice.config import settings

    results: list[tuple[bool | None, str]] = []  # (ok/None=warn, message)

    # ── Python version ────────────────────────────────────────────────────
    major, minor = sys.version_info[:2]
    if major < 3 or minor < 12:
        results.append((False, f"Python 3.12+ required (got {major}.{minor})"))
    else:
        results.append((True, f"Python {major}.{minor}"))

    # ── Required packages ────────────────────────────────────────────────
    required_packages = [
        ("pydantic", "pydantic"),
        ("aiosqlite", "aiosqlite"),
        ("httpx", "httpx"),
        ("yaml", "pyyaml"),
        ("aiohttp", "aiohttp"),
    ]
    for module, pkg in required_packages:
        try:
            __import__(module)
            results.append((True, f"Package: {pkg}"))
        except ImportError:
            results.append((False, f"Package missing: {pkg}  ->  pip install {pkg}"))

    # ── LLM provider chain ────────────────────────────────────────────────
    chain = [s.strip().lower() for s in settings.llm_fallback_chain.split(",") if s.strip()]
    active_providers = []
    if "groq" in chain:
        if settings.groq_api_key and not settings.groq_api_key.startswith("your_"):
            results.append((True, f"Groq: {settings.groq_model}"))
            active_providers.append("groq")
        else:
            results.append((None, "Groq: GROQ_API_KEY not set — skipped in chain"))
    if "gemini" in chain:
        if settings.gemini_api_key and not settings.gemini_api_key.startswith("your_"):
            results.append((True, f"Gemini: {settings.gemini_model}"))
            active_providers.append("gemini")
        else:
            results.append((None, "Gemini: GEMINI_API_KEY not set — skipped in chain"))
    if "openrouter" in chain:
        if settings.openrouter_api_key and not settings.openrouter_api_key.startswith("your_"):
            results.append((True, f"OpenRouter: {settings.openrouter_model}"))
            active_providers.append("openrouter")
        else:
            results.append((None, "OpenRouter: OPENROUTER_API_KEY not set — skipped in chain"))
    if "ollama" in chain:
        results.append((None, f"Ollama: ensure Ollama is running at {settings.ollama_base_url}"))
    if not active_providers and "ollama" not in chain:
        results.append((False, "No LLM providers configured — set at least one API key in .env"))

    # ── Database ──────────────────────────────────────────────────────────
    import os
    from pathlib import Path
    db_path = Path(settings.database_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    results.append((True, f"DB path: {db_path}"))

    # ── Audio packages (optional — required for voice mode) ───────────────
    voice_packages = [
        ("sounddevice", "sounddevice"),
        ("faster_whisper", "faster-whisper"),
        ("openwakeword", "openwakeword"),
        ("edge_tts", "edge-tts"),
    ]
    voice_ok = True
    for module, pkg in voice_packages:
        try:
            __import__(module)
        except ImportError:
            results.append((None, f"Voice package missing: {pkg} - voice mode unavailable"))
            voice_ok = False
    if voice_ok:
        results.append((True, "All voice packages available"))

    # ── Weather API ───────────────────────────────────────────────────────
    if not settings.openweather_api_key:
        results.append((None, "OPENWEATHER_API_KEY not set — weather tool disabled"))
    else:
        results.append((True, "OpenWeatherMap API key set"))

    # ── Shoot To Thrill path ──────────────────────────────────────────────
    if not settings.shoot_to_thrill_path:
        results.append((None, "SHOOT_TO_THRILL_PATH not set — boot music disabled"))
    else:
        p = Path(settings.shoot_to_thrill_path)
        if p.exists():
            results.append((True, f"Boot music: {p.name}"))
        else:
            results.append((None, f"Boot music file not found: {settings.shoot_to_thrill_path}"))

    # ── Speaker verification enrollment ──────────────────────────────────
    emb_path = Path(__file__).parent.parent.parent / "data" / "voice_enrollment" / "embeddings.npy"
    if settings.speaker_verify_enabled:
        if emb_path.exists():
            results.append((True, "Speaker verification: enrolled"))
        else:
            results.append((None, "SPEAKER_VERIFY_ENABLED=true but no enrollment data. Run scripts/enroll_voice.py"))
    else:
        results.append((None, "Speaker verification disabled (set SPEAKER_VERIFY_ENABLED=true to enable)"))

    # ── Print results ─────────────────────────────────────────────────────
    if verbose:
        sep = "-" * 50
        print(f"\n{sep}")
        print("  Alice Health Check")
        print(sep)
        for ok, msg in results:
            if ok is True:
                tag = _OK
            elif ok is False:
                tag = _FAIL
            else:
                tag = _WARN
            print(f"  {tag} {msg}")
        print(f"{sep}\n")

    critical_failures = [msg for ok, msg in results if ok is False]
    if critical_failures:
        logger.error("Health check failed: %s", "; ".join(critical_failures))
        return False

    return True
