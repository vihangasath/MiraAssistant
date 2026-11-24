"""HTTP API.

* POST /api/agui            – AG-UI run endpoint (SSE). A2UI messages travel in CUSTOM events named "a2ui".
* POST /api/booking         – mocked booking + payment. Contact details go straight to the enquiry row,
                              never to the LLM or a trace.
* /api/staff/...            – staff page (enquiries, data issues, content approvals). Roles enforced in code.
"""
from __future__ import annotations

import json
import logging
import re
import secrets
import uuid
from typing import Any

from ag_ui.core import (CustomEvent, EventType, RunAgentInput, RunErrorEvent, RunFinishedEvent, RunStartedEvent,
                        StepFinishedEvent, StepStartedEvent, TextMessageContentEvent, TextMessageEndEvent,
                        TextMessageStartEvent)
from ag_ui.encoder import EventEncoder
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, EmailStr, Field, field_validator

from mira.catalog import PRICING_RULES_PATH, get_catalog, reload_catalog
from mira.config import settings
from mira.permissions import can, current_staff, require
from mira.store.db import get_store
from mira.tracing import init_tracing, trace_url
from mira.ui.catalog import catalog_json_schema

log = logging.getLogger("mira.api")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Mira – Ceylon Compass Holidays")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
def _startup() -> None:
    init_tracing()
    get_catalog()   # load rates + content once, fail fast if the dataset is unreadable


@app.exception_handler(Exception)
async def _friendly_errors(request: Request, exc: Exception):
    log.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"ok": False, "message": "Something went wrong on our side. Please try again, or leave your request and our team will reply."})


# ---------------------------------------------------------------- public

@app.get("/api/health")
def health() -> dict:
    c = get_catalog()
    return {"ok": True, "today": c.today.isoformat(), "tours": len(c.published_tours()),
            "models": {"small": settings.model_small, "large": settings.model_large}}


@app.get("/api/brand")
def brand() -> dict:
    return json.loads(settings.brand_pack.read_text())


@app.get("/api/a2ui/catalog")
def a2ui_catalog() -> dict:
    return catalog_json_schema()


@app.post("/api/agui")
async def agui_run(body: RunAgentInput):
    """AG-UI endpoint. forwarded_props: {visitor_id, action?}. The latest user message is the turn input."""
    from mira.agents.runtime import get_runtime

    encoder = EventEncoder()
    props: dict[str, Any] = body.forwarded_props or {}
    visitor_id = str(props.get("visitor_id") or f"anon-{uuid.uuid4().hex[:8]}")
    action = props.get("action")
    text = None
    if not action:
        for m in reversed(body.messages or []):
            if getattr(m, "role", None) == "user":
                content = getattr(m, "content", "")
                text = content if isinstance(content, str) else " ".join(getattr(p, "text", "") for p in content or [])
                break
    if not action and not (text or "").strip():
        action = {"name": "send_text", "context": {"text": "Hello"}}

    async def stream():
        yield encoder.encode(RunStartedEvent(type=EventType.RUN_STARTED, thread_id=body.thread_id, run_id=body.run_id))
        result = None
        try:
            async for item in get_runtime().run_turn_stream(visitor_id=visitor_id, session_id=body.thread_id,
                                                             text=text, action=action):
                if item["type"] == "step":
                    yield encoder.encode(StepStartedEvent(type=EventType.STEP_STARTED, step_name=item["name"]))
                    yield encoder.encode(StepFinishedEvent(type=EventType.STEP_FINISHED, step_name=item["name"]))
                else:
                    result = item
            out = result["output"]
            msg_id = f"m-{uuid.uuid4().hex[:10]}"
            yield encoder.encode(CustomEvent(type=EventType.CUSTOM, name="turn_meta", value={
                "user_text": result["user_text"], "trace_id": result["trace_id"], "trace_url": result["trace_url"],
                "route": out.get("route"), "message_id": msg_id}))
            yield encoder.encode(TextMessageStartEvent(type=EventType.TEXT_MESSAGE_START, message_id=msg_id, role="assistant"))
            yield encoder.encode(TextMessageContentEvent(type=EventType.TEXT_MESSAGE_CONTENT, message_id=msg_id,
                                                         delta=out.get("text") or " "))
            yield encoder.encode(TextMessageEndEvent(type=EventType.TEXT_MESSAGE_END, message_id=msg_id))
            if out.get("a2ui"):
                yield encoder.encode(CustomEvent(type=EventType.CUSTOM, name="a2ui",
                                                 value={"message_id": msg_id, "messages": out["a2ui"]}))
            yield encoder.encode(RunFinishedEvent(type=EventType.RUN_FINISHED, thread_id=body.thread_id, run_id=body.run_id))
        except Exception as exc:  # the traveller always gets a friendly message, never a stack trace
            log.exception("AG-UI run failed")
            yield encoder.encode(RunErrorEvent(type=EventType.RUN_ERROR, code="MIRA_UNAVAILABLE",
                                               message="Sorry, I can't answer right now. Please try again in a moment."))

    return StreamingResponse(stream(), media_type=encoder.get_content_type())


