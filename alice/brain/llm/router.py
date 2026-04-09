import logging

from alice.brain.llm.base import LLMProvider
from alice.config import settings

logger = logging.getLogger(__name__)

_provider: LLMProvider | None = None


def get_provider() -> LLMProvider:
    """Return the configured LLM provider (singleton)."""
    global _provider
    if _provider is None:
        _provider = _build_provider()
    return _provider


def _build_provider() -> LLMProvider:
    name = settings.llm_provider.lower()
    if name == "groq":
        from alice.brain.llm.groq_provider import GroqProvider
        logger.info("LLM provider: Groq (%s)", settings.groq_model)
        return GroqProvider()
    if name == "ollama":
        from alice.brain.llm.ollama_provider import OllamaProvider
        logger.info("LLM provider: Ollama (%s)", settings.ollama_model)
        return OllamaProvider()
    raise ValueError(f"Unknown LLM provider: '{name}'. Use 'groq' or 'ollama'.")


def switch_provider(name: str) -> LLMProvider:
    """Hot-swap the provider at runtime."""
    global _provider
    settings.llm_provider = name
    _provider = _build_provider()
    return _provider
