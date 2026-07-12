"""Performance Management module — cycles, reviews, and AI evaluation (Valkey or memory).

Implements:
- PerformanceCycle: configure and run performance review cycles.
- PerformanceReview: store individual reviewer submissions with normalized scores.
- activate_cycle: move cycle from draft → active.
- submit_review: normalize score from form responses, persist review.
- evaluate_cycle: call promotion_readiness_predictor for each participant,
  store predictions, and mark cycle as completed.

Storage keys:
  perf_cycle:{cycle_id}            — serialized PerformanceCycle
  employer_perf_cycles:{employer_id} — list of cycle_ids for an employer
  cycle_reviews:{cycle_id}         — list of review_ids for a cycle
  perf_review:{review_id}          — serialized PerformanceReview

Requirements: 6.1, 6.2, 6.3, 6.4
"""
from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional

from .config import get_settings
from .evaluation_models import promotion_readiness_predictor
from .model_registry import ModelPrediction

# ---------------------------------------------------------------------------
# In-memory fallback store
# ---------------------------------------------------------------------------
_memory_store: dict[str, str] = {}

PERFORMANCE_TTL = 60 * 60 * 24 * 365 * 3  # 3 years


def _valkey():
    settings = get_settings()
    if not settings.valkey_url:
        return None
    import valkey
    return valkey.from_url(settings.valkey_url, decode_responses=True)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class PerformanceCycle:
    """A configured performance review period for a set of participants.

    status lifecycle: draft → active → completed
    """
    cycle_id: str
    employer_id: str
    name: str
    start_date: str             # ISO-8601 date string YYYY-MM-DD
    end_date: str               # ISO-8601 date string YYYY-MM-DD
    participant_ids: list[str]  # engineer IDs enrolled in this cycle
    review_template: dict       # free-form form template (field definitions)
    status: str                 # draft | active | completed
    predictions: list[dict] = field(default_factory=list)
    # Each prediction stored as dict so it survives JSON round-trips.
    # Shape: {"engineer_id": ..., "score": ..., "model_version": ...,
    #         "confidence_interval": [lower, upper], "model_type": ...}


@dataclass
class PerformanceReview:
    """A single reviewer's submission within a PerformanceCycle."""
    review_id: str
    cycle_id: str
    reviewer_id: str
    reviewee_id: str
    form_responses: dict        # raw form field → response value
    normalized_score: float     # 0.0–1.0, computed from form_responses
    submitted_at: str           # ISO-8601 UTC


# ---------------------------------------------------------------------------
# Storage key helpers
# ---------------------------------------------------------------------------

def _cycle_key(cycle_id: str) -> str:
    return f"perf_cycle:{cycle_id}"


def _employer_cycles_key(employer_id: str) -> str:
    return f"employer_perf_cycles:{employer_id}"


def _cycle_reviews_key(cycle_id: str) -> str:
    return f"cycle_reviews:{cycle_id}"


def _review_key(review_id: str) -> str:
    return f"perf_review:{review_id}"


# ---------------------------------------------------------------------------
# Generic get/set helpers
# ---------------------------------------------------------------------------

def _store_get(key: str) -> str | None:
    client = _valkey()
    if client:
        return client.get(key)
    return _memory_store.get(key)


def _store_set(key: str, value: str) -> None:
    client = _valkey()
    if client:
        client.setex(key, PERFORMANCE_TTL, value)
    else:
        _memory_store[key] = value


def _store_get_list(key: str) -> list[str]:
    raw = _store_get(key)
    if not raw:
        return []
    return json.loads(raw)


def _store_append_to_list(key: str, item: str) -> None:
    existing = _store_get_list(key)
    if item not in existing:
        existing.append(item)
    _store_set(key, json.dumps(existing))


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def _serialize_cycle(cycle: PerformanceCycle) -> str:
    return json.dumps(asdict(cycle))


def _deserialize_cycle(raw: str) -> PerformanceCycle:
    d = json.loads(raw)
    # predictions list — stored as plain dicts, no further processing needed
    d.setdefault("predictions", [])
    return PerformanceCycle(**d)


def _serialize_review(review: PerformanceReview) -> str:
    return json.dumps(asdict(review))


def _deserialize_review(raw: str) -> PerformanceReview:
    d = json.loads(raw)
    return PerformanceReview(**d)


# ---------------------------------------------------------------------------
# PerformanceCycle CRUD
# ---------------------------------------------------------------------------

def save_cycle(cycle: PerformanceCycle) -> None:
    """Persist a PerformanceCycle (create or overwrite)."""
    _store_set(_cycle_key(cycle.cycle_id), _serialize_cycle(cycle))
    _store_append_to_list(_employer_cycles_key(cycle.employer_id), cycle.cycle_id)


def get_cycle(cycle_id: str) -> PerformanceCycle | None:
    """Retrieve a PerformanceCycle by ID, or None if not found."""
    raw = _store_get(_cycle_key(cycle_id))
    if not raw:
        return None
    return _deserialize_cycle(raw)


def list_employer_cycles(employer_id: str) -> list[PerformanceCycle]:
    """Return all PerformanceCycles for an employer, newest first."""
    cycle_ids = _store_get_list(_employer_cycles_key(employer_id))
    cycles = []
    for cid in cycle_ids:
        c = get_cycle(cid)
        if c:
            cycles.append(c)
    cycles.sort(key=lambda c: c.start_date, reverse=True)
    return cycles


# ---------------------------------------------------------------------------
# PerformanceReview CRUD
# ---------------------------------------------------------------------------

