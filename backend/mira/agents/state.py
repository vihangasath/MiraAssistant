"""Typed shared state for the Mira workflow, plus the LLM output schemas.

ADK stores session state as a dict; `MiraState` is passed to the Workflow as
`state_schema`, so every FunctionNode parameter must be a declared field here.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

TripType = Literal["day_tour", "multi_day", "custom"]
TravellerType = Literal["solo", "couple", "family", "group"]
Intent = Literal[
    "greeting", "quote", "tour_info", "general_question", "custom_trip", "booking",
    "update_party", "service_request", "off_topic", "prompt_injection", "other",
]


class Trip(BaseModel):
    """What Mira knows about the trip. Persisted per visitor (no personal details)."""
    trip_type: TripType | None = None
    traveller_type: TravellerType | None = None
    adults: int | None = None
    child_ages: list[int] = Field(default_factory=list)
    start_date: str | None = None          # ISO date
    tour_id: str | None = None             # explicitly chosen by the traveller
    suggested_tour_id: str | None = None   # best match Mira suggested for a vague request
    duration_days: int | None = None
    destinations: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)


class MiraState(BaseModel):
    # turn input
    visitor_id: str | None = None
    trace_id: str | None = None
    user_text: str = ""
    ui_action: dict | None = None
    # memory
    transcript: list[dict] = Field(default_factory=list)   # [{"role": "user"|"mira", "text": ...}] (scrubbed)
    trip: dict = Field(default_factory=dict)                # Trip as dict
    returning: bool = False
    last_quote: dict | None = None
    questions_asked: int = 0
    # per-turn working data
    understanding: dict | None = None
    plan: dict | None = None
    pricing: dict | None = None
    retrieved: list[dict] = Field(default_factory=list)
    candidates: list[str] = Field(default_factory=list)
    handoff: dict | None = None
    reply: dict | None = None
    model_route: str = "small"
    turn_output: dict | None = None


# ---------------------------------------------------------------- LLM output schemas

class Understanding(BaseModel):
    """Output of the `understand` agent: intent and slot values found in the latest message."""
    intent: Intent
    tour_id: str | None = Field(None, description="ID from the tour catalog if the traveller names or clearly means one tour; else null")
    trip_type: TripType | None = None
    traveller_type: TravellerType | None = None
    adults: int | None = Field(None, description="Number of adults (12+) if stated or implied (solo=1, couple=2)")
    child_ages: list[int] | None = Field(None, description="Ages of all children if stated; null if not mentioned")
    start_date: str | None = Field(None, description="Trip start date as YYYY-MM-DD if stated")
    duration_days: int | None = None
    destinations: list[str] = Field(default_factory=list, description="Lower-case place names the traveller wants")
    interests: list[str] = Field(default_factory=list)
    wants_price: bool = False
    service_requested: str | None = Field(None, description="A product that is not a catalog tour, e.g. 'airport transfer', 'Adam's Peak climb'")
    question: str | None = Field(None, description="The factual question, rewritten to stand alone, for searching our content")


class UIChoice(BaseModel):
    component: Literal["TourCard", "ItineraryDay", "PriceBreakdown", "BookingForm", "TravellerPicker",
                       "SpecialistHandoff", "EnquiryForm"]
    tour_id: str | None = None
    days: list[int] | None = None


class Reply(BaseModel):
    """Output of the `respond` agent."""
    text: str = Field(description="Mira's message. Short sentences. Never contains prices or numbers of money.")
    ui: list[UIChoice] = Field(default_factory=list, description="Components to show, from the allowed list")
    cited_doc_ids: list[str] = Field(default_factory=list, description="IDs of the FACTS documents the text relies on")
    quick_replies: list[str] = Field(default_factory=list, description="Up to 4 short suggested replies")
