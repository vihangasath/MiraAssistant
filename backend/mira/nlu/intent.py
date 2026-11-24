"""Intent classifier: TF-IDF (word 1-2 grams) + logistic regression, trained on `training_data.py`.

Small enough to train in under a second, so if the saved model file is missing or was built with another
scikit-learn version it is simply retrained on load. Training needs no API calls and no GPU.
"""
from __future__ import annotations

import re
from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from mira.nlu.training_data import build

MODEL_PATH = Path(__file__).parent / "intent_model.joblib"
_model: Pipeline | None = None


def _prep(text: str) -> str:
    text = text.lower().replace("’", "'")
    text = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", " isodate ", text)
    text = re.sub(r"\b\d+(st|nd|rd|th)?\b", " num ", text)
    return re.sub(r"[^a-z' ]", " ", text)


def train(seed: int = 7) -> Pipeline:
    rows = build(seed)
    X, y = [t for t, _ in rows], [l for _, l in rows]
    pipe = Pipeline([
        ("tfidf", TfidfVectorizer(preprocessor=_prep, ngram_range=(1, 2), sublinear_tf=True, min_df=1)),
        ("clf", LogisticRegression(C=12.0, max_iter=2000, class_weight="balanced")),
    ])
    pipe.fit(X, y)
    return pipe


def get_model() -> Pipeline:
    global _model
    if _model is None:
        try:
            _model = joblib.load(MODEL_PATH)
        except Exception:        # missing file or version mismatch -> retrain (takes well under a second)
            _model = train()
    return _model


def predict(text: str) -> tuple[str, float]:
    """Return (intent, probability of that intent)."""
    model = get_model()
    probs = model.predict_proba([text])[0]
    i = int(probs.argmax())
    return str(model.classes_[i]), float(probs[i])
