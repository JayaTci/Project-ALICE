"""
Wake word detection using OpenWakeWord (MIT license, no account needed).

Default model: "hey_jarvis" (pre-trained, downloads automatically).
Custom "hey_alice": train via OpenWakeWord training pipeline (see scripts/train_wake_word.py).

Set in .env:
  WAKE_WORD_MODEL=hey_jarvis          (model name or path to .onnx file)
  WAKE_WORD_THRESHOLD=0.5             (confidence threshold 0.0–1.0)
"""

import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
# OpenWakeWord expects 80ms chunks = 1280 samples @ 16kHz
CHUNK_SAMPLES = 1280

_model = None
_model_name = "hey_jarvis"
_threshold = 0.5


def load(model_name: str = "hey_jarvis", threshold: float = 0.5) -> None:
    """
    Load the OpenWakeWord model.
    model_name: built-in name (e.g. 'hey_jarvis') or path to .onnx file.
    """
    global _model, _model_name, _threshold
    from openwakeword.model import Model

    _model_name = model_name
    _threshold = threshold

    # Check if it's a file path
    if Path(model_name).exists():
        logger.info("Wake word: custom model %s (threshold=%.2f)", model_name, threshold)
        _model = Model(wakeword_models=[model_name], inference_framework="onnx")
    else:
        # Built-in model — download if needed
        logger.info("Wake word: '%s' (threshold=%.2f)", model_name, threshold)
        from openwakeword.utils import download_models
        try:
            download_models(model_names=[model_name])
        except Exception as exc:
            logger.warning("Model download skipped (may already exist): %s", exc)
        _model = Model(wakeword_models=[model_name], inference_framework="onnx")

    logger.info("Wake word model loaded: %s", model_name)


def process(chunk: np.ndarray) -> bool:
    """
    Feed CHUNK_SAMPLES int16 samples (1280 samples = 80ms @ 16kHz).
    Returns True if wake word detected above threshold.
    """
    if _model is None:
        raise RuntimeError("Wake word model not loaded. Call wake_word.load() first.")

    # OpenWakeWord expects float32 in range [-1, 1]
    audio_float = chunk.astype(np.float32) / 32768.0
    prediction = _model.predict(audio_float)

    # prediction is a dict: {model_name: confidence_score}
    for name, score in prediction.items():
        if score >= _threshold:
            logger.debug("Wake word '%s' detected (score=%.3f)", name, score)
            return True
    return False


def reset() -> None:
    """Reset model state (call after wake word detected to avoid re-triggering)."""
    if _model is not None:
        _model.reset()


def cleanup() -> None:
    global _model
    _model = None
