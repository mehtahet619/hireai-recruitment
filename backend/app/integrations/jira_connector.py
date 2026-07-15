"""Jira Integration Connector."""
from __future__ import annotations
from datetime import datetime
from .base import BaseConnector, RawEvent


class JiraConnector(BaseConnector):
    def validate_credentials(self, config: dict) -> bool:
        return bool(config.get("api_token") and config.get("base_url"))

    def pull_events(self, since: datetime) -> list[RawEvent]:
        return []

    def normalize_event(self, event: RawEvent):
        from ..signal_store import SignalType
        if event.event_type not in ("issue_resolved", "issue_updated"):
            return None
        payload = event.payload
        issue = payload.get("issue", {})
        return {
            "signal_type": SignalType.COLLABORATION_FREQUENCY.value,
            "source_system": "jira",
            "payload": {
                "issue_key": issue.get("key", ""),
                "status": issue.get("fields", {}).get("status", {}).get("name", ""),
                "resolution_time_hours": payload.get("resolution_time_hours", 0),
            },
            "engineer_ref": payload.get("user", {}).get("accountId", ""),
            "employer_id": self.connector.employer_id,
            "occurred_at": event.occurred_at,
        }