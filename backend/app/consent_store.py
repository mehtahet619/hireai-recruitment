"""Consent management — ConsentRecord persistence and Consent_Manager operations.

SignalType enum is defined here and re-exported for use by signal_store.py and
other modules, since consent_store.py is the foundation that other stores import.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from .config import get_settings

# ---------------------------------------------------------------------------
# In-memory fallback store
# ---------------------------------------------------------------------------
_memory_consent: dict[str, str] = {}

CONSENT_TTL = 60 * 60 * 24 * 365 * 5  # 5 years


# ---------------------------------------------------------------------------
# SignalType enum
# Defined here so that consent_store.py has no dependency on signal_store.py.
# signal_store.py imports SignalType from here.
# ---------------------------------------------------------------------------
class SignalType(str, Enum):
    CODING_SESSION = "coding_session"
    DEBUGGING_TRACE = "debugging_trace"
    AI_PROMPT_CATEGORY = "ai_prompt_category"
    COMMIT_METADATA = "commit_metadata"
    PR_REVIEW_QUALITY = "pr_review_quality"
    INTERVIEW_TRANSCRIPT_EMBEDDING = "interview_transcript_embedding"
    ARCHITECTURE_DECISION_TAG = "architecture_decision_tag"
    ONBOARDING_TASK_COMPLETION = "onboarding_task_completion"
    COLLABORATION_FREQUENCY = "collaboration_frequency"
    JOB_PERFORMANCE_RATING = "job_performance_rating"
    ONBOARDING_COMPLETION_SUMMARY = "onboarding_completion_summary"
    CONSENT_CHANGE_AUDIT = "consent_change_audit"


# ---------------------------------------------------------------------------
# ConsentRecord dataclass
# ---------------------------------------------------------------------------
@dataclass
class ConsentRecord:
    consent_id: str
    engineer_id: str
    signal_categories: list[str]   # stored as plain strings for JSON round-trip
    granted_at: str                # ISO-8601 UTC
    consent_version: str
    revoked_at: Optional[str] = None


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------
def _valkey():
    settings = get_settings()
    if not settings.valkey_url:
        return None
    import valkey  # type: ignore
    return valkey.from_url(settings.valkey_url, decode_responses=True)


def _consent_key(engineer_id: str) -> str:
    return f"consent:{engineer_id}"


def _save_record(record: ConsentRecord) -> None:
    payload = json.dumps(asdict(record))
    key = _consent_key(record.engineer_id)
    client = _valkey()
    if client:
        client.setex(key, CONSENT_TTL, payload)
    else:
        _memory_consent[key] = payload


def _load_record(engineer_id: str) -> ConsentRecord | None:
    key = _consent_key(engineer_id)
    client = _valkey()
    raw = client.get(key) if client else _memory_consent.get(key)
    if not raw:
        return None
    data = json.loads(raw)
    return ConsentRecord(**data)


# ---------------------------------------------------------------------------
# Consent_Manager operations
# ---------------------------------------------------------------------------

def grant_consent(
    engineer_id: str,
    categories: list[SignalType],
    consent_version: str = "1.0",
) -> ConsentRecord:
    """Create or update a consent record for an engineer.

    If an existing record exists (even a revoked one), it is replaced with a
    fresh grant: new consent_id, new granted_at, cleared revoked_at.
    """
    record = ConsentRecord(
        consent_id=str(uuid.uuid4()),
        engineer_id=engineer_id,
        signal_categories=[cat.value if isinstance(cat, SignalType) else cat for cat in categories],
        granted_at=datetime.now(timezone.utc).isoformat(),
        consent_version=consent_version,
        revoked_at=None,
    )
    _save_record(record)
    return record


def revoke_consent(engineer_id: str) -> ConsentRecord:
    """Mark the engineer's consent as revoked.

    Raises ValueError if no consent record exists for the engineer.
    """
    record = _load_record(engineer_id)
    if record is None:
        raise ValueError(f"No consent record found for engineer '{engineer_id}'")
    record.revoked_at = datetime.now(timezone.utc).isoformat()
    _save_record(record)
    return record


def get_consent(engineer_id: str) -> ConsentRecord | None:
    """Return the current consent record for an engineer, or None if absent."""
    return _load_record(engineer_id)


def has_active_consent(engineer_id: str, signal_type: SignalType) -> bool:
    """Return True iff the engineer has a non-revoked consent covering signal_type."""
    record = _load_record(engineer_id)
    if record is None:
        return False
    if record.revoked_at is not None:
        return False
    signal_value = signal_type.value if isinstance(signal_type, SignalType) else signal_type
    return signal_value in record.signal_categories
