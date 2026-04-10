from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM Providers
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    openrouter_api_key: str = ""
    openrouter_model: str = "meta-llama/llama-3.3-70b-instruct:free"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    llm_provider: str = "groq"  # legacy — kept for backwards compat
    # Fallback chain: providers tried in order when rate-limited. Skip providers with no API key.
    # Ollama is opt-in — add "ollama" here if you have it running with the model pulled.
    llm_fallback_chain: str = "groq,gemini,openrouter"

    # Database
    database_path: str = str(Path(__file__).parent.parent / "data" / "alice.db")

    # Persona
    persona_path: str = str(Path(__file__).parent / "persona.yaml")

    # Memory
    max_history_messages: int = 20

    # Weather (Phase 2+)
    openweather_api_key: str = ""
    weather_city: str = "Tagum"
    weather_country_code: str = "PH"

    # Voice / Audio (Phase 3+)
    wake_word_model: str = "hey_alice"      # OpenWakeWord model name or path to .onnx
    wake_word_threshold: float = 0.5        # confidence threshold 0.0–1.0
    stt_model_size: str = "base.en"         # "tiny.en", "base.en", "small", "medium"
    stt_model_size_ja: str = "small"        # multilingual model for Japanese STT (Phase 8)
    speaker_verify_enabled: bool = False    # enable speaker verification (Phase 5)
    speaker_verify_threshold: float = 0.35

    # Language (Phase 8)
    default_language: str = "en"           # "en" | "ja" — starting language

    # Music (Phase 7)
    shoot_to_thrill_path: str = ""
    preset_apps: str = "chrome,spotify,discord"

    # Owner PIN — virtual authentication when mic unavailable
    # Entering this in chat triggers the full boot sequence (same as double clap)
    # Set via OWNER_PIN in .env — leave empty to disable PIN auth
    owner_pin: str = ""

    # Logging
    log_level: str = "INFO"


settings = Settings()