@app.get("/api/visitor/{visitor_id}")
def visitor_profile(visitor_id: str) -> dict:
    """What Mira remembers about this browser (no personal details)."""
    return {"visitor_id": visitor_id, "profile": get_store().get_profile(visitor_id)}


@app.delete("/api/visitor/{visitor_id}")
def forget_visitor(visitor_id: str) -> dict:
    get_store().forget_visitor(visitor_id)
    return {"ok": True}


# ---------------------------------------------------------------- mocked booking & payment

class BookingRequest(BaseModel):
    visitor_id: str
    quote_ref: str = Field(pattern=r"^ENQ-[A-F0-9]{6}$")
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=40)
    card_number: str = Field(min_length=12, max_length=23)
    card_expiry: str = Field(pattern=r"^(0[1-9]|1[0-2])/\d{2}$")

    @field_validator("card_number")
    @classmethod
    def digits_only(cls, v: str) -> str:
        digits = re.sub(r"[\s-]", "", v)
        if not digits.isdigit():
            raise ValueError("Card number must be digits.")
        return digits


@app.post("/api/booking")
def create_booking(req: BookingRequest) -> dict:
    """Mock booking. Test cards: ending 0002 = payment declined, ending 0003 = booking system down."""
    store = get_store()
    enquiry = store.get_enquiry(req.quote_ref)
    if not enquiry or enquiry["kind"] != "quote" or enquiry.get("visitor_id") != req.visitor_id:
        return {"ok": False, "kind": "not_found", "title": "I couldn't find that quote",
                "message": "Please ask me for a fresh price and try again.",
                "next_steps": ["Ask Mira for a new quote"]}
    contact = {"full_name": req.full_name, "email": req.email, "phone": req.phone, "card_last4": req.card_number[-4:]}
    store.update_enquiry(req.quote_ref, contact=contact)   # the full card number is never stored
    if req.card_number.endswith(settings.mock_decline_suffix):
        store.update_enquiry(req.quote_ref, status="payment_failed")
        store.audit("traveller", "payment_declined", req.quote_ref)
        return {"ok": False, "kind": "payment_declined", "title": "Your payment didn't go through",
                "message": "Your card was declined, so nothing has been charged. Your quote is saved.",
                "next_steps": ["Try another card", "Ask our team to send a secure payment link"],
                "reference": req.quote_ref}
    if req.card_number.endswith("0003"):
        store.update_enquiry(req.quote_ref, status="needs_follow_up")
        store.audit("traveller", "booking_system_unavailable", req.quote_ref)
        return {"ok": False, "kind": "booking_unavailable", "title": "Our booking system is busy",
                "message": "We couldn't complete the booking just now and nothing has been charged. "
                           "Our team has your details and will confirm by email.",
                "next_steps": ["Wait for our email", "Try again in a few minutes"], "reference": req.quote_ref}
    booking_ref = f"CCH-{secrets.token_hex(3).upper()}"
    store.update_enquiry(req.quote_ref, status="booked", booking_ref=booking_ref)
    store.audit("traveller", "booked", req.quote_ref, booking_ref)
    return {"ok": True, "kind": "booked", "title": "Booking received",
            "message": f"Thank you. Your booking reference is {booking_ref}. We have charged the amount shown in your quote "
                       "and our team will email your confirmation.",
            "booking_ref": booking_ref, "amount_charged_usd": enquiry["deposit_usd"], "reference": req.quote_ref}


