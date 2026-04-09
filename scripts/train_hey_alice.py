"""
Phase 3.5 — Step 2: Train "hey alice" wake word model.

Uses:
- OpenWakeWord's shared embedding model (already downloaded)
- scikit-learn MLPClassifier (tiny, fast, no torch training needed)
- Exports to ONNX for use with OpenWakeWord inference

Prerequisites:
  1. Run scripts/generate_hey_alice.py first
  2. pip install scikit-learn soundfile skl2onnx onnx

Usage:
  py -3.14 scripts/train_hey_alice.py

Output: data/hey_alice.onnx
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import soundfile as sf

POSITIVE_DIR = Path("data/wake_word_samples/positive")
NEGATIVE_DIR = Path("data/wake_word_samples/negative")
OUTPUT_MODEL = Path("data/hey_alice.onnx")
SAMPLE_RATE = 16000


def load_audio(path: Path) -> np.ndarray:
    audio, sr = sf.read(str(path), dtype="float32")
    if audio.ndim > 1:
        audio = audio[:, 0]
    return audio


def extract_embeddings(audio_files: list[Path]) -> np.ndarray:
    """Use OWW's embedding model to extract feature vectors from audio clips."""
    from openwakeword.model import Model
    from openwakeword.utils import AudioFeatures

    # Load OWW just for its preprocessor (embedding model)
    m = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
    preprocessor = m.preprocessor

    all_embeddings = []
    for path in audio_files:
        try:
            audio = load_audio(path)
            # Convert to int16 for OWW
            int16 = (audio * 32767).astype(np.int16)
            # embed_clips expects list of audio arrays
            embeddings = preprocessor.embed_clips([int16], batch_size=1)
            if embeddings is not None and len(embeddings) > 0:
                # Use mean pooling over time frames
                emb = np.array(embeddings).mean(axis=0).flatten()
                all_embeddings.append(emb)
        except Exception as exc:
            print(f"  [skip] {path.name}: {exc}")

    return np.array(all_embeddings)


def train() -> None:
    from sklearn.neural_network import MLPClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import Pipeline
    from sklearn.model_selection import cross_val_score

    print("=== Phase 3.5: Training 'hey alice' wake word model ===\n")

    pos_files = list(POSITIVE_DIR.glob("*.wav"))
    neg_files = list(NEGATIVE_DIR.glob("*.wav"))

    if not pos_files:
        print(f"ERROR: No positive samples found in {POSITIVE_DIR}")
        print("Run scripts/generate_hey_alice.py first.")
        sys.exit(1)

    print(f"Positive samples: {len(pos_files)}")
    print(f"Negative samples: {len(neg_files)}")

    print("\nExtracting embeddings from positive samples...")
    X_pos = extract_embeddings(pos_files)
    y_pos = np.ones(len(X_pos))

    print(f"Extracting embeddings from negative samples...")
    X_neg = extract_embeddings(neg_files)
    y_neg = np.zeros(len(X_neg))

    X = np.vstack([X_pos, X_neg])
    y = np.concatenate([y_pos, y_neg])
    print(f"\nFeature matrix: {X.shape}")

    print("Training MLP classifier...")
    clf = Pipeline([
        ("scaler", StandardScaler()),
        ("mlp", MLPClassifier(
            hidden_layer_sizes=(64, 32),
            max_iter=500,
            random_state=42,
            early_stopping=True,
        )),
    ])

    scores = cross_val_score(clf, X, y, cv=5, scoring="f1")
    print(f"Cross-val F1: {scores.mean():.3f} ± {scores.std():.3f}")

    clf.fit(X, y)
    print("Model trained.")

    # Export to ONNX
    try:
        from skl2onnx import convert_sklearn
        from skl2onnx.common.data_types import FloatTensorType

        initial_type = [("float_input", FloatTensorType([None, X.shape[1]]))]
        onnx_model = convert_sklearn(clf, initial_types=initial_type)

        OUTPUT_MODEL.parent.mkdir(exist_ok=True)
        with open(OUTPUT_MODEL, "wb") as f:
            f.write(onnx_model.SerializeToString())
        print(f"\nModel saved: {OUTPUT_MODEL}")
        print(f"Set WAKE_WORD_MODEL={OUTPUT_MODEL} in .env to use it.")
    except ImportError:
        # Save as pickle fallback
        import pickle
        pkl_path = OUTPUT_MODEL.with_suffix(".pkl")
        with open(pkl_path, "wb") as f:
            pickle.dump(clf, f)
        print(f"\nONNX export skipped (pip install skl2onnx onnx for ONNX).")
        print(f"Model saved as pickle: {pkl_path}")


if __name__ == "__main__":
    train()
