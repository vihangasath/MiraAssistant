"""Runtime configuration. Everything comes from environment variables so the
demo can change behaviour (today's date, models, margins file) without code edits."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")


def _env(name: str, default: str) -> str:
    value = os.getenv(name)
    return value if value not in (None, "") else default


@dataclass(frozen=True)
class Settings:
    dataset_dir: Path = field(default_factory=lambda: Path(_env("MIRA_DATASET_DIR", str(REPO_ROOT / "ceylon-compass-dataset"))))
    db_path: Path = field(default_factory=lambda: Path(_env("MIRA_DB_PATH", str(REPO_ROOT / "var" / "mira.db"))))
    # "Today" is configurable because the expected eval results assume 19 November 2026.
    today_override: str = field(default_factory=lambda: _env("MIRA_TODAY", "2026-11-19"))
    # Gemini models. Simple turns go to the small model, complex itineraries to the large one.
    model_small: str = field(default_factory=lambda: _env("MIRA_MODEL_SMALL", "gemini-3.1-flash-lite"))
    model_large: str = field(default_factory=lambda: _env("MIRA_MODEL_LARGE", "gemini-3-flash-preview"))
    model_fallback: str = field(default_factory=lambda: _env("MIRA_MODEL_FALLBACK", "gemini-2.5-flash"))
    model_judge: str = field(default_factory=lambda: _env("MIRA_MODEL_JUDGE", "gemini-2.5-flash"))
    phoenix_endpoint: str = field(default_factory=lambda: _env("PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006"))
    phoenix_ui_url: str = field(default_factory=lambda: _env("PHOENIX_UI_URL", "http://localhost:6006"))
    phoenix_project: str = field(default_factory=lambda: _env("PHOENIX_PROJECT_NAME", "mira"))
    tracing_enabled: bool = field(default_factory=lambda: _env("MIRA_TRACING", "1") == "1")
    # Mock payment: card numbers ending in this suffix are declined (to demo the friendly failure path).
    # S09 fix (stricter grounding rule + factual answers routed to the large model). 0 reproduces "before".
    grounding_fix: bool = field(default_factory=lambda: _env("MIRA_GROUNDING_FIX", "1") == "1")
    # Understand each message with rules + a trained classifier first; call Gemini only when unsure. 0 = always Gemini.
    local_nlu: bool = field(default_factory=lambda: _env("MIRA_LOCAL_NLU", "1") == "1")
    mock_decline_suffix: str = field(default_factory=lambda: _env("MIRA_MOCK_DECLINE_SUFFIX", "0002"))

    @property
    def rate_workbook(self) -> Path:
        return self.dataset_dir / "rates" / "rate_sheet_2026-27.xlsx"

    @property
    def content_dir(self) -> Path:
        return self.dataset_dir / "content"

    @property
    def brand_pack(self) -> Path:
        return self.dataset_dir / "brand" / "brand_pack.json"

    def today(self) -> date:
        return date.fromisoformat(self.today_override)


settings = Settings()