class EnquiryContact(BaseModel):
    visitor_id: str
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=40)
    message: str | None = Field(default=None, max_length=1000)


@app.post("/api/enquiry/{reference}/contact")
def enquiry_contact(reference: str, req: EnquiryContact) -> dict:
    store = get_store()
    enquiry = store.get_enquiry(reference)
    if not enquiry or enquiry.get("visitor_id") != req.visitor_id:
        return {"ok": False, "message": "I couldn't find that request. Please start a new one in the chat."}
    store.update_enquiry(reference, contact=req.model_dump(exclude={"visitor_id"}))
    return {"ok": True, "message": f"Thank you. Our team will reply by email about request {reference}."}


# ---------------------------------------------------------------- staff

@app.get("/api/staff/me")
def staff_me(user: dict = Depends(current_staff)) -> dict:
    from mira.permissions import ROLE_PERMISSIONS
    return {**user, "permissions": sorted(ROLE_PERMISSIONS[user["role"]])}


@app.get("/api/staff/enquiries")
def staff_enquiries(user: dict = Depends(current_staff)) -> list[dict]:
    require(user, "view_enquiries")
    rows = get_store().list_enquiries()
    for r in rows:
        r["trace_url"] = trace_url(r.get("trace_id"))
    return rows


class EnquiryUpdate(BaseModel):
    status: str | None = Field(default=None, pattern=r"^(new|needs_specialist|contacted|quoted|booked|payment_failed|needs_follow_up|closed)$")
    notes: str | None = Field(default=None, max_length=4000)


@app.patch("/api/staff/enquiries/{enquiry_id}")
def staff_update_enquiry(enquiry_id: str, body: EnquiryUpdate, user: dict = Depends(current_staff)) -> dict:
    require(user, "edit_enquiries")
    store = get_store()
    if not store.get_enquiry(enquiry_id):
        raise HTTPException(404, "Enquiry not found")
    store.update_enquiry(enquiry_id, **body.model_dump(exclude_none=True))
    store.audit(user["name"], "update_enquiry", enquiry_id, json.dumps(body.model_dump(exclude_none=True)))
    return store.get_enquiry(enquiry_id)


@app.get("/api/staff/issues")
def staff_issues(user: dict = Depends(current_staff)) -> list[dict]:
    require(user, "view_issues")
    return get_catalog().data_issues()


@app.get("/api/staff/pricing-rules")
def get_pricing_rules(user: dict = Depends(current_staff)) -> dict:
    require(user, "view_enquiries")
    c = get_catalog()
    return {"file": json.loads(PRICING_RULES_PATH.read_text()) if PRICING_RULES_PATH.exists() else {},
            "workbook": {"margin_day": float(c.rates.settings.margin_day), "margin_multi": float(c.rates.settings.margin_multi),
                         "fx_lkr_per_usd": float(c.rates.settings.fx_lkr_per_usd)}}


class PricingRules(BaseModel):
    margin_day: float | None = Field(default=None, ge=0, lt=0.9)
    margin_multi: float | None = Field(default=None, ge=0, lt=0.9)
    margin_by_tour: dict[str, float] = Field(default_factory=dict)


