"""Content drafting agent (requirement 8).

A staff member types a command ("Add a 5-day Hill Country tour using the Ella photos").
This agent drafts a tour page grounded in our existing published content. The draft is
saved with status `draft`; only code paths guarded by the `publish_content` permission
(Approver role) can publish it. Drafts are never indexed, so Mira cannot use them.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import date

from google.adk import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from opentelemetry import trace
from pydantic import BaseModel, Field

from mira.catalog import get_catalog
from mira.config import settings
from mira.agents.workflow import fallback_on_model_error, rate_limit_before_model
from mira.tracing import current_trace_id

tracer = trace.get_tracer("mira")

# The dataset ships no images. A real media library would list rights-cleared photos here.
MEDIA_LIBRARY: dict[str, list[str]] = {}


class DraftDay(BaseModel):
    day: int
    title: str
    description: str
    meals: str
    accommodation: str


class TourDraft(BaseModel):
    title: str
    category: str = Field(description="One of: Day tour, City tour, Round trip, Short stay, Beach stay, Special interest")
    duration: str = Field(description="e.g. '4 nights / 5 days'")
    start: str
    destinations: list[str]
    summary: str
    days: list[DraftDay]
    inclusions: list[str]
    open_questions: list[str] = Field(default_factory=list, description="Things staff must check before publishing")


def _instruction(ctx) -> str:
    return f"""You draft new tour pages for Ceylon Compass Holidays (Sri Lanka). A human approver reviews everything before it goes live.
Use ONLY facts found in the REFERENCE CONTENT below (places, hotels, activities). Do not invent hotels, prices, opening times or claims.
Never include prices or discounts. If the command asks for something the reference content cannot support, add it to open_questions.
Write in the brand voice: short sentences, plain English, warm but not gushing, "we" for the company.
Media library: {json.dumps(MEDIA_LIBRARY) if MEDIA_LIBRARY else "EMPTY – no photos are available. If the command mentions photos, add an open question asking staff to upload rights-cleared images."}

STAFF COMMAND: {ctx.state.get("command", "")}

REFERENCE CONTENT:
{ctx.state.get("reference", "")}"""


_agent = Agent(
    name="content_drafter",
    model=settings.model_large,
    instruction=_instruction,
    include_contents="none",
    output_schema=TourDraft,
    output_key="draft",
    generate_content_config=types.GenerateContentConfig(temperature=0.4),
    before_model_callback=rate_limit_before_model,
    on_model_error_callback=fallback_on_model_error,
)
_sessions = InMemorySessionService()
_runner = Runner(app_name="mira-content", agent=_agent, session_service=_sessions, auto_create_session=True)


def _reference_for(command: str) -> str:
    catalog = get_catalog()
    hits = catalog.index.search(command, k=10)
    blocks = [f"[{h.chunk.doc_id}] {h.chunk.doc_title} › {h.chunk.heading}\n{h.chunk.text}" for h in hits if h.chunk.doc_id != "P06"]
    return "\n\n".join(blocks)[:12000]


def render_markdown(doc_id: str, draft: TourDraft) -> str:
    front = {
        "id": doc_id, "type": "tour", "title": draft.title, "status": "draft",
        "last_updated": date.today().isoformat(), "category": draft.category, "duration": draft.duration,
        "start": draft.start, "destinations": [d.lower().replace(" ", "-") for d in draft.destinations],
        "origin": "ai-draft",
    }
    lines = ["---", *[f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in front.items()], "---", "",
             f"# {draft.title}", "", draft.summary, ""]
    for d in draft.days:
        lines += [f"### Day {d.day}: {d.title}", "", d.description, "",
                  f"- **Meals:** {d.meals}", f"- **Accommodation:** {d.accommodation}", ""]
    lines += ["## Inclusions", *[f"- {i}" for i in draft.inclusions], ""]
    if draft.open_questions:
        lines += ["<!-- STAFF CHECKLIST (removed on publish):", *[f"- {q}" for q in draft.open_questions], "-->", ""]
    return "\n".join(lines)


async def draft_tour(command: str, staff_name: str) -> dict:
    with tracer.start_as_current_span("content.draft_tour") as span:
        trace_id = current_trace_id()
        span.set_attribute("openinference.span.kind", "CHAIN")
        span.set_attribute("input.value", command)
        reference = _reference_for(command)
        span.set_attribute("retrieval.documents", reference[:4000])
        session_id = f"draft-{uuid.uuid4().hex[:8]}"
        async for _ in _runner.run_async(user_id="staff", session_id=session_id,
                                         new_message=types.Content(role="user", parts=[types.Part(text=command)]),
                                         state_delta={"command": command, "reference": reference}):
            pass
        session = await _sessions.get_session(app_name="mira-content", user_id="staff", session_id=session_id)
        draft = TourDraft.model_validate(session.state["draft"])
        # Code-side guard: drafts may never carry prices.
        text_blob = json.dumps(draft.model_dump())
        if re.search(r"(\$\s?\d|USD\s?\d|LKR\s?\d|\d\s?(USD|LKR))", text_blob):
            draft.open_questions.append("The draft mentioned a price; prices were removed. Prices come only from the rate workbook.")
        doc_id = f"AI{uuid.uuid4().hex[:4].upper()}"
        markdown = render_markdown(doc_id, draft)
        span.set_attribute("output.value", markdown[:4000])
    return {"doc_id": doc_id, "title": draft.title, "markdown": markdown, "trace_id": trace_id,
            "open_questions": draft.open_questions}


def publishable_markdown(markdown: str) -> str:
    """On publish: flip status to published and strip the staff checklist comment."""
    md = re.sub(r"^status:\s*\"?draft\"?\s*$", 'status: "published"', markdown, count=1, flags=re.M)
    return re.sub(r"<!-- STAFF CHECKLIST.*?-->\n?", "", md, flags=re.S)
