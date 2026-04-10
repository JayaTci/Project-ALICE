"""
LLM Router — priority-based fallback chain with automatic rate-limit rotation.

Provider priority order (from LLM_FALLBACK_CHAIN in .env):
  groq → gemini → openrouter → ollama  (default)

When a provider raises RateLimitError (HTTP 429), it is cooled down for
COOLDOWN_SECONDS and the next available provider is tried automatically.
After the cooldown expires, the provider re-enters the rotation.

Providers without an API key configured are silently skipped.
"""

import logging
import time
from collections.abc import AsyncGenerator

from alice.brain.llm.base import LLMChunk, LLMProvider, Message, RateLimitError

logger = logging.getLogger(__name__)

COOLDOWN_SECONDS = 60.0  # seconds before retrying a rate-limited provider

_router: "FallbackRouter | None" = None


# ─── Public API ──────────────────────────────────────────────────────────────

def get_provider() -> "FallbackRouter":
    """Return the singleton FallbackRouter (builds on first call)."""
    global _router
    if _router is None:
        _router = FallbackRouter(_build_providers())
    return _router


def reset_provider() -> None:
    """Force rebuild on next get_provider() call (e.g. after .env change)."""
    global _router
    _router = None


# ─── FallbackRouter ───────────────────────────────────────────────────────────

class FallbackRouter(LLMProvider):
    """
    Wraps an ordered list of LLM providers.
    On RateLimitError, marks provider as cooling down and tries the next one.
    """

    def __init__(self, providers: list[tuple[str, LLMProvider]]) -> None:
        # providers: [(name, provider), ...] in priority order
        self._providers = providers
        self._limited_until: dict[int, float] = {}  # index → monotonic time

        names = [n for n, _ in providers]
        logger.info("LLM fallback chain: %s", " → ".join(names))

    def _available(self) -> list[tuple[int, str, LLMProvider]]:
        now = time.monotonic()
        return [
            (idx, name, p)
            for idx, (name, p) in enumerate(self._providers)
            if now >= self._limited_until.get(idx, 0.0)
        ]

    def _mark_limited(self, idx: int, name: str) -> None:
        self._limited_until[idx] = time.monotonic() + COOLDOWN_SECONDS
        remaining = [n for i, (n, _) in enumerate(self._providers)
                     if time.monotonic() < self._limited_until.get(i, 0.0)]
        logger.warning(
            "Provider '%s' rate-limited — cooling down %ds. Still available: %s",
            name, int(COOLDOWN_SECONDS),
            [n for i, (n, _) in enumerate(self._providers)
             if time.monotonic() < self._limited_until.get(i, 0.0) is False]
        )

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
    ) -> LLMChunk:
        available = self._available()
        if not available:
            # All cooling down — try all anyway as last resort
            logger.warning("All providers cooling down — trying all anyway")
            available = [(i, n, p) for i, (n, p) in enumerate(self._providers)]

        last_exc: Exception = RuntimeError("No LLM providers configured.")
        for idx, name, provider in available:
            try:
                logger.debug("LLM request → %s", name)
                return await provider.complete(messages, tools=tools)
            except RateLimitError as exc:
                self._limited_until[idx] = time.monotonic() + COOLDOWN_SECONDS
                logger.warning("'%s' rate-limited — trying next provider", name)
                last_exc = exc
            except Exception as exc:
                # Any other error (connection refused, HTTP error, parse error, etc.)
                # — log it and try the next provider rather than crashing.
                logger.warning("'%s' failed (%s: %s) — trying next provider",
                               name, type(exc).__name__, exc)
                last_exc = exc if isinstance(exc, RuntimeError) else RuntimeError(str(exc))

        raise RuntimeError(
            "All LLM providers unavailable. "
            f"Last error: {last_exc}"
        ) from last_exc

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
    ) -> AsyncGenerator[LLMChunk, None]:
        # Engine uses complete(), not stream(). Delegate to complete() for fallback support.
        result = await self.complete(messages, tools)
        yield result

    async def health_check(self) -> bool:
        for _, _, provider in self._providers:
            try:
                if await provider.health_check():
                    return True
            except Exception:
                continue
        return False

    def status(self) -> dict:
        """Return provider availability status (for health check / logging)."""
        now = time.monotonic()
        return {
            name: "available" if now >= self._limited_until.get(idx, 0.0) else
                  f"cooling ({int(self._limited_until[idx] - now)}s)"
            for idx, (name, _) in enumerate(self._providers)
        }


# ─── Provider builder ─────────────────────────────────────────────────────────

def _build_providers() -> list[tuple[str, LLMProvider]]:
    from alice.config import settings

    chain = [s.strip().lower() for s in settings.llm_fallback_chain.split(",") if s.strip()]
    providers: list[tuple[str, LLMProvider]] = []

    for name in chain:
        try:
            if name == "groq":
                if not settings.groq_api_key:
                    logger.info("Skipping Groq — GROQ_API_KEY not set")
                    continue
                from alice.brain.llm.groq_provider import GroqProvider
                providers.append(("groq", GroqProvider()))
                logger.info("LLM chain: +Groq (%s)", settings.groq_model)

            elif name == "gemini":
                if not settings.gemini_api_key:
                    logger.info("Skipping Gemini — GEMINI_API_KEY not set")
                    continue
                from alice.brain.llm.gemini_provider import GeminiProvider
                providers.append(("gemini", GeminiProvider()))
                logger.info("LLM chain: +Gemini (%s)", settings.gemini_model)

            elif name == "openrouter":
                if not settings.openrouter_api_key:
                    logger.info("Skipping OpenRouter — OPENROUTER_API_KEY not set")
                    continue
                from alice.brain.llm.openrouter_provider import OpenRouterProvider
                providers.append(("openrouter", OpenRouterProvider()))
                logger.info("LLM chain: +OpenRouter (%s)", settings.openrouter_model)

            elif name == "ollama":
                from alice.brain.llm.ollama_provider import OllamaProvider
                providers.append(("ollama", OllamaProvider()))
                logger.info("LLM chain: +Ollama (%s)", settings.ollama_model)

            else:
                logger.warning("Unknown provider in LLM_FALLBACK_CHAIN: '%s'", name)

        except Exception as exc:
            logger.warning("Failed to init provider '%s': %s", name, exc)

    if not providers:
        raise ValueError(
            "No LLM providers available. Set at least one API key in .env "
            "(GROQ_API_KEY, GEMINI_API_KEY, or OPENROUTER_API_KEY) or run Ollama locally."
        )

    return providers