@app.put("/api/staff/pricing-rules")
def put_pricing_rules(body: PricingRules, user: dict = Depends(current_staff)) -> dict:
    require(user, "edit_pricing_rules")
    data = {"_comment": "Live business-rule overrides. null = use the Settings tab of the rate workbook.", **body.model_dump()}
    PRICING_RULES_PATH.write_text(json.dumps(data, indent=2) + "\n")
    reload_catalog()
    get_store().audit(user["name"], "edit_pricing_rules", None, json.dumps(body.model_dump()))
    return {"ok": True, **data}


class ContentCommand(BaseModel):
    command: str = Field(min_length=5, max_length=500)


@app.post("/api/staff/content/command")
async def content_command(body: ContentCommand, user: dict = Depends(current_staff)) -> dict:
    require(user, "draft_content")
    from mira.agents.content_agent import draft_tour
    result = await draft_tour(body.command, user["name"])
    store = get_store()
    draft_id = store.create_draft(created_by=user["name"], command=body.command, doc_id=result["doc_id"],
                                  title=result["title"], markdown=result["markdown"], trace_id=result["trace_id"])
    store.audit(user["name"], "draft_content", draft_id, body.command)
    return {**store.get_draft(draft_id), "open_questions": result["open_questions"], "trace_url": trace_url(result["trace_id"])}


@app.get("/api/staff/content")
def list_content(user: dict = Depends(current_staff)) -> list[dict]:
    require(user, "view_content")
    rows = get_store().list_drafts()
    for r in rows:
        r["trace_url"] = trace_url(r.get("trace_id"))
        r["can_publish"] = can(user, "publish_content") and r["status"] == "draft"
    return rows


class DraftEdit(BaseModel):
    markdown: str = Field(min_length=20, max_length=30000)


@app.patch("/api/staff/content/{draft_id}")
def edit_draft(draft_id: str, body: DraftEdit, user: dict = Depends(current_staff)) -> dict:
    require(user, "draft_content")
    from mira.data.content_loader import parse_markdown
    try:
        doc = parse_markdown(body.markdown, "staff/edit.md")
    except Exception as exc:
        raise HTTPException(422, f"Front matter is invalid: {exc}")
    store = get_store()
    draft = store.get_draft(draft_id)
    if not draft or draft["status"] != "draft":
        raise HTTPException(409, "Only drafts can be edited.")
    store.update_draft_markdown(draft_id, body.markdown, doc.title)
    store.audit(user["name"], "edit_draft", draft_id)
    return store.get_draft(draft_id)


@app.post("/api/staff/content/{draft_id}/publish")
def publish_draft(draft_id: str, user: dict = Depends(current_staff)) -> dict:
    require(user, "publish_content")   # Approver role only – enforced here, not in a prompt
    from mira.agents.content_agent import publishable_markdown
    store = get_store()
    draft = store.get_draft(draft_id)
    if not draft or draft["status"] != "draft":
        raise HTTPException(409, "Only drafts can be published.")
    store.update_draft_markdown(draft_id, publishable_markdown(draft["markdown"]), draft["title"])
    store.set_draft_status(draft_id, "published", approved_by=user["name"])
    store.audit(user["name"], "publish_content", draft_id, draft["title"])
    reload_catalog()
    return store.get_draft(draft_id)


@app.post("/api/staff/content/{draft_id}/reject")
def reject_draft(draft_id: str, user: dict = Depends(current_staff)) -> dict:
    require(user, "reject_content")
    store = get_store()
    draft = store.get_draft(draft_id)
    if not draft or draft["status"] != "draft":
        raise HTTPException(409, "Only drafts can be rejected.")
    store.set_draft_status(draft_id, "rejected")
    store.audit(user["name"], "reject_content", draft_id)
    return store.get_draft(draft_id)


@app.get("/api/staff/audit")
def audit(user: dict = Depends(current_staff)) -> list[dict]:
    require(user, "view_enquiries")
    return get_store().audit_log()
