"""The single source of truth Mira's tools read from: rates + published content.

`Catalog.quote()` wraps the pure pricing engine with checks that need the
content as well (is the tour published, is the offer stale, do the page and
the workbook agree on duration). Every path out of here is either a priced
Quote or a NeedsSpecialist with reasons – never a guess.
"""
from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass
from datetime import date
from fractions import Fraction
from pathlib import Path

from mira.config import REPO_ROOT, settings
from mira.data.content_loader import ContentIssue, Doc, load_content
from mira.data.rates_loader import DataIssue, RateBook, load_ratebook
from mira.pricing.engine import (FlagReason, InvalidRequest, NeedsSpecialist, Party, PriceResult,
                                 PricingOverrides, price_tour)
from mira.retrieval.index import ContentIndex

PRICING_RULES_PATH = REPO_ROOT / "config" / "pricing_rules.json"


def load_overrides(path: Path = PRICING_RULES_PATH) -> PricingOverrides:
    if not path.exists():
        return PricingOverrides()
    raw = json.loads(path.read_text())

    def frac(v):
        return None if v is None else Fraction(str(v))
    return PricingOverrides(
        margin_day=frac(raw.get("margin_day")),
        margin_multi=frac(raw.get("margin_multi")),
        margin_by_tour={k: Fraction(str(v)) for k, v in (raw.get("margin_by_tour") or {}).items()},
    )


def content_days(duration: str | None) -> int | None:
    """'6 nights / 7 days' -> 7, '1 day' -> 1, 'Half day' -> 1."""
    if not duration:
        return None
    m = re.search(r"(\d+)\s*days?", duration, re.I)
    if m:
        return int(m.group(1))
    if re.search(r"half\s*day", duration, re.I):
        return 1
    return None


@dataclass
class TourSummary:
    tour_id: str
    title: str
    category: str | None
    duration: str | None
    destinations: list[str]
    start: str | None
    has_rates: bool
    source: str

    def as_dict(self) -> dict:
        return self.__dict__.copy()


class Catalog:
    def __init__(self, today: date | None = None, extra_docs: list[Doc] | None = None):
        self.today = today or settings.today()
        self.rates: RateBook = load_ratebook(settings.rate_workbook)
        self.overrides = load_overrides()
        docs, issues = load_content(settings.content_dir, self.today)
        for d in extra_docs or []:
            docs[d.id] = d
        self.docs: dict[str, Doc] = docs
        self.content_issues: list[ContentIssue] = issues
        self.index = ContentIndex(docs)

    # ------------------------------------------------------------ tours
    def tour_doc(self, tour_id: str) -> Doc | None:
        doc = self.docs.get(tour_id)
        return doc if doc and doc.type == "tour" else None

    def published_tours(self) -> list[TourSummary]:
        out = []
        for d in self.index.published_tours():
            out.append(TourSummary(d.id, d.title, d.category, d.duration, d.destinations, d.meta.get("start"),
                                   d.id in self.rates.tours, d.path))
        return sorted(out, key=lambda t: t.tour_id)

    # ------------------------------------------------------------ pricing
    def quote(self, tour_id: str, start_date: date, party: Party) -> PriceResult:
        doc = self.docs.get(tour_id)
        tour_rate = self.rates.tours.get(tour_id)
        name = (doc.title if doc else None) or (tour_rate.name if tour_rate else None)

        def flag(code, detail) -> NeedsSpecialist:
            return NeedsSpecialist("needs_specialist", tour_id, name, start_date, party, (FlagReason(code, detail),))

        if doc is None or doc.type != "tour":
            return InvalidRequest("invalid", "UNKNOWN_TOUR", f"{tour_id} is not one of our tours.")
        if not doc.is_published:
            return flag("TOUR_NOT_PUBLISHED", f"{doc.title} is not published.")
        if doc.meta.get("expired_offer") or re.search(r"\b20\d\d/\d\d\b", doc.title) and doc.last_updated and doc.last_updated.year < self.today.year - 1:
            return flag("STALE_OFFER", f"{doc.title} is an old seasonal offer (page last updated {doc.last_updated}).")
        if tour_rate is not None:
            page_days = content_days(doc.duration)
            if page_days is not None and page_days != tour_rate.days:
                return flag("CONTENT_RATE_MISMATCH",
                            f"Tour page says {doc.duration!r} but the workbook prices {tour_rate.days} day(s) / {tour_rate.nights} night(s).")
        return price_tour(self.rates, tour_id, start_date, party, self.today, self.overrides)

    # ------------------------------------------------------------ staff
    def data_issues(self) -> list[dict]:
        rate_issues = [{"source": "rates", "where": f"{i.sheet} {i.cell}", "kind": i.kind, "message": i.message}
                       for i in self.rates.issues]
        content_issues = [{"source": "content", "where": i.doc_id, "kind": i.kind, "message": i.message}
                          for i in self.content_issues]
        return rate_issues + content_issues


_lock = threading.Lock()
_catalog: Catalog | None = None


def get_catalog() -> Catalog:
    global _catalog
    with _lock:
        if _catalog is None:
            from mira.store.db import get_store  # local import avoids a cycle
            _catalog = Catalog(extra_docs=get_store().published_staff_docs())
        return _catalog


def reload_catalog() -> Catalog:
    """Called after a staff publish or a pricing-rule change."""
    global _catalog
    with _lock:
        _catalog = None
    return get_catalog()
