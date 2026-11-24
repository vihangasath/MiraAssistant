"""Personal-data scrubbing applied before text reaches the LLM, the session, or a trace.

Contact details are collected only by the booking/enquiry forms, which post
straight to the API and are stored in the enquiry row. If a traveller types
them into the chat anyway, they are replaced here.
"""
from __future__ import annotations

import re

_PATTERNS = [
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "[email removed]"),
    (re.compile(r"\b(?:\d[ -]?){13,19}\b"), "[card number removed]"),
    (re.compile(r"(?<!\w)(?:\+?\d{1,3}[\s-]?)?(?:\(?\d{2,4}\)?[\s-]?)?\d{3}[\s-]?\d{3,4}(?!\w)"), "[phone removed]"),
    (re.compile(r"\b[A-Z]{1,2}\d{6,9}\b"), "[document number removed]"),   # passport-like
]
_NAME_INTRO = re.compile(r"\b(my name is|i am called|this is)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})", re.I)


def scrub(text: str) -> str:
    if not text:
        return text
    out = text
    for pattern, repl in _PATTERNS:
        out = pattern.sub(repl, out)
    out = _NAME_INTRO.sub(lambda m: f"{m.group(1)} [name removed]", out)
    return out


def contains_pii(text: str) -> bool:
    return scrub(text) != text
