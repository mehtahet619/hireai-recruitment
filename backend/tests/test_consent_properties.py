"""Property-based tests for consent gating and consent revocation.

Validates: Requirements 1.1, 1.2

These tests target the consent_store functions directly, since signal_store.py
does not exist yet (task 1.3). The properties tested are the foundational
consent invariants that the signal ingestion layer will depend on.
"""
from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from app.consent_store import (
    SignalType,
    grant_consent,
    has_active_consent,
    revoke_consent,
    _memory_consent,
    _consent_key,
)

# ---------------------------------------------------------------------------
# Shared strategies
# ---------------------------------------------------------------------------

# Valid engineer_id: non-empty text (strip whitespace to avoid blank-after-strip IDs)
engineer_id_st = st.text(min_size=1, max_size=64).map(str.strip).filter(bool)

# Any single SignalType value
signal_type_st = st.sampled_from(list(SignalType))

# A non-empty subset of SignalType values (for grant_consent categories)
signal_categories_st = st.lists(signal_type_st, min_size=1, unique=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clear(engineer_id: str) -> None:
    """Remove any stored consent record for the given engineer_id."""
    _memory_consent.pop(_consent_key(engineer_id), None)


# ---------------------------------------------------------------------------
# Property 1: Consent gates Signal ingestion
#
# For any engineer_id and SignalType, if no consent has ever been granted,
# has_active_consent MUST return False.
#
# This is the consent-level half of the property: before any grant, the gate
# is closed. The signal_store layer (task 1.3) will enforce this at ingestion
# time by calling has_active_consent before appending.
# ---------------------------------------------------------------------------

# Feature: engineering-lifecycle-platform, Property 1: Consent gates Signal ingestion
@given(engineer_id=engineer_id_st, signal_type=signal_type_st)
@settings(max_examples=200)
def test_no_consent_record_blocks_signal_ingestion(
    engineer_id: str,
    signal_type: SignalType,
) -> None:
    """Without a consent grant, has_active_consent returns False for every
    engineer/signal-type combination — the gate is closed."""
    _clear(engineer_id)

    result = has_active_consent(engineer_id, signal_type)

    assert result is False, (
        f"Expected has_active_consent to be False for engineer '{engineer_id}' "
        f"and signal '{signal_type}' with no consent record, but got {result}"
    )


# Feature: engineering-lifecycle-platform, Property 1: Consent gates Signal ingestion
@given(
    engineer_id=engineer_id_st,
    consented_types=signal_categories_st,
    non_consented_type=signal_type_st,
)
@settings(max_examples=200)
def test_consent_only_opens_gate_for_consented_signal_types(
    engineer_id: str,
    consented_types: list[SignalType],
    non_consented_type: SignalType,
) -> None:
    """has_active_consent returns True only for signal types explicitly included
    in the grant, and False for any type that was not consented to."""
    _clear(engineer_id)

    grant_consent(engineer_id, consented_types)

    # Every consented type should have an open gate
    for st_val in consented_types:
        assert has_active_consent(engineer_id, st_val) is True, (
            f"Expected has_active_consent to be True for consented signal '{st_val}' "
            f"on engineer '{engineer_id}'"
        )

    # A type not in the consent record must still be blocked
    if non_consented_type not in consented_types:
        assert has_active_consent(engineer_id, non_consented_type) is False, (
            f"Expected has_active_consent to be False for non-consented signal "
            f"'{non_consented_type}' on engineer '{engineer_id}'"
        )


# ---------------------------------------------------------------------------
# Property 4: Consent revocation stops new Signals
#
# For any engineer who has an active consent and then revokes it,
# has_active_consent MUST return False for every SignalType after revocation —
# regardless of which signal types were originally consented to.
# ---------------------------------------------------------------------------

# Feature: engineering-lifecycle-platform, Property 4: Consent revocation stops new Signals
@given(
    engineer_id=engineer_id_st,
    consented_types=signal_categories_st,
    signal_type=signal_type_st,
)
@settings(max_examples=200)
def test_revoked_consent_blocks_all_signal_types(
    engineer_id: str,
    consented_types: list[SignalType],
    signal_type: SignalType,
) -> None:
    """After revocation, has_active_consent returns False for every signal type,
    including types that were originally in the consent record."""
    _clear(engineer_id)

    grant_consent(engineer_id, consented_types)
    revoke_consent(engineer_id)

    result = has_active_consent(engineer_id, signal_type)

    assert result is False, (
        f"Expected has_active_consent to be False after revocation for engineer "
        f"'{engineer_id}' and signal '{signal_type}', but got {result}"
    )


# Feature: engineering-lifecycle-platform, Property 4: Consent revocation stops new Signals
@given(
    engineer_id=engineer_id_st,
    consented_types=signal_categories_st,
    signal_type=signal_type_st,
)
@settings(max_examples=200)
def test_revocation_is_permanent_until_re_grant(
    engineer_id: str,
    consented_types: list[SignalType],
    signal_type: SignalType,
) -> None:
    """Revocation is persistent: a second call to has_active_consent still
    returns False, confirming the revoked state is durably stored."""
    _clear(engineer_id)

    grant_consent(engineer_id, consented_types)
    revoke_consent(engineer_id)

    # Check twice to confirm the revoked state persists across multiple reads
    first_check = has_active_consent(engineer_id, signal_type)
    second_check = has_active_consent(engineer_id, signal_type)

    assert first_check is False, (
        f"First check after revocation should be False for engineer '{engineer_id}', "
        f"signal '{signal_type}'"
    )
    assert second_check is False, (
        f"Second check after revocation should still be False for engineer "
        f"'{engineer_id}', signal '{signal_type}' — revocation is not durable"
    )
