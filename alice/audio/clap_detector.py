"""
Double clap detector.
Listens for 2 sharp amplitude spikes within a time window.
No ML needed — pure signal processing.
"""

import logging
import time

import numpy as np

logger = logging.getLogger(__name__)

# Thresholds
CLAP_ENERGY_THRESHOLD = 0.15      # RMS spike above this = clap candidate
CLAP_WINDOW_SEC = 1.2             # max seconds between first and second clap
MIN_GAP_SEC = 0.15                # min gap between claps (avoid double-trigger)
COOLDOWN_SEC = 2.0                # seconds to wait after successful double-clap

SAMPLE_RATE = 16000
FRAME_SIZE = 480  # 30ms


class ClapDetector:
    def __init__(self) -> None:
        self._first_clap_time: float | None = None
        self._last_clap_time: float = 0.0
        self._cooldown_until: float = 0.0

    def _rms(self, frame: np.ndarray) -> float:
        return float(np.sqrt(np.mean(frame.astype(np.float32) ** 2)))

    def process(self, frame: np.ndarray) -> bool:
        """
        Feed one audio frame. Returns True if double-clap detected.
        """
        now = time.monotonic()

        # Skip during cooldown
        if now < self._cooldown_until:
            return False

        energy = self._rms(frame)
        if energy < CLAP_ENERGY_THRESHOLD:
            return False

        # Loud spike detected — is it a clap?
        gap = now - self._last_clap_time
        if gap < MIN_GAP_SEC:
            return False  # Too close — same clap still ringing

        self._last_clap_time = now
        logger.debug("Clap candidate (energy=%.3f)", energy)

        if self._first_clap_time is None:
            # First clap
            self._first_clap_time = now
            return False

        # Second clap — check timing
        elapsed = now - self._first_clap_time
        if elapsed <= CLAP_WINDOW_SEC:
            logger.info("Double clap detected! (gap=%.2fs)", elapsed)
            self._first_clap_time = None
            self._cooldown_until = now + COOLDOWN_SEC
            return True

        # Too slow — treat as new first clap
        self._first_clap_time = now
        return False
