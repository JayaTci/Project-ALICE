"""
TTS using Microsoft Edge-TTS (free, cloud, high quality).
Supports English and Japanese with natural neural voices.
"""

import asyncio
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

RATE = "+0%"
PITCH = "+0Hz"


async def synthesize(text: str, language: str = "en") -> bytes:
    """Synthesize text to MP3 bytes using Edge-TTS."""
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
    """Synthesize and play audio. Logs errors but never raises."""
    if not text.strip():
        return
    logger.info("TTS: synthesizing %d chars [%s]", len(text), language)
    try:
        mp3_data = await synthesize(text, language)
        logger.info("TTS: synthesized %d bytes — starting playback", len(mp3_data))
        await _play_mp3(mp3_data)
        logger.info("TTS: playback complete")
    except Exception as exc:
        logger.error("TTS speak failed: %s", exc)


async def _play_mp3(mp3_data: bytes) -> None:
    """Save to temp file, try MCI then PowerShell fallback."""
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        f.write(mp3_data)
        tmp_path = Path(f.name)

    try:
        try:
            logger.debug("TTS: attempting MCI playback")
            await _play_with_mci(str(tmp_path))
            logger.debug("TTS: MCI playback returned")
        except Exception as mci_exc:
            logger.warning("TTS: MCI failed (%s) — trying PowerShell fallback", mci_exc)
            await _play_with_powershell(str(tmp_path))
            logger.debug("TTS: PowerShell playback returned")
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass


async def _play_with_mci(path: str) -> None:
    """
    Play MP3 via Windows MCI (winmm.dll).
    Raises RuntimeError if MCI returns a non-zero error code.
    """
    import ctypes
    winmm = ctypes.windll.winmm
    alias = "alice_tts"

    def _blocking_play() -> None:
        # Close any stale alias from a previous call
        winmm.mciSendStringW(f"close {alias}", None, 0, 0)

        # Open with explicit type for reliable MP3 support
        ret = winmm.mciSendStringW(f'open "{path}" type mpegvideo alias {alias}', None, 0, 0)
        if ret != 0:
            raise RuntimeError(f"MCI open failed (code {ret})")

        try:
            ret = winmm.mciSendStringW(f"play {alias} wait", None, 0, 0)
            if ret != 0:
                raise RuntimeError(f"MCI play failed (code {ret})")
        finally:
            winmm.mciSendStringW(f"close {alias}", None, 0, 0)

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _blocking_play)


async def _play_with_powershell(path: str) -> None:
    """
    Play MP3 via PowerShell WPF MediaPlayer — fallback when MCI fails.
    Available on all Windows versions with .NET Framework.
    """
    # Escape backslashes for PowerShell
    ps_path = path.replace("\\", "\\\\")
    script = (
        "Add-Type -AssemblyName PresentationCore; "
        "$p = New-Object System.Windows.Media.MediaPlayer; "
        f"$p.Open([System.Uri]::new('{ps_path}')); "
        "$p.Play(); "
        "Start-Sleep -Milliseconds 800; "
        "while (-not $p.NaturalDuration.HasTimeSpan) { Start-Sleep -Milliseconds 100 }; "
        "$ms = [int]($p.NaturalDuration.TimeSpan.TotalMilliseconds); "
        "Start-Sleep -Milliseconds $ms; "
        "$p.Stop(); $p.Close()"
    )

    loop = asyncio.get_event_loop()
    proc = await asyncio.create_subprocess_exec(
        "powershell",
        "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden",
        "-Command", script,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0 and stderr:
        raise RuntimeError(f"PowerShell playback failed: {stderr.decode(errors='replace')[:200]}")
