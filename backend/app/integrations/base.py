"""Integration Connector framework — base classes and shared types."""
from __future__ import annotations
import json, uuid, time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional
from ..config import get_settings

_memory_store: dict = {}
CONNECTOR_TTL = 60 * 60 * 24 * 365 * 2

def _valkey():
    s = get_settings()
    if not s.valkey_url: return None
    import valkey
    return valkey.from_url(s.valkey_url, decode_responses=True)

def _store_get(key):
    c = _valkey()
    return c.get(key) if c else _memory_store.get(key)

def _store_set(key, value):
    c = _valkey()
    if c: c.setex(key, CONNECTOR_TTL, value)
    else: _memory_store[key] = value

def _store_get_list(key):
    raw = _store_get(key)
    return json.loads(raw) if raw else []

def _store_append_list(key, item):
    lst = _store_get_list(key)
    if item not in lst: lst.append(item)
    _store_set(key, json.dumps(lst))


@dataclass
class RawEvent:
    event_id: str
    source_system: str
    event_type: str
    payload: dict
    occurred_at: str


@dataclass
class IntegrationConnector:
    connector_id: str
    employer_id: str
    connector_type: str  # github | jira | slack | hris_webhook
    config: dict         # credentials and settings (stored encrypted ideally)
    status: str          # active | degraded | disabled
    last_sync_at: Optional[str] = None
    error_count: int = 0
    consecutive_failures: int = 0
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()


class BaseConnector(ABC):
    def __init__(self, connector: IntegrationConnector):
        self.connector = connector

    @abstractmethod
    def validate_credentials(self, config: dict) -> bool: ...

    @abstractmethod
    def pull_events(self, since: datetime) -> list[RawEvent]: ...

    @abstractmethod
    def normalize_event(self, event: RawEvent): ...  # returns Signal | None

    def pull_with_retry(self, since: datetime) -> list[RawEvent]:
        """Pull events with 3 attempts and exponential back-off."""
        last_exc = None
        for attempt in range(3):
            try:
                events = self.pull_events(since)
                self.connector.consecutive_failures = 0
                self.connector.last_sync_at = datetime.now(timezone.utc).isoformat()
                save_connector(self.connector)
                return events
            except Exception as exc:
                last_exc = exc
                self.connector.consecutive_failures += 1
                self.connector.error_count += 1
                if self.connector.consecutive_failures >= 3:
                    self.connector.status = "degraded"
                save_connector(self.connector)
                if attempt < 2:
                    time.sleep(2 ** attempt)
        raise last_exc


def save_connector(c: IntegrationConnector) -> None:
    _store_set(f"connector:{c.connector_id}", json.dumps(asdict(c)))
    _store_append_list(f"employer_connectors:{c.employer_id}", c.connector_id)

def get_connector(connector_id: str) -> IntegrationConnector | None:
    raw = _store_get(f"connector:{connector_id}")
    return IntegrationConnector(**json.loads(raw)) if raw else None

def list_employer_connectors(employer_id: str) -> list[IntegrationConnector]:
    return [c for cid in _store_get_list(f"employer_connectors:{employer_id}")
            if (c := get_connector(cid))]