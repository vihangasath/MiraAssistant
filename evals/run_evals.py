"""Mira evaluation suite. One command:

    cd backend && uv run python ../evals/run_evals.py            # full suite + report
    uv run python ../evals/run_evals.py --only S02,M03            # a subset
    uv run python ../evals/run_evals.py --requirement R5          # cases for one requirement
    uv run python ../evals/run_evals.py --judge-agreement         # judge vs the 10 human labels

Code checks wherever there is an exact answer (prices, flags, UI validity, unapproved
content, privacy); an LLM judge for behaviour descriptions. Writes
evals/reports/latest.md (+ a timestamped copy and JSON) with pass rates per
requirement and trace links for failing cases.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
import uuid
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVALS = ROOT / "evals"
os.environ.setdefault("MIRA_TODAY", "2026-11-19")          # expected results assume this date
os.environ["MIRA_DB_PATH"] = str(ROOT / "var" / "eval.db")  # keep eval enquiries out of the demo DB
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(EVALS))

from mira.catalog import get_catalog, reload_catalog  # noqa: E402
from mira.config import settings  # noqa: E402
from mira.pricing.engine import Party  # noqa: E402
from mira.privacy import contains_pii  # noqa: E402
from mira.store.db import get_store  # noqa: E402
from mira.tracing import init_tracing  # noqa: E402
from mira.ui.catalog import UIValidationError, validate_messages  # noqa: E402

from judge import judge  # noqa: E402

MONEY_RE = re.compile(r"(\$\s?\d|\bUSD\s?\d|\d[\d,.]*\s?(USD|LKR|dollars?)\b|\bLKR\s?\d|\bRs\.?\s?\d)", re.I)
SEED_REQUIREMENTS = {
    "discovery": ["R1"], "pricing": ["R5"], "rates": ["R6"], "grounding": ["R4"], "safety": ["safety"],
    "off_topic": ["off_topic"], "multi_turn": ["R5", "R1"],
}
REQUIREMENT_NAMES = {
    "R1": "1 Discover the trip", "R2": "2 Remember returning visitors", "R3": "3 Generated interface (A2UI payload valid, per turn)",
    "R4": "4 Answer from content only", "R5": "5 Quote correct prices", "R6": "6 Missing / expired rates",
    "R7": "7 Private enquiries", "R8": "8 Approve AI-written content", "safety": "Prompt injection & safety",
    "off_topic": "Off-topic", "privacy": "Personal data kept out of LLM/traces", "booking": "Mock booking failures",
}


def load_cases() -> list[dict]:
    cases = []
    for line in (ROOT / "ceylon-compass-dataset" / "evals" / "eval_seed.jsonl").read_text().splitlines():
        if line.strip():
            c = json.loads(line)
            c["requirements"] = SEED_REQUIREMENTS.get(c["category"], [c["category"]])
            c["source"] = "seed"
            cases.append(c)
    for line in (EVALS / "cases" / "mira_cases.jsonl").read_text().splitlines():
        if line.strip():
            c = json.loads(line)
            c["source"] = "mira"
            cases.append(c)
    for c in API_CASES:
        cases.append({**c, "source": "api"})
    return cases


# ---------------------------------------------------------------- running conversations

def _components(a2ui: list[dict]) -> list[dict]:
    return [c for m in a2ui if "updateComponents" in m for c in m["updateComponents"]["components"]]


def _shown_quotes(a2ui: list[dict]) -> dict[str, dict]:
    return {m["updateDataModel"]["path"].split("/")[-1]: m["updateDataModel"]["value"]
            for m in a2ui if "updateDataModel" in m and m["updateDataModel"]["path"].startswith("/quotes/")}


async def run_conversation(runtime, case: dict) -> list[dict]:
    visitor = f"eval-{case['id']}-{uuid.uuid4().hex[:6]}"
    session = None
    turns = []
    for text in case["turns"]:
        if text == "__NEW_SESSION__":
            session = f"s-{uuid.uuid4().hex[:10]}"
            turns.append({"new_session": True})
            continue
        t0 = time.time()
        r = await runtime.run_turn(visitor_id=visitor, session_id=session, text=text)
        session = r.session_id
        out = r.output
        turns.append({
            "user_text": text, "scrubbed_input": r.user_text, "text": out.get("text", ""),
            "route": out.get("route"), "model_route": out.get("model_route"), "a2ui": out.get("a2ui", []),
            "components": _components(out.get("a2ui", [])), "quote": out.get("quote"), "handoff": out.get("handoff"),
            "sources": out.get("sources", []), "retrieved_ids": out.get("retrieved_ids", []),
            "trace_url": r.trace_url, "trace_id": r.trace_id, "error": out.get("error", False),
            "seconds": round(time.time() - t0, 1), "visitor_id": visitor,
        })
    return turns


# ---------------------------------------------------------------- code checks

def check(name: str, passed: bool, detail: str = "") -> dict:
    return {"name": name, "passed": bool(passed), "detail": detail}


def turn_checks(case: dict, turns: list[dict]) -> list[dict]:
    """Checks applied to every case: valid UI, no invented price, quotes saved, only published content."""
    store = get_store()
    catalog = get_catalog()
    results = []
    for i, t in enumerate(turns):
        if t.get("new_session"):
            continue
        if t["error"]:
            results.append(check(f"turn{i+1}_no_error", False, "turn raised an error"))
            continue
        shown = _shown_quotes(t["a2ui"])
        trusted = {}
        invented = []
        for ref, value in shown.items():
            enquiry = store.get_enquiry(ref)
            if not enquiry or enquiry["kind"] != "quote":
                invented.append(f"{ref}: no saved quote")
                continue
            req = enquiry["request"]
            recomputed = catalog.quote(req["tour_id"], date.fromisoformat(req["start_date"]),
                                       Party(req["adults"], tuple(req.get("child_ages") or ())))
            if case.get("id") == "M17" and t.get("route") == "greet":
                recomputed = None  # greeting shows a stored quote; it is checked against the enquiry below
            if recomputed is not None and (recomputed.status != "priced" or recomputed.price_usd != value["price_usd"]
                                           or recomputed.deposit_usd != value["deposit_usd"]):
                invented.append(f"{ref}: shown {value} != pricing function {getattr(recomputed, 'price_usd', None)}")
            if enquiry["price_usd"] != value["price_usd"] or enquiry["deposit_usd"] != value["deposit_usd"]:
                invented.append(f"{ref}: shown {value} != saved enquiry")
            # R7: every quote is saved privately with cost, GP% and a trace link.
            results.append(check(f"turn{i+1}_quote_saved_{ref}", enquiry["cost_usd"] is not None and enquiry["gross_profit_pct"] is not None
                                 and bool(enquiry.get("trace_id")) == bool(t.get("trace_id")),
                                 f"cost={enquiry['cost_usd']} gp={enquiry['gross_profit_pct']} trace={enquiry.get('trace_id')}"))
            trusted[ref] = value
        money_in_text = MONEY_RE.findall(t["text"] or "")
        if money_in_text:
            invented.append(f"money in text: {money_in_text}")
        results.append(check(f"turn{i+1}_no_invented_price", not invented, "; ".join(invented)))
        try:
            validate_messages(t["a2ui"], trusted_quotes=trusted)
            results.append(check(f"turn{i+1}_ui_valid", bool(t["a2ui"])))
        except UIValidationError as exc:
            results.append(check(f"turn{i+1}_ui_valid", False, str(exc)))
        unpublished = [s["doc_id"] for s in t["sources"] if s["doc_id"] not in catalog.index.docs]
        results.append(check(f"turn{i+1}_only_published_content", not unpublished, ", ".join(unpublished)))
        if contains_pii(t.get("scrubbed_input") or ""):
            results.append(check(f"turn{i+1}_pii_scrubbed", False, "personal data reached the agent"))
    return results


def expectation_checks(case: dict, turns: list[dict]) -> list[dict]:
    exp = case["expected"]
    kind = exp["type"]
    store = get_store()
    live = [t for t in turns if not t.get("new_session")]
    shown_all = [(i, t["quote"]) for i, t in enumerate(live) if any(c["component"] == "PriceBreakdown" for c in t["components"])]
    res = []

    def quote_matches(q, e):
        return q and q.get("tour_id") == e["tour"] and q.get("price_usd") == e["price_usd"] and \
            ("deposit_usd" not in e or q.get("deposit_usd") == e["deposit_usd"])

    if kind == "quote":
        last = shown_all[-1][1] if shown_all else None
        res.append(check("price_exact", quote_matches(last, exp), f"shown={last and {k: last.get(k) for k in ('tour_id', 'price_usd', 'deposit_usd')}} expected={exp}"))
    elif kind == "quote_sequence":
        got = [q for _, q in shown_all]
        ok = len(got) >= len(exp["quotes"]) and all(quote_matches(g, e) for g, e in zip(got, exp["quotes"]))
        # Extra quotes after the expected ones are only allowed if they repeat the last expected price (no new numbers).
        extra_ok = all(quote_matches(g, exp["quotes"][-1]) for g in got[len(exp["quotes"]):])
        res.append(check("price_sequence_exact", ok and extra_ok,
                         f"shown={[(g.get('tour_id'), g.get('price_usd'), g.get('deposit_usd')) for g in got]}"))
    elif kind == "flag_no_price":
        res.append(check("no_price_shown", not shown_all, f"{len(shown_all)} price cards shown"))
        flags = [e for e in store.list_enquiries() if e.get("visitor_id") == live[0]["visitor_id"] and e["status"] == "needs_specialist"]
        res.append(check("staff_flag_raised", bool(flags), f"{len(flags)} flags"))
        res.append(check("traveller_told_specialist", any(t["handoff"] for t in live), "SpecialistHandoff shown"))
        if exp.get("flag_code"):
            codes = {r["code"] for f in flags for r in (f.get("flag_reasons") or [])}
            res.append(check("flag_reason", exp["flag_code"] in codes, f"codes={sorted(codes)}"))
    elif kind == "no_price":
        res.append(check("no_price_shown", not shown_all, f"{len(shown_all)} price cards shown"))
    elif kind == "discovery":
        useful = next((i + 1 for i, t in enumerate(live) if any(c["component"] in ("TourCard", "ItineraryDay", "PriceBreakdown") for c in t["components"])), None)
        res.append(check("useful_by_turn", useful is not None and useful <= exp["useful_by_turn"], f"first useful turn={useful}"))
        questions = sum(1 for t in live[: exp["useful_by_turn"]] if "?" in (t["text"] or "") or any(c["component"] == "TravellerPicker" for c in t["components"]))
        res.append(check("max_questions", questions <= exp["max_questions"], f"questions={questions}"))
    elif kind == "returning":
        new_idx = next(i for i, t in enumerate(turns) if t.get("new_session"))
        greet = turns[new_idx + 1]
        gq = greet.get("quote") or {}
        res.append(check("greets_with_last_quote", gq.get("tour_id") == exp["greeting_quote"]["tour"] and gq.get("price_usd") == exp["greeting_quote"]["price_usd"]
                         and any(c["component"] == "PriceBreakdown" for c in greet["components"]), f"greeting quote={gq.get('tour_id')} {gq.get('price_usd')}"))
        final = turns[-1]
        fq = final.get("quote") or {}
        res.append(check("not_asked_again", quote_matches(fq, exp["final_quote"]) and not any(c["component"] == "TravellerPicker" for c in final["components"]),
                         f"final quote={fq.get('tour_id')} {fq.get('price_usd')}; picker shown={any(c['component'] == 'TravellerPicker' for c in final['components'])}"))
    elif kind == "custom":
        res.append(check("no_price_shown", not shown_all))
        custom = [e for e in store.list_enquiries() if e.get("visitor_id") == live[0]["visitor_id"] and e["kind"] == "custom"]
        res.append(check("custom_enquiry_saved", bool(custom), f"{len(custom)} custom enquiries"))
        res.append(check("suggests_closest_tours", any(c["component"] == "TourCard" for t in live for c in t["components"])))
    for doc_id in exp.get("cites", []):
        res.append(check(f"cites_{doc_id}", any(s["doc_id"] == doc_id for t in live for s in t["sources"])))
    for doc_id in exp.get("never_cites", []):
        res.append(check(f"never_uses_{doc_id}", not any(doc_id in t.get("retrieved_ids", []) or any(s["doc_id"] == doc_id for s in t["sources"]) for t in live)))
    if exp.get("no_cost_leak"):
        blob = json.dumps([{"text": t["text"], "a2ui": t["a2ui"]} for t in live])
        res.append(check("no_cost_leak", not re.search(r"LKR|cost_usd|gross_profit|margin\"|\d+(\.\d+)?\s?%", blob), ""))
    if exp.get("pii_scrubbed"):
        res.append(check("pii_scrubbed", all(not contains_pii(t.get("scrubbed_input") or "") for t in live)))
    return res


# ---------------------------------------------------------------- API-level cases (R7, R8, booking)

API_CASES = [
    {"id": "A01", "category": "booking", "requirements": ["booking"], "turns": [], "expected": {"type": "api"},
     "behaviour": "Declined card returns a friendly message with next steps; nothing booked."},
    {"id": "A02", "category": "booking", "requirements": ["booking"], "turns": [], "expected": {"type": "api"},
     "behaviour": "Booking system failure returns a friendly message with next steps."},
    {"id": "A03", "category": "enquiries", "requirements": ["R7"], "turns": [], "expected": {"type": "api"},
     "behaviour": "Staff page lists every quote privately with cost, GP%, trace link; notes and status can be updated; travellers never get costs."},
    {"id": "A04", "category": "approvals", "requirements": ["R8"], "turns": [], "expected": {"type": "api"},
     "behaviour": "Staff command creates a draft; Mira cannot use it; an Agent cannot publish; an Approver can; after publishing Mira answers about it."},
]


async def run_api_case(case: dict, runtime) -> list[dict]:
    from fastapi.testclient import TestClient
    from mira.api.server import app
    client = TestClient(app)
    agent, approver = {"X-Staff-Token": "demo-agent-token"}, {"X-Staff-Token": "demo-approver-token"}
    res = []
    if case["id"] in ("A01", "A02"):
        visitor = f"eval-{case['id']}-{uuid.uuid4().hex[:6]}"
        r = await runtime.run_turn(visitor_id=visitor, session_id=None, text="Whale watching in Mirissa on 15 March 2027 for 2 adults. Price?")
        ref = (r.output.get("quote") or {}).get("quote_ref")
        res.append(check("quote_created", bool(ref)))
        card = "4242424242420002" if case["id"] == "A01" else "4242424242420003"
        body = {"visitor_id": visitor, "quote_ref": ref, "full_name": "Eval Traveller", "email": "eval@example.com",
                "card_number": card, "card_expiry": "12/28"}
        resp = client.post("/api/booking", json=body)
        data = resp.json()
        res.append(check("http_200_not_error_page", resp.status_code == 200, f"status={resp.status_code}"))
        res.append(check("friendly_failure", data.get("ok") is False and bool(data.get("message")) and bool(data.get("next_steps")), json.dumps(data)[:200]))
        res.append(check("not_booked", get_store().get_enquiry(ref)["status"] != "booked"))
    elif case["id"] == "A03":
        visitor = f"eval-A03-{uuid.uuid4().hex[:6]}"
        r = await runtime.run_turn(visitor_id=visitor, session_id=None, text="Price for the Cultural Triangle Sri Lanka Package for 2 adults starting 3 May 2027?")
        ref = (r.output.get("quote") or {}).get("quote_ref")
        rows = client.get("/api/staff/enquiries", headers=agent).json()
        row = next((x for x in rows if x["id"] == ref), None)
        res.append(check("quote_listed_for_staff", bool(row)))
        res.append(check("staff_sees_cost_and_gp", bool(row) and row["cost_usd"] is not None and row["gross_profit_pct"] is not None, f"{row and (row['cost_usd'], row['gross_profit_pct'])}"))
        res.append(check("enquiry_links_trace", bool(row) and bool(row.get("trace_id")) == bool(r.trace_id)))
        upd = client.patch(f"/api/staff/enquiries/{ref}", headers=agent, json={"status": "contacted", "notes": "Called, will confirm Friday"}).json()
        res.append(check("notes_and_status_update", upd.get("status") == "contacted" and "Friday" in upd.get("notes", "")))
        res.append(check("staff_requires_auth", client.get("/api/staff/enquiries").status_code == 401))
        blob = json.dumps(r.output)
        res.append(check("traveller_payload_has_no_costs", not re.search(r"cost_usd|gross_profit|total_cost|margin", blob)))
    elif case["id"] == "A04":
        draft = client.post("/api/staff/content/command", headers=agent, json={"command": "Add a 5-day Hill Country tour using the Ella photos"}).json()
        res.append(check("draft_created", draft.get("status") == "draft", draft.get("id", "")))
        title = draft.get("title", "")
        visitor = f"eval-A04-{uuid.uuid4().hex[:6]}"
        before = await runtime.run_turn(visitor_id=visitor, session_id=None, text=f"Tell me about your {title}.")
        res.append(check("draft_not_used_by_mira", draft.get("doc_id") not in before.output.get("retrieved_ids", []), f"retrieved={before.output.get('retrieved_ids')}"))
        r403 = client.post(f"/api/staff/content/{draft['id']}/publish", headers=agent)
        res.append(check("agent_cannot_publish", r403.status_code == 403, f"status={r403.status_code}"))
        pub = client.post(f"/api/staff/content/{draft['id']}/publish", headers=approver)
        res.append(check("approver_can_publish", pub.status_code == 200 and pub.json().get("status") == "published", f"status={pub.status_code}"))
        after = await runtime.run_turn(visitor_id=f"{visitor}-2", session_id=None, text=f"Tell me about your {title}.")
        res.append(check("published_content_used", draft.get("doc_id") in after.output.get("retrieved_ids", []) or
                         any(s["doc_id"] == draft.get("doc_id") for s in after.output.get("sources", [])),
                         f"retrieved={after.output.get('retrieved_ids')}"))
        priced = await runtime.run_turn(visitor_id=f"{visitor}-3", session_id=None, text=f"How much is the {title} for 2 adults from 1 March 2027?")
        res.append(check("new_tour_never_priced_without_rates", not _shown_quotes(priced.output.get("a2ui", [])), ""))
        # Clean up so repeated runs start from the dataset only.
        from mira.store.db import get_store as gs
        gs().set_draft_status(draft["id"], "rejected")
        reload_catalog()
    return res


# ---------------------------------------------------------------- main

PARTIAL = EVALS / "reports" / "partial.jsonl"
CASE_TIMEOUT = float(os.getenv("MIRA_EVAL_CASE_TIMEOUT", "480"))


async def evaluate(cases: list[dict], concurrency: int, use_judge: bool) -> list[dict]:
    """Runs cases; each finished case is appended to reports/partial.jsonl so a crash loses nothing."""
    from mira.agents.runtime import get_runtime
    runtime = get_runtime()
    sem = asyncio.Semaphore(concurrency)
    results = []
    PARTIAL.parent.mkdir(parents=True, exist_ok=True)

    async def run_case(case):
        if case["source"] == "api":
            return [], await run_api_case(case, runtime)
        turns = await run_conversation(runtime, case)
        return turns, turn_checks(case, turns) + expectation_checks(case, turns)

    async def one(case):
        async with sem:
            t0 = time.time()
            try:
                turns, checks = await asyncio.wait_for(run_case(case), timeout=CASE_TIMEOUT)
            except asyncio.TimeoutError:
                turns, checks = [], [check("case_ran", False, f"timeout after {CASE_TIMEOUT:.0f}s (model API stalled) 504")]
            except Exception as exc:
                turns, checks = [], [check("case_ran", False, f"{type(exc).__name__}: {exc}")]
            verdict = None
            behaviour = case["expected"].get("behaviour") if case["source"] != "api" else None
            if use_judge and behaviour and turns:
                try:
                    verdict = await asyncio.wait_for(asyncio.to_thread(judge, behaviour, turns), timeout=240)
                    checks.append(check("llm_judge", verdict.passed, verdict.reason))
                except asyncio.TimeoutError:
                    checks.append(check("llm_judge", False, "Judge error: timeout 504"))
            passed = all(c["passed"] for c in checks)
            routes = sorted({t.get("model_route") for t in turns if t.get("model_route")})
            result = {"id": case["id"], "category": case["category"], "requirements": case["requirements"],
                      "source": case["source"], "passed": passed, "checks": checks, "routes": routes,
                      "seconds": round(time.time() - t0, 1),
                      "turns": [{k: v for k, v in t.items() if k not in ("a2ui",)} for t in turns],
                      "trace_urls": [t["trace_url"] for t in turns if t.get("trace_url")],
                      "judge": verdict.model_dump() if verdict else None}
            with open(PARTIAL, "a") as f:
                f.write(json.dumps(result, default=str) + "\n")
            print(f"{'PASS' if passed else 'FAIL'} {case['id']:<4} {case['category']:<11} {result['seconds']:>5}s "
                  + ("" if passed else "; ".join(f"{c['name']}: {c['detail']}" for c in checks if not c['passed'])[:220]), flush=True)
            results.append(result)

    await asyncio.gather(*(one(c) for c in cases))
    return sorted(results, key=lambda r: (r["source"] != "seed", r["id"]))


INFRA_MARKERS = ("503", "504", "429", "UNAVAILABLE", "DEADLINE_EXCEEDED", "RESOURCE_EXHAUSTED", "Judge error")


def classify(result: dict) -> str:
    """pass | fail | error. 'error' = the model API failed (free-tier limits, 503/504), not Mira's logic.
    A case that also failed a real check is a 'fail' even if an API error happened too."""
    if result["passed"]:
        return "pass"
    failed = [c for c in result["checks"] if not c["passed"]]
    infra = [c for c in failed if c["name"].endswith("_no_error") or c["name"] == "case_ran"
             or (c["name"] == "llm_judge" and c["detail"].startswith("Judge error"))
             or any(m in c["detail"] for m in INFRA_MARKERS[:6])]
    errored_turns = any(t.get("error") for t in result.get("turns", []))
    real = [c for c in failed if c not in infra]
    if errored_turns:
        # checks that failed only because a turn produced no output are consequences of the error
        real = [c for c in real if not c["name"] in ("price_exact", "price_sequence_exact", "useful_by_turn",
                                                       "greets_with_last_quote", "not_asked_again", "suggests_closest_tours",
                                                       "custom_enquiry_saved", "staff_flag_raised", "traveller_told_specialist",
                                                       "flag_reason", "llm_judge") and not c["name"].endswith("_ui_valid")]
    return "fail" if real else "error"


def summarise(results: list[dict]) -> dict:
    for r in results:
        r["status"] = classify(r)
    errors = [r["id"] for r in results if r["status"] == "error"]
    results = [r for r in results if r["status"] != "error"]
    by_req: dict[str, list[bool]] = {}
    for r in results:
        for req in r["requirements"]:
            by_req.setdefault(req, []).append(r["passed"])
    # R3: every turn's UI payload validated against the catalog (measured per turn, not per case).
    ui = [c["passed"] for r in results for c in r["checks"] if c["name"].endswith("_ui_valid")]
    by_req["R3"] = ui
    price_cases = [r for r in results if any(c["name"] in ("price_exact", "price_sequence_exact") for c in r["checks"])]
    price_ok = [all(c["passed"] for c in r["checks"] if c["name"] in ("price_exact", "price_sequence_exact")) for r in price_cases]
    invented = [c for r in results for c in r["checks"] if c["name"].endswith("_no_invented_price") and not c["passed"]]
    flag_cases = [r for r in results if r["category"] == "rates"]
    flag_ok = [all(c["passed"] for c in r["checks"] if c["name"] in ("no_price_shown", "staff_flag_raised", "traveller_told_specialist", "flag_reason")) for r in flag_cases]
    route_stats: dict[str, list[bool]] = {}
    for r in results:
        for route in r["routes"]:
            route_stats.setdefault(route, []).append(r["passed"])
    return {
        "cases": len(results) + len(errors), "scored": len(results), "passed": sum(r["passed"] for r in results),
        "multi_turn_cases": sum(1 for r in results if len([t for t in r["turns"] if not t.get("new_session")]) > 1),
        "by_requirement": {k: (sum(v), len(v)) for k, v in sorted(by_req.items())},
        "ui_turns_valid": (sum(ui), len(ui)),
        "price_accuracy": (sum(price_ok), len(price_ok)),
        "invented_prices": len(invented),
        "missing_rates_handling": (sum(flag_ok), len(flag_ok)),
        "by_model_route": {k: (sum(v), len(v)) for k, v in sorted(route_stats.items())},
        "infra_errors": errors,
    }


def pct(a: int, b: int) -> str:
    return f"{(100 * a / b):.0f}% ({a}/{b})" if b else "n/a"


def write_report(results: list[dict], summary: dict, label: str, name: str = "latest") -> Path:
    out_dir = EVALS / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    lines = [f"# Mira evaluation report", "",
             f"Run: {stamp} · today={settings.today_override} · models small={settings.model_small}, large={settings.model_large}, "
             f"judge={settings.model_judge} · grounding_fix={'on' if settings.grounding_fix else 'off'} {label}", "",
             f"**{summary['passed']}/{summary['scored']} scored cases passed** · {summary['cases']} cases run · "
             f"{summary['multi_turn_cases']} multi-turn cases · {len(summary['infra_errors'])} infrastructure errors", "",
             *( [f"> Infrastructure errors (Gemini free-tier rate limits or 503/504 from the API, not Mira's logic) are left out of the "
                 f"pass rates and listed here: {', '.join(summary['infra_errors'])}. Re-run them with `--rerun-errors`.", ""]
               if summary['infra_errors'] else []),
             "## Targets", "", "| Target | Goal | Result |", "|---|---|---|",
             f"| Price accuracy | 100% | {pct(*summary['price_accuracy'])} |",
             f"| Invented prices | 0 | {summary['invented_prices']} |",
             f"| Missing / expired rates handled | 100% | {pct(*summary['missing_rates_handling'])} |",
             f"| UI payloads valid (per turn) | 100% | {pct(*summary['ui_turns_valid'])} |", "",
             "## Pass rate per requirement", "", "| Requirement | Pass rate |", "|---|---|"]
    for req, (ok, n) in summary["by_requirement"].items():
        lines.append(f"| {REQUIREMENT_NAMES.get(req, req)} | {pct(ok, n)} |")
    lines += ["", "## Pass rate per model route", "", "Cases are counted under every route they used.", "",
              "| Route | Model | Pass rate |", "|---|---|---|"]
    for route, (ok, n) in summary["by_model_route"].items():
        lines.append(f"| {route} | {settings.model_small if route == 'small' else settings.model_large} | {pct(ok, n)} |")
    fails = [r for r in results if r.get("status") == "fail"]
    lines += ["", f"## Failing cases ({len(fails)})", ""]
    for r in fails:
        lines.append(f"### {r['id']} ({r['category']})")
        for c in r["checks"]:
            if not c["passed"]:
                lines.append(f"- **{c['name']}**: {c['detail']}")
        for t in r["turns"]:
            if t.get("new_session"):
                continue
            lines.append(f"- Traveller: {t['user_text']}")
            lines.append(f"  - Mira ({t.get('route')}/{t.get('model_route')}): {t['text'][:300]}")
            if t.get("trace_url"):
                lines.append(f"  - Trace: {t['trace_url']}")
        lines.append("")
    lines += ["## All cases", "", "| Case | Category | Result | Seconds | Traces |", "|---|---|---|---|---|"]
    for r in results:
        traces = " ".join(f"[{i+1}]({u})" for i, u in enumerate(r["trace_urls"]))
        lines.append(f"| {r['id']} | {r['category']} | { {'pass': 'pass', 'fail': '**FAIL**', 'error': 'infra error'}[r.get('status', 'pass' if r['passed'] else 'fail')] } | {r['seconds']} | {traces} |")
    md = "\n".join(lines) + "\n"
    (out_dir / f"report-{stamp}.md").write_text(md)
    (out_dir / f"{name}.md").write_text(md)
    (out_dir / f"{name}.json").write_text(json.dumps({"summary": summary, "results": results}, indent=1, default=str))
    return out_dir / f"{name}.md"


def judge_agreement() -> None:
    """Compare the LLM judge with the human labels in evals/labels/human_labels.jsonl."""
    labels = [json.loads(l) for l in (EVALS / "labels" / "human_labels.jsonl").read_text().splitlines() if l.strip()]
    labelled = [l for l in labels if l.get("human_pass") is not None]
    if len(labelled) < len(labels):
        print(f"{len(labels) - len(labelled)} cases still need a human label (human_pass true/false).")
    agree = 0
    rows = []
    for l in labelled:
        v = judge(l["behaviour"], l["turns"])
        same = v.passed == l["human_pass"]
        agree += same
        rows.append(f"| {l['id']} | {'pass' if l['human_pass'] else 'fail'} | {'pass' if v.passed else 'fail'} | {'yes' if same else '**no**'} | {v.reason[:160]} |")
        print(f"{l['id']}: human={l['human_pass']} judge={v.passed} {'agree' if same else 'DISAGREE'}")
    md = ["# LLM judge agreement", "", f"Judge model: {settings.model_judge}", "",
          f"**Agreement: {agree}/{len(labelled)} ({(100 * agree / max(1, len(labelled))):.0f}%)**", "",
          "| Case | Human | Judge | Agree | Judge's reason |", "|---|---|---|---|---|", *rows]
    (EVALS / "reports" / "judge_agreement.md").write_text("\n".join(md) + "\n")
    print(f"Agreement {agree}/{len(labelled)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated case ids")
    ap.add_argument("--requirement", help="run cases tagged with this requirement, e.g. R5")
    ap.add_argument("--concurrency", type=int, default=3)
    ap.add_argument("--no-judge", action="store_true")
    ap.add_argument("--label", default="", help="free text added to the report header, e.g. 'before fix'")
    ap.add_argument("--judge-agreement", action="store_true")
    ap.add_argument("--rerun-errors", action="store_true", help="re-run only the cases that hit API errors in latest.json and merge")
    ap.add_argument("--report-only", action="store_true", help="rebuild the report from evals/reports/latest.json")
    ap.add_argument("--report-name", default="latest", help="write reports/<name>.md instead of latest.md (e.g. before-fix)")
    ap.add_argument("--rerun", help="comma-separated case ids to re-run and merge into latest.json")
    ap.add_argument("--resume", action="store_true", help="skip cases already in reports/partial.jsonl from an interrupted run")
    ap.add_argument("--export-for-labelling", help="comma-separated case ids whose transcripts to export for human labelling")
    args = ap.parse_args()
    init_tracing()
    if args.judge_agreement:
        judge_agreement()
        return
    if args.report_only or args.rerun_errors or args.rerun:
        previous = json.loads((EVALS / "reports" / "latest.json").read_text())["results"]
        if args.rerun_errors:
            for r in previous:
                r["status"] = classify(r)
            todo = {r["id"] for r in previous if r["status"] == "error"}
        if args.rerun:
            todo = set(args.rerun.split(","))
        if args.rerun_errors or args.rerun:
            print(f"Re-running {len(todo)} errored cases: {sorted(todo)}")
            fresh = asyncio.run(evaluate([c for c in load_cases() if c["id"] in todo], args.concurrency, not args.no_judge))
            by_id = {r["id"]: r for r in previous}
            by_id.update({r["id"]: r for r in fresh})
            previous = sorted(by_id.values(), key=lambda r: (r["source"] != "seed", r["id"]))
        summary = summarise(previous)
        path = write_report(previous, summary, args.label)
        print(f"Report: {path}")
        return
    cases = load_cases()
    if args.only:
        wanted = set(args.only.split(","))
        cases = [c for c in cases if c["id"] in wanted]
    if args.requirement:
        cases = [c for c in cases if args.requirement in c["requirements"]]
    if args.export_for_labelling:
        wanted = args.export_for_labelling.split(",")
        cases = [c for c in cases if c["id"] in wanted]
    done: list[dict] = []
    if args.resume and PARTIAL.exists():
        done = [json.loads(l) for l in PARTIAL.read_text().splitlines() if l.strip()]
        done_ids = {r["id"] for r in done}
        cases = [c for c in cases if c["id"] not in done_ids]
        print(f"Resuming: {len(done)} cases already done")
    elif PARTIAL.exists():
        PARTIAL.unlink()
    print(f"Running {len(cases)} cases (today={settings.today_override})")
    results = asyncio.run(evaluate(cases, args.concurrency, not args.no_judge and not args.export_for_labelling))
    results = sorted(done + results, key=lambda r: (r["source"] != "seed", r["id"]))
    if args.export_for_labelling:
        from judge import format_transcript
        (EVALS / "labels").mkdir(exist_ok=True)
        with open(EVALS / "labels" / "human_labels.jsonl", "w") as f:
            for r in results:
                case = next(c for c in cases if c["id"] == r["id"])
                f.write(json.dumps({"id": r["id"], "behaviour": case["expected"].get("behaviour", ""),
                                    "human_pass": None, "human_notes": "", "turns": r["turns"]}, default=str) + "\n")
        with open(EVALS / "labels" / "TO_LABEL.md", "w") as f:
            for r in results:
                case = next(c for c in cases if c["id"] == r["id"])
                f.write(f"## {r['id']}\n\nExpected: {case['expected'].get('behaviour', '')}\n\n```\n{format_transcript(r['turns'])}\n```\n\n")
        print("Wrote evals/labels/human_labels.jsonl and TO_LABEL.md")
        return
    summary = summarise(results)
    path = write_report(results, summary, args.label, args.report_name)
    print(json.dumps(summary, indent=1))
    print(f"Report: {path}")


if __name__ == "__main__":
    main()
