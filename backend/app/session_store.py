"""Interview session persistence (Valkey in production, memory for local dev)."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any
from datetime import datetime

from .config import get_settings

SESSION_TTL_SECONDS = 60 * 60 * 24
BAN_KEY_PREFIX = "ban:"

_valkey_client = None
_memory: dict[str, str] = {}
_ban_memory: dict[str, dict] = {}


@dataclass
class InterviewSession:
    session_id: str
    candidate_id: str
    job_description: str
    resume: str
    requirements: dict[str, Any]
    resume_analysis: dict[str, Any]
    questions: dict[str, Any]
    conversation_state: dict[str, Any] = field(default_factory=dict)
    transcript: list[dict[str, str]] = field(default_factory=list)
    history: list[dict[str, str]] = field(default_factory=list)
    handoff: dict[str, Any] | None = None
    is_complete: bool = False
    review_id: str | None = None
    tab_changes_count: int = 0


def _valkey():
    global _valkey_client
    settings = get_settings()
    if not settings.valkey_url:
        return None
    if _valkey_client is None:
        import valkey
        _valkey_client = valkey.from_url(settings.valkey_url, decode_responses=True)
    return _valkey_client


def session_backend() -> str:
    return "valkey" if get_settings().valkey_url else "memory"


def _key(session_id: str) -> str:
    return f"interview:{session_id}"


def _ban_key(candidate_id: str) -> str:
    return f"{BAN_KEY_PREFIX}{candidate_id}"


def _persist(session: InterviewSession) -> None:
    payload = json.dumps(asdict(session), ensure_ascii=False)
    client = _valkey()
    if client:
        client.setex(_key(session.session_id), SESSION_TTL_SECONDS, payload)
    else:
        _memory[session.session_id] = payload


def _deserialize(raw: str) -> InterviewSession:
    return InterviewSession(**json.loads(raw))


def create_session(
    *,
    candidate_id: str,
    job_description: str,
    resume: str,
    requirements: dict[str, Any],
    resume_analysis: dict[str, Any],
    questions: dict[str, Any],
) -> InterviewSession:
    session = InterviewSession(
        session_id=str(uuid.uuid4()),
        candidate_id=candidate_id,
        job_description=job_description,
        resume=resume,
        requirements=requirements,
        resume_analysis=resume_analysis,
        questions=questions,
        tab_changes_count=0,
    )
    _persist(session)
    return session


def get_session(session_id: str) -> InterviewSession | None:
    client = _valkey()
    raw = client.get(_key(session_id)) if client else _memory.get(session_id)
    return _deserialize(raw) if raw else None


def save_session(session: InterviewSession) -> None:
    _persist(session)


def delete_session(session_id: str) -> None:
    client = _valkey()
    if client:
        client.delete(_key(session_id))
    else:
        _memory.pop(session_id, None)


def is_banned(candidate_id: str) -> dict:
    client = _valkey()
    key = _ban_key(candidate_id)
    if client:
        raw = client.get(key)
        if raw:
            return json.loads(raw)
    else:
        if key in _ban_memory:
            return _ban_memory[key]
    return {"banned": False}


def ban_user(candidate_id: str, reason: str = "Too many tab changes") -> dict:
    ban_data = {
        "banned": True,
        "candidate_id": candidate_id,
        "reason": reason,
        "banned_at": datetime.now().isoformat(),
    }
    client = _valkey()
    key = _ban_key(candidate_id)
    if client:
        client.set(key, json.dumps(ban_data))
    else:
        _ban_memory[key] = ban_data
    return ban_data


def unban_user(candidate_id: str) -> dict:
    client = _valkey()
    key = _ban_key(candidate_id)
    if client:
        client.delete(key)
    else:
        _ban_memory.pop(key, None)
    return {"banned": False, "candidate_id": candidate_id}
