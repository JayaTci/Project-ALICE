"""
Voice Activity Detection — simple amplitude-based VAD.
Detects when the user starts and stops speaking.
No ML model needed — works on CPU with minimal RAM.
"""

import logging
from collections import deque

import numpy as np

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
FRAME_DURATION_MS = 30           # ms per frame
FRAME_SIZE = int(SAMPLE_RATE * FRAME_DURATION_MS / 1000)  # samples per frame

# Tunable thresholds
SPEECH_ENERGY_THRESHOLD = 0.005  # RMS above this → speech
SILENCE_FRAMES_TO_END = 25       # ~750ms silence → end of utterance
PRE_SPEECH_FRAMES = 10           # frames to keep before speech detected


class VAD:
    """
    Ring-buffer VAD. Feed audio frames via `process()`.
    Returns (is_speech, audio_buffer) tuples.
    Call `flush()` to retrieve final utterance when speech ends.
    """

    def __init__(self) -> None:
        self._pre_buffer: deque[np.ndarray] = deque(maxlen=PRE_SPEECH_FRAMES)
        self._speech_buffer: list[np.ndarray] = []
        self._in_speech = False
        self._silence_count = 0

    def _rms(self, frame: np.ndarray) -> float:
        return float(np.sqrt(np.mean(frame.astype(np.float32) ** 2)))

    def process(self, frame: np.ndarray) -> tuple[bool, np.ndarray | None]:
        """
        Feed one audio frame (FRAME_SIZE samples, int16).
        Returns (speech_ended, utterance_audio) — utterance_audio is non-None only when speech ends.
        """
        energy = self._rms(frame)
        is_voiced = energy > SPEECH_ENERGY_THRESHOLD

        if not self._in_speech:
            self._pre_buffer.append(frame)
            if is_voiced:
                self._in_speech = True
                self._silence_count = 0
                self._speech_buffer = list(self._pre_buffer)
                logger.debug("VAD: speech start (energy=%.4f)", energy)
            return False, None

        # Currently in speech
        self._speech_buffer.append(frame)

        if is_voiced:
            self._silence_count = 0
        else:
            self._silence_count += 1

        if self._silence_count >= SILENCE_FRAMES_TO_END:
            logger.debug("VAD: speech end (%d frames collected)", len(self._speech_buffer))
            audio = self.flush()
            return True, audio

        return False, None

    def flush(self) -> np.ndarray:
        """Return collected speech as float32 array and reset state."""
        audio = np.concatenate(self._speech_buffer).astype(np.float32) / 32768.0
        self._in_speech = False
        self._silence_count = 0
        self._speech_buffer = []
        self._pre_buffer.clear()
        return audio

    @property
    def in_speech(self) -> bool:
        return self._in_speech
