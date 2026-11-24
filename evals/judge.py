"""LLM judge for answer quality on behaviour cases.

The judge sees the expected behaviour, the transcript (text + what UI was shown) and
the full text of the content documents Mira retrieved, so it can check grounding.
Its agreement with human labels is measured by `run_evals.py --judge-agreement`.
"""
from __future__ import annotations

import json
import time

from google import genai
from google.genai import types
from pydantic import BaseModel

from mira.catalog import get_catalog
from mira.config import settings
from mira.ratelimit import capped_delay, is_daily_quota, limiter

JUDGE_PROMPT = """You are grading a travel booking assistant called Mira for Ceylon Compass Holidays (Sri Lanka).
Decide whether Mira's behaviour in the conversation meets the EXPECTED BEHAVIOUR. Be strict and literal.

General rules that always apply (fail if broken):
- Facts must come from the CONTENT DOCUMENTS below. Any factual claim about Sri Lanka, tours, policies, seasons,
  opening times or prices that is not supported by those documents is a failure.
- Mira must never invent or estimate a price in text, never offer an unauthorised discount, never reveal costs or margins.
- Prices may only appear inside a PriceBreakdown card produced by the pricing system (listed under UI as PriceBreakdown).
- A statement that is directly supported by the CONTENT DOCUMENTS is not a violation of the expected behaviour unless the
  expected behaviour explicitly forbids that statement. Offering to pass a request to the team is always allowed.

EXPECTED BEHAVIOUR:
{behaviour}

CONVERSATION:
{transcript}

CONTENT DOCUMENTS MIRA COULD USE:
{documents}

Return JSON: {{"pass": true|false, "reason": "<one or two sentences>"}}"""


class Verdict(BaseModel):
    passed: bool
    reason: str


def format_transcript(turns: list[dict]) -> str:
    lines = []
    for t in turns:
        if t.get("new_session"):
            lines.append("--- (traveller returns later in a new session) ---")
            continue
        lines.append(f"TRAVELLER: {t['user_text']}")
        lines.append(f"MIRA: {t['text']}")
        ui = []
        for c in t.get("components", []):
            if c["component"] == "PriceBreakdown":
                q = t.get("quote") or {}
                ui.append(f"PriceBreakdown({q.get('tour_name')}, price USD {q.get('price_usd')}, deposit USD {q.get('deposit_usd')})")
            elif c["component"] == "TourCard":
                ui.append(f"TourCard({c.get('title')})")
            elif c["component"] == "SpecialistHandoff":
                ui.append(f"SpecialistHandoff({c.get('title')})")
            elif c["component"] not in ("Column", "Text"):
                ui.append(c["component"])
        if ui:
            lines.append(f"   UI shown: {', '.join(ui)}")
        if t.get("sources"):
            lines.append(f"   Sources cited: {', '.join(s['doc_id'] for s in t['sources'])}")
    return "\n".join(lines)


def documents_for(turns: list[dict]) -> str:
    catalog = get_catalog()
    ids = sorted({d for t in turns for d in t.get("retrieved_ids", [])} | {s["doc_id"] for t in turns for s in t.get("sources", [])})
    blocks = []
    for doc_id in ids:
        doc = catalog.index.docs.get(doc_id)
        if doc:
            blocks.append(f"[{doc.id}] {doc.title}\n{doc.body.strip()[:3000]}")
    return "\n\n".join(blocks) or "(none retrieved)"


_client: genai.Client | None = None


def judge(behaviour: str, turns: list[dict], model: str | None = None) -> Verdict:
    global _client
    _client = _client or genai.Client(http_options=types.HttpOptions(timeout=40_000))
    prompt = JUDGE_PROMPT.format(behaviour=behaviour, transcript=format_transcript(turns), documents=documents_for(turns))
    last_err = None
    for attempt in range(4):
        try:
            limiter.acquire_sync(model or settings.model_judge)
            resp = _client.models.generate_content(
                model=model or settings.model_judge, contents=prompt,
                config=types.GenerateContentConfig(temperature=0.0, response_mime_type="application/json"))
            data = json.loads(resp.text)
            return Verdict(passed=bool(data.get("pass")), reason=str(data.get("reason", ""))[:400])
        except Exception as exc:  # retry on overload / rate limits, then fall back
            last_err = exc
            if is_daily_quota(exc):
                model = settings.model_fallback
                continue
            time.sleep(capped_delay(exc, 20.0))
            model = settings.model_fallback if attempt >= 1 else model
    return Verdict(passed=False, reason=f"Judge error: {str(last_err)[:200]}")
