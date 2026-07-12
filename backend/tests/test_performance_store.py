"""Unit tests for backend/app/performance_store.py — Task 7.1.

Tests cover:
- PerformanceCycle save/get/list
- PerformanceReview save/get/list
- normalize_score
- activate_cycle
- submit_review
- evaluate_cycle (predictions shape, cycle status, storage)
"""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.performance_store import (
    PerformanceCycle,
    PerformanceReview,
    _memory_store,
    activate_cycle,
    evaluate_cycle,
    get_cycle,
    get_review,
    list_cycle_reviews,
    list_employer_cycles,
    normalize_score,
    save_cycle,
    save_review_record,
    submit_review,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_memory_store():
    """Wipe the in-memory store before each test for isolation."""
    _memory_store.clear()
    yield
    _memory_store.clear()


def _new_id() -> str:
    return str(uuid.uuid4())


def _make_cycle(
    employer_id: str | None = None,
    status: str = "draft",
    participant_ids: list[str] | None = None,
) -> PerformanceCycle:
    return PerformanceCycle(
        cycle_id=_new_id(),
        employer_id=employer_id or _new_id(),
        name="Q1 2024 Review",
        start_date="2024-01-01",
        end_date="2024-03-31",
        participant_ids=participant_ids if participant_ids is not None else [_new_id(), _new_id()],
        review_template={"fields": [{"name": "score", "type": "number", "min": 0, "max": 10}]},
        status=status,
    )


def _make_review(cycle_id: str, score: float = 0.75) -> PerformanceReview:
    return PerformanceReview(
        review_id=_new_id(),
        cycle_id=cycle_id,
        reviewer_id=_new_id(),
        reviewee_id=_new_id(),
        form_responses={"overall_score": score},
        normalized_score=score,
        submitted_at="2024-02-15T10:00:00+00:00",
    )


# ---------------------------------------------------------------------------
# PerformanceCycle CRUD
# ---------------------------------------------------------------------------

class TestCycleCRUD:
    def test_save_and_get_roundtrip(self):
        cycle = _make_cycle()
        save_cycle(cycle)
        loaded = get_cycle(cycle.cycle_id)
        assert loaded is not None
        assert loaded.cycle_id == cycle.cycle_id
        assert loaded.name == cycle.name
        assert loaded.status == cycle.status
        assert loaded.employer_id == cycle.employer_id

    def test_get_nonexistent_returns_none(self):
        assert get_cycle("does-not-exist") is None

    def test_overwrite_cycle(self):
        cycle = _make_cycle()
        save_cycle(cycle)
        cycle.status = "active"
        save_cycle(cycle)
        loaded = get_cycle(cycle.cycle_id)
        assert loaded.status == "active"

    def test_list_employer_cycles_returns_all(self):
        employer_id = _new_id()
        c1 = _make_cycle(employer_id=employer_id)
        c2 = _make_cycle(employer_id=employer_id)
        save_cycle(c1)
        save_cycle(c2)
        result = list_employer_cycles(employer_id)
        ids = {c.cycle_id for c in result}
        assert c1.cycle_id in ids
        assert c2.cycle_id in ids

    def test_list_employer_cycles_empty(self):
        assert list_employer_cycles("unknown-employer") == []

    def test_list_employer_cycles_sorted_newest_first(self):
        employer_id = _new_id()
        early = _make_cycle(employer_id=employer_id)
        early.start_date = "2023-01-01"
        late = _make_cycle(employer_id=employer_id)
        late.start_date = "2024-06-01"
        save_cycle(early)
        save_cycle(late)
        result = list_employer_cycles(employer_id)
        assert result[0].start_date == "2024-06-01"
        assert result[1].start_date == "2023-01-01"

    def test_participant_ids_preserved(self):
        participants = [_new_id(), _new_id(), _new_id()]
        cycle = _make_cycle(participant_ids=participants)
        save_cycle(cycle)
        loaded = get_cycle(cycle.cycle_id)
        assert loaded.participant_ids == participants

    def test_predictions_field_defaults_to_empty_list(self):
        cycle = _make_cycle()
        save_cycle(cycle)
        loaded = get_cycle(cycle.cycle_id)
        assert loaded.predictions == []

    def test_review_template_preserved(self):
        cycle = _make_cycle()
        cycle.review_template = {"fields": [{"name": "score", "type": "number"}]}
        save_cycle(cycle)
        loaded = get_cycle(cycle.cycle_id)
        assert loaded.review_template == cycle.review_template

    def test_tenant_isolation(self):
        emp_a = _new_id()
        emp_b = _new_id()
        save_cycle(_make_cycle(employer_id=emp_a))
        save_cycle(_make_cycle(employer_id=emp_b))
        # Only see own cycles
        a_cycles = list_employer_cycles(emp_a)
        b_cycles = list_employer_cycles(emp_b)
        assert len(a_cycles) == 1
        assert len(b_cycles) == 1
        assert a_cycles[0].employer_id == emp_a
        assert b_cycles[0].employer_id == emp_b


# ---------------------------------------------------------------------------
# PerformanceReview CRUD
# ---------------------------------------------------------------------------

class TestReviewCRUD:
    def test_save_and_get_roundtrip(self):
        cycle = _make_cycle()
        save_cycle(cycle)
        review = _make_review(cycle.cycle_id)
        save_review_record(review)
        loaded = get_review(review.review_id)
        assert loaded is not None
        assert loaded.review_id == review.review_id
        assert loaded.cycle_id == review.cycle_id
        assert loaded.normalized_score == review.normalized_score

    def test_get_nonexistent_returns_none(self):
        assert get_review("does-not-exist") is None

    def test_list_cycle_reviews_returns_all(self):
        cycle = _make_cycle()
        save_cycle(cycle)
        r1 = _make_review(cycle.cycle_id)
        r2 = _make_review(cycle.cycle_id)
        save_review_record(r1)
        save_review_record(r2)
        reviews = list_cycle_reviews(cycle.cycle_id)
        ids = {r.review_id for r in reviews}
        assert r1.review_id in ids
        assert r2.review_id in ids

    def test_list_cycle_reviews_empty(self):
        assert list_cycle_reviews("unknown-cycle") == []

    def test_form_responses_preserved(self):
        cycle = _make_cycle()
        save_cycle(cycle)
        review = _make_review(cycle.cycle_id)
        review.form_responses = {"q1": 8, "q2": 7, "comments": "Great work"}
        save_review_record(review)
        loaded = get_review(review.review_id)
        assert loaded.form_responses == {"q1": 8, "q2": 7, "comments": "Great work"}


# ---------------------------------------------------------------------------
# normalize_score
# ---------------------------------------------------------------------------

class TestNormalizeScore:
    def test_single_numeric_value_in_range(self):
        assert normalize_score({"score": 0.8}) == pytest.approx(0.8)

    def test_average_of_multiple_numeric_values(self):
        result = normalize_score({"a": 0.4, "b": 0.8})
        assert result == pytest.approx(0.6)

    def test_no_numeric_values_returns_half(self):
        assert normalize_score({"comment": "excellent", "flag": True}) == 0.5

    def test_empty_dict_returns_half(self):
        assert normalize_score({}) == 0.5

    def test_clamps_above_one(self):
        # raw average would be 5.0; should be clamped to 1.0
        assert normalize_score({"score": 5.0}) == 1.0

    def test_clamps_below_zero(self):
        # raw value negative; should be clamped to 0.0
        assert normalize_score({"score": -2.0}) == 0.0

    def test_nested_dict_extracts_numerics(self):
        responses = {"section": {"technical": 0.9, "communication": 0.7}}
        result = normalize_score(responses)
        assert result == pytest.approx(0.8)

    def test_list_values_extracted(self):
        responses = {"ratings": [0.5, 1.0, 0.0]}
        result = normalize_score(responses)
        assert result == pytest.approx(0.5)

    def test_booleans_not_treated_as_numeric(self):
        # booleans should be ignored (True/False would be 1/0 as int but we exclude bool)
        result = normalize_score({"passed": True, "failed": False})
        assert result == 0.5  # no numeric values → default

    def test_mixed_types_only_numerics_counted(self):
        result = normalize_score({"score": 0.6, "label": "good", "active": True})
        assert result == pytest.approx(0.6)

    def test_integer_values_treated_as_numeric(self):
        result = normalize_score({"q1": 8, "q2": 6})
        # Average = 7.0, clamped to 1.0
        assert result == 1.0

    def test_deeply_nested_values(self):
        responses = {"a": {"b": {"c": 0.4}}, "d": 0.6}
        result = normalize_score(responses)
        assert result == pytest.approx(0.5)

    def test_boundary_zero(self):
        assert normalize_score({"score": 0.0}) == pytest.approx(0.0)

    def test_boundary_one(self):
        assert normalize_score({"score": 1.0}) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# activate_cycle
# ---------------------------------------------------------------------------

class TestActivateCycle:
    def test_status_changed_to_active(self):
        cycle = _make_cycle(status="draft")
        save_cycle(cycle)
        updated = activate_cycle(cycle.cycle_id)
        assert updated.status == "active"

    def test_status_persisted(self):
        cycle = _make_cycle(status="draft")
        save_cycle(cycle)
        activate_cycle(cycle.cycle_id)
        reloaded = get_cycle(cycle.cycle_id)
        assert reloaded.status == "active"

    def test_raises_for_missing_cycle(self):
        with pytest.raises(ValueError, match="not found"):
            activate_cycle("nonexistent-cycle-id")

    def test_other_fields_unchanged(self):
        cycle = _make_cycle(status="draft")
        save_cycle(cycle)
        updated = activate_cycle(cycle.cycle_id)
        assert updated.name == cycle.name
        assert updated.employer_id == cycle.employer_id
        assert updated.participant_ids == cycle.participant_ids
        assert updated.start_date == cycle.start_date
        assert updated.end_date == cycle.end_date

    def test_activate_already_active_cycle_is_idempotent(self):
        """Activating an already-active cycle leaves status as active."""
        cycle = _make_cycle(status="active")
        save_cycle(cycle)
        updated = activate_cycle(cycle.cycle_id)
        assert updated.status == "active"


# ---------------------------------------------------------------------------
# submit_review
# ---------------------------------------------------------------------------

class TestSubmitReview:
    def test_review_is_returned(self):
        cycle = _make_cycle()
        save_cycle(cycle)
        review = submit_review(
            cycle_id=cycle.cycle_id,
            reviewer_id="reviewer-1",
            reviewee_id="reviewee-1",
            responses={"score": 0.7},
        )
        assert review.cycle_id == cycle.cycle_id
        assert review.reviewer_id == "reviewer-1"
        assert review.reviewee_id == "reviewee-1"

    def test_normalized_score_stored(self):
        cycle = _make_cycle()
        save_cycle(cycle)
        review = submit_review(
            cycle_id=cycle.cycle_id,
            reviewer_id="reviewer-1",
            reviewee_id="reviewee-1",
            responses={"score": 0.8},
        )
        assert review.normalized_score == pytest.approx(0.8)

    def test_review_persisted_and_retrievable(self):
        cycle = _make_cycle()
        save_cycle(cycle)
        review = submit_review(
            cycle_id=cycle.cycle_id,
            reviewer_id="r1",
            reviewee_id="e1",
            responses={"q": 0.5},
        )
        loaded = get_review(review.review_id)
        assert loaded is not None
        assert loaded.review_id == review.review_id

    def test_review_indexed_under_cycle(self):
        cycle = _make_cycle()
        save_cycle(cycle)
        r1 = submit_review(cycle_id=cycle.cycle_id, reviewer_id="r1", reviewee_id="e1", responses={"s": 0.5})
        r2 = submit_review(cycle_id=cycle.cycle_id, reviewer_id="r2", reviewee_id="e2", responses={"s": 0.9})
        cycle_reviews = list_cycle_reviews(cycle.cycle_id)
        ids = {r.review_id for r in cycle_reviews}
        assert r1.review_id in ids
        assert r2.review_id in ids

    def test_raises_for_missing_cycle(self):
        with pytest.raises(ValueError, match="not found"):
            submit_review(
                cycle_id="nonexistent-cycle",
                reviewer_id="r1",
                reviewee_id="e1",
                responses={"s": 0.5},
            )

    def test_submitted_at_is_set(self):
        cycle = _make_cycle()
        save_cycle(cycle)
        review = submit_review(
            cycle_id=cycle.cycle_id,
            reviewer_id="r1",
            reviewee_id="e1",
            responses={"score": 0.6},
        )
        assert review.submitted_at is not None
        # Should be a valid ISO-8601 string
        from datetime import datetime
        datetime.fromisoformat(review.submitted_at)

    def test_form_responses_preserved_in_review(self):
        cycle = _make_cycle()
        save_cycle(cycle)
        responses = {"technical": 8, "communication": 9, "comments": "Excellent"}
        review = submit_review(
            cycle_id=cycle.cycle_id,
            reviewer_id="r1",
            reviewee_id="e1",
            responses=responses,
        )
        assert review.form_responses == responses

    def test_score_uses_normalize_score_logic(self):
        """normalize_score({}) returns 0.5 — verify submit_review honors that."""
        cycle = _make_cycle()
        save_cycle(cycle)
        review = submit_review(
            cycle_id=cycle.cycle_id,
            reviewer_id="r1",
            reviewee_id="e1",
            responses={},  # no numeric values → 0.5
        )
        assert review.normalized_score == pytest.approx(0.5)

    def test_multiple_reviews_for_same_reviewee(self):
        """Multiple reviewers can submit for the same reviewee."""
        cycle = _make_cycle()
        save_cycle(cycle)
        r1 = submit_review(cycle.cycle_id, "manager", "eng-1", {"score": 0.8})
        r2 = submit_review(cycle.cycle_id, "peer", "eng-1", {"score": 0.6})
        assert r1.review_id != r2.review_id
        assert r1.reviewee_id == r2.reviewee_id


# ---------------------------------------------------------------------------
# evaluate_cycle
# ---------------------------------------------------------------------------

class TestEvaluateCycle:
    def _mock_prediction(self, engineer_id: str, score: float = 0.75):
        """Create a realistic mock ModelPrediction."""
        from app.model_registry import EvaluationModelType, ModelPrediction
        return ModelPrediction(
            score=score,
            model_version=1,
            confidence_interval=(max(0.0, score - 0.1), min(1.0, score + 0.1)),
            model_type=EvaluationModelType.PROMOTION_READINESS,
        )

    def test_returns_predictions_for_all_participants(self):
        participant_ids = [_new_id(), _new_id(), _new_id()]
        cycle = _make_cycle(participant_ids=participant_ids)
        save_cycle(cycle)

        mock_predict = MagicMock(side_effect=lambda eid: self._mock_prediction(eid))
        with patch("app.performance_store.promotion_readiness_predictor") as mock_predictor:
            mock_predictor.predict = mock_predict
            predictions = evaluate_cycle(cycle.cycle_id)

        assert len(predictions) == 3
        assert mock_predict.call_count == 3

    def test_cycle_status_set_to_completed(self):
        participant_ids = [_new_id()]
        cycle = _make_cycle(participant_ids=participant_ids, status="active")
        save_cycle(cycle)

        mock_predict = MagicMock(side_effect=lambda eid: self._mock_prediction(eid))
        with patch("app.performance_store.promotion_readiness_predictor") as mock_predictor:
            mock_predictor.predict = mock_predict
            evaluate_cycle(cycle.cycle_id)

        reloaded = get_cycle(cycle.cycle_id)
        assert reloaded.status == "completed"

    def test_predictions_stored_on_cycle(self):
        participant_ids = [_new_id(), _new_id()]
        cycle = _make_cycle(participant_ids=participant_ids)
        save_cycle(cycle)

        mock_predict = MagicMock(side_effect=lambda eid: self._mock_prediction(eid, 0.8))
        with patch("app.performance_store.promotion_readiness_predictor") as mock_predictor:
            mock_predictor.predict = mock_predict
            evaluate_cycle(cycle.cycle_id)

        reloaded = get_cycle(cycle.cycle_id)
        assert len(reloaded.predictions) == 2
        for pred in reloaded.predictions:
            assert "engineer_id" in pred
            assert "score" in pred
            assert "model_version" in pred
            assert "confidence_interval" in pred
            assert "model_type" in pred

    def test_engineer_ids_in_predictions_match_participants(self):
        participant_ids = [_new_id(), _new_id()]
        cycle = _make_cycle(participant_ids=participant_ids)
        save_cycle(cycle)

        mock_predict = MagicMock(side_effect=lambda eid: self._mock_prediction(eid))
        with patch("app.performance_store.promotion_readiness_predictor") as mock_predictor:
            mock_predictor.predict = mock_predict
            evaluate_cycle(cycle.cycle_id)

        reloaded = get_cycle(cycle.cycle_id)
        stored_ids = {p["engineer_id"] for p in reloaded.predictions}
        assert stored_ids == set(participant_ids)

    def test_raises_for_missing_cycle(self):
        with pytest.raises(ValueError, match="not found"):
            evaluate_cycle("nonexistent-cycle-id")

    def test_empty_participant_list_returns_empty_predictions(self):
        """With no participants, evaluate_cycle returns [] and completes the cycle.

        The predictor is never called so no mock is needed.
        """
        cycle = _make_cycle(participant_ids=[])
        save_cycle(cycle)

        predictions = evaluate_cycle(cycle.cycle_id)

        assert predictions == []
        reloaded = get_cycle(cycle.cycle_id)
        assert reloaded.status == "completed"
        assert reloaded.predictions == []

    def test_returned_predictions_are_model_prediction_objects(self):
        from app.model_registry import ModelPrediction
        participant_ids = [_new_id()]
        cycle = _make_cycle(participant_ids=participant_ids)
        save_cycle(cycle)

        mock_predict = MagicMock(side_effect=lambda eid: self._mock_prediction(eid))
        with patch("app.performance_store.promotion_readiness_predictor") as mock_predictor:
            mock_predictor.predict = mock_predict
            predictions = evaluate_cycle(cycle.cycle_id)

        assert all(isinstance(p, ModelPrediction) for p in predictions)

    def test_prediction_scores_in_valid_range(self):
        participant_ids = [_new_id(), _new_id()]
        cycle = _make_cycle(participant_ids=participant_ids)
        save_cycle(cycle)

        mock_predict = MagicMock(side_effect=lambda eid: self._mock_prediction(eid, 0.65))
        with patch("app.performance_store.promotion_readiness_predictor") as mock_predictor:
            mock_predictor.predict = mock_predict
            predictions = evaluate_cycle(cycle.cycle_id)

        for p in predictions:
            assert 0.0 <= p.score <= 1.0

    def test_confidence_interval_lower_le_upper(self):
        participant_ids = [_new_id()]
        cycle = _make_cycle(participant_ids=participant_ids)
        save_cycle(cycle)

        mock_predict = MagicMock(side_effect=lambda eid: self._mock_prediction(eid, 0.5))
        with patch("app.performance_store.promotion_readiness_predictor") as mock_predictor:
            mock_predictor.predict = mock_predict
            predictions = evaluate_cycle(cycle.cycle_id)

        for p in predictions:
            lower, upper = p.confidence_interval
            assert lower <= upper

    def test_predictions_call_order_matches_participant_order(self):
        participant_ids = [_new_id(), _new_id(), _new_id()]
        cycle = _make_cycle(participant_ids=participant_ids)
        save_cycle(cycle)

        called_with = []

        def capture_predict(eid):
            called_with.append(eid)
            return self._mock_prediction(eid)

        mock_predict = MagicMock(side_effect=capture_predict)
        with patch("app.performance_store.promotion_readiness_predictor") as mock_predictor:
            mock_predictor.predict = mock_predict
            evaluate_cycle(cycle.cycle_id)

        assert called_with == participant_ids
