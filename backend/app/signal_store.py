"""Signal storage — Signal dataclass, Signal_Processor, and Signal_Store.

Architecture
------------
- SignalType enum is defined in consent_store.py and re-exported here so callers
  only need to import from signal_store.
- Signal records are stored in a Valkey sorted set keyed by
  ``signals:{employer_id}:{pseudonymous_id}`` (score = Unix epoch float of
  collected_at) to support efficient time-range queries.
- A separate ``pii_link:{engineer_id}`` key stores the engineer_id →
  pseudonymous_id mapping so that erase_pii_linkage can sever the link
  without touching the anonymised signal records.
- Falls back to in-memory structures when Valkey is unavailable (local dev).

PII handling
------------
- ``Signal_Processor.normalize_signal`` strips the keys ``name``, ``email``, and
  ``employee_id`` from the raw payload, plus any *values* that equal the
  engineer's name, email, or employee_id (case-insensitive string comparison).
- The pseudonymous_id is HMAC-SHA256(engineer_id, platform_secret) — not
  reversible without the secret.

Consent
-------
- ``Signal_Processor.normalize_signal`` calls ``has_active_consent`` before
  appending. If consent is absent it raises ``ConsentError`` (subclass of
  ValueError, mapped to HTTP 403 in the routes layer).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional

from .config import get_settings
from .consent_store import SignalType, has_active_consent  # re-export SignalType

__all__ = [
    "Signal",
    "SignalType",
    "ConsentError",
    "Signal_Processor",
    "append_signal",
    "query_signals",
    "revoke_signals",
    "erase_pii_linkage",
    "get_signal_count",
]

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ConsentError(ValueError):
    """Raised when a Signal cannot be stored because the engineer has not
    provided (or has revoked) consent for the given signal type."""


# ---------------------------------------------------------------------------
# Signal dataclass
# ---------------------------------------------------------------------------


@dataclass
class Signal:
    signal_id: str           # uuid4
    pseudonymous_id: str     # HMAC-SHA256(engineer_id, secret) — not reversible
    signal_type: SignalType
    payload: dict            # anonymised, schema-validated
    source_system: str       # e.g. "github", "platform_interview"
    collected_at: str        # ISO-8601 UTC
    consent_version: str     # consent version at collection time
    employer_id: str         # tenant isolation
    revoked: bool = False    # set to True by revoke_signals


# ---------------------------------------------------------------------------
# In-memory fallback store
# ---------------------------------------------------------------------------

# signals keyed as: _memory_signals[(employer_id, pseudonymous_id)] = list[Signal]
_memory_signals: dict[tuple[str, str], list[Signal]] = {}

# pii_link: engineer_id → pseudonymous_id
_memory_pii_links: dict[str, str] = {}

# per-employer signal counters: employer_id → count
_memory_signal_counts: dict[str, int] = {}


# ---------------------------------------------------------------------------
# Valkey helper
# ---------------------------------------------------------------------------

def _valkey():
    settings = get_settings()
    if not settings.valkey_url:
        return None
    import valkey  # type: ignore
    return valkey.from_url(settings.valkey_url, decode_responses=True)


# ---------------------------------------------------------------------------
# Key helpers
# ---------------------------------------------------------------------------

def _signal_set_key(employer_id: str, pseudonymous_id: str) -> str:
    return f"signals:{employer_id}:{pseudonymous_id}"


def _pii_link_key(engineer_id: str) -> str:
    return f"pii_link:{engineer_id}"


def _signal_count_key(employer_id: str) -> str:
    return f"signal_count:{employer_id}"


# ---------------------------------------------------------------------------
# Pseudonymisation helper
# ---------------------------------------------------------------------------

def compute_pseudonymous_id(engineer_id: str) -> str:
    """Return HMAC-SHA256(engineer_id, secret_key) as a hex digest."""
    settings = get_settings()
    key = settings.secret_key.encode()
    return hmac.new(key, engineer_id.encode(), hashlib.sha256).hexdigest()


# ---------------------------------------------------------------------------
# Signal_Processor
# ---------------------------------------------------------------------------

_PII_KEYS = frozenset({"name", "email", "employee_id"})


class Signal_Processor:
    """Transforms raw integration events into anonymised Signal records."""

    def normalize_signal(
        self,
        engineer_id: str,
        signal_type: SignalType,
        raw_payload: dict,
        source_system: str,
        employer_id: str,
        consent_version: str = "1.0",
    ) -> Signal:
        """Normalise a raw event into a Signal and write it to the store.

        Steps
        -----
        1. Check consent — raises ConsentError if absent.
        2. Compute pseudonymous_id via HMAC.
        3. Strip PII from the payload.
        4. Build and append the Signal.

        Returns the appended Signal.
        """
        # 1 — consent check
        if not has_active_consent(engineer_id, signal_type):
            raise ConsentError(
                f"Engineer '{engineer_id}' has no active consent for signal type "
                f"'{signal_type.value}'. Signal rejected."
            )

        # 2 — pseudonymise
        pseudonymous_id = compute_pseudonymous_id(engineer_id)

        # 3 — strip PII from payload
        clean_payload = _strip_pii(raw_payload, engineer_id)

        # 4 — persist PII link so erase_pii_linkage can later sever it
        _store_pii_link(engineer_id, pseudonymous_id)

        # 5 — build and append Signal
        signal = Signal(
            signal_id=str(uuid.uuid4()),
            pseudonymous_id=pseudonymous_id,
            signal_type=signal_type,
            payload=clean_payload,
            source_system=source_system,
            collected_at=datetime.now(timezone.utc).isoformat(),
            consent_version=consent_version,
            employer_id=employer_id,
        )
        append_signal(signal)
        return signal


def _strip_pii(payload: dict, engineer_id: str) -> dict:
    """Return a copy of payload with PII keys and PII values removed.

    Removes:
    - Keys: ``name``, ``email``, ``employee_id``
    - Any string value that equals (case-insensitive) the engineer's:
      - raw engineer_id
      - value stored under removed PII keys

    Only top-level keys are inspected (deep-nested PII is out of scope for
    this iteration, following the spec's payload schema validation approach).
    """
    # Collect the PII literals we want to strip from values
    pii_literals: set[str] = {engineer_id.lower()}
    for key in _PII_KEYS:
        val = payload.get(key)
        if isinstance(val, str) and val:
            pii_literals.add(val.lower())

    clean: dict = {}
    for k, v in payload.items():
        if k in _PII_KEYS:
            continue
        if isinstance(v, str) and v.lower() in pii_literals:
            continue
        clean[k] = v
    return clean


# ---------------------------------------------------------------------------
# PII link store helpers
# ---------------------------------------------------------------------------

def _store_pii_link(engineer_id: str, pseudonymous_id: str) -> None:
    """Persist the engineer_id → pseudonymous_id mapping."""
    client = _valkey()
    key = _pii_link_key(engineer_id)
    if client:
        client.set(key, pseudonymous_id)
    else:
        _memory_pii_links[key] = pseudonymous_id


def _load_pii_link(engineer_id: str) -> str | None:
    """Return the stored pseudonymous_id for an engineer, or None."""
    client = _valkey()
    key = _pii_link_key(engineer_id)
    if client:
        return client.get(key)
    return _memory_pii_links.get(key)


# ---------------------------------------------------------------------------
# Signal serialisation helpers
# ---------------------------------------------------------------------------

def _signal_to_json(signal: Signal) -> str:
    d = asdict(signal)
    d["signal_type"] = signal.signal_type.value  # store as plain string
    return json.dumps(d)


def _signal_from_json(raw: str) -> Signal:
    d = json.loads(raw)
    d["signal_type"] = SignalType(d["signal_type"])
    return Signal(**d)


def _collected_at_to_score(collected_at: str) -> float:
    """Convert ISO-8601 string to a Unix timestamp float for use as Valkey score."""
    dt = datetime.fromisoformat(collected_at)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


# ---------------------------------------------------------------------------
# Signal_Store public API
# ---------------------------------------------------------------------------

def append_signal(signal: Signal) -> None:
    """Append an immutable Signal to the store.

    Requirements 1.3, 1.4: records are append-only and cannot be modified
    except via the explicit erasure paths.
    """
    client = _valkey()
    if client:
        key = _signal_set_key(signal.employer_id, signal.pseudonymous_id)
        score = _collected_at_to_score(signal.collected_at)
        client.zadd(key, {_signal_to_json(signal): score})
        # increment employer counter
        count_key = _signal_count_key(signal.employer_id)
        client.incr(count_key)
    else:
        mem_key = (signal.employer_id, signal.pseudonymous_id)
        _memory_signals.setdefault(mem_key, []).append(signal)
        _memory_signal_counts[signal.employer_id] = (
            _memory_signal_counts.get(signal.employer_id, 0) + 1
        )


def query_signals(
    pseudonymous_id: str,
    signal_type: Optional[SignalType],
    since: datetime,
    until: datetime,
) -> list[Signal]:
    """Return Signals for a pseudonymous_id within [since, until].

    Parameters
    ----------
    pseudonymous_id:
        The HMAC pseudonymous identifier for the engineer.
    signal_type:
        If provided, filter results to this type only.
    since:
        Inclusive lower bound (UTC datetime).
    until:
        Inclusive upper bound (UTC datetime).
    """
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
    if until.tzinfo is None:
        until = until.replace(tzinfo=timezone.utc)

    client = _valkey()
    results: list[Signal] = []

    if client:
        # Scan all employer partitions — we know only the pseudonymous_id
        pattern = f"signals:*:{pseudonymous_id}"
        keys = list(client.scan_iter(pattern))
        for key in keys:
            raws = client.zrangebyscore(key, since.timestamp(), until.timestamp())
            for raw in raws:
                try:
                    sig = _signal_from_json(raw)
                    results.append(sig)
                except Exception:
                    pass
    else:
        for (emp_id, pid), signals in _memory_signals.items():
            if pid != pseudonymous_id:
                continue
            for sig in signals:
                collected = datetime.fromisoformat(sig.collected_at)
                if collected.tzinfo is None:
                    collected = collected.replace(tzinfo=timezone.utc)
                if since <= collected <= until:
                    results.append(sig)

    if signal_type is not None:
        results = [s for s in results if s.signal_type == signal_type]

    return results


def revoke_signals(pseudonymous_id: str) -> int:
    """Mark all Signals for a pseudonymous_id as revoked.

    Returns the count of signals marked.

    Requirement 1.2: after consent revocation the existing signals are marked
    revoked (not deleted — they remain for aggregate training as anonymised data).
    """
    client = _valkey()
    count = 0

    if client:
        pattern = f"signals:*:{pseudonymous_id}"
        keys = list(client.scan_iter(pattern))
        for key in keys:
            # Fetch all members with their scores
            members_with_scores = client.zrange(key, 0, -1, withscores=True)
            for raw, score in members_with_scores:
                try:
                    sig = _signal_from_json(raw)
                    if not sig.revoked:
                        # Remove old entry, re-add with revoked=True
                        client.zrem(key, raw)
                        sig.revoked = True
                        client.zadd(key, {_signal_to_json(sig): score})
                        count += 1
                except Exception:
                    pass
    else:
        for (emp_id, pid), signals in _memory_signals.items():
            if pid != pseudonymous_id:
                continue
            for sig in signals:
                if not sig.revoked:
                    sig.revoked = True
                    count += 1

    return count


def erase_pii_linkage(engineer_id: str) -> None:
    """Delete the engineer_id → pseudonymous_id mapping.

    After this call the engineer can no longer be linked to their signals
    (the pseudonymous signal records remain intact for aggregate model
    training, satisfying Requirement 10.3).
    """
    client = _valkey()
    key = _pii_link_key(engineer_id)
    if client:
        client.delete(key)
    else:
        _memory_pii_links.pop(key, None)


def get_signal_count(employer_id: Optional[str] = None) -> int:
    """Return the total number of signals, optionally scoped to an employer.

    Parameters
    ----------
    employer_id:
        If provided, return the count for that employer only.
        If None, return the platform-wide total.
    """
    client = _valkey()
    if client:
        if employer_id is not None:
            raw = client.get(_signal_count_key(employer_id))
            return int(raw) if raw else 0
        else:
            # Sum all employer counters
            keys = list(client.scan_iter("signal_count:*"))
            total = 0
            for k in keys:
                raw = client.get(k)
                if raw:
                    total += int(raw)
            return total
    else:
        if employer_id is not None:
            return _memory_signal_counts.get(employer_id, 0)
        return sum(_memory_signal_counts.values())
