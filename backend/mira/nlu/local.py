"""Local understanding: rules for slots + a trained classifier for intent, with a safe hand-off to Gemini.

`understand_locally` returns an `Understanding`-shaped dict when it is confident, or None plus a reason when
the turn should go to the LLM. "Confident" means all of:
  * the classifier's top intent has probability >= CONFIDENCE and is one the rules can fully fill in;
  * the extractor found nothing it could not read with certainty (relative dates, children without ages,
    several tours, "the second one" references to earlier turns, ...).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from mira.nlu import intent as intent_model
from mira.nlu.extractor import extract

CONFIDENCE = 0.5
# Intents whose slots the rules can fill completely. custom_trip / service_request / other need free-text
# understanding (what service? what kind of trip?), so they always go to the LLM.
LOCAL_INTENTS = {"greeting", "quote", "tour_info", "general_question", "off_topic", "prompt_injection", "update_party", "booking"}
_ANAPHORA = re.compile(r"\b(it|that|this|those|these|them|the (first|second|third|last|other|same|cheaper|previous) one|that one|the one|instead|actually|also|too)\b", re.I)


@dataclass
class LocalResult:
    understanding: dict | None
    reason: str
    intent: str = ""
    confidence: float = 0.0


def understand_locally(text: str, has_history: bool, published: set[str], tour_categories: dict[str, str],
                       today: date) -> LocalResult:
    text = (text or "").strip()
    if not text or len(text) > 600:
        return LocalResult(None, "empty or very long message")
    label, prob = intent_model.predict(text)
    ex = extract(text, published, tour_categories, today)
    base = {"intent": label, "confidence": prob}
    if label not in LOCAL_INTENTS:
        return LocalResult(None, f"intent '{label}' needs the LLM", label, prob)
    if prob < CONFIDENCE:
        return LocalResult(None, f"low intent confidence ({prob:.2f})", label, prob)
    if ex.ambiguities:
        return LocalResult(None, "ambiguous: " + "; ".join(ex.ambiguities), label, prob)
    if has_history and label in ("tour_info", "general_question", "quote", "booking") and _ANAPHORA.search(text) \
            and not ex.tour_id and label != "booking":
        return LocalResult(None, "refers to an earlier turn", label, prob)
    if label == "update_party" and ex.adults is None and ex.child_ages is None and not ex.start_date:
        return LocalResult(None, "party change without numbers", label, prob)
    if label == "quote" and not ex.wants_price and not (ex.tour_id or ex.adults or ex.start_date):
        return LocalResult(None, "quote without price or slots", label, prob)

    u = ex.slots()
    u["intent"] = label
    if label == "quote":
        u["wants_price"] = True
    if label in ("tour_info", "general_question"):
        u["question"] = text
    return LocalResult(u, "local", label, prob)
