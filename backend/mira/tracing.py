"""Arize Phoenix tracing (OpenTelemetry + OpenInference ADK instrumentation).

Each traveller turn is one trace: a root `mira.turn` span with the ADK agent,
LLM, tool and our own pricing / retrieval / UI spans underneath.

Privacy: a span processor scrubs e-mails, phone and card numbers from every
string attribute before export, as a second line of defence after the API
already scrubs the chat text.
"""
from __future__ import annotations

import logging

from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, SpanProcessor

from mira.config import settings
from mira.privacy import scrub

log = logging.getLogger(__name__)
_initialised = False


class PIIScrubbingProcessor(SpanProcessor):
    """Rewrites string attributes in place when a span ends, before the exporter sees it."""

    def on_end(self, span: ReadableSpan) -> None:
        attrs = getattr(span, "_attributes", None)
        if not attrs:
            return
        for key in list(attrs.keys()):
            value = attrs[key]
            if isinstance(value, str):
                cleaned = scrub(value)
                if cleaned != value:
                    try:
                        attrs._dict[key] = cleaned          # BoundedAttributes is read-only after end()
                    except Exception:
                        pass

    def on_start(self, span, parent_context=None) -> None:  # noqa: D401
        return None

    def shutdown(self) -> None:
        return None

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True


def init_tracing() -> None:
    global _initialised
    if _initialised or not settings.tracing_enabled:
        return
    try:
        from openinference.instrumentation.google_adk import GoogleADKInstrumentor
        from phoenix.otel import register

        provider = register(
            project_name=settings.phoenix_project,
            endpoint=f"{settings.phoenix_endpoint.rstrip('/')}/v1/traces",
            batch=True,
            set_global_tracer_provider=True,
        )
        # Scrubber must run before the batch exporter: insert it first.
        provider._active_span_processor._span_processors = (
            PIIScrubbingProcessor(), *provider._active_span_processor._span_processors)
        GoogleADKInstrumentor().instrument(tracer_provider=provider)
        _initialised = True
        log.info("Phoenix tracing enabled -> %s", settings.phoenix_endpoint)
    except Exception as exc:  # tracing must never take Mira down
        log.warning("Tracing disabled: %s", exc)


def trace_url(trace_id: str | None) -> str | None:
    if not trace_id:
        return None
    return f"{settings.phoenix_ui_url.rstrip('/')}/redirects/traces/{trace_id}"


def current_trace_id() -> str | None:
    ctx = trace.get_current_span().get_span_context()
    return format(ctx.trace_id, "032x") if ctx.is_valid else None
