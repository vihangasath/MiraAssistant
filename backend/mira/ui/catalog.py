"""Mira's A2UI component catalog (A2UI protocol v0.9 message shapes).

The LLM chooses *which* components to show (a UI plan); code builds the actual
A2UI messages from deterministic data, and `validate_messages` checks every
payload against this catalog before it is sent to the browser.

Price integrity rules enforced here, on top of the schemas:
  * PriceBreakdown is the only component that may display money, and its money
    fields must be data-model bindings ({"path": "/quotes/<ref>/..."}), never literals.
  * The data model values under /quotes/<ref> must equal the stored quote for that
    enquiry reference (checked by the caller passing `trusted_quotes`).
  * No literal string anywhere in a payload may contain a currency amount.
"""
from __future__ import annotations

import re
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

CATALOG_ID = "https://ceyloncompass.example/a2ui/catalogs/mira/v1.json"
PROTOCOL_VERSION = "v0.9"

ACCENTS = Literal["orange", "teal", "leaf", "sun", "sky", "coral"]


class Binding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(pattern=r"^/[A-Za-z0-9_/\-]+$")


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid")
    doc_id: str
    title: str
    section: str | None = None
    source: str


class Action(BaseModel):
    """A user action sent back to the agent as an A2UI client event."""
    model_config = ConfigDict(extra="forbid")
    name: Literal["send_text", "get_quote", "show_itinerary", "set_travellers", "start_booking",
                  "send_enquiry", "choose_trip_type"]
    context: dict[str, Any] = Field(default_factory=dict)


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-z0-9_\-]{1,64}$")


class Column(_Base):
    component: Literal["Column"]
    children: list[str]


class Text(_Base):
    component: Literal["Text"]
    text: str = Field(max_length=2000)
    variant: Literal["body", "caption", "heading"] = "body"


class QuickReplies(_Base):
    component: Literal["QuickReplies"]
    options: list[Annotated[str, Field(max_length=60)]] = Field(min_length=1, max_length=5)


class TravellerPicker(_Base):
    component: Literal["TravellerPicker"]
    adults: int = Field(ge=0, le=20)
    child_ages: list[Annotated[int, Field(ge=0, le=17)]] = Field(default_factory=list, max_length=19)
    trip_type: Literal["day_tour", "multi_day", "custom"] | None = None
    start_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    action: Action


class TourCard(_Base):
    component: Literal["TourCard"]
    tour_id: str
    title: str
    category: str | None = None
    duration: str | None = None
    destinations: list[str] = Field(default_factory=list)
    summary: str = Field(max_length=400)
    accent: ACCENTS
    bookable_online: bool        # False -> "a specialist will price this"
    source: Source
    actions: list[Action] = Field(default_factory=list, max_length=3)


class ItineraryDay(_Base):
    component: Literal["ItineraryDay"]
    tour_id: str
    day: int = Field(ge=1, le=30)
    title: str
    description: str = Field(max_length=600)
    meals: str | None = None
    accommodation: str | None = None
    source: Source


class PriceBreakdown(_Base):
    component: Literal["PriceBreakdown"]
    quote_ref: str = Field(pattern=r"^ENQ-[A-F0-9]{6}$")
    tour_title: str
    start_date: str
    end_date: str
    travellers: str
    price_usd: Binding
    deposit_usd: Binding
    balance_usd: Binding
    pay_in_full: bool
    balance_due: str | None = None
    actions: list[Action] = Field(default_factory=list, max_length=2)


class SpecialistHandoff(_Base):
    component: Literal["SpecialistHandoff"]
    reference: str = Field(pattern=r"^ENQ-[A-F0-9]{6}$")
    title: str
    message: str = Field(max_length=500)


class BookingForm(_Base):
    component: Literal["BookingForm"]
    quote_ref: str = Field(pattern=r"^ENQ-[A-F0-9]{6}$")
    tour_title: str
    deposit_usd: Binding
    pay_in_full: bool


class EnquiryForm(_Base):
    component: Literal["EnquiryForm"]
    reference: str = Field(pattern=r"^ENQ-[A-F0-9]{6}$")
    summary: str = Field(max_length=600)


class SourceList(_Base):
    component: Literal["SourceList"]
    sources: list[Source] = Field(min_length=1, max_length=8)


class Notice(_Base):
    component: Literal["Notice"]
    tone: Literal["info", "warning", "error"]
    title: str
    message: str = Field(max_length=400)
    actions: list[Action] = Field(default_factory=list, max_length=2)


