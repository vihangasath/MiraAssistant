"""Role-based permissions, enforced in code (never by prompt)."""
from __future__ import annotations

from fastapi import Header, HTTPException

from mira.store.db import get_store

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "agent": {"view_enquiries", "edit_enquiries", "view_issues", "draft_content", "view_content"},
    "approver": {"view_enquiries", "edit_enquiries", "view_issues", "draft_content", "view_content",
                 "publish_content", "reject_content", "edit_pricing_rules"},
}


def can(user: dict | None, permission: str) -> bool:
    return bool(user) and permission in ROLE_PERMISSIONS.get(user.get("role", ""), set())


def current_staff(x_staff_token: str | None = Header(default=None)) -> dict:
    user = get_store().staff_by_token(x_staff_token)
    if not user:
        raise HTTPException(status_code=401, detail="Staff sign-in required.")
    return user


def require(user: dict, permission: str) -> None:
    if not can(user, permission):
        raise HTTPException(status_code=403, detail=f"Your role ({user.get('role')}) cannot {permission.replace('_', ' ')}.")
