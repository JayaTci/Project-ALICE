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
    """Save MP3 to temp file and play via Windows Media Player / default player."""
    import subprocess

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        f.write(mp3_data)
        tmp_path = f.name

    try:
        # Use Windows built-in player (non-blocking — returns immediately)
        proc = await asyncio.create_subprocess_exec(
            "powershell", "-c",
            f"(New-Object Media.SoundPlayer '{tmp_path}').PlaySync()",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        # For MP3, SoundPlayer doesn't work — use Windows Media Player via COM
        # Fallback: use mplayer/vlc/ffplay if available, else shell open
        proc.kill()  # kill the failed attempt

        proc2 = await asyncio.create_subprocess_exec(
            "cmd", "/c", "start", "/wait", "", tmp_path,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc2.wait()
    except Exception:
        # Last resort: sounddevice with pydub
        await _play_with_sounddevice(mp3_data)
    finally:
        try:
            Path(tmp_path).unlink()
        except OSError:
            pass


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
