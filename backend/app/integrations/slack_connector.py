"""Slack Integration Connector."""
from __future__ import annotations
from datetime import datetime
from .base import BaseConnector, RawEvent


class SlackConnector(BaseConnector):
    def validate_credentials(self, config: dict) -> bool:
        return bool(config.get("bot_token"))

    def pull_events(self, since: datetime) -> list[RawEvent]:
        return []

    def normalize_event(self, event: RawEvent):
        from ..signal_store import SignalType
        if event.event_type != "message":
            return None
        payload = event.payload
        return {
            "signal_type": SignalType.COLLABORATION_FREQUENCY.value,
            "source_system": "slack",
            "payload": {
                "channel": payload.get("channel", ""),
                "message_count": payload.get("message_count", 1),
                "thread_replies": payload.get("reply_count", 0),
            },
            "engineer_ref": payload.get("user", ""),
            "employer_id": self.connector.employer_id,
            "occurred_at": event.occurred_at,
        }