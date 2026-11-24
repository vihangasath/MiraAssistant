"""Runs one traveller turn through the workflow. One turn = one trace."""
from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from opentelemetry import trace

from mira.agents.workflow import build_workflow
from mira.privacy import scrub
from mira.tracing import current_trace_id, trace_url

log = logging.getLogger(__name__)
tracer = trace.get_tracer("mira")
APP_NAME = "mira"

ACTION_TEXT = {
    "get_quote": "Please price {title}.",
    "show_itinerary": "Show me the day-by-day itinerary for {title}.",
    "set_travellers": "{party}",
    "start_booking": "I'd like to book this.",
    "send_enquiry": "Please pass my request to your team.",
    "choose_trip_type": "I'm looking for a {trip_type_label}.",
    "send_text": "{text}",
}
TRIP_TYPE_LABEL = {"day_tour": "day tour", "multi_day": "multi-day tour", "custom": "custom trip"}


def action_to_text(action: dict) -> str:
    """Turn a UI click into the words a traveller would have typed (shown in the transcript)."""
    from mira.catalog import get_catalog
    name, c = action.get("name"), action.get("context") or {}
    title = ""
    if c.get("tour_id"):
        doc = get_catalog().tour_doc(c["tour_id"])
        title = doc.title if doc else c["tour_id"]
    party = ""
    if name == "set_travellers":
        bits = [f"We are {c.get('adults', 0)} adult{'s' if c.get('adults') != 1 else ''}"]
        if c.get("child_ages"):
            bits.append(f"with children aged {', '.join(str(a) for a in c['child_ages'])}")
        if c.get("start_date"):
            bits.append(f"starting {c['start_date']}")
        if c.get("trip_type"):
            bits.append(f"looking for a {TRIP_TYPE_LABEL.get(c['trip_type'], c['trip_type'])}")
        party = ", ".join(bits) + "."
    template = ACTION_TEXT.get(name, "{text}")
    return template.format(title=title, party=party, text=c.get("text", ""),
                           trip_type_label=TRIP_TYPE_LABEL.get(c.get("trip_type", ""), "trip"))


@dataclass
class TurnResult:
    output: dict
    trace_id: str | None
    trace_url: str | None
    session_id: str
    user_text: str = ""


class MiraRuntime:
    def __init__(self):
        self.session_service = InMemorySessionService()
        self.runner = Runner(app_name=APP_NAME, node=build_workflow(), session_service=self.session_service,
                             auto_create_session=True)

    async def run_turn_stream(self, *, visitor_id: str, session_id: str | None, text: str | None,
                              action: dict | None = None) -> AsyncIterator[dict]:
        """Yields progress dicts ({"type": "step", ...}) and finally {"type": "result", ...}."""
        session_id = session_id or f"s-{uuid.uuid4().hex[:12]}"
        user_text = scrub(text or "") if text else scrub(action_to_text(action or {}))
        with tracer.start_as_current_span("mira.turn") as span:
            trace_id = current_trace_id()
            span.set_attribute("openinference.span.kind", "CHAIN")
            span.set_attribute("input.value", user_text)
            span.set_attribute("session.id", session_id)
            span.set_attribute("user.id", visitor_id)   # random UUID from the browser, not personal data
            if action:
                span.set_attribute("mira.ui_action", action.get("name", ""))
            state_delta = {"visitor_id": visitor_id, "trace_id": trace_id, "user_text": user_text, "ui_action": action}
            message = types.Content(role="user", parts=[types.Part(text=user_text)])
            seen_nodes: set[str] = set()
            try:
                async for event in self.runner.run_async(user_id=visitor_id, session_id=session_id,
                                                         new_message=message, state_delta=state_delta):
                    author = event.author or ""
                    if author and author not in seen_nodes and author != "user":
                        seen_nodes.add(author)
                        yield {"type": "step", "name": author}
                session = await self.session_service.get_session(app_name=APP_NAME, user_id=visitor_id, session_id=session_id)
                output = (session.state.get("turn_output") if session else None) or {}
            except Exception as exc:
                log.exception("Turn failed")
                span.record_exception(exc)
                span.set_attribute("mira.error", str(exc)[:300])
                output = {"error": True, "text": "Sorry, I hit a problem on my side. Please try again in a moment, "
                                                 "or leave your request and our team will reply.", "a2ui": []}
            span.set_attribute("output.value", output.get("text", ""))
            span.set_attribute("mira.route", str(output.get("route")))
        yield {"type": "result", "output": output, "trace_id": trace_id, "trace_url": trace_url(trace_id),
               "session_id": session_id, "user_text": user_text}

    async def run_turn(self, **kwargs) -> TurnResult:
        result = None
        async for item in self.run_turn_stream(**kwargs):
            if item["type"] == "result":
                result = item
        assert result is not None
        return TurnResult(result["output"], result["trace_id"], result["trace_url"], result["session_id"], result["user_text"])


_runtime: MiraRuntime | None = None


def get_runtime() -> MiraRuntime:
    global _runtime
    if _runtime is None:
        _runtime = MiraRuntime()
    return _runtime
