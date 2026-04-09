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
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    llm_provider: str = "groq"  # "groq" | "ollama"

    # Database
    database_path: str = str(Path(__file__).parent.parent / "data" / "alice.db")

    # Persona
    persona_path: str = str(Path(__file__).parent / "persona.yaml")

    # Memory
    max_history_messages: int = 20

    # Weather (Phase 2+)
    openweather_api_key: str = ""
    weather_city: str = "Manila"
    weather_country_code: str = "PH"

    # Voice / Audio (Phase 3+)
    wake_word_model: str = "hey_jarvis"     # OpenWakeWord model name or path to .onnx
    wake_word_threshold: float = 0.5        # confidence threshold 0.0–1.0
    stt_model_size: str = "base.en"         # "tiny.en", "base.en", "small", "medium"
    speaker_verify_enabled: bool = False    # enable speaker verification (Phase 5)
    speaker_verify_threshold: float = 0.35

    # Music (Phase 7)
    shoot_to_thrill_path: str = ""
    preset_apps: str = "chrome,spotify,discord"

    # Logging
    log_level: str = "INFO"


settings = Settings()