def save_review_record(review: PerformanceReview) -> None:
    """Persist an individual PerformanceReview (create or overwrite)."""
    _store_set(_review_key(review.review_id), _serialize_review(review))
    _store_append_to_list(_cycle_reviews_key(review.cycle_id), review.review_id)


def get_review(review_id: str) -> PerformanceReview | None:
    """Retrieve a PerformanceReview by ID, or None if not found."""
    raw = _store_get(_review_key(review_id))
    if not raw:
        return None
    return _deserialize_review(raw)


def list_cycle_reviews(cycle_id: str) -> list[PerformanceReview]:
    """Return all PerformanceReviews for a given cycle, sorted by submission time."""
    review_ids = _store_get_list(_cycle_reviews_key(cycle_id))
    reviews = []
    for rid in review_ids:
        r = get_review(rid)
        if r:
            reviews.append(r)
    reviews.sort(key=lambda r: r.submitted_at)
    return reviews


# ---------------------------------------------------------------------------
# Score normalization
# ---------------------------------------------------------------------------

def normalize_score(form_responses: dict) -> float:
    """Compute a normalized score from raw form responses.

    Algorithm:
    1. Recursively extract all numeric values from the responses dict.
    2. Average them.
    3. Clamp the result to [0.0, 1.0].
    4. If no numeric values are found, return 0.5 (neutral default).

    Args:
        form_responses: Free-form dict of field name → response value.

    Returns:
        Float in [0.0, 1.0].
    """
    def _extract_numerics(obj) -> list[float]:
        """Recursively collect all numeric values from nested dicts/lists."""
        nums: list[float] = []
        if isinstance(obj, (int, float)) and not isinstance(obj, bool):
            nums.append(float(obj))
        elif isinstance(obj, dict):
            for v in obj.values():
                nums.extend(_extract_numerics(v))
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                nums.extend(_extract_numerics(item))
        return nums

    numerics = _extract_numerics(form_responses)
    if not numerics:
        return 0.5

    avg = sum(numerics) / len(numerics)
    return max(0.0, min(1.0, avg))


# ---------------------------------------------------------------------------
# Core business logic
# ---------------------------------------------------------------------------

def activate_cycle(cycle_id: str) -> PerformanceCycle:
    """Move a PerformanceCycle from draft → active.

    Args:
        cycle_id: The ID of the cycle to activate.

    Returns:
        The updated PerformanceCycle with status="active".

    Raises:
        ValueError: If the cycle is not found.
    """
    cycle = get_cycle(cycle_id)
    if cycle is None:
        raise ValueError(f"PerformanceCycle not found: {cycle_id}")

    cycle.status = "active"
    save_cycle(cycle)
    return cycle


def submit_review(
    cycle_id: str,
    reviewer_id: str,
    reviewee_id: str,
    responses: dict,
) -> PerformanceReview:
    """Submit a performance review for a reviewee within a cycle.

    Steps:
    1. Validate the cycle exists.
    2. Normalize the score from ``responses``.
    3. Create and persist a PerformanceReview.
    4. Index the review under ``cycle_reviews:{cycle_id}``.

    Note: emitting a job_performance_rating Signal will be wired in task 7.3.
    For now, only storage is performed.

    Args:
        cycle_id:    The cycle this review belongs to.
        reviewer_id: The engineer (or manager) submitting the review.
        reviewee_id: The engineer being reviewed.
        responses:   Dict of form field → response value.

    Returns:
        The created and persisted PerformanceReview.

    Raises:
        ValueError: If the cycle is not found.
    """
    cycle = get_cycle(cycle_id)
    if cycle is None:
        raise ValueError(f"PerformanceCycle not found: {cycle_id}")

    score = normalize_score(responses)
    now = datetime.now(timezone.utc).isoformat()

    review = PerformanceReview(
        review_id=str(uuid.uuid4()),
        cycle_id=cycle_id,
        reviewer_id=reviewer_id,
        reviewee_id=reviewee_id,
        form_responses=responses,
        normalized_score=score,
        submitted_at=now,
    )
    save_review_record(review)
    return review


def evaluate_cycle(cycle_id: str) -> list[ModelPrediction]:
    """Evaluate a completed performance cycle using the promotion readiness predictor.

    Steps:
    1. Validate the cycle exists.
    2. Set cycle status to "completed".
    3. For each participant_id in cycle.participant_ids, call
       ``promotion_readiness_predictor.predict(engineer_id)``.
    4. Store all predictions on the cycle as cycle.predictions (list of dicts).
    5. Persist the updated cycle.
    6. Return the list of ModelPrediction objects.

    Args:
        cycle_id: The ID of the cycle to evaluate.

    Returns:
        List of ModelPrediction, one per participant.

    Raises:
        ValueError: If the cycle is not found.
    """
    cycle = get_cycle(cycle_id)
    if cycle is None:
        raise ValueError(f"PerformanceCycle not found: {cycle_id}")

    cycle.status = "completed"

    predictions: list[ModelPrediction] = []
    prediction_dicts: list[dict] = []

    for engineer_id in cycle.participant_ids:
        prediction = promotion_readiness_predictor.predict(engineer_id)
        predictions.append(prediction)
        prediction_dicts.append({
            "engineer_id": engineer_id,
            "score": prediction.score,
            "model_version": prediction.model_version,
            "confidence_interval": list(prediction.confidence_interval),
            "model_type": prediction.model_type.value,
        })

    cycle.predictions = prediction_dicts
    save_cycle(cycle)
    return predictions
