"""STT using faster-whisper (local, no cloud needed)."""

import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

_model = None
_model_size = "base.en"


def load_model(model_size: str = "base.en") -> None:
    global _model, _model_size
    from faster_whisper import WhisperModel
    _model_size = model_size
    logger.info("Loading Whisper model: %s", model_size)
    _model = WhisperModel(
        model_size,
        device="cpu",
        compute_type="int8",
        download_root=str(Path(__file__).parent.parent.parent.parent / "data" / "models"),
    )
    logger.info("Whisper model loaded.")


def get_model():
    global _model
    if _model is None:
        load_model()
    return _model


def transcribe(audio_bytes: np.ndarray, language: str = "en") -> str:
    """
    Transcribe audio array (float32, 16kHz mono) to text.
    Returns empty string if speech not detected or too short.
    """
    model = get_model()
    lang = language if language != "en" else None  # None = auto-detect for base.en

    segments, info = model.transcribe(
        audio_bytes,
        language=lang,
        beam_size=5,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
    )
    text = " ".join(seg.text for seg in segments).strip()
    logger.debug("Transcribed: %r (lang=%s, prob=%.2f)", text, info.language, info.language_probability)
    return text
