"""SQLite persistence: visitor profiles, private enquiries, staff, content drafts.

Privacy split:
  * `visitors.profile` holds only trip preferences (party make-up, dates, interests).
  * Names / emails / phones exist only in `enquiries.contact` (written by the booking
    form endpoint, never by the LLM) and are never sent to the model or to traces.
  * Costs and margins live in `enquiries.staff_quote` and are only served by staff endpoints.
"""
from __future__ import annotations

import json
import secrets
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from mira.config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS visitors (
    visitor_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    profile TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS enquiries (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    visitor_id TEXT,
    kind TEXT NOT NULL,              -- quote | flag | custom | booking
    tour_id TEXT,
    tour_name TEXT,
    request TEXT NOT NULL,           -- party + dates + free-text summary (no PII)
    price_usd INTEGER,
    deposit_usd INTEGER,
    cost_usd REAL,
    gross_profit_pct REAL,
    staff_quote TEXT,                -- full cost breakdown, staff only
    flag_reasons TEXT,               -- JSON list for needs_specialist
    trace_id TEXT,
    status TEXT NOT NULL,            -- new | needs_specialist | contacted | booked | payment_failed | closed
    notes TEXT NOT NULL DEFAULT '',
    contact TEXT,                    -- PII: only from the booking form
    booking_ref TEXT
);
CREATE TABLE IF NOT EXISTS staff_users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    role TEXT NOT NULL,              -- agent | approver
    token TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS content_drafts (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    command TEXT NOT NULL,
    doc_id TEXT NOT NULL,
    title TEXT NOT NULL,
    markdown TEXT NOT NULL,
    status TEXT NOT NULL,            -- draft | published | rejected
    approved_by TEXT,
    published_at TEXT,
    trace_id TEXT
);
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT NOT NULL,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    target TEXT,
    detail TEXT
);
"""

# Demo staff accounts. Tokens are demo values, not secrets; override with env in a real deployment.
DEMO_STAFF = [
    ("u-agent", "Nimal Perera (Sales agent)", "agent", "demo-agent-token"),
    ("u-approver", "Ayesha Fernando (Content approver)", "approver", "demo-approver-token"),
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_id(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(3).upper()}"


class Store:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._conn() as c:
            c.executescript(SCHEMA)
            for uid, name, role, token in DEMO_STAFF:
                c.execute("INSERT OR IGNORE INTO staff_users(id,name,role,token) VALUES (?,?,?,?)", (uid, name, role, token))

    @contextmanager
    def _conn(self):
        with self._lock:
            conn = sqlite3.connect(self.path)
            conn.row_factory = sqlite3.Row
            try:
                yield conn
                conn.commit()
            finally:
                conn.close()

    # ------------------------------------------------------------ visitors
    def get_profile(self, visitor_id: str) -> dict | None:
        with self._conn() as c:
            row = c.execute("SELECT profile FROM visitors WHERE visitor_id=?", (visitor_id,)).fetchone()
        return json.loads(row["profile"]) if row else None

    def save_profile(self, visitor_id: str, profile: dict) -> None:
        now = _now()
        with self._conn() as c:
            c.execute(
                "INSERT INTO visitors(visitor_id,created_at,updated_at,profile) VALUES (?,?,?,?) "
                "ON CONFLICT(visitor_id) DO UPDATE SET profile=excluded.profile, updated_at=excluded.updated_at",
                (visitor_id, now, now, json.dumps(profile)),
            )

    def forget_visitor(self, visitor_id: str) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM visitors WHERE visitor_id=?", (visitor_id,))

    # ------------------------------------------------------------ enquiries
    def create_enquiry(self, *, visitor_id: str | None, kind: str, tour_id: str | None, tour_name: str | None,
                       request: dict, trace_id: str | None, status: str, price_usd: int | None = None,
                       deposit_usd: int | None = None, cost_usd: float | None = None,
                       gross_profit_pct: float | None = None, staff_quote: dict | None = None,
                       flag_reasons: list | None = None) -> str:
        enquiry_id = _new_id("ENQ")
        now = _now()
        with self._conn() as c:
            c.execute(
                "INSERT INTO enquiries(id,created_at,updated_at,visitor_id,kind,tour_id,tour_name,request,price_usd,"
                "deposit_usd,cost_usd,gross_profit_pct,staff_quote,flag_reasons,trace_id,status) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (enquiry_id, now, now, visitor_id, kind, tour_id, tour_name, json.dumps(request), price_usd,
                 deposit_usd, cost_usd, gross_profit_pct, json.dumps(staff_quote) if staff_quote else None,
                 json.dumps(flag_reasons) if flag_reasons else None, trace_id, status),
            )
        return enquiry_id

    def get_enquiry(self, enquiry_id: str) -> dict | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM enquiries WHERE id=?", (enquiry_id,)).fetchone()
        return self._enquiry_row(row) if row else None

    def list_enquiries(self) -> list[dict]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM enquiries ORDER BY created_at DESC").fetchall()
        return [self._enquiry_row(r) for r in rows]

    def update_enquiry(self, enquiry_id: str, **fields) -> None:
        allowed = {"status", "notes", "contact", "booking_ref"}
        sets = {k: (json.dumps(v) if k == "contact" and v is not None else v) for k, v in fields.items() if k in allowed}
        if not sets:
            return
        sets["updated_at"] = _now()
        cols = ", ".join(f"{k}=?" for k in sets)
        with self._conn() as c:
            c.execute(f"UPDATE enquiries SET {cols} WHERE id=?", (*sets.values(), enquiry_id))

    @staticmethod
    def _enquiry_row(row: sqlite3.Row) -> dict:
        d = dict(row)
        for key in ("request", "staff_quote", "flag_reasons", "contact"):
            if d.get(key):
                d[key] = json.loads(d[key])
        return d

    # ------------------------------------------------------------ staff
    def staff_by_token(self, token: str | None) -> dict | None:
        if not token:
            return None
        with self._conn() as c:
            row = c.execute("SELECT id,name,role FROM staff_users WHERE token=?", (token,)).fetchone()
        return dict(row) if row else None

    def audit(self, actor: str, action: str, target: str | None = None, detail: str | None = None) -> None:
        with self._conn() as c:
            c.execute("INSERT INTO audit_log(at,actor,action,target,detail) VALUES (?,?,?,?,?)",
                      (_now(), actor, action, target, detail))

    def audit_log(self, limit: int = 100) -> list[dict]:
        with self._conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,))]

    # ------------------------------------------------------------ content drafts
    def create_draft(self, *, created_by: str, command: str, doc_id: str, title: str, markdown: str,
                     trace_id: str | None) -> str:
        draft_id = _new_id("DRAFT")
        now = _now()
        with self._conn() as c:
            c.execute(
                "INSERT INTO content_drafts(id,created_at,updated_at,created_by,command,doc_id,title,markdown,status,trace_id) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (draft_id, now, now, created_by, command, doc_id, title, markdown, "draft", trace_id),
            )
        return draft_id

    def get_draft(self, draft_id: str) -> dict | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM content_drafts WHERE id=?", (draft_id,)).fetchone()
        return dict(row) if row else None

    def list_drafts(self) -> list[dict]:
        with self._conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM content_drafts ORDER BY created_at DESC")]

    def set_draft_status(self, draft_id: str, status: str, approved_by: str | None = None) -> None:
        now = _now()
        with self._conn() as c:
            c.execute("UPDATE content_drafts SET status=?, approved_by=?, published_at=?, updated_at=? WHERE id=?",
                      (status, approved_by, now if status == "published" else None, now, draft_id))

    def update_draft_markdown(self, draft_id: str, markdown: str, title: str) -> None:
        with self._conn() as c:
            c.execute("UPDATE content_drafts SET markdown=?, title=?, updated_at=? WHERE id=? AND status='draft'",
                      (markdown, title, _now(), draft_id))

    def published_staff_docs(self):
        from mira.data.content_loader import parse_markdown
        docs = []
        with self._conn() as c:
            rows = c.execute("SELECT * FROM content_drafts WHERE status='published'").fetchall()
        for r in rows:
            try:
                doc = parse_markdown(r["markdown"], f"staff/{r['id']}.md", origin="staff")
            except Exception:  # a malformed draft should never take the site down
                continue
            doc.status = "published"
            docs.append(doc)
        return docs


_store: Store | None = None
_store_lock = threading.Lock()


def get_store() -> Store:
    global _store
    with _store_lock:
        if _store is None:
            _store = Store(settings.db_path)
        return _store
