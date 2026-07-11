"""Persist interview sessions for human review."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .storage import save_bytes, save_json


def save_review(session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    review_id = f"{ts}_{session_id[:8]}"
    key = f"{review_id}/review.json"
    record = {
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "review_id": review_id,
        **payload,
    }
    stored = save_json(key, record)
    return {"review_id": review_id, "saved": True, "storage": stored}


def save_recording(session_id: str, review_id: str | None, data: bytes, filename: str) -> dict[str, Any]:
    rid = review_id or f"upload_{session_id[:8]}"
    key = f"{rid}/{filename or 'interview.webm'}"
    stored = save_bytes(key, data, "video/webm")
    return {"review_id": rid, "saved": True, "storage": stored}
