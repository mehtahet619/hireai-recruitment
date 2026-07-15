"""Example-based tests for Integration Connector normalize_event.

Tests use fixture payloads matching real event shapes from each source system.

Validates: Requirements 9.1, 9.3
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone

import pytest

from app.integrations.base import IntegrationConnector, RawEvent
from app.integrations.github_connector import GitHubConnector
from app.integrations.jira_connector import JiraConnector
from app.integrations.slack_connector import SlackConnector
from app.integrations.hris_connector import HRISWebhookConnector


def _connector(connector_type: str) -> IntegrationConnector:
    return IntegrationConnector(
        connector_id=str(uuid.uuid4()),
        employer_id="emp-1",
        connector_type=connector_type,
        config={"token": "test"},
        status="active",
    )


NOW = datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# GitHub push event
# ---------------------------------------------------------------------------

GITHUB_PUSH_PAYLOAD = {
    "ref": "refs/heads/main",
    "repository": {"full_name": "acme/backend"},
    "sender": {"login": "dev123"},
    "commits": [{"id": "abc"}, {"id": "def"}],
}


def test_github_push_normalizes_to_commit_metadata():
    conn = GitHubConnector(_connector("github"))
    event = RawEvent(
        event_id=str(uuid.uuid4()), source_system="github",
        event_type="push", payload=GITHUB_PUSH_PAYLOAD, occurred_at=NOW,
    )
    result = conn.normalize_event(event)
    assert result is not None
    assert result["signal_type"] == "commit_metadata"
    assert result["source_system"] == "github"
    assert result["payload"]["repo"] == "acme/backend"
    assert result["payload"]["commits"] == 2


def test_github_unknown_event_returns_none():
    conn = GitHubConnector(_connector("github"))
    event = RawEvent(
        event_id=str(uuid.uuid4()), source_system="github",
        event_type="unknown_event", payload={}, occurred_at=NOW,
    )
    assert conn.normalize_event(event) is None


def test_github_validate_credentials_requires_token():
    conn = GitHubConnector(_connector("github"))
    assert conn.validate_credentials({"token": "ghp_abc"}) is True
    assert conn.validate_credentials({}) is False


# ---------------------------------------------------------------------------
# Jira issue resolved event
# ---------------------------------------------------------------------------

JIRA_RESOLVED_PAYLOAD = {
    "issue": {
        "key": "ENG-42",
        "fields": {"status": {"name": "Done"}},
    },
    "user": {"accountId": "user-xyz"},
    "resolution_time_hours": 8,
}


def test_jira_resolved_normalizes_to_collaboration_frequency():
    conn = JiraConnector(_connector("jira"))
    event = RawEvent(
        event_id=str(uuid.uuid4()), source_system="jira",
        event_type="issue_resolved", payload=JIRA_RESOLVED_PAYLOAD, occurred_at=NOW,
    )
    result = conn.normalize_event(event)
    assert result is not None
    assert result["signal_type"] == "collaboration_frequency"
    assert result["payload"]["issue_key"] == "ENG-42"
    assert result["payload"]["resolution_time_hours"] == 8


def test_jira_unrecognised_event_returns_none():
    conn = JiraConnector(_connector("jira"))
    event = RawEvent(
        event_id=str(uuid.uuid4()), source_system="jira",
        event_type="sprint_started", payload={}, occurred_at=NOW,
    )
    assert conn.normalize_event(event) is None


# ---------------------------------------------------------------------------
# Slack channel message event
# ---------------------------------------------------------------------------

SLACK_MESSAGE_PAYLOAD = {
    "channel": "C012AB3CD",
    "user": "U056DEF",
    "message_count": 3,
    "reply_count": 1,
}


def test_slack_message_normalizes_to_collaboration_frequency():
    conn = SlackConnector(_connector("slack"))
    event = RawEvent(
        event_id=str(uuid.uuid4()), source_system="slack",
        event_type="message", payload=SLACK_MESSAGE_PAYLOAD, occurred_at=NOW,
    )
    result = conn.normalize_event(event)
    assert result is not None
    assert result["signal_type"] == "collaboration_frequency"
    assert result["payload"]["channel"] == "C012AB3CD"
    assert result["payload"]["message_count"] == 3


def test_slack_non_message_event_returns_none():
    conn = SlackConnector(_connector("slack"))
    event = RawEvent(
        event_id=str(uuid.uuid4()), source_system="slack",
        event_type="reaction_added", payload={}, occurred_at=NOW,
    )
    assert conn.normalize_event(event) is None


# ---------------------------------------------------------------------------
# HRIS webhook payload
# ---------------------------------------------------------------------------

HRIS_HIRED_PAYLOAD = {
    "employee_id": "emp-789",
    "job_title": "Senior Engineer",
    "department": "Engineering",
    "location": "Remote",
}


def test_hris_hired_normalizes_to_onboarding_completion():
    conn = HRISWebhookConnector(_connector("hris_webhook"))
    event = RawEvent(
        event_id=str(uuid.uuid4()), source_system="hris_webhook",
        event_type="employee_hired", payload=HRIS_HIRED_PAYLOAD, occurred_at=NOW,
    )
    result = conn.normalize_event(event)
    assert result is not None
    assert result["signal_type"] == "onboarding_task_completion"
    assert result["payload"]["role"] == "Senior Engineer"
    assert result["payload"]["event_type"] == "employee_hired"


def test_hris_unknown_event_returns_none():
    conn = HRISWebhookConnector(_connector("hris_webhook"))
    event = RawEvent(
        event_id=str(uuid.uuid4()), source_system="hris_webhook",
        event_type="payroll_updated", payload={}, occurred_at=NOW,
    )
    assert conn.normalize_event(event) is None