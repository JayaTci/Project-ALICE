"""
Phase 3.5 — Step 1: Generate synthetic "hey alice" audio samples.

Uses Edge-TTS with multiple voices, speeds, and pitch variations to create
a diverse training set. No external dependencies beyond edge-tts.

Usage:
  py -3.14 scripts/generate_hey_alice.py

Output: data/wake_word_samples/positive/*.wav  (hey alice variations)
        data/wake_word_samples/negative/*.wav  (similar-sounding phrases)
"""

import asyncio
import io
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import edge_tts
import soundfile as sf
import numpy as np

OUT_DIR = Path(__file__).parent.parent / "data" / "wake_word_samples"
POSITIVE_DIR = OUT_DIR / "positive"
NEGATIVE_DIR = OUT_DIR / "negative"

SAMPLE_RATE = 16000

# Variations of the target phrase
POSITIVE_PHRASES = [
    "hey alice",
    "Hey Alice",
    "hey, alice",
    "Hey, Alice",
    "hey alice,",
    "Hey Alice,",
]

# Similar-sounding / common phrases (hard negatives)
NEGATIVE_PHRASES = [
    "hey siri",
    "okay google",
    "hello there",
    "hey listen",
    "hey everyone",
    "alice in wonderland",
    "hey alicia",
    "hey alyssa",
    "what time is it",
    "open chrome",
    "good morning",
]

# Multiple voices for diversity
EN_VOICES = [
    "en-US-AriaNeural",
    "en-US-GuyNeural",
    "en-US-JennyNeural",
    "en-GB-SoniaNeural",
    "en-AU-NatashaNeural",
    "en-CA-ClaraNeural",
]

# Rate/pitch variations to simulate real-world speech
VARIATIONS = [
    {"rate": "+0%",  "pitch": "+0Hz"},
    {"rate": "+10%", "pitch": "+0Hz"},
    {"rate": "-10%", "pitch": "+0Hz"},
    {"rate": "+0%",  "pitch": "+5Hz"},
    {"rate": "+0%",  "pitch": "-5Hz"},
    {"rate": "+15%", "pitch": "+10Hz"},
    {"rate": "-15%", "pitch": "-10Hz"},
]


async def synthesize_wav(text: str, voice: str, rate: str, pitch: str) -> np.ndarray | None:
    """Synthesize text to 16kHz mono float32 numpy array via Edge-TTS."""
    try:
        communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
        mp3_chunks = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                mp3_chunks.append(chunk["data"])
        if not mp3_chunks:
            return None

        mp3_data = b"".join(mp3_chunks)

        # Decode MP3 → WAV using soundfile + io trick via ffmpeg subprocess
        import subprocess, tempfile
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(mp3_data)
            mp3_path = f.name

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wav_path = f.name

        # Convert to 16kHz mono WAV using ffmpeg
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", mp3_path, "-ar", "16000", "-ac", "1", wav_path],
            capture_output=True, timeout=15,
        )
        os.unlink(mp3_path)

        if result.returncode != 0:
            os.unlink(wav_path)
            return None

        audio, sr = sf.read(wav_path, dtype="float32")
        os.unlink(wav_path)
        return audio

    except Exception as exc:
        print(f"  [skip] {exc}")
        return None


async def generate_set(phrases: list[str], out_dir: Path, label: str) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for phrase in phrases:
        for voice in EN_VOICES:
            for var in VARIATIONS:
                filename = out_dir / f"{label}_{count:04d}.wav"
                if filename.exists():
                    count += 1
                    continue
                audio = await synthesize_wav(phrase, voice, var["rate"], var["pitch"])
                if audio is not None:
                    sf.write(str(filename), audio, SAMPLE_RATE)
                    count += 1
                    if count % 20 == 0:
                        print(f"  {label}: {count} samples")
    return count


async def main() -> None:
    print("=== Phase 3.5: Generating 'hey alice' training samples ===")
    print(f"Output: {OUT_DIR}")
    print()

    # Check ffmpeg available
    import subprocess
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("ERROR: ffmpeg not found. Install it:")
        print("  winget install Gyan.FFmpeg")
        print("  Then restart terminal and re-run this script.")
        sys.exit(1)

    print("Generating POSITIVE samples (hey alice)...")
    pos_count = await generate_set(POSITIVE_PHRASES, POSITIVE_DIR, "positive")
    print(f"  → {pos_count} positive samples generated")

    print("\nGenerating NEGATIVE samples (hard negatives)...")
    neg_count = await generate_set(NEGATIVE_PHRASES, NEGATIVE_DIR, "negative")
    print(f"  → {neg_count} negative samples generated")

    print(f"\nDone! Total: {pos_count + neg_count} samples in {OUT_DIR}")
    print("Next step: run scripts/train_hey_alice.py")


if __name__ == "__main__":
    asyncio.run(main())
