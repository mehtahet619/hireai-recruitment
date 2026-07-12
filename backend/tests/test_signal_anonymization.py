"""Property-based tests for Signal anonymization — no PII in payload.

# Feature: engineering-lifecycle-platform, Property 2: Signal anonymization — no PII in payload

Validates: Requirements 1.3

Property: For any Signal written to the Signal_Store, the signal payload field
SHALL contain no string that matches the originating Engineer's name, email
address, or employee ID.
"""
from __future__ import annotations

import string

from hypothesis import given, settings
from hypothesis import strategies as st

from app.consent_store import (
    SignalType,
    grant_consent,
    _memory_consent,
    _consent_key,
)
from app.signal_store import (
    Signal_Processor,
    _memory_pii_links,
    _memory_signal_counts,
    _memory_signals,
    _pii_link_key,
    compute_pseudonymous_id,
)

# ---------------------------------------------------------------------------
# Shared strategies
# ---------------------------------------------------------------------------

# engineer_id: non-empty printable text (strip to avoid whitespace-only IDs)
engineer_id_st = (
    st.text(alphabet=string.printable, min_size=1, max_size=32)
    .map(str.strip)
    .filter(bool)
)

# name: non-empty printable text, stripped
name_st = (
    st.text(alphabet=string.printable, min_size=1, max_size=32)
    .map(str.strip)
    .filter(bool)
)

# email: simple "localpart@domain.tld" pattern
email_st = st.builds(
    lambda local, domain, tld: f"{local}@{domain}.{tld}",
    local=st.text(alphabet=string.ascii_lowercase + string.digits, min_size=1, max_size=16),
    domain=st.text(alphabet=string.ascii_lowercase + string.digits, min_size=1, max_size=16),
    tld=st.sampled_from(["com", "org", "net", "io", "co"]),
)

# employee_id: non-empty printable text
employee_id_st = (
    st.text(alphabet=string.printable, min_size=1, max_size=32)
    .map(str.strip)
    .filter(bool)
)

# Non-PII payload fields: keys are safe strings, values are safe non-PII strings
safe_key_st = st.text(
    alphabet=string.ascii_lowercase + "_",
    min_size=1,
    max_size=16,
).filter(lambda k: k not in {"name", "email", "employee_id"})

safe_value_st = st.one_of(
    st.integers(min_value=0, max_value=10_000),
    st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    st.booleans(),
    st.text(alphabet=string.ascii_lowercase + "_0123456789", min_size=0, max_size=32),
)

extra_payload_st = st.dictionaries(
    keys=safe_key_st,
    values=safe_value_st,
    min_size=0,
    max_size=5,
)

signal_type_st = st.sampled_from(list(SignalType))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clear_engineer(engineer_id: str) -> None:
    """Remove all in-memory state associated with an engineer."""
    _memory_consent.pop(_consent_key(engineer_id), None)
    _memory_pii_links.pop(_pii_link_key(engineer_id), None)


def _clear_signals_for(employer_id: str, engineer_id: str) -> None:
    pid = compute_pseudonymous_id(engineer_id)
    _memory_signals.pop((employer_id, pid), None)
    _memory_signal_counts.pop(employer_id, None)


def _payload_contains(payload: dict, pii_value: str) -> bool:
    """Return True if any string value in the (top-level) payload equals
    pii_value (case-insensitive)."""
    needle = pii_value.lower()
    for v in payload.values():
        if isinstance(v, str) and v.lower() == needle:
            return True
    return False


# ---------------------------------------------------------------------------
# Property 2: Signal anonymization — no PII in payload
#
# For any Signal written to the Signal_Store, the signal payload field SHALL
# contain no string that matches the originating Engineer's name, email
# address, or employee ID.
# ---------------------------------------------------------------------------

