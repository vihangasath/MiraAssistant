"""Train the intent classifier and report accuracy on the held-out set.

    cd backend && uv run python -m mira.nlu.train
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import joblib

from mira.nlu import intent

HELDOUT = Path(__file__).parent / "data" / "heldout.jsonl"


def evaluate(model=None, threshold: float = 0.0) -> dict:
    model = model or intent.get_model()
    rows = [json.loads(l) for l in HELDOUT.read_text().splitlines() if l.strip()]
    ok, wrong, covered = 0, [], 0
    for r in rows:
        probs = model.predict_proba([r["text"]])[0]
        i = int(probs.argmax())
        pred, p = str(model.classes_[i]), float(probs[i])
        if p < threshold:
            continue
        covered += 1
        if pred == r["intent"]:
            ok += 1
        else:
            wrong.append((r["text"], r["intent"], pred, round(p, 2)))
    return {"n": len(rows), "covered": covered, "correct": ok, "wrong": wrong}


if __name__ == "__main__":
    model = intent.train()
    joblib.dump(model, intent.MODEL_PATH)
    print(f"saved {intent.MODEL_PATH.name}; classes: {dict(Counter(intent.build()[i][1] for i in range(len(intent.build()))))}")
    for th in (0.0, 0.5, 0.6, 0.7):
        r = evaluate(model, th)
        print(f"threshold {th}: answered {r['covered']}/{r['n']}, correct {r['correct']}/{r['covered']}")
    for w in evaluate(model)["wrong"]:
        print("  MISS", w)
