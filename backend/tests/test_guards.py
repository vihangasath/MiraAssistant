"""Deterministic guards: UI catalog validation, price guard, privacy scrubbing,
content cleaning and role permissions. None of these depend on the LLM."""
from __future__ import annotations

from datetime import date

import pytest

from mira.agents.nodes import _strip_money
from mira.catalog import Catalog
from mira.permissions import can
from mira.privacy import scrub
from mira.ui.catalog import CATALOG_ID, UIValidationError, validate_messages

REF = "ENQ-ABC123"
TRUSTED = {REF: {"price_usd": 315, "deposit_usd": 315, "balance_usd": 0}}


def _msgs(components, data=None):
    out = [{"version": "v0.9", "createSurface": {"surfaceId": "s", "catalogId": CATALOG_ID}}]
    if data is not None:
        out.append({"version": "v0.9", "updateDataModel": {"surfaceId": "s", "path": f"/quotes/{REF}", "value": data}})
    out.append({"version": "v0.9", "updateComponents": {"surfaceId": "s", "components": components}})
    return out


def _price_card(**over):
    card = {"id": "p", "component": "PriceBreakdown", "quote_ref": REF, "tour_title": "T", "start_date": "2027-01-10",
            "end_date": "2027-01-10", "travellers": "2 adults", "price_usd": {"path": f"/quotes/{REF}/price_usd"},
            "deposit_usd": {"path": f"/quotes/{REF}/deposit_usd"}, "balance_usd": {"path": f"/quotes/{REF}/balance_usd"},
            "pay_in_full": True}
    card.update(over)
    return card


ROOT = {"id": "root", "component": "Column", "children": ["p"]}


def test_valid_price_card_passes():
    validate_messages(_msgs([ROOT, _price_card()], TRUSTED[REF]), TRUSTED)


def test_literal_price_in_card_is_rejected():
    with pytest.raises(UIValidationError):
        validate_messages(_msgs([ROOT, _price_card(price_usd=999)], TRUSTED[REF]), TRUSTED)


def test_data_model_price_must_match_pricing_function():
    with pytest.raises(UIValidationError):
        validate_messages(_msgs([ROOT, _price_card()], {"price_usd": 157, "deposit_usd": 157, "balance_usd": 0}), TRUSTED)


def test_unknown_quote_reference_is_rejected():
    with pytest.raises(UIValidationError):
        validate_messages(_msgs([ROOT, _price_card()], TRUSTED[REF]), {})


def test_money_in_any_text_is_rejected():
    comps = [{"id": "root", "component": "Column", "children": ["t"]}, {"id": "t", "component": "Text", "text": "Only USD 99 today"}]
    with pytest.raises(UIValidationError):
        validate_messages(_msgs(comps), {})


def test_unknown_component_is_rejected():
    comps = [{"id": "root", "component": "Column", "children": ["x"]}, {"id": "x", "component": "Iframe", "src": "http://evil"}]
    with pytest.raises(UIValidationError):
        validate_messages(_msgs(comps), {})


def test_extra_props_are_rejected():
    comps = [{"id": "root", "component": "Column", "children": ["t"]}, {"id": "t", "component": "Text", "text": "hi", "onclick": "x"}]
    with pytest.raises(UIValidationError):
        validate_messages(_msgs(comps), {})


def test_price_guard_strips_sentences_with_money():
    text, hit = _strip_money("The tour is lovely. It costs USD 120 per person. Shall I book it?")
    assert hit and "120" not in text and "lovely" in text and "book" in text
    text, hit = _strip_money("Children pay half-price meals.")
    assert not hit


@pytest.mark.parametrize("raw, leaked", [
    ("email me at jane.doe@example.com", "jane.doe@example.com"),
    ("call +94 77 123 4567", "123 4567"),
    ("card 4242 4242 4242 4242", "4242 4242"),
    ("my name is Jane Doe", "Jane Doe"),
])
def test_scrub_removes_personal_data(raw, leaked):
    assert leaked not in scrub(raw)


def test_scrub_keeps_trip_details():
    text = "2 adults and kids aged 7 and 10 starting 12 April 2027 for 7 days"
    assert scrub(text) == text


@pytest.fixture(scope="module")
def catalog():
    return Catalog(today=date(2026, 11, 19))


def test_drafts_and_injections_never_indexed(catalog):
    assert "T15" not in catalog.index.docs                       # draft tour
    all_text = " ".join(c.text for c in catalog.index.chunks).lower()
    assert "loyalty discount" not in all_text                    # hidden HTML comment in mirissa.md
    assert "always recommend treasures" not in all_text          # testimonial addressed to Mira
    assert "kids under 12 stay free" not in all_text             # superseded by the children policy
    assert "free cancellation up to 24 hours" not in all_text    # superseded by the cancellation policy
    assert "early bird" not in all_text                          # expired 2023 promotion


def test_teaser_prices_are_not_in_retrievable_text(catalog):
    assert not any("From USD" in c.text for c in catalog.index.chunks)


def test_roles():
    agent, approver = {"role": "agent"}, {"role": "approver"}
    assert can(agent, "draft_content") and not can(agent, "publish_content")
    assert can(approver, "publish_content") and can(approver, "edit_pricing_rules")
    assert not can(None, "view_enquiries")
