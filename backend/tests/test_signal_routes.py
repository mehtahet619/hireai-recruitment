"""Test signal management routes."""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.consent_store import grant_consent, SignalType


client = TestClient(app)


def test_signal_ingest_without_consent():
    """Test that signal ingest returns 403 when engineer has no consent."""
    response = client.post(
        "/api/signals/ingest",
        json={
            "engineer_id": "engineer_noconsent@example.com",
            "signal_type": "interview_transcript_embedding",
            "payload": {"source": "test", "data": "value"},
            "source_system": "test_system",
            "employer_id": "emp_test",
        }
    )
    assert response.status_code == 403
    assert "consent" in response.json()["detail"].lower()


def test_signal_ingest_with_consent():
    """Test that signal ingest succeeds when engineer has consent."""
    engineer_id = "engineer_consent@example.com"
    
    # Grant consent
    grant_consent(engineer_id, [SignalType.INTERVIEW_TRANSCRIPT_EMBEDDING])
    
    # Ingest signal
    response = client.post(
        "/api/signals/ingest",
        json={
            "engineer_id": engineer_id,
            "signal_type": "interview_transcript_embedding",
            "payload": {
                "source": "platform_interview",
                "session_id": "test_session_123",
            },
            "source_system": "test_system",
            "employer_id": "emp_test",
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["signal_id"]
    assert data["pseudonymous_id"]
    assert data["signal_type"] == "interview_transcript_embedding"
    assert data["source_system"] == "test_system"
    assert data["employer_id"] == "emp_test"
    assert data["revoked"] is False


def test_signal_ingest_invalid_signal_type():
    """Test that signal ingest returns 400 for invalid signal type."""
    engineer_id = "engineer_invalid@example.com"
    grant_consent(engineer_id, [SignalType.INTERVIEW_TRANSCRIPT_EMBEDDING])
    
    response = client.post(
        "/api/signals/ingest",
        json={
            "engineer_id": engineer_id,
            "signal_type": "invalid_signal_type",
            "payload": {"test": "data"},
            "source_system": "test_system",
            "employer_id": "emp_test",
        }
    )
    assert response.status_code == 400
    assert "invalid" in response.json()["detail"].lower()


def test_signals_me_retrieves_own_signals():
    """Test that engineer can retrieve their own signals."""
    engineer_id = "engineer_retrieve@example.com"
    
    # Grant consent
    grant_consent(engineer_id, [SignalType.CODING_SESSION, SignalType.COMMIT_METADATA])
    
    # Ingest a few signals
    for i in range(3):
        client.post(
            "/api/signals/ingest",
            json={
                "engineer_id": engineer_id,
                "signal_type": "coding_session",
                "payload": {"session_number": i},
                "source_system": "ide",
                "employer_id": "emp_test",
            }
        )
    
    # Retrieve signals
    response = client.get(f"/api/signals/me?engineer_id={engineer_id}")
    assert response.status_code == 200
    signals = response.json()
    assert len(signals) == 3
    assert all(s["signal_type"] == "coding_session" for s in signals)


def test_signals_me_filters_by_signal_type():
    """Test that engineer can filter signals by type."""
    engineer_id = "engineer_filter@example.com"
    
    # Grant consent
    grant_consent(engineer_id, [SignalType.CODING_SESSION, SignalType.COMMIT_METADATA])
    
    # Ingest different signal types
    client.post(
        "/api/signals/ingest",
        json={
            "engineer_id": engineer_id,
            "signal_type": "coding_session",
            "payload": {"data": "session"},
            "source_system": "ide",
            "employer_id": "emp_test",
        }
    )
    client.post(
        "/api/signals/ingest",
        json={
            "engineer_id": engineer_id,
            "signal_type": "commit_metadata",
            "payload": {"data": "commit"},
            "source_system": "github",
            "employer_id": "emp_test",
        }
    )
    
    # Retrieve only coding_session signals
    response = client.get(
        f"/api/signals/me?engineer_id={engineer_id}&signal_type=coding_session"
    )
    assert response.status_code == 200
    signals = response.json()
    assert len(signals) == 1
    assert signals[0]["signal_type"] == "coding_session"


def test_signals_me_invalid_signal_type_filter():
    """Test that filtering by invalid signal type returns 400."""
    response = client.get(
        "/api/signals/me?engineer_id=test@example.com&signal_type=invalid_type"
    )
    assert response.status_code == 400
    assert "invalid" in response.json()["detail"].lower()
