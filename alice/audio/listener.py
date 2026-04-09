"""
Audio Listener — Process 1.
Continuously captures mic audio and routes to:
  - Clap detector (always on)
  - Wake word detector via OpenWakeWord (always on, no API key needed)
  - VAD → STT pipeline (after wake word / clap trigger)

Sends events to Core Brain via multiprocessing.Queue.
"""

import logging
import multiprocessing
import time
from dataclasses import dataclass
from enum import Enum

import numpy as np

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
VAD_FRAME_SIZE = 480      # 30ms for VAD
WW_CHUNK_SIZE = 1280      # 80ms for OpenWakeWord


class EventType(str, Enum):
    WAKE_WORD = "wake_word"
    DOUBLE_CLAP = "double_clap"
    TRANSCRIPT = "transcript"
    ERROR = "error"


@dataclass
class AudioEvent:
    type: EventType
    text: str = ""
    error: str = ""


def _listen_loop(
    queue: multiprocessing.Queue,
    wake_word_model: str,
    wake_word_threshold: float,
    stt_model_size: str,
    language: str,
    speaker_verify: bool,
    speaker_threshold: float,
) -> None:
    """Runs in a dedicated process. All imports inside to avoid pickling issues."""
    import numpy as np
    import sounddevice as sd

    from alice.audio import wake_word as ww
    from alice.audio.clap_detector import ClapDetector
    from alice.audio.vad import VAD, FRAME_SIZE
    from alice.brain.stt import faster_whisper as stt

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    log = logging.getLogger("alice.audio.listener")

    # Load models
    log.info("Loading STT model: %s", stt_model_size)
    stt.load_model(stt_model_size)

    log.info("Loading wake word model: %s", wake_word_model)
    ww.load(wake_word_model, threshold=wake_word_threshold)

    # Load speaker verification if enabled
    sv = None
    if speaker_verify:
        from alice.audio import speaker_verify as sv_mod
        if sv_mod.load_enrolled_embeddings():
            sv = sv_mod
            log.info("Speaker verification ENABLED (threshold=%.2f)", speaker_threshold)
        else:
            log.warning("Speaker verification disabled — no enrollment data found.")

    clap = ClapDetector()
    vad = VAD()

    # State
    IDLE = "idle"
    LISTENING = "listening"
    state = IDLE

    # Rolling buffer for OpenWakeWord (needs 1280-sample chunks)
    ww_buffer = np.array([], dtype=np.int16)

    log.info("Mic active. Waiting for 'hey alice' or double clap...")

    def audio_callback(indata: np.ndarray, frames: int, time_info, status) -> None:
        nonlocal state, ww_buffer

        if status:
            log.debug("Audio status: %s", status)

        mono = indata[:, 0]
        int16 = (mono * 32767).astype(np.int16)

        # ── Clap detection (always on) ──────────────────────────────
        clap_frame = int16[:FRAME_SIZE] if len(int16) >= FRAME_SIZE else int16
        if clap.process(clap_frame):
            log.info("DOUBLE CLAP → sending event")
            queue.put(AudioEvent(type=EventType.DOUBLE_CLAP))
            return

        # ── Wake word detection (always on when IDLE) ────────────────
        if state == IDLE:
            ww_buffer = np.concatenate([ww_buffer, int16])
            while len(ww_buffer) >= WW_CHUNK_SIZE:
                chunk = ww_buffer[:WW_CHUNK_SIZE]
                ww_buffer = ww_buffer[WW_CHUNK_SIZE:]
                if ww.process(chunk):
                    log.info("WAKE WORD detected → switching to LISTENING")
                    queue.put(AudioEvent(type=EventType.WAKE_WORD))
                    ww.reset()
                    state = LISTENING
                    vad.__init__()  # reset VAD state
                    return

        # ── VAD + STT (when LISTENING) ───────────────────────────────
        if state == LISTENING:
            speech_ended, audio_data = vad.process(int16[:FRAME_SIZE])
            if speech_ended and audio_data is not None:
                state = IDLE
                ww_buffer = np.array([], dtype=np.int16)
                log.info("Speech captured (%d samples) — transcribing...", len(audio_data))
                try:
                    # Speaker verification before STT
                    if sv is not None:
                        authorized, score = sv.verify(audio_data, threshold=speaker_threshold)
                        if not authorized:
                            log.info("Speaker rejected (score=%.3f < %.2f)", score, speaker_threshold)
                            queue.put(AudioEvent(type=EventType.WAKE_WORD))  # re-arm silently
                            return

                    text = stt.transcribe(audio_data, language=language)
                    if text:
                        log.info("Transcript: %r", text)
                        queue.put(AudioEvent(type=EventType.TRANSCRIPT, text=text))
                    else:
                        log.debug("Empty transcript — re-arming")
                        queue.put(AudioEvent(type=EventType.WAKE_WORD))
                except Exception as exc:
                    log.exception("STT error")
                    queue.put(AudioEvent(type=EventType.ERROR, error=str(exc)))

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
        blocksize=VAD_FRAME_SIZE,
        callback=audio_callback,
    ):
        log.info("InputStream open.")
        while True:
            time.sleep(0.1)


class AudioListener:
    """Manages the audio listener subprocess and exposes an event Queue."""

    def __init__(
        self,
        wake_word_model: str = "hey_alice",
        wake_word_threshold: float = 0.5,
        stt_model_size: str = "base.en",
        language: str = "en",
        speaker_verify: bool = False,
        speaker_threshold: float = 0.35,
    ) -> None:
        self.queue: multiprocessing.Queue = multiprocessing.Queue()
        self._args = (
            self.queue,
            wake_word_model,
            wake_word_threshold,
            stt_model_size,
            language,
            speaker_verify,
            speaker_threshold,
        )
        self._process: multiprocessing.Process | None = None

    def start(self) -> None:
        self._process = multiprocessing.Process(
            target=_listen_loop,
            args=self._args,
            daemon=True,
            name="alice-audio",
        )
        self._process.start()
        logger.info("Audio listener started (PID %d)", self._process.pid)

    def stop(self) -> None:
        if self._process and self._process.is_alive():
            self._process.terminate()
            self._process.join(timeout=3)
            logger.info("Audio listener stopped.")

    def get_event(self, timeout: float = 0.5) -> AudioEvent | None:
        try:
            return self.queue.get(timeout=timeout)
        except Exception:
            return None
