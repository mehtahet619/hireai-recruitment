"""Property-based tests for Signal immutability and serialization round-trip.

# Feature: engineering-lifecycle-platform
# Property 3: Signal immutability — read-after-write returns identical record
# Property 12: Signal serialization round-trip

Validates: Requirements 1.4, 1.6
"""
from __future__ import annotations

import string
import uuid
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

from hypothesis import given, settings
from hypothesis import strategies as st

from app.signal_store import (
    Signal,
    SignalType,
    _memory_signals,
    _signal_from_json,
    _signal_to_json,
    append_signal,
    query_signals,
)

# ---------------------------------------------------------------------------
# Shared strategies
# ---------------------------------------------------------------------------

# Printable, non-empty strings for IDs
_safe_text_st = st.text(
    alphabet=string.ascii_letters + string.digits + "_-",
    min_size=1,
    max_size=32,
)

signal_type_st = st.sampled_from(list(SignalType))

# Payload: string keys (safe, non-empty), JSON-safe scalar values
_payload_key_st = st.text(
    alphabet=string.ascii_lowercase + "_",
    min_size=1,
    max_size=16,
)

_payload_value_st = st.one_of(
    st.integers(min_value=0, max_value=9_999),
    st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    st.booleans(),
    st.text(
        alphabet=string.ascii_letters + string.digits + "_",
        min_size=0,
        max_size=32,
    ),
)

payload_st = st.dictionaries(
    keys=_payload_key_st,
    values=_payload_value_st,
    min_size=0,
    max_size=5,
)

# ISO-8601 UTC timestamps: use a fixed recent base to keep the window small
_BASE_DT = datetime(2024, 1, 1, tzinfo=timezone.utc)

collected_at_st = st.builds(
    lambda delta_s: (_BASE_DT + timedelta(seconds=delta_s)).isoformat(),
    delta_s=st.integers(min_value=0, max_value=365 * 24 * 3600),
)


def _signal_st() -> st.SearchStrategy[Signal]:
    """Strategy that builds a fully-populated Signal with a fresh signal_id."""
    return st.builds(
        Signal,
        signal_id=st.builds(lambda: str(uuid.uuid4())),
        pseudonymous_id=_safe_text_st,
        signal_type=signal_type_st,
        payload=payload_st,
        source_system=_safe_text_st,
        collected_at=collected_at_st,
        consent_version=st.just("1.0"),
        employer_id=_safe_text_st,
        revoked=st.just(False),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clear_signal(signal: Signal) -> None:
    """Remove the signal's entry from the in-memory store."""
    mem_key = (signal.employer_id, signal.pseudonymous_id)
    bucket = _memory_signals.get(mem_key)
    if bucket is not None:
        try:
            bucket.remove(signal)
        except ValueError:
            pass


# ---------------------------------------------------------------------------
# Property 3: Signal immutability — read-after-write returns identical record
#
# For any Signal appended to the Signal_Store with a given signal_id, a
# subsequent read of that signal_id SHALL return a record identical to the one
# written (same type, payload, pseudonymous_id, collected_at).
# ---------------------------------------------------------------------------

# Feature: engineering-lifecycle-platform, Property 3: Signal immutability
@given(signal=_signal_st())
@settings(max_examples=200)
def test_signal_read_after_write_is_identical(signal: Signal) -> None:
    """**Validates: Requirements 1.4**

    After appending a Signal, querying the store with the signal's
    pseudonymous_id and a time window that covers collected_at MUST return
    at least one record whose signal_id matches, with all fields equal to
    the original.
    """
    # Arrange: ensure a clean slate for this (employer_id, pseudonymous_id) pair
    mem_key = (signal.employer_id, signal.pseudonymous_id)
    _memory_signals.pop(mem_key, None)

    # Act: write
    append_signal(signal)

    # Act: read — query window covers ±1 hour around collected_at
    collected_dt = datetime.fromisoformat(signal.collected_at)
    if collected_dt.tzinfo is None:
        collected_dt = collected_dt.replace(tzinfo=timezone.utc)
    since = collected_dt - timedelta(hours=1)
    until = collected_dt + timedelta(hours=1)

    results = query_signals(
        pseudonymous_id=signal.pseudonymous_id,
        signal_type=None,  # no type filter — let all through
        since=since,
        until=until,
    )

    # Find the record that matches our signal_id
    match = next((r for r in results if r.signal_id == signal.signal_id), None)

    # Assert: a matching record exists
    assert match is not None, (
        f"signal_id={signal.signal_id} not found in query results "
        f"(got {[r.signal_id for r in results]})"
    )

    # Assert: every field equals the original
    assert match.signal_type == signal.signal_type, (
        f"signal_type mismatch: expected {signal.signal_type!r}, got {match.signal_type!r}"
    )
    assert match.payload == signal.payload, (
        f"payload mismatch: expected {signal.payload!r}, got {match.payload!r}"
    )
    assert match.pseudonymous_id == signal.pseudonymous_id, (
        f"pseudonymous_id mismatch: expected {signal.pseudonymous_id!r}, "
        f"got {match.pseudonymous_id!r}"
    )
    assert match.collected_at == signal.collected_at, (
        f"collected_at mismatch: expected {signal.collected_at!r}, "
        f"got {match.collected_at!r}"
    )

    # Cleanup
    _memory_signals.pop(mem_key, None)


# ---------------------------------------------------------------------------
# Property 12: Signal serialization round-trip
#
# For any valid Signal object, serializing it to JSON and deserializing it back
# SHALL produce an object equal to the original (same signal_id, signal_type,
# payload, pseudonymous_id, collected_at).
# ---------------------------------------------------------------------------

# Feature: engineering-lifecycle-platform, Property 12: Signal serialization round-trip
@given(signal=_signal_st())
@settings(max_examples=200)
def test_signal_serialization_round_trip(signal: Signal) -> None:
    """**Validates: Requirements 1.6**

    _signal_to_json followed by _signal_from_json MUST produce a Signal
    object that is field-for-field identical to the original.
    """
    serialized = _signal_to_json(signal)
    deserialized = _signal_from_json(serialized)

    assert deserialized.signal_id == signal.signal_id, (
        f"signal_id mismatch after round-trip: "
        f"expected {signal.signal_id!r}, got {deserialized.signal_id!r}"
    )
    assert deserialized.signal_type == signal.signal_type, (
        f"signal_type mismatch after round-trip: "
        f"expected {signal.signal_type!r}, got {deserialized.signal_type!r}"
    )
    assert deserialized.payload == signal.payload, (
        f"payload mismatch after round-trip: "
        f"expected {signal.payload!r}, got {deserialized.payload!r}"
    )
    assert deserialized.pseudonymous_id == signal.pseudonymous_id, (
        f"pseudonymous_id mismatch after round-trip: "
        f"expected {signal.pseudonymous_id!r}, got {deserialized.pseudonymous_id!r}"
    )
    assert deserialized.collected_at == signal.collected_at, (
        f"collected_at mismatch after round-trip: "
        f"expected {signal.collected_at!r}, got {deserialized.collected_at!r}"
    )
