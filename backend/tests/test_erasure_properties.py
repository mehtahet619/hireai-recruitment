"""Property-based test for data erasure (Task 11.2).

Property: Data erasure leaves no recoverable PII linkage.

For any engineer_id, after erase_pii_linkage:
  1. The engineer_id -> pseudonymous_id mapping is severed (not recoverable)
  2. Total signal count in the store is unchanged (signals remain anonymised)

Validates: Requirements 10.2, 10.3
# Feature: engineering-lifecycle-platform, Property: Data erasure leaves no recoverable PII linkage
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone, timedelta
from hypothesis import given, settings
from hypothesis import strategies as st

from app.signal_store import (
    Signal_Processor, SignalType,
    _memory_signals, _memory_pii_links, _memory_signal_counts,
    erase_pii_linkage, _pii_link_key, _store_pii_link,
    compute_pseudonymous_id, get_signal_count,
)
from app.consent_store import grant_consent
from app.consent_store import _memory_consent as _consent_store


def _clear_all():
    _memory_signals.clear()
    _memory_pii_links.clear()
    _memory_signal_counts.clear()
    _consent_store.clear()


@given(
    engineer_id=st.emails(),
    n_signals=st.integers(min_value=1, max_value=5),
)
@settings(max_examples=100)
def test_erasure_severs_pii_linkage(engineer_id: str, n_signals: int):
    """After erase_pii_linkage:
    1. The pii_link mapping for engineer_id is gone (no recoverable link)
    2. Total signal count is unchanged (signals remain anonymised)

    Validates: Requirements 10.2, 10.3
    """
    _clear_all()

    grant_consent(engineer_id, list(SignalType))
    processor = Signal_Processor()
    employer_id = str(uuid.uuid4())

    for i in range(n_signals):
        processor.normalize_signal(
            engineer_id=engineer_id,
            signal_type=SignalType.COMMIT_METADATA,
            raw_payload={"repo": f"repo-{i}", "commits": i + 1},
            source_system="github",
            employer_id=employer_id,
            consent_version="1.0",
        )

    # PII link should exist before erasure
    link_key = _pii_link_key(engineer_id)
    assert link_key in _memory_pii_links, "PII link should exist before erasure"

    total_before = get_signal_count(None)
    assert total_before == n_signals

    # Erase the PII linkage
    erase_pii_linkage(engineer_id)

    # After erasure: the pii_link entry must be gone
    assert link_key not in _memory_pii_links, (
        "PII link still present after erasure — engineer can be re-identified"
    )

    # Total signal count must be unchanged
    total_after = get_signal_count(None)
    assert total_after == total_before, (
        f"Signal count changed: {total_before} -> {total_after}"
    )