"""Unit tests for consent_store.py — ConsentRecord and Consent_Manager."""
from __future__ import annotations

import pytest

from app.consent_store import (
    ConsentRecord,
    SignalType,
    grant_consent,
    get_consent,
    has_active_consent,
    revoke_consent,
    _memory_consent,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clear_consent(*engineer_ids: str) -> None:
    """Remove consent entries from the in-memory store before each test."""
    from app.consent_store import _consent_key
    for eid in engineer_ids:
        _memory_consent.pop(_consent_key(eid), None)


# ---------------------------------------------------------------------------
# grant_consent
# ---------------------------------------------------------------------------

class TestGrantConsent:
    def test_creates_record_with_correct_fields(self):
        _clear_consent("eng-001")
        record = grant_consent("eng-001", [SignalType.COMMIT_METADATA])

        assert record.engineer_id == "eng-001"
        assert record.consent_id  # non-empty uuid
        assert SignalType.COMMIT_METADATA.value in record.signal_categories
        assert record.revoked_at is None
        assert record.granted_at

    def test_stores_multiple_signal_categories(self):
        _clear_consent("eng-002")
        categories = [SignalType.CODING_SESSION, SignalType.PR_REVIEW_QUALITY, SignalType.AI_PROMPT_CATEGORY]
        record = grant_consent("eng-002", categories)

        for cat in categories:
            assert cat.value in record.signal_categories

    def test_re_grant_replaces_previous_record(self):
        _clear_consent("eng-003")
        first = grant_consent("eng-003", [SignalType.COMMIT_METADATA])
        second = grant_consent("eng-003", [SignalType.CODING_SESSION])

        assert second.consent_id != first.consent_id
        assert second.engineer_id == first.engineer_id
        assert second.revoked_at is None
        # Old category is gone; new one is present
        assert SignalType.CODING_SESSION.value in second.signal_categories
        assert SignalType.COMMIT_METADATA.value not in second.signal_categories

    def test_re_grant_after_revocation_clears_revoked_at(self):
        _clear_consent("eng-004")
        grant_consent("eng-004", [SignalType.COMMIT_METADATA])
        revoke_consent("eng-004")

        re_granted = grant_consent("eng-004", [SignalType.COMMIT_METADATA])
        assert re_granted.revoked_at is None

    def test_default_consent_version_is_set(self):
        _clear_consent("eng-005")
        record = grant_consent("eng-005", [SignalType.CODING_SESSION])
        assert record.consent_version == "1.0"

    def test_custom_consent_version(self):
        _clear_consent("eng-006")
        record = grant_consent("eng-006", [SignalType.CODING_SESSION], consent_version="2.1")
        assert record.consent_version == "2.1"

    def test_empty_categories_allowed(self):
        _clear_consent("eng-007")
        record = grant_consent("eng-007", [])
        assert record.signal_categories == []


# ---------------------------------------------------------------------------
# revoke_consent
# ---------------------------------------------------------------------------

class TestRevokeConsent:
    def test_sets_revoked_at(self):
        _clear_consent("eng-010")
        grant_consent("eng-010", [SignalType.COMMIT_METADATA])
        revoked = revoke_consent("eng-010")

        assert revoked.revoked_at is not None

    def test_returns_updated_record(self):
        _clear_consent("eng-011")
        original = grant_consent("eng-011", [SignalType.CODING_SESSION])
        revoked = revoke_consent("eng-011")

        assert revoked.consent_id == original.consent_id
        assert revoked.engineer_id == "eng-011"

    def test_raises_if_no_record(self):
        _clear_consent("eng-012")
        with pytest.raises(ValueError, match="eng-012"):
            revoke_consent("eng-012")

    def test_persists_revoked_state(self):
        _clear_consent("eng-013")
        grant_consent("eng-013", [SignalType.COMMIT_METADATA])
        revoke_consent("eng-013")

        record = get_consent("eng-013")
        assert record is not None
        assert record.revoked_at is not None


# ---------------------------------------------------------------------------
# get_consent
# ---------------------------------------------------------------------------

class TestGetConsent:
    def test_returns_none_for_unknown_engineer(self):
        _clear_consent("eng-020")
        assert get_consent("eng-020") is None

    def test_returns_record_after_grant(self):
        _clear_consent("eng-021")
        grant_consent("eng-021", [SignalType.DEBUGGING_TRACE])
        record = get_consent("eng-021")

        assert record is not None
        assert record.engineer_id == "eng-021"

    def test_returns_latest_record_after_re_grant(self):
        _clear_consent("eng-022")
        grant_consent("eng-022", [SignalType.DEBUGGING_TRACE])
        second = grant_consent("eng-022", [SignalType.CODING_SESSION])

        record = get_consent("eng-022")
        assert record.consent_id == second.consent_id


# ---------------------------------------------------------------------------
# has_active_consent
# ---------------------------------------------------------------------------

class TestHasActiveConsent:
    def test_false_when_no_record(self):
        _clear_consent("eng-030")
        assert has_active_consent("eng-030", SignalType.CODING_SESSION) is False

    def test_true_for_consented_signal_type(self):
        _clear_consent("eng-031")
        grant_consent("eng-031", [SignalType.CODING_SESSION, SignalType.COMMIT_METADATA])

        assert has_active_consent("eng-031", SignalType.CODING_SESSION) is True
        assert has_active_consent("eng-031", SignalType.COMMIT_METADATA) is True

    def test_false_for_non_consented_signal_type(self):
        _clear_consent("eng-032")
        grant_consent("eng-032", [SignalType.CODING_SESSION])

        assert has_active_consent("eng-032", SignalType.DEBUGGING_TRACE) is False

    def test_false_after_revocation(self):
        _clear_consent("eng-033")
        grant_consent("eng-033", [SignalType.CODING_SESSION])
        revoke_consent("eng-033")

        assert has_active_consent("eng-033", SignalType.CODING_SESSION) is False

    def test_true_after_re_grant_following_revocation(self):
        _clear_consent("eng-034")
        grant_consent("eng-034", [SignalType.CODING_SESSION])
        revoke_consent("eng-034")
        grant_consent("eng-034", [SignalType.CODING_SESSION])

        assert has_active_consent("eng-034", SignalType.CODING_SESSION) is True


# ---------------------------------------------------------------------------
# ConsentRecord round-trip (serialization)
# ---------------------------------------------------------------------------

class TestConsentRecordSerialization:
    def test_round_trip_via_storage(self):
        """grant_consent → get_consent returns an equivalent record."""
        _clear_consent("eng-040")
        original = grant_consent(
            "eng-040",
            [SignalType.CODING_SESSION, SignalType.PR_REVIEW_QUALITY],
            consent_version="1.5",
        )
        retrieved = get_consent("eng-040")

        assert retrieved is not None
        assert retrieved.consent_id == original.consent_id
        assert retrieved.engineer_id == original.engineer_id
        assert retrieved.signal_categories == original.signal_categories
        assert retrieved.granted_at == original.granted_at
        assert retrieved.consent_version == original.consent_version
        assert retrieved.revoked_at == original.revoked_at
