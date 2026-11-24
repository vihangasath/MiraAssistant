"""Loads tour / destination / policy Markdown and makes it safe to ground answers on.

Cleaning rules, all logged as ContentIssue so staff can see what was changed:
  * Only `status: published` documents are used; drafts never reach Mira.
  * HTML comments are removed (one hides a prompt injection in mirissa.md).
  * Sentences that address the assistant ("Mira, ...", "ignore your ...") are removed.
  * Newer policies override older page text, as the policies themselves say
    (cancellation policy P02 and children policy P03).
  * Promotions whose "book by" date has passed are removed.
  * Teaser prices ("From USD 85 per person") are never shown: they are not
    computed from the rate workbook and disagree with it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import yaml


@dataclass(frozen=True)
class ContentIssue:
    doc_id: str
    kind: str
    message: str


@dataclass
class Doc:
    id: str
    type: str                    # tour | destination | policy | faq | page
    title: str
    status: str
    last_updated: date | None
    body: str                    # cleaned markdown body
    path: str                    # source path relative to the dataset, shown as the citation
    meta: dict = field(default_factory=dict)
    origin: str = "dataset"      # dataset | staff (published through the approval flow)

    @property
    def is_published(self) -> bool:
        return self.status == "published"

    @property
    def destinations(self) -> list[str]:
        return list(self.meta.get("destinations") or [])

    @property
    def duration(self) -> str | None:
        return self.meta.get("duration")

    @property
    def category(self) -> str | None:
        return self.meta.get("category")


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    doc_id: str
    doc_title: str
    doc_type: str
    heading: str
    text: str
    source: str

    def citation(self) -> dict:
        return {"doc_id": self.doc_id, "title": self.doc_title, "section": self.heading, "source": self.source}


_FRONT_MATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.S)
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
# Text that tries to instruct the assistant rather than inform the guest.
_INJECTION_PATTERNS = [
    re.compile(r"\b(ignore|disregard|forget)\b[^.\n]*\b(instructions|rules|prompt)\b", re.I),
    re.compile(r"\bnote for the ai\b", re.I),
    re.compile(r"\b(mira|assistant|ai)\s*,\s*(if you|please|always|you must|you should)\b", re.I),
]
_BOOK_BY = re.compile(r"book by (\d{1,2} \w+ \d{4})", re.I)


def _parse_date(value) -> date | None:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def parse_markdown(text: str, rel_path: str, origin: str = "dataset") -> Doc:
    m = _FRONT_MATTER.match(text)
    if not m:
        raise ValueError(f"{rel_path}: no front matter")
    meta = yaml.safe_load(m.group(1)) or {}
    return Doc(
        id=str(meta["id"]),
        type=str(meta.get("type", "page")),
        title=str(meta.get("title", rel_path)),
        status=str(meta.get("status", "draft")),
        last_updated=_parse_date(meta.get("last_updated")),
        body=m.group(2),
        path=rel_path,
        meta=meta,
        origin=origin,
    )


def _remove_injections(doc: Doc, issues: list[ContentIssue]) -> None:
    def _strip_comment(match):
        issues.append(ContentIssue(doc.id, "hidden_instruction", f"Removed HTML comment: {match.group(0)[:80]!r}…"))
        return ""
    body = _HTML_COMMENT.sub(_strip_comment, doc.body)

    kept_lines = []
    for line in body.splitlines():
        if any(p.search(line) for p in _INJECTION_PATTERNS):
            issues.append(ContentIssue(doc.id, "instruction_in_content", f"Removed text addressed to the assistant: {line.strip()[:90]!r}"))
            continue
        kept_lines.append(line)
    doc.body = "\n".join(kept_lines)


def _remove_expired_promotions(doc: Doc, today: date, issues: list[ContentIssue]) -> None:
    kept = []
    for line in doc.body.splitlines():
        m = _BOOK_BY.search(line)
        if m:
            try:
                deadline = datetime.strptime(m.group(1), "%d %B %Y").date()
            except ValueError:
                deadline = None
            if deadline and deadline < today:
                issues.append(ContentIssue(doc.id, "expired_offer", f"Removed promotion that ended {deadline.isoformat()}: {line.strip()!r}"))
                doc.meta["expired_offer"] = True
                continue
        kept.append(line)
    doc.body = "\n".join(kept)


def _apply_policy_overrides(docs: dict[str, Doc], issues: list[ContentIssue]) -> None:
    """Policies P02/P03 say they replace older terms on individual pages. Enforce that."""
    cancellation = docs.get("P02")
    children = docs.get("P03")
    for doc in docs.values():
        if doc.type != "tour":
            continue
        if cancellation and re.search(r"^#+\s*Cancellation", doc.body, re.M | re.I):
            doc.body = re.sub(r"^(#+)\s*Cancellation.*?(?=^#|\Z)", "", doc.body, flags=re.M | re.S | re.I)
            issues.append(ContentIssue(doc.id, "superseded_by_policy", "Removed page-level cancellation terms; the current Cancellation policy (P02) applies."))
        if children:
            new_lines = []
            for line in doc.body.splitlines():
                if re.search(r"(kids|children)[^.\n]*\b(stay|go|travel)s? free", line, re.I):
                    issues.append(ContentIssue(doc.id, "superseded_by_policy", f"Removed old family offer {line.strip()!r}; the Children and infants policy (P03) applies."))
                    continue
                new_lines.append(line)
            doc.body = "\n".join(new_lines)


def _check_tour_meta(doc: Doc, issues: list[ContentIssue]) -> None:
    if doc.type == "tour" and doc.meta.get("teaser_price"):
        issues.append(ContentIssue(doc.id, "teaser_price_hidden", f"Teaser price {doc.meta['teaser_price']!r} is not computed from the rate workbook, so it is never shown."))
    if doc.type == "tour" and doc.last_updated and doc.last_updated.year < 2026:
        issues.append(ContentIssue(doc.id, "stale_page", f"Page last updated {doc.last_updated.isoformat()}; check it is still current."))


def load_content(content_dir: Path, today: date) -> tuple[dict[str, Doc], list[ContentIssue]]:
    issues: list[ContentIssue] = []
    docs: dict[str, Doc] = {}
    for path in sorted(content_dir.rglob("*.md")):
        rel = str(path.relative_to(content_dir.parent))
        doc = parse_markdown(path.read_text(encoding="utf-8"), rel)
        if not doc.is_published:
            issues.append(ContentIssue(doc.id, "draft_excluded", f"{doc.title!r} is a draft and is not used by Mira."))
        docs[doc.id] = doc
    for doc in docs.values():
        _remove_injections(doc, issues)
        _remove_expired_promotions(doc, today, issues)
        _check_tour_meta(doc, issues)
    _apply_policy_overrides(docs, issues)
    return docs, issues


def chunk_doc(doc: Doc) -> list[Chunk]:
    """Split a document by headings. Each chunk keeps its doc title for context."""
    chunks: list[Chunk] = []
    heading = doc.title
    buf: list[str] = []
    idx = 0

    def flush():
        nonlocal idx, buf
        text = "\n".join(buf).strip()
        if text:
            chunks.append(Chunk(f"{doc.id}#{idx}", doc.id, doc.title, doc.type, heading, text, doc.path))
            idx += 1
        buf = []

    header_facts = []
    if doc.type == "tour":
        for key in ("category", "duration", "start"):
            if doc.meta.get(key):
                header_facts.append(f"{key.capitalize()}: {doc.meta[key]}")
        if doc.meta.get("destinations"):
            header_facts.append("Destinations: " + ", ".join(doc.meta["destinations"]))
        if doc.meta.get("hotels"):
            header_facts.append("Hotels: " + ", ".join(doc.meta["hotels"]))
    if header_facts:
        chunks.append(Chunk(f"{doc.id}#facts", doc.id, doc.title, doc.type, "Key facts", "\n".join(header_facts), doc.path))

    for line in doc.body.splitlines():
        m = re.match(r"^(#{1,4})\s+(.*)", line)
        if m:
            flush()
            heading = m.group(2).strip()
            continue
        buf.append(line)
    flush()
    return chunks
