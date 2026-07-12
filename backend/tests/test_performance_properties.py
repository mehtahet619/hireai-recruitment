"""Property-based tests for the Performance Management module (Task 7.2).

Property tested:
  For any engineer_id with active consent for JOB_PERFORMANCE_RATING, after
  Signal_Processor.normalize_signal is called with signal_type=JOB_PERFORMANCE_RATING,
  the Signal_Store contains a signal with that engineer's pseudonymous_id and
  type JOB_PERFORMANCE_RATING.

  This property validates the Signal_Store contract that MUST hold once task 7.3
  wires submit_review → Signal emission. It directly exercises the signal ingestion
  pipeline with a JOB_PERFORMANCE_RATING signal type to verify that:
    1. consent for JOB_PERFORMANCE_RATING allows the signal through
    2. the stored signal carries the correct pseudonymous_id
    3. the stored signal has signal_type == JOB_PERFORMANCE_RATING
    4. query_signals returns the signal when queried by pseudonymous_id

# Feature: engineering-lifecycle-platform, Validates: Requirements 6.3
"""
from __future__ import annotations

from datetime import datetime, timezone

from hypothesis import given, settings
from hypothesis import strategies as st

from app.consent_store import (
    SignalType,
    _memory_consent,
    grant_consent,
)
from app.signal_store import (
    Signal_Processor,
    _memory_pii_links,
    _memory_signal_counts,
    _memory_signals,
    compute_pseudonymous_id,
    query_signals,
)

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# reviewee_id: non-empty text (mirrors the engineer_id used in the performance review)
reviewee_id_st = st.text(min_size=1, max_size=64).map(str.strip).filter(bool)

# normalized_score: floats in [0.0, 1.0], no NaN
normalized_score_st = st.floats(
    min_value=0.0,
    max_value=1.0,
    allow_nan=False,
    allow_infinity=False,
)


# ---------------------------------------------------------------------------
# Helper: clear all in-memory stores before each example
# ---------------------------------------------------------------------------

def _clear_stores() -> None:
    """Reset all in-memory stores so examples are fully isolated."""
    _memory_consent.clear()
    _memory_signals.clear()
    _memory_pii_links.clear()
    _memory_signal_counts.clear()


# ---------------------------------------------------------------------------
# Property: JOB_PERFORMANCE_RATING signal lands in Signal_Store with
# the reviewee's pseudonymous_id
#
# For any engineer_id (reviewee) with active consent for JOB_PERFORMANCE_RATING,
# after Signal_Processor.normalize_signal is called with
# signal_type=SignalType.JOB_PERFORMANCE_RATING and payload={"score": <float>},
# query_signals for that engineer's pseudonymous_id returns at least one signal
# with signal_type == JOB_PERFORMANCE_RATING.
#
# Feature: engineering-lifecycle-platform, Validates: Requirements 6.3
# ---------------------------------------------------------------------------

@given(
    reviewee_id=reviewee_id_st,
    normalized_score=normalized_score_st,
)
@settings(max_examples=200)
def test_job_performance_rating_signal_stored_with_pseudonymous_id(
    reviewee_id: str,
    normalized_score: float,
) -> None:
    """For any reviewee_id with consent, emitting a JOB_PERFORMANCE_RATING signal
    via Signal_Processor results in a matching signal in the Signal_Store keyed
    by the reviewee's pseudonymous_id.

    This verifies the Signal_Store contract required by Requirement 6.3:
    "THE Platform SHALL store the review, compute a normalized score from the
    review form, and emit a job_performance_rating Signal to the Signal_Store."

    Test steps:
    1. Clear all in-memory stores for isolation.
    2. Grant consent for reviewee_id covering JOB_PERFORMANCE_RATING.
    3. Emit a JOB_PERFORMANCE_RATING signal via Signal_Processor.normalize_signal.
    4. Derive the expected pseudonymous_id via compute_pseudonymous_id.
    5. Query the Signal_Store for that pseudonymous_id.
    6. Assert at least one JOB_PERFORMANCE_RATING signal is present.

    Validates: Requirements 6.3
    """
    # Step 1: isolate this example
    _clear_stores()

    # Step 2: grant consent for the reviewee covering JOB_PERFORMANCE_RATING
    grant_consent(reviewee_id, [SignalType.JOB_PERFORMANCE_RATING])

    # Step 3: emit the signal (simulating what task 7.3 wires into submit_review)
    processor = Signal_Processor()
    processor.normalize_signal(
        engineer_id=reviewee_id,
        signal_type=SignalType.JOB_PERFORMANCE_RATING,
        raw_payload={"score": normalized_score},
        source_system="performance_review",
        employer_id="test-employer",
        consent_version="1.0",
    )

    # Step 4: derive the pseudonymous_id the store uses for this engineer
    expected_pseudonymous_id = compute_pseudonymous_id(reviewee_id)

    # Step 5: query all JOB_PERFORMANCE_RATING signals for this pseudonymous_id
    signals = query_signals(
        pseudonymous_id=expected_pseudonymous_id,
        signal_type=SignalType.JOB_PERFORMANCE_RATING,
        since=datetime(2000, 1, 1, tzinfo=timezone.utc),
        until=datetime(2100, 1, 1, tzinfo=timezone.utc),
    )

    # Step 6: assert the signal is present
    assert len(signals) >= 1, (
        f"Expected at least one JOB_PERFORMANCE_RATING signal in the Signal_Store "
        f"for pseudonymous_id derived from reviewee_id={reviewee_id!r}, "
        f"but got 0 signals. normalized_score={normalized_score}"
    )

    # Extra: confirm the signal has the correct type and pseudonymous_id
    matching = [
        s for s in signals
        if s.signal_type == SignalType.JOB_PERFORMANCE_RATING
        and s.pseudonymous_id == expected_pseudonymous_id
    ]
    assert len(matching) >= 1, (
        f"Signals found but none match both signal_type=JOB_PERFORMANCE_RATING "
        f"and pseudonymous_id={expected_pseudonymous_id!r}. "
        f"Found signals: {signals}"
    )
