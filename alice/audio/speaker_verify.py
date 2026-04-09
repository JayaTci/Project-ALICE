"""
Speaker verification using SpeechBrain ECAPA-TDNN.

Only Chester's voice is accepted. All others are silently rejected.
Enrollment: run scripts/enroll_voice.py to record voice samples.

Model: spkrec-ecapa-voxceleb (downloaded automatically on first use, ~80MB)
RAM: ~200MB
"""

import logging
import os
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

ENROLLMENT_DIR = Path(__file__).parent.parent.parent / "data" / "voice_enrollment"
EMBEDDINGS_FILE = ENROLLMENT_DIR / "embeddings.npy"
MODEL_SAVE_DIR = str(Path(__file__).parent.parent.parent / "data" / "models" / "speaker")

SAMPLE_RATE = 16000

_model = None
_enrolled_embeddings: np.ndarray | None = None


def _get_model():
    global _model
    if _model is not None:
        return _model

    from speechbrain.inference.speaker import EncoderClassifier

    logger.info("Loading speaker verification model (ECAPA-TDNN)...")
    _model = EncoderClassifier.from_hparams(
        source="speechbrain/spkrec-ecapa-voxceleb",
        savedir=MODEL_SAVE_DIR,
        run_opts={"device": "cpu"},
    )
    logger.info("Speaker model loaded.")
    return _model


def _extract_embedding(audio: np.ndarray) -> np.ndarray:
    """Extract speaker embedding from float32 16kHz mono audio array."""
    import torch

    model = _get_model()
    tensor = torch.tensor(audio, dtype=torch.float32).unsqueeze(0)  # [1, T]
    with torch.no_grad():
        embedding = model.encode_batch(tensor)  # [1, 1, D]
    return embedding.squeeze().numpy()  # [D]


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))


def load_enrolled_embeddings() -> bool:
    """
    Load enrolled speaker embeddings from disk.
    Returns True if embeddings exist, False if enrollment needed.
    """
    global _enrolled_embeddings
    if EMBEDDINGS_FILE.exists():
        _enrolled_embeddings = np.load(str(EMBEDDINGS_FILE))
        logger.info("Loaded %d enrolled speaker embeddings.", len(_enrolled_embeddings))
        return True
    logger.warning("No enrolled embeddings found. Run scripts/enroll_voice.py first.")
    return False


def enroll_from_audio(audio_clips: list[np.ndarray]) -> None:
    """
    Compute and save speaker embeddings from a list of audio clips.
    Call this during enrollment (scripts/enroll_voice.py).
    """
    global _enrolled_embeddings
    ENROLLMENT_DIR.mkdir(parents=True, exist_ok=True)

    embeddings = []
    for i, clip in enumerate(audio_clips):
        logger.info("Extracting embedding from clip %d/%d...", i + 1, len(audio_clips))
        emb = _extract_embedding(clip)
        embeddings.append(emb)

    _enrolled_embeddings = np.array(embeddings)
    np.save(str(EMBEDDINGS_FILE), _enrolled_embeddings)
    logger.info("Saved %d speaker embeddings to %s", len(embeddings), EMBEDDINGS_FILE)


def verify(audio: np.ndarray, threshold: float = 0.35) -> tuple[bool, float]:
    """
    Verify if the audio matches the enrolled speaker.

    Args:
        audio: float32 16kHz mono audio
        threshold: cosine similarity threshold (0.0–1.0)
                   higher = stricter. 0.35 is typical.

    Returns:
        (is_authorized, best_score)
    """
    if _enrolled_embeddings is None:
        if not load_enrolled_embeddings():
            # No enrollment — pass-through (trust all voices)
            logger.warning("Speaker verification skipped — no enrollment data.")
            return True, 1.0

    query_emb = _extract_embedding(audio)

    scores = [
        _cosine_similarity(query_emb, ref_emb)
        for ref_emb in _enrolled_embeddings
    ]
    best_score = max(scores)
    is_authorized = best_score >= threshold

    logger.debug(
        "Speaker verify: score=%.3f threshold=%.3f → %s",
        best_score, threshold, "ACCEPT" if is_authorized else "REJECT",
    )
    return is_authorized, best_score
