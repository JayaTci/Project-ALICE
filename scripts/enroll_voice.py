"""
Phase 5 — Voice Enrollment Wizard.
Records Chester's voice samples and saves speaker embeddings.

Run once:
  py -3.14 scripts/enroll_voice.py

Records 5 prompts × ~3 seconds each = ~15 seconds total.
"""

import asyncio
import sys
import time
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf

sys.path.insert(0, str(Path(__file__).parent.parent))

SAMPLE_RATE = 16000
RECORD_SECONDS = 3
ENROLLMENT_DIR = Path("data/voice_enrollment")

PROMPTS = [
    "Hey Alice, open Chrome",
    "Hey Alice, what's the weather today?",
    "Hey Alice, give me the latest news",
    "Alice, what time is it right now?",
    "Hey Alice, I need your help with something",
]


def record_clip(prompt: str, duration: float = RECORD_SECONDS) -> np.ndarray:
    print(f"\n  Say: \"{prompt}\"")
    print(f"  Recording in 2 seconds...", end="", flush=True)
    time.sleep(2)
    print(f" GO! ({duration}s)")

    audio = sd.rec(
        int(duration * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
    )
    sd.wait()
    return audio.flatten()


def main() -> None:
    print("=" * 50)
    print("  Alice — Voice Enrollment Wizard")
    print("=" * 50)
    print()
    print("This wizard records your voice so Alice can")
    print("recognize you and reject unauthorized users.")
    print()
    print("You'll be asked to say 5 short phrases.")
    print("Speak clearly, at a normal volume.")
    print()
    input("Press Enter when ready...")

    clips = []
    for i, prompt in enumerate(PROMPTS, 1):
        print(f"\n[{i}/{len(PROMPTS)}]", end="")
        clip = record_clip(prompt)
        clips.append(clip)

        # Save raw WAV for reference
        ENROLLMENT_DIR.mkdir(parents=True, exist_ok=True)
        wav_path = ENROLLMENT_DIR / f"sample_{i:02d}.wav"
        sf.write(str(wav_path), clip, SAMPLE_RATE)
        print(f"  Saved: {wav_path}")

    print("\nExtracting speaker embeddings...")
    from alice.audio.speaker_verify import enroll_from_audio
    enroll_from_audio(clips)

    print("\n✓ Enrollment complete!")
    print("Enable verification by setting SPEAKER_VERIFY_ENABLED=true in .env")
    print()


if __name__ == "__main__":
    main()
