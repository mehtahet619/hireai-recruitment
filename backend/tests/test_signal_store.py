"""Unit tests for signal_store.py.

Covers:
- Signal dataclass construction and serialisation round-trip
- Signal_Processor.normalize_signal (PII stripping, HMAC pseudonymisation,
  consent gating)
- Signal_Store: append_signal, query_signals, revoke_signals,
  erase_pii_linkage, get_signal_count
- ConsentError raised when consent is absent

Validates: Requirements 1.3, 1.4, 1.5, 1.6
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

import pytest

from app.consent_store import (
    SignalType,
    grant_consent,
    revoke_consent,
    _memory_consent,
    _consent_key,
)
from app.signal_store import (
    ConsentError,
    Signal,
    Signal_Processor,
    _memory_pii_links,
    _memory_signal_counts,
    _memory_signals,
    _pii_link_key,
    _signal_from_json,
    _signal_set_key,
    _signal_to_json,
    _strip_pii,
    append_signal,
    compute_pseudonymous_id,
    erase_pii_linkage,
    get_signal_count,
    query_signals,
    revoke_signals,
)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def _clear_consent(*engineer_ids: str) -> None:
    for eid in engineer_ids:
        _memory_consent.pop(_consent_key(eid), None)


def _clear_signals(*employer_pseudonymous_pairs: tuple[str, str]) -> None:
    for emp_id, pid in employer_pseudonymous_pairs:
        _memory_signals.pop((emp_id, pid), None)


def _clear_counts(*employer_ids: str) -> None:
    for eid in employer_ids:
        _memory_signal_counts.pop(eid, None)


def _clear_pii_links(*engineer_ids: str) -> None:
    for eid in engineer_ids:
        _memory_pii_links.pop(_pii_link_key(eid), None)


def _grant_full_consent(engineer_id: str) -> None:
    grant_consent(engineer_id, list(SignalType))


def _make_signal(
    pseudonymous_id: str = "pid-test",
    employer_id: str = "emp-test",
    signal_type: SignalType = SignalType.COMMIT_METADATA,
    payload: dict | None = None,
) -> Signal:
    return Signal(
        signal_id="sig-123",
        pseudonymous_id=pseudonymous_id,
        signal_type=signal_type,
        payload=payload or {"repo": "acme/api", "branch": "main"},
        source_system="github",
        collected_at=datetime.now(timezone.utc).isoformat(),
        consent_version="1.0",
        employer_id=employer_id,
    )


# ---------------------------------------------------------------------------
# compute_pseudonymous_id
# ---------------------------------------------------------------------------

class TestComputePseudonymousId:
    def test_returns_hex_string(self):
        pid = compute_pseudonymous_id("eng-001")
        assert isinstance(pid, str)
        assert len(pid) == 64  # SHA-256 hex digest length

    def test_deterministic(self):
        assert compute_pseudonymous_id("eng-abc") == compute_pseudonymous_id("eng-abc")

    def test_different_ids_produce_different_pseudonymous_ids(self):
        assert compute_pseudonymous_id("eng-001") != compute_pseudonymous_id("eng-002")

    def test_not_equal_to_original(self):
        eid = "eng-001"
        assert compute_pseudonymous_id(eid) != eid


# ---------------------------------------------------------------------------
# _strip_pii
# ---------------------------------------------------------------------------

class TestStripPii:
    def test_removes_name_key(self):
        payload = {"name": "Alice Smith", "repo": "api"}
        result = _strip_pii(payload, "eng-001")
        assert "name" not in result
        assert result["repo"] == "api"

    def test_removes_email_key(self):
        payload = {"email": "alice@example.com", "duration": 120}
        result = _strip_pii(payload, "eng-001")
        assert "email" not in result
        assert result["duration"] == 120

    def test_removes_employee_id_key(self):
        payload = {"employee_id": "E-9876", "score": 0.9}
        result = _strip_pii(payload, "eng-001")
        assert "employee_id" not in result
        assert result["score"] == 0.9

    def test_removes_value_matching_engineer_id(self):
        payload = {"user": "eng-001", "repo": "api"}
        result = _strip_pii(payload, "eng-001")
        assert "user" not in result
        assert result["repo"] == "api"

    def test_removes_value_matching_name_from_payload(self):
        payload = {"name": "Alice", "author": "Alice", "repo": "api"}
        result = _strip_pii(payload, "eng-001")
        assert "name" not in result
        assert "author" not in result  # value "Alice" was in the name field
        assert result["repo"] == "api"

    def test_removes_value_matching_email_from_payload(self):
        payload = {"email": "a@b.com", "contact": "a@b.com", "lines": 10}
        result = _strip_pii(payload, "eng-001")
        assert "email" not in result
        assert "contact" not in result
        assert result["lines"] == 10

    def test_case_insensitive_value_removal(self):
        payload = {"name": "Alice", "author": "ALICE", "repo": "api"}
        result = _strip_pii(payload, "eng-001")
        assert "author" not in result

    def test_non_pii_payload_unchanged(self):
        payload = {"repo": "api", "branch": "main", "commits": 3}
        result = _strip_pii(payload, "eng-001")
        assert result == payload

    def test_non_string_values_retained(self):
        payload = {"name": "Alice", "count": 42, "metadata": {"key": "val"}}
        result = _strip_pii(payload, "eng-001")
        assert "name" not in result
        assert result["count"] == 42
        assert result["metadata"] == {"key": "val"}


# ---------------------------------------------------------------------------
# Signal serialisation round-trip
# ---------------------------------------------------------------------------

class TestSignalSerialisation:
    def test_json_round_trip(self):
        sig = _make_signal()
        restored = _signal_from_json(_signal_to_json(sig))
        assert restored.signal_id == sig.signal_id
        assert restored.pseudonymous_id == sig.pseudonymous_id
        assert restored.signal_type == sig.signal_type
        assert restored.payload == sig.payload
        assert restored.collected_at == sig.collected_at
        assert restored.source_system == sig.source_system
        assert restored.employer_id == sig.employer_id
        assert restored.revoked == sig.revoked

    def test_signal_type_deserialised_as_enum(self):
        sig = _make_signal(signal_type=SignalType.CODING_SESSION)
        restored = _signal_from_json(_signal_to_json(sig))
        assert isinstance(restored.signal_type, SignalType)
        assert restored.signal_type == SignalType.CODING_SESSION


# ---------------------------------------------------------------------------
# append_signal & query_signals
# ---------------------------------------------------------------------------

class TestAppendAndQuerySignals:
    def _setup(self, engineer_id: str = "eng-q1", employer_id: str = "emp-q1"):
        pid = compute_pseudonymous_id(engineer_id)
        _clear_signals((employer_id, pid))
        _clear_counts(employer_id)
        return pid

    def test_appended_signal_queryable(self):
        pid = self._setup()
        sig = _make_signal(pseudonymous_id=pid, employer_id="emp-q1")
        append_signal(sig)

        now = datetime.now(timezone.utc)
        results = query_signals(pid, None, now - timedelta(minutes=1), now + timedelta(minutes=1))
        assert any(s.signal_id == sig.signal_id for s in results)

    def test_query_filters_by_signal_type(self):
        pid = self._setup("eng-q2", "emp-q2")
        sig_commit = _make_signal(pseudonymous_id=pid, employer_id="emp-q2",
                                   signal_type=SignalType.COMMIT_METADATA)
        sig_coding = _make_signal(pseudonymous_id=pid, employer_id="emp-q2",
                                   signal_type=SignalType.CODING_SESSION)
        sig_coding.signal_id = "sig-coding-456"
        append_signal(sig_commit)
        append_signal(sig_coding)

        now = datetime.now(timezone.utc)
        results = query_signals(pid, SignalType.CODING_SESSION,
                                now - timedelta(minutes=1), now + timedelta(minutes=1))
        assert all(s.signal_type == SignalType.CODING_SESSION for s in results)
        ids = [s.signal_id for s in results]
        assert "sig-coding-456" in ids

    def test_query_outside_time_range_returns_empty(self):
        pid = self._setup("eng-q3", "emp-q3")
        sig = _make_signal(pseudonymous_id=pid, employer_id="emp-q3")
        append_signal(sig)

        future = datetime.now(timezone.utc) + timedelta(hours=1)
        results = query_signals(pid, None, future, future + timedelta(hours=1))
        assert results == []

    def test_appended_signal_increments_count(self):
        pid = self._setup("eng-q4", "emp-q4")
        before = get_signal_count("emp-q4")
        sig = _make_signal(pseudonymous_id=pid, employer_id="emp-q4")
        append_signal(sig)
        assert get_signal_count("emp-q4") == before + 1


# ---------------------------------------------------------------------------
# revoke_signals
# ---------------------------------------------------------------------------

class TestRevokeSignals:
    def _setup(self, engineer_id: str = "eng-r1", employer_id: str = "emp-r1"):
        pid = compute_pseudonymous_id(engineer_id)
        _clear_signals((employer_id, pid))
        _clear_counts(employer_id)
        return pid

    def test_revoke_marks_signals(self):
        pid = self._setup()
        sig1 = _make_signal(pseudonymous_id=pid, employer_id="emp-r1")
        sig2 = _make_signal(pseudonymous_id=pid, employer_id="emp-r1")
        sig2.signal_id = "sig-r2"
        append_signal(sig1)
        append_signal(sig2)

        count = revoke_signals(pid)
        assert count == 2

        now = datetime.now(timezone.utc)
        results = query_signals(pid, None, now - timedelta(minutes=1), now + timedelta(minutes=1))
        assert all(s.revoked for s in results)

    def test_revoke_returns_count_of_revoked(self):
        pid = self._setup("eng-r2", "emp-r2")
        sig = _make_signal(pseudonymous_id=pid, employer_id="emp-r2")
        append_signal(sig)
        count = revoke_signals(pid)
        assert count == 1

    def test_revoke_idempotent_second_call_returns_zero(self):
        pid = self._setup("eng-r3", "emp-r3")
        sig = _make_signal(pseudonymous_id=pid, employer_id="emp-r3")
        append_signal(sig)
        revoke_signals(pid)
        count2 = revoke_signals(pid)
        assert count2 == 0

    def test_revoke_does_not_delete_signals(self):
        pid = self._setup("eng-r4", "emp-r4")
        before_count = get_signal_count("emp-r4")
        sig = _make_signal(pseudonymous_id=pid, employer_id="emp-r4")
        append_signal(sig)
        revoke_signals(pid)
        assert get_signal_count("emp-r4") == before_count + 1


# ---------------------------------------------------------------------------
# erase_pii_linkage
# ---------------------------------------------------------------------------

class TestErasePiiLinkage:
    def test_erase_removes_link(self):
        engineer_id = "eng-e1"
        _clear_pii_links(engineer_id)
        _clear_consent(engineer_id)
        _grant_full_consent(engineer_id)

        processor = Signal_Processor()
        processor.normalize_signal(
            engineer_id=engineer_id,
            signal_type=SignalType.COMMIT_METADATA,
            raw_payload={"repo": "api"},
            source_system="github",
            employer_id="emp-e1",
        )

        # Before erasure the link exists
        from app.signal_store import _load_pii_link
        assert _load_pii_link(engineer_id) is not None

        erase_pii_linkage(engineer_id)

        # After erasure the link is gone
        assert _load_pii_link(engineer_id) is None

    def test_erase_twice_is_safe(self):
        engineer_id = "eng-e2"
        _clear_pii_links(engineer_id)
        erase_pii_linkage(engineer_id)  # no-op on non-existent
        erase_pii_linkage(engineer_id)  # should not raise

    def test_signals_remain_after_erase(self):
        engineer_id = "eng-e3"
        employer_id = "emp-e3"
        pid = compute_pseudonymous_id(engineer_id)
        _clear_signals((employer_id, pid))
        _clear_counts(employer_id)
        _clear_pii_links(engineer_id)
        _clear_consent(engineer_id)
        _grant_full_consent(engineer_id)

        processor = Signal_Processor()
        processor.normalize_signal(
            engineer_id=engineer_id,
            signal_type=SignalType.COMMIT_METADATA,
            raw_payload={"repo": "api"},
            source_system="github",
            employer_id=employer_id,
        )
        count_before = get_signal_count(employer_id)
        assert count_before >= 1

        erase_pii_linkage(engineer_id)

        # Signal count unchanged — signals remain, just unattributable
        assert get_signal_count(employer_id) == count_before


# ---------------------------------------------------------------------------
# get_signal_count
# ---------------------------------------------------------------------------

class TestGetSignalCount:
    def test_count_per_employer(self):
        employer_id = "emp-cnt1"
        engineer_id = "eng-cnt1"
        pid = compute_pseudonymous_id(engineer_id)
        _clear_signals((employer_id, pid))
        _clear_counts(employer_id)

        before = get_signal_count(employer_id)
        sig = _make_signal(pseudonymous_id=pid, employer_id=employer_id)
        append_signal(sig)
        assert get_signal_count(employer_id) == before + 1

    def test_count_none_employer_returns_sum(self):
        emp_a = "emp-total-a"
        emp_b = "emp-total-b"
        pid_a = compute_pseudonymous_id("eng-total-a")
        pid_b = compute_pseudonymous_id("eng-total-b")
        _clear_signals((emp_a, pid_a), (emp_b, pid_b))
        _clear_counts(emp_a, emp_b)

        append_signal(_make_signal(pseudonymous_id=pid_a, employer_id=emp_a))
        append_signal(_make_signal(pseudonymous_id=pid_b, employer_id=emp_b))

        total = get_signal_count(None)
        assert total >= 2

    def test_unknown_employer_returns_zero(self):
        assert get_signal_count("emp-nonexistent-xyz") == 0


# ---------------------------------------------------------------------------
# Signal_Processor — consent check
# ---------------------------------------------------------------------------

class TestSignalProcessorConsentCheck:
    def setup_method(self):
        self.processor = Signal_Processor()

    def test_raises_consent_error_without_consent(self):
        engineer_id = "eng-p1"
        _clear_consent(engineer_id)
        with pytest.raises(ConsentError):
            self.processor.normalize_signal(
                engineer_id=engineer_id,
                signal_type=SignalType.COMMIT_METADATA,
                raw_payload={"repo": "api"},
                source_system="github",
                employer_id="emp-p1",
            )

    def test_raises_consent_error_after_revocation(self):
        engineer_id = "eng-p2"
        _clear_consent(engineer_id)
        grant_consent(engineer_id, [SignalType.COMMIT_METADATA])
        revoke_consent(engineer_id)
        with pytest.raises(ConsentError):
            self.processor.normalize_signal(
                engineer_id=engineer_id,
                signal_type=SignalType.COMMIT_METADATA,
                raw_payload={"repo": "api"},
                source_system="github",
                employer_id="emp-p2",
            )

    def test_raises_consent_error_for_unconsented_type(self):
        engineer_id = "eng-p3"
        _clear_consent(engineer_id)
        grant_consent(engineer_id, [SignalType.CODING_SESSION])
        with pytest.raises(ConsentError):
            self.processor.normalize_signal(
                engineer_id=engineer_id,
                signal_type=SignalType.COMMIT_METADATA,
                raw_payload={"repo": "api"},
                source_system="github",
                employer_id="emp-p3",
            )

    def test_succeeds_with_active_consent(self):
        engineer_id = "eng-p4"
        employer_id = "emp-p4"
        pid = compute_pseudonymous_id(engineer_id)
        _clear_consent(engineer_id)
        _clear_signals((employer_id, pid))
        _clear_counts(employer_id)
        grant_consent(engineer_id, [SignalType.COMMIT_METADATA])
        signal = self.processor.normalize_signal(
            engineer_id=engineer_id,
            signal_type=SignalType.COMMIT_METADATA,
            raw_payload={"repo": "api", "branch": "main"},
            source_system="github",
            employer_id=employer_id,
        )
        assert signal.pseudonymous_id == compute_pseudonymous_id(engineer_id)
        assert signal.employer_id == employer_id


# ---------------------------------------------------------------------------
# Signal_Processor — PII stripping via normalize_signal
# ---------------------------------------------------------------------------

class TestSignalProcessorPiiStripping:
    def setup_method(self):
        self.processor = Signal_Processor()

    def test_pii_fields_stripped_from_stored_signal(self):
        engineer_id = "eng-pii1"
        employer_id = "emp-pii1"
        pid = compute_pseudonymous_id(engineer_id)
        _clear_consent(engineer_id)
        _clear_signals((employer_id, pid))
        _clear_counts(employer_id)
        grant_consent(engineer_id, [SignalType.COMMIT_METADATA])

        raw = {
            "name": "Jane Doe",
            "email": "jane@example.com",
            "employee_id": "E-123",
            "repo": "acme/api",
        }
        signal = self.processor.normalize_signal(
            engineer_id=engineer_id,
            signal_type=SignalType.COMMIT_METADATA,
            raw_payload=raw,
            source_system="github",
            employer_id=employer_id,
        )
        assert "name" not in signal.payload
        assert "email" not in signal.payload
        assert "employee_id" not in signal.payload
        assert signal.payload.get("repo") == "acme/api"

    def test_engineer_id_not_in_payload_values(self):
        engineer_id = "eng-pii2"
        employer_id = "emp-pii2"
        pid = compute_pseudonymous_id(engineer_id)
        _clear_consent(engineer_id)
        _clear_signals((employer_id, pid))
        _clear_counts(employer_id)
        grant_consent(engineer_id, [SignalType.COMMIT_METADATA])

        raw = {"user": engineer_id, "repo": "acme/api"}
        signal = self.processor.normalize_signal(
            engineer_id=engineer_id,
            signal_type=SignalType.COMMIT_METADATA,
            raw_payload=raw,
            source_system="github",
            employer_id=employer_id,
        )
        assert "user" not in signal.payload
        assert signal.payload.get("repo") == "acme/api"

    def test_pseudonymous_id_is_hmac_of_engineer_id(self):
        engineer_id = "eng-pii3"
        employer_id = "emp-pii3"
        pid = compute_pseudonymous_id(engineer_id)
        _clear_consent(engineer_id)
        _clear_signals((employer_id, pid))
        _clear_counts(employer_id)
        grant_consent(engineer_id, [SignalType.COMMIT_METADATA])

        signal = self.processor.normalize_signal(
            engineer_id=engineer_id,
            signal_type=SignalType.COMMIT_METADATA,
            raw_payload={"repo": "api"},
            source_system="github",
            employer_id=employer_id,
        )
        assert signal.pseudonymous_id == compute_pseudonymous_id(engineer_id)
        assert signal.pseudonymous_id != engineer_id

    def test_signal_does_not_contain_engineer_id_in_any_field(self):
        engineer_id = "eng-pii4"
        employer_id = "emp-pii4"
        pid = compute_pseudonymous_id(engineer_id)
        _clear_consent(engineer_id)
        _clear_signals((employer_id, pid))
        _clear_counts(employer_id)
        grant_consent(engineer_id, [SignalType.COMMIT_METADATA])

        signal = self.processor.normalize_signal(
            engineer_id=engineer_id,
            signal_type=SignalType.COMMIT_METADATA,
            raw_payload={"repo": "api"},
            source_system="github",
            employer_id=employer_id,
        )
        # serialise and check the whole JSON blob for the raw engineer_id
        raw_json = _signal_to_json(signal)
        assert engineer_id not in raw_json
