"""Test that /api/apply/complete emits interview_transcript_embedding signal."""
import pytest
from unittest.mock import Mock, patch
from app.consent_store import grant_consent, SignalType
from app.signal_store import query_signals, compute_pseudonymous_id
from datetime import datetime, timedelta, timezone


def test_apply_complete_emits_signal_with_consent(mocker):
    """Test that completing an interview emits a signal when applicant has consent."""
    # Mock the dependencies
    mock_session = Mock()
    mock_session.session_id = "test_session_123"
    mock_session.candidate_id = "app_456"
    mock_session.resume_analysis = {"score": 0.8}
    mock_session.handoff = {"assessments": []}
    mock_session.transcript = []
    
    mock_application = Mock()
    mock_application.application_id = "app_456"
    mock_application.candidate_name = "Test Candidate"
    mock_application.candidate_email = "test@example.com"
    mock_application.job_id = "job_789"
    mock_application.employer_id = "emp_test"
    
    mocker.patch("app.main.get_session", return_value=mock_session)
    mocker.patch("app.main.score_candidate", return_value={"overall": 0.85})
    mocker.patch("app.main.generate_feedback", return_value={"message": "Good job"})
    mocker.patch("app.main.get_application", return_value=mock_application)
    mocker.patch("app.main.save_review", return_value={"review_id": "review_123"})
    mocker.patch("app.main.update_application")
    
    # Grant consent for the applicant
    grant_consent("test@example.com", [SignalType.INTERVIEW_TRANSCRIPT_EMBEDDING])
    
    # Call the endpoint
    from fastapi.testclient import TestClient
    from app.main import app
    
    client = TestClient(app)
    response = client.post(
        "/api/apply/complete",
        json={"session_id": "test_session_123"}
    )
    
    assert response.status_code == 200
    
    # Verify signal was emitted
    pseudonymous_id = compute_pseudonymous_id("test@example.com")
    signals = query_signals(
        pseudonymous_id,
        SignalType.INTERVIEW_TRANSCRIPT_EMBEDDING,
        datetime.now(timezone.utc) - timedelta(seconds=5),
        datetime.now(timezone.utc) + timedelta(seconds=5),
    )
    
    assert len(signals) == 1
    signal = signals[0]
    assert signal.signal_type == SignalType.INTERVIEW_TRANSCRIPT_EMBEDDING
    assert signal.source_system == "platform_interview"
    assert signal.payload["source"] == "platform_interview"
    assert signal.payload["session_id"] == "test_session_123"
    assert signal.employer_id == "emp_test"
    # Verify no PII in payload
    assert "test@example.com" not in str(signal.payload)
    assert "Test Candidate" not in str(signal.payload)


def test_apply_complete_skips_signal_without_consent(mocker):
    """Test that completing an interview skips signal emission when applicant has no consent."""
    # Mock the dependencies
    mock_session = Mock()
    mock_session.session_id = "test_session_noconsent"
    mock_session.candidate_id = "app_noconsent"
    mock_session.resume_analysis = {"score": 0.8}
    mock_session.handoff = {"assessments": []}
    mock_session.transcript = []
    
    mock_application = Mock()
    mock_application.application_id = "app_noconsent"
    mock_application.candidate_name = "No Consent Candidate"
    mock_application.candidate_email = "noconsent@example.com"
    mock_application.job_id = "job_789"
    mock_application.employer_id = "emp_test"
    
    mocker.patch("app.main.get_session", return_value=mock_session)
    mocker.patch("app.main.score_candidate", return_value={"overall": 0.85})
    mocker.patch("app.main.generate_feedback", return_value={"message": "Good job"})
    mocker.patch("app.main.get_application", return_value=mock_application)
    mocker.patch("app.main.save_review", return_value={"review_id": "review_noconsent"})
    mocker.patch("app.main.update_application")
    
    # DO NOT grant consent
    
    # Call the endpoint
    from fastapi.testclient import TestClient
    from app.main import app
    
    client = TestClient(app)
    response = client.post(
        "/api/apply/complete",
        json={"session_id": "test_session_noconsent"}
    )
    
    # Should still succeed even without consent
    assert response.status_code == 200
    
    # Verify no signal was emitted
    pseudonymous_id = compute_pseudonymous_id("noconsent@example.com")
    signals = query_signals(
        pseudonymous_id,
        SignalType.INTERVIEW_TRANSCRIPT_EMBEDDING,
        datetime.now(timezone.utc) - timedelta(seconds=5),
        datetime.now(timezone.utc) + timedelta(seconds=5),
    )
    
    assert len(signals) == 0


def test_apply_complete_succeeds_even_if_signal_fails(mocker):
    """Test that apply/complete succeeds even if signal ingestion fails for other reasons."""
    # Mock the dependencies
    mock_session = Mock()
    mock_session.session_id = "test_session_failsignal"
    mock_session.candidate_id = "app_failsignal"
    mock_session.resume_analysis = {"score": 0.8}
    mock_session.handoff = {"assessments": []}
    mock_session.transcript = []
    
    mock_application = Mock()
    mock_application.application_id = "app_failsignal"
    mock_application.candidate_name = "Fail Signal"
    mock_application.candidate_email = "failsignal@example.com"
    mock_application.job_id = "job_789"
    mock_application.employer_id = "emp_test"
    
    mocker.patch("app.main.get_session", return_value=mock_session)
    mocker.patch("app.main.score_candidate", return_value={"overall": 0.85})
    mocker.patch("app.main.generate_feedback", return_value={"message": "Good job"})
    mocker.patch("app.main.get_application", return_value=mock_application)
    mocker.patch("app.main.save_review", return_value={"review_id": "review_fail"})
    mocker.patch("app.main.update_application")
    
    # Grant consent but mock Signal_Processor to raise an exception
    grant_consent("failsignal@example.com", [SignalType.INTERVIEW_TRANSCRIPT_EMBEDDING])
    
    # Mock normalize_signal to raise a generic exception
    with patch("app.main.Signal_Processor") as mock_processor_class:
        mock_processor = Mock()
        mock_processor.normalize_signal.side_effect = RuntimeError("Database connection failed")
        mock_processor_class.return_value = mock_processor
        
        # Call the endpoint
        from fastapi.testclient import TestClient
        from app.main import app
        
        client = TestClient(app)
        response = client.post(
            "/api/apply/complete",
            json={"session_id": "test_session_failsignal"}
        )
        
        # Should still succeed even if signal ingestion fails
        assert response.status_code == 200
