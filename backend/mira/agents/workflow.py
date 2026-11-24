"""The Mira graph: 3 LLM agents + 8 deterministic nodes over a typed shared state."""
from __future__ import annotations

import asyncio

from google import genai
from google.adk import Agent, Workflow
from google.adk.models import LlmRequest, LlmResponse
from google.genai import types
from opentelemetry import trace

from mira.agents import nodes
from mira.agents.prompts import respond_instruction, understand_instruction
from mira.agents.state import MiraState, Reply, Understanding
from mira.config import settings
from mira.ratelimit import capped_delay, exhausted_today, is_daily_quota, limiter

# Two quick attempts, then the fallback model: a traveller should not wait minutes on an overloaded model.
_RETRY = types.HttpRetryOptions(attempts=2, initial_delay=1.5, max_delay=8.0, exp_base=2.0)


def _gen_config(temperature: float) -> types.GenerateContentConfig:
    return types.GenerateContentConfig(temperature=temperature, http_options=types.HttpOptions(retry_options=_RETRY, timeout=30_000))


_fallback_client: genai.Client | None = None


async def rate_limit_before_model(callback_context, llm_request: LlmRequest) -> None:
    """Wait for a free slot under the model's requests-per-minute limit (see mira/ratelimit.py).
    If the routed model's daily quota is already used up, switch this request to the fallback model."""
    if llm_request.model in exhausted_today and settings.model_fallback not in exhausted_today:
        trace.get_current_span().set_attribute("mira.model_fallback", f"{llm_request.model} daily quota used up -> {settings.model_fallback}")
        llm_request.model = settings.model_fallback
    await limiter.acquire(llm_request.model)
    return None


async def fallback_on_model_error(callback_context, llm_request: LlmRequest, error: Exception) -> LlmResponse | None:
    """Recover from model errors without failing the traveller's turn:
      * 429 rate limit -> wait the delay Gemini suggests, retry the same model once;
      * anything else (503 overload, 504 deadline, or a second 429) -> the fallback model.
    Every recovery is recorded on the current span so it is visible in the trace."""
    global _fallback_client
    _fallback_client = _fallback_client or genai.Client()
    span = trace.get_current_span()
    config = llm_request.config.model_copy() if llm_request.config else types.GenerateContentConfig()
    config.http_options = types.HttpOptions(retry_options=_RETRY, timeout=30_000)
    if is_daily_quota(error):
        exhausted_today.add(llm_request.model)
        span.set_attribute("mira.daily_quota_exhausted", llm_request.model)
    elif "429" in str(error)[:20] or "RESOURCE_EXHAUSTED" in str(error):
        delay = capped_delay(error)
        span.set_attribute("mira.rate_limited", f"{llm_request.model}: waited {delay:.1f}s")
        await asyncio.sleep(delay)
        try:
            await limiter.acquire(llm_request.model)
            resp = await _fallback_client.aio.models.generate_content(model=llm_request.model,
                                                                      contents=llm_request.contents, config=config)
            return LlmResponse.create(resp)
        except Exception as again:  # fall through to the fallback model
            error = again
    if llm_request.model == settings.model_fallback:
        return None
    span.set_attribute("mira.model_fallback", f"{llm_request.model} -> {settings.model_fallback}: {str(error)[:120]}")
    await limiter.acquire(settings.model_fallback)
    resp = await _fallback_client.aio.models.generate_content(model=settings.model_fallback,
                                                              contents=llm_request.contents, config=config)
    return LlmResponse.create(resp)


def build_workflow() -> Workflow:
    understand = Agent(
        name="understand",
        model=settings.model_small,
        description="Classifies intent and extracts trip slots from the latest traveller message.",
        instruction=understand_instruction,
        include_contents="none",          # the transcript is in the instruction, already scrubbed
        output_schema=Understanding,
        output_key="understanding",
        generate_content_config=_gen_config(0.0),
        before_model_callback=rate_limit_before_model,
        on_model_error_callback=fallback_on_model_error,
    )
    respond_small = Agent(
        name="respond_small",
        model=settings.model_small,
        description="Writes Mira's reply and chooses UI components for simple turns.",
        instruction=respond_instruction,
        include_contents="none",
        output_schema=Reply,
        output_key="reply",
        generate_content_config=_gen_config(0.3),
        before_model_callback=rate_limit_before_model,
        on_model_error_callback=fallback_on_model_error,
    )
    respond_large = Agent(
        name="respond_large",
        model=settings.model_large,
        description="Writes Mira's reply for multi-day and custom itinerary planning.",
        instruction=respond_instruction,
        include_contents="none",
        output_schema=Reply,
        output_key="reply",
        generate_content_config=_gen_config(0.3),
        before_model_callback=rate_limit_before_model,
        on_model_error_callback=fallback_on_model_error,
    )
    return Workflow(
        name="mira",
        state_schema=MiraState,
        edges=[
            ("START", nodes.load_context, nodes.local_understand),
            (nodes.local_understand, {"done": nodes.plan_turn, "llm": understand}),
            (understand, nodes.plan_turn),
            (nodes.plan_turn, {
                "quote": nodes.price_quote,
                "flag": nodes.raise_flag,
                "custom": nodes.recommend,
                "other": nodes.retrieve,
            }),
            (nodes.price_quote, nodes.retrieve),
            (nodes.raise_flag, nodes.retrieve),
            (nodes.recommend, nodes.retrieve),
            (nodes.retrieve, {"small": respond_small, "large": respond_large}),
            (respond_small, nodes.compose_ui),
            (respond_large, nodes.compose_ui),
        ],
    )
