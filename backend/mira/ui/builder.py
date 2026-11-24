"""Turns the responder's UI plan into A2UI v0.9 messages.

The LLM only says *which* components to show and for which tour/day. All facts
(titles, itinerary text, sources) come from published content, and all money
comes from the stored quote. The result is validated before it leaves the server.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from mira.catalog import Catalog
from mira.data.content_loader import Doc
from mira.ui.catalog import CATALOG_ID, PROTOCOL_VERSION, validate_messages

CATEGORY_ACCENT = {
    "day tour": "orange", "city tour": "sky", "round trip": "teal", "beach stay": "leaf",
    "short stay": "sun", "special interest": "coral",
}


@dataclass
class ItineraryDayData:
    day: int
    title: str
    description: str
    meals: str | None
    accommodation: str | None


def parse_itinerary(doc: Doc) -> list[ItineraryDayData]:
    """Parse '### Day N: Title' sections with '**Meals:**' / '**Accommodation:**' bullets."""
    days = []
    for m in re.finditer(r"^###\s*Day\s+(\d+)\s*:\s*(.+?)\n(.*?)(?=^###\s*Day|\n##\s|\Z)", doc.body, re.M | re.S):
        body = m.group(3)
        desc_lines = [line.strip() for line in body.splitlines() if line.strip() and not line.strip().startswith("-")]
        meals = re.search(r"\*\*Meals:\*\*\s*(.+)", body)
        acc = re.search(r"\*\*Accommodation:\*\*\s*(.+)", body)
        days.append(ItineraryDayData(int(m.group(1)), m.group(2).strip(), " ".join(desc_lines),
                                     meals.group(1).strip() if meals else None, acc.group(1).strip() if acc else None))
    return days


def tour_summary(doc: Doc) -> str:
    for para in re.split(r"\n\s*\n", doc.body):
        p = para.strip()
        if p and not p.startswith("#") and not p.startswith("-") and not p.startswith("**"):
            return p[:390]
    return doc.title


def _source(doc: Doc, section: str | None = None) -> dict:
    return {"doc_id": doc.id, "title": doc.title, "section": section, "source": doc.path}


@dataclass
class TurnUIData:
    """Everything deterministic the builder may draw on for this turn."""
    surface_id: str
    quote: dict | None = None            # traveller view + quote_ref (priced)
    handoff: dict | None = None          # {"reference", "title", "message"} for needs_specialist / custom
    party: dict | None = None            # {"adults", "child_ages", "trip_type", "start_date"}
    sources: list[dict] = field(default_factory=list)
    notice: dict | None = None


def _travellers_text(q: dict) -> str:
    parts = [f"{q['adults']} adult{'s' if q['adults'] != 1 else ''}"]
    if q.get("children"):
        parts.append(f"{q['children']} child{'ren' if q['children'] != 1 else ''}")
    if q.get("infants"):
        parts.append(f"{q['infants']} infant{'s' if q['infants'] != 1 else ''}")
    return ", ".join(parts)


def build_messages(catalog: Catalog, plan: list[dict], data: TurnUIData, reply_text: str,
                   quick_replies: list[str] | None = None) -> list[dict]:
    """Build and validate A2UI messages for one assistant turn.

    `plan` items look like {"component": "TourCard", "tour_id": "T09"} – chosen by the LLM.
    Items that cannot be backed by real data are dropped (and the drop is visible in the trace).
    """
    components: list[dict] = []
    data_updates: list[dict] = []
    trusted: dict[str, dict] = {}
    children: list[str] = []
    seen: set[tuple] = set()

    def add(comp: dict):
        components.append(comp)
        children.append(comp["id"])

    add({"id": "reply", "component": "Text", "text": reply_text or " ", "variant": "body"})

    for n, item in enumerate(plan or []):
        kind = item.get("component")
        key = (kind, item.get("tour_id"), item.get("day"))
        if key in seen:
            continue
        seen.add(key)
        cid = f"c{n}"

        if kind == "TourCard":
            doc = catalog.tour_doc(item.get("tour_id", ""))
            if not doc or not doc.is_published:
                continue
            has_rates = doc.id in catalog.rates.tours
            actions = [{"name": "get_quote", "context": {"tour_id": doc.id}}] if has_rates else \
                      [{"name": "send_enquiry", "context": {"tour_id": doc.id}}]
            if parse_itinerary(doc):
                actions.append({"name": "show_itinerary", "context": {"tour_id": doc.id}})
            add({"id": cid, "component": "TourCard", "tour_id": doc.id, "title": doc.title,
                 "category": doc.category, "duration": doc.duration, "destinations": doc.destinations,
                 "summary": tour_summary(doc), "accent": CATEGORY_ACCENT.get((doc.category or "").lower(), "teal"),
                 "bookable_online": has_rates, "source": _source(doc), "actions": actions})

        elif kind == "ItineraryDay":
            doc = catalog.tour_doc(item.get("tour_id", ""))
            if not doc or not doc.is_published:
                continue
            days = parse_itinerary(doc)
            wanted = item.get("days") or ([item["day"]] if item.get("day") else [d.day for d in days])
            for d in days:
                if d.day in wanted:
                    add({"id": f"{cid}_d{d.day}", "component": "ItineraryDay", "tour_id": doc.id, "day": d.day,
                         "title": d.title, "description": d.description[:590], "meals": d.meals,
                         "accommodation": d.accommodation, "source": _source(doc, f"Day {d.day}")})

        elif kind == "PriceBreakdown" and data.quote:
            q = data.quote
            ref = q["quote_ref"]
            trusted[ref] = q
            data_updates.append({"version": PROTOCOL_VERSION, "updateDataModel": {
                "surfaceId": data.surface_id, "path": f"/quotes/{ref}",
                "value": {"price_usd": q["price_usd"], "deposit_usd": q["deposit_usd"], "balance_usd": q["balance_usd"]}}})
            add({"id": cid, "component": "PriceBreakdown", "quote_ref": ref, "tour_title": q["tour_name"],
                 "start_date": q["start_date"], "end_date": q["end_date"], "travellers": _travellers_text(q),
                 "price_usd": {"path": f"/quotes/{ref}/price_usd"},
                 "deposit_usd": {"path": f"/quotes/{ref}/deposit_usd"},
                 "balance_usd": {"path": f"/quotes/{ref}/balance_usd"},
                 "pay_in_full": q["pay_in_full"], "balance_due": q.get("balance_due"),
                 "actions": [{"name": "start_booking", "context": {"quote_ref": ref}}]})

        elif kind == "BookingForm" and data.quote:
            q = data.quote
            trusted[q["quote_ref"]] = q
            if not any(u["updateDataModel"]["path"] == f"/quotes/{q['quote_ref']}" for u in data_updates):
                data_updates.append({"version": PROTOCOL_VERSION, "updateDataModel": {
                    "surfaceId": data.surface_id, "path": f"/quotes/{q['quote_ref']}",
                    "value": {"price_usd": q["price_usd"], "deposit_usd": q["deposit_usd"], "balance_usd": q["balance_usd"]}}})
            add({"id": cid, "component": "BookingForm", "quote_ref": q["quote_ref"], "tour_title": q["tour_name"],
                 "deposit_usd": {"path": f"/quotes/{q['quote_ref']}/deposit_usd"}, "pay_in_full": q["pay_in_full"]})

        elif kind == "TravellerPicker":
            p = data.party or {}
            add({"id": cid, "component": "TravellerPicker", "adults": p.get("adults") or 2,
                 "child_ages": p.get("child_ages") or [], "trip_type": p.get("trip_type"),
                 "start_date": p.get("start_date"), "action": {"name": "set_travellers"}})

        elif kind == "SpecialistHandoff" and data.handoff:
            add({"id": cid, "component": "SpecialistHandoff", **data.handoff})

        elif kind == "EnquiryForm" and data.handoff:
            add({"id": cid, "component": "EnquiryForm", "reference": data.handoff["reference"],
                 "summary": data.handoff.get("summary") or data.handoff["message"]})

    # Deterministic guarantees that do not depend on the LLM's plan:
    if data.handoff and not any(c["component"] in ("SpecialistHandoff", "EnquiryForm") for c in components):
        add({"id": "handoff", "component": "SpecialistHandoff", **{k: data.handoff[k] for k in ("reference", "title", "message")}})
    if data.quote and not any(c["component"] == "PriceBreakdown" for c in components):
        return build_messages(catalog, [*(plan or []), {"component": "PriceBreakdown"}], data, reply_text, quick_replies)
    if data.notice:
        add({"id": "notice", "component": "Notice", **data.notice})
    if data.sources:
        add({"id": "sources", "component": "SourceList", "sources": data.sources[:8]})
    if quick_replies:
        add({"id": "quick", "component": "QuickReplies", "options": [q[:60] for q in quick_replies[:5]]})

    components.insert(0, {"id": "root", "component": "Column", "children": children})
    messages = [
        {"version": PROTOCOL_VERSION, "createSurface": {"surfaceId": data.surface_id, "catalogId": CATALOG_ID}},
        *data_updates,
        {"version": PROTOCOL_VERSION, "updateComponents": {"surfaceId": data.surface_id, "components": components}},
    ]
    validate_messages(messages, trusted_quotes=trusted)
    return messages
