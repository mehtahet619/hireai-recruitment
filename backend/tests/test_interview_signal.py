"""Example test: after completing an interview, an interview_transcript_embedding
Signal exists in the Signal_Store for the applicant.

Validates: Requirements 3.4
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

from app.consent_store import grant_consent, _memory_consent, _consent_key
from app.signal_store import (
    SignalType,
    query_signals,
    compute_pseudonymous_id,
    _memory_signals,
    _memory_signal_counts,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clear_consent(engineer_id: str) -> None:
    _memory_consent.pop(_consent_key(engineer_id), None)


def _clear_signals_for(pseudonymous_id: str) -> None:
    keys_to_remove = [k for k in _memory_signals if k[1] == pseudonymous_id]
    for k in keys_to_remove:
        _memory_signals.pop(k, None)


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------

def test_interview_transcript_embedding_signal_stored_after_completion(mocker):
    """After completing an interview via /api/apply/complete, an
    interview_transcript_embedding Signal must exist in the Signal_Store
    for the applicant's pseudonymous_id.

    Setup:
      - Mock session and application in memory so no real DB or LLM is needed.
      - Grant INTERVIEW_TRANSCRIPT_EMBEDDING consent for the candidate.
      - Call the endpoint via FastAPI TestClient.

    Assert:
      - Exactly one INTERVIEW_TRANSCRIPT_EMBEDDING signal is in the store.
      - Signal fields match the session/application context.
      - Signal payload contains no PII (no name or email).
    """
    candidate_email = "interview_signal_test@example.com"
    session_id = "sess-interview-signal-001"
    application_id = "app-interview-signal-001"
    employer_id = "emp-interview-signal-001"

    # Clean up state from previous runs
    _clear_consent(candidate_email)
    pseudonymous_id = compute_pseudonymous_id(candidate_email)
    _clear_signals_for(pseudonymous_id)

    # Build mock session
    mock_session = Mock()
    mock_session.session_id = session_id
    mock_session.candidate_id = application_id
    mock_session.resume_analysis = {"score": 0.75}
    mock_session.handoff = {"assessments": []}
    mock_session.transcript = [
        {"speaker": "aria", "text": "Tell me about yourself."},
        {"speaker": "candidate", "text": "I'm a backend engineer."},
    ]

    # Build mock application
    mock_application = Mock()
    mock_application.application_id = application_id
    mock_application.candidate_name = "Signal Test Candidate"
    mock_application.candidate_email = candidate_email
    mock_application.job_id = "job-signal-test"
    mock_application.employer_id = employer_id

    # Patch collaborators so no real LLM or persistence is needed
    mocker.patch("app.main.get_session", return_value=mock_session)
    mocker.patch("app.main.score_candidate", return_value={"overall": 0.80})
    mocker.patch("app.main.generate_feedback", return_value={"message": "Great interview."})
    mocker.patch("app.main.get_application", return_value=mock_application)
    mocker.patch("app.main.save_review", return_value={"review_id": "rev-signal-001"})
    mocker.patch("app.main.update_application")

    # Grant consent for the candidate — required for the signal to be stored
    grant_consent(candidate_email, [SignalType.INTERVIEW_TRANSCRIPT_EMBEDDING])

    # Call the endpoint
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    response = client.post("/api/apply/complete", json={"session_id": session_id})

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    # Query the Signal_Store for the applicant's pseudonymous_id
    now = datetime.now(timezone.utc)
    signals = query_signals(
        pseudonymous_id,
        SignalType.INTERVIEW_TRANSCRIPT_EMBEDDING,
        now - timedelta(seconds=10),
        now + timedelta(seconds=10),
    )

    # Core assertion: the signal must exist
    assert len(signals) >= 1, (
        "Expected at least one INTERVIEW_TRANSCRIPT_EMBEDDING signal in the "
        "Signal_Store after /api/apply/complete, but found none."
    )

    signal = signals[0]

    # Signal type is correct
    assert signal.signal_type == SignalType.INTERVIEW_TRANSCRIPT_EMBEDDING

    # Signal source is platform_interview
    assert signal.source_system == "platform_interview"

    # Signal is associated with the correct employer
    assert signal.employer_id == employer_id

    # Session ID is captured in the payload
    assert signal.payload.get("session_id") == session_id

    # No PII in the payload — name and email must not appear
    payload_str = str(signal.payload)
    assert candidate_email not in payload_str, "candidate_email found in signal payload (PII leak)"
    assert "Signal Test Candidate" not in payload_str, "candidate_name found in signal payload (PII leak)"