Component = Annotated[
    Union[Column, Text, QuickReplies, TravellerPicker, TourCard, ItineraryDay, PriceBreakdown,
          SpecialistHandoff, BookingForm, EnquiryForm, SourceList, Notice],
    Field(discriminator="component"),
]
COMPONENT_NAMES = ["Column", "Text", "QuickReplies", "TravellerPicker", "TourCard", "ItineraryDay",
                   "PriceBreakdown", "SpecialistHandoff", "BookingForm", "EnquiryForm", "SourceList", "Notice"]
_component_adapter = TypeAdapter(Component)


class CreateSurface(BaseModel):
    model_config = ConfigDict(extra="forbid")
    surfaceId: str
    catalogId: Literal["https://ceyloncompass.example/a2ui/catalogs/mira/v1.json"]


class UpdateComponents(BaseModel):
    model_config = ConfigDict(extra="forbid")
    surfaceId: str
    components: list[dict]


class UpdateDataModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    surfaceId: str
    path: str
    value: Any


class UIValidationError(ValueError):
    pass


_MONEY_RE = re.compile(r"(\$\s?\d|\bUSD\s?\d|\d[\d,.]*\s?(USD|LKR|dollars?)\b|\bLKR\s?\d|\brs\.?\s?\d)", re.I)


def _literal_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for k, v in value.items():
            if k == "path":
                continue
            yield from _literal_strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _literal_strings(v)


def validate_messages(messages: list[dict], trusted_quotes: dict[str, dict] | None = None) -> None:
    """Raise UIValidationError unless every message conforms to the catalog and price rules."""
    trusted_quotes = trusted_quotes or {}
    surfaces: set[str] = set()
    for msg in messages:
        if msg.get("version") != PROTOCOL_VERSION:
            raise UIValidationError(f"Unsupported A2UI version {msg.get('version')!r}")
        kinds = [k for k in ("createSurface", "updateComponents", "updateDataModel", "deleteSurface") if k in msg]
        if len(kinds) != 1:
            raise UIValidationError(f"Message must have exactly one A2UI operation, got {kinds}")
        kind = kinds[0]
        try:
            if kind == "createSurface":
                surfaces.add(CreateSurface.model_validate(msg[kind]).surfaceId)
            elif kind == "updateComponents":
                upd = UpdateComponents.model_validate(msg[kind])
                ids = set()
                parsed = []
                for raw in upd.components:
                    comp = _component_adapter.validate_python(raw)
                    if comp.id in ids:
                        raise UIValidationError(f"Duplicate component id {comp.id}")
                    ids.add(comp.id)
                    parsed.append(comp)
                    for s in _literal_strings(raw):
                        if _MONEY_RE.search(s):
                            raise UIValidationError(f"Literal money text in {comp.component} {comp.id!r}: {s[:60]!r}")
                if "root" not in ids:
                    raise UIValidationError("updateComponents must include a 'root' component")
                for comp in parsed:
                    if isinstance(comp, Column):
                        missing = [c for c in comp.children if c not in ids]
                        if missing:
                            raise UIValidationError(f"Column {comp.id} references unknown children {missing}")
                    if isinstance(comp, (PriceBreakdown, BookingForm)):
                        prefix = f"/quotes/{comp.quote_ref}/"
                        for b in [getattr(comp, f) for f in ("price_usd", "deposit_usd", "balance_usd") if hasattr(comp, f)]:
                            if not b.path.startswith(prefix):
                                raise UIValidationError(f"{comp.component} binds {b.path} outside {prefix}")
                        if comp.quote_ref not in trusted_quotes:
                            raise UIValidationError(f"{comp.component} references unknown quote {comp.quote_ref}")
            elif kind == "updateDataModel":
                upd = UpdateDataModel.model_validate(msg[kind])
                m = re.match(r"^/quotes/(ENQ-[A-F0-9]{6})$", upd.path)
                if upd.path.startswith("/quotes"):
                    if not m or m.group(1) not in trusted_quotes:
                        raise UIValidationError(f"Data model write to {upd.path} is not a trusted quote")
                    trusted = trusted_quotes[m.group(1)]
                    for key in ("price_usd", "deposit_usd", "balance_usd"):
                        if upd.value.get(key) != trusted.get(key):
                            raise UIValidationError(f"{key} for {m.group(1)} does not match the pricing function")
        except ValidationError as exc:
            raise UIValidationError(f"{kind} failed catalog validation: {exc.errors()[0]}") from exc


def catalog_json_schema() -> dict:
    """The catalog as JSON Schema, published at /api/a2ui/catalog for documentation and tests."""
    return {
        "$id": CATALOG_ID,
        "title": "Ceylon Compass Mira catalog",
        "protocolVersion": PROTOCOL_VERSION,
        "components": _component_adapter.json_schema(),
    }