# Feature: engineering-lifecycle-platform, Property 2: Signal anonymization — no PII in payload
@given(
    engineer_id=engineer_id_st,
    name=name_st,
    email=email_st,
    employee_id=employee_id_st,
    extra=extra_payload_st,
    signal_type=signal_type_st,
)
@settings(max_examples=200)
def test_signal_payload_contains_no_pii(
    engineer_id: str,
    name: str,
    email: str,
    employee_id: str,
    extra: dict,
    signal_type: SignalType,
) -> None:
    """**Validates: Requirements 1.3**

    After calling Signal_Processor.normalize_signal with a raw_payload that
    contains the engineer's name, email, and employee_id, the resulting
    signal.payload MUST NOT contain any of those PII values as a string.
    """
    employer_id = f"emp-pbt2-{abs(hash(engineer_id)) % 100_000}"

    # Setup: clear any stale state, then grant full consent
    _clear_engineer(engineer_id)
    _clear_signals_for(employer_id, engineer_id)

    grant_consent(engineer_id, list(SignalType))

    # Build a raw payload that intentionally embeds PII
    raw_payload: dict = {
        "name": name,
        "email": email,
        "employee_id": employee_id,
        **extra,
    }

    processor = Signal_Processor()
    signal = processor.normalize_signal(
        engineer_id=engineer_id,
        signal_type=signal_type,
        raw_payload=raw_payload,
        source_system="test",
        employer_id=employer_id,
    )

    # Property assertion: none of the PII literals appear as a payload value
    assert not _payload_contains(signal.payload, name), (
        f"name '{name}' found in signal.payload: {signal.payload}"
    )
    assert not _payload_contains(signal.payload, email), (
        f"email '{email}' found in signal.payload: {signal.payload}"
    )
    assert not _payload_contains(signal.payload, employee_id), (
        f"employee_id '{employee_id}' found in signal.payload: {signal.payload}"
    )

    # Also confirm the dedicated PII keys were removed entirely
    assert "name" not in signal.payload, (
        f"'name' key still present in signal.payload: {signal.payload}"
    )
    assert "email" not in signal.payload, (
        f"'email' key still present in signal.payload: {signal.payload}"
    )
    assert "employee_id" not in signal.payload, (
        f"'employee_id' key still present in signal.payload: {signal.payload}"
    )

    # Cleanup
    _clear_engineer(engineer_id)
    _clear_signals_for(employer_id, engineer_id)


# Feature: engineering-lifecycle-platform, Property 2: Signal anonymization — no PII in payload
@given(
    engineer_id=engineer_id_st,
    name=name_st,
    email=email_st,
    employee_id=employee_id_st,
    extra=extra_payload_st,
    signal_type=signal_type_st,
)
@settings(max_examples=200)
def test_signal_payload_contains_no_engineer_id_value(
    engineer_id: str,
    name: str,
    email: str,
    employee_id: str,
    extra: dict,
    signal_type: SignalType,
) -> None:
    """**Validates: Requirements 1.3**

    Even when the raw engineer_id itself appears as a payload value (e.g. under
    a custom key), normalize_signal MUST strip it so the resulting signal.payload
    does not contain the engineer_id as a string value.
    """
    employer_id = f"emp-pbt2b-{abs(hash(engineer_id)) % 100_000}"

    _clear_engineer(engineer_id)
    _clear_signals_for(employer_id, engineer_id)

    grant_consent(engineer_id, list(SignalType))

    # Embed the raw engineer_id as a payload value under a non-PII key
    raw_payload: dict = {
        "user": engineer_id,  # engineer_id masquerading as a generic field
        "name": name,
        "email": email,
        "employee_id": employee_id,
        **extra,
    }

    processor = Signal_Processor()
    signal = processor.normalize_signal(
        engineer_id=engineer_id,
        signal_type=signal_type,
        raw_payload=raw_payload,
        source_system="test",
        employer_id=employer_id,
    )

    assert not _payload_contains(signal.payload, engineer_id), (
        f"engineer_id '{engineer_id}' found as a payload value: {signal.payload}"
    )

    _clear_engineer(engineer_id)
    _clear_signals_for(employer_id, engineer_id)
