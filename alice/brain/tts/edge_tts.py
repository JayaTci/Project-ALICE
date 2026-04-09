"""
TTS using Microsoft Edge-TTS (free, cloud, high quality).
Supports English and Japanese with natural neural voices.
"""

import asyncio
import io
import logging
import tempfile
from pathlib import Path

import edge_tts

logger = logging.getLogger(__name__)

# Voice config per language
VOICES = {
    "en": "en-US-AriaNeural",
    "ja": "ja-JP-NanamiNeural",
}

# Playback rate/pitch adjustments for Alice's character
RATE = "+0%"    # normal speed
PITCH = "+0Hz"  # normal pitch


async def synthesize(text: str, language: str = "en") -> bytes:
    """
    Synthesize text to MP3 bytes using Edge-TTS.
    Returns raw MP3 audio data.
    """
    voice = VOICES.get(language, VOICES["en"])
    communicate = edge_tts.Communicate(text, voice, rate=RATE, pitch=PITCH)

    audio_chunks = []
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_chunks.append(chunk["data"])

    if not audio_chunks:
        raise RuntimeError(f"No audio generated for text: {text!r}")

    return b"".join(audio_chunks)


async def speak(text: str, language: str = "en") -> None:
    """
    Synthesize and play audio through the default system audio output.
    Uses sounddevice for playback (cross-platform).
    """
    if not text.strip():
        return

    mp3_data = await synthesize(text, language)

    # Decode MP3 to PCM using pydub or just save+play via subprocess
    await _play_mp3(mp3_data)


async def _play_mp3(mp3_data: bytes) -> None:
    """Save MP3 to temp file and play silently via Windows MCI (no GUI pop-up)."""
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        f.write(mp3_data)
        tmp_path = Path(f.name)

    try:
        await _play_with_mci(str(tmp_path))
    except Exception as exc:
        logger.warning("MCI audio playback failed: %s", exc)
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass


async def _play_with_mci(path: str) -> None:
    """
    Play MP3 via Windows MCI (winmm.dll).
    Silent — no GUI pop-up. Blocks until playback finishes.
    Zero extra dependencies; winmm.dll is built into all Windows versions.
    """
    import ctypes

    winmm = ctypes.windll.winmm
    alias = "alice_tts"

    def _blocking_play() -> None:
        winmm.mciSendStringW(f'open "{path}" alias {alias}', None, 0, 0)
        winmm.mciSendStringW(f'play {alias} wait', None, 0, 0)
        winmm.mciSendStringW(f'close {alias}', None, 0, 0)

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _blocking_play)


async def _play_with_sounddevice(mp3_data: bytes) -> None:
    """Decode MP3 and play via sounddevice (requires pydub + ffmpeg)."""
    try:
        from pydub import AudioSegment
        import sounddevice as sd
        import numpy as np

        audio = AudioSegment.from_mp3(io.BytesIO(mp3_data))
        samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
        samples /= 2 ** (audio.sample_width * 8 - 1)

        if audio.channels == 2:
            samples = samples.reshape(-1, 2)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: sd.play(samples, samplerate=audio.frame_rate, blocking=True),
        )
    except ImportError:
        logger.warning("pydub not installed — cannot play audio via sounddevice.")
    except Exception as exc:
        logger.error("Audio playback error: %s", exc)
