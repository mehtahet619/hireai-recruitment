"""HRIS Webhook Connector."""
from __future__ import annotations
from datetime import datetime
from .base import BaseConnector, RawEvent


class HRISWebhookConnector(BaseConnector):
    def validate_credentials(self, config: dict) -> bool:
        return bool(config.get("webhook_secret"))

    def pull_events(self, since: datetime) -> list[RawEvent]:
        return []

    def normalize_event(self, event: RawEvent):
        from ..signal_store import SignalType
        if event.event_type not in ("employee_hired", "employee_updated", "employee_terminated"):
            return None
        payload = event.payload
        return {
            "signal_type": SignalType.ONBOARDING_TASK_COMPLETION.value,
            "source_system": "hris_webhook",
            "payload": {
                "event_type": event.event_type,
                "department": payload.get("department", ""),
                "role": payload.get("job_title", ""),
                "location": payload.get("location", ""),
            },
            "engineer_ref": payload.get("employee_id", ""),
            "employer_id": self.connector.employer_id,
            "occurred_at": event.occurred_at,
        }