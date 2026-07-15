"""GitHub Integration Connector."""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from .base import BaseConnector, RawEvent


class GitHubConnector(BaseConnector):
    """Ingests GitHub push/PR/review events and normalises to Signals."""

    def validate_credentials(self, config: dict) -> bool:
        return bool(config.get("token"))

    def pull_events(self, since: datetime) -> list[RawEvent]:
        # In production: call GitHub API with token from self.connector.config
        return []

    def normalize_event(self, event: RawEvent):
        from ..signal_store import Signal, SignalType
        mapping = {
            "push": SignalType.COMMIT_METADATA,
            "pull_request": SignalType.PR_REVIEW_QUALITY,
            "pull_request_review": SignalType.PR_REVIEW_QUALITY,
        }
        signal_type = mapping.get(event.event_type)
        if not signal_type:
            return None
        payload = event.payload
        return {
            "signal_type": signal_type.value,
            "source_system": "github",
            "payload": {
                "repo": payload.get("repository", {}).get("full_name", ""),
                "ref": payload.get("ref", ""),
                "commits": len(payload.get("commits", [])),
                "action": payload.get("action", ""),
            },
            "engineer_ref": payload.get("sender", {}).get("login", ""),
            "employer_id": self.connector.employer_id,
            "occurred_at": event.occurred_at,
        }