"""Unit tests for backend/app/evaluation_models.py (Task 3.3).

Covers:
- EvaluationModel.predict() returns valid ModelPrediction
- Score is clamped to [0.0, 1.0]
- Confidence interval is ±0.1 of score, clamped to [0.0, 1.0]
- Auto-seeding registers default v1 production model
- All four predictor instances exist and have correct model_type
- extract_features returns expected keys per model type
- Graceful fallback to 0.5 on LLM error
- Context is merged into features
"""
from __future__ import annotations

import json
import pytest
from unittest.mock import patch

import app.model_registry as mr
import app.evaluation_models as em
from app.evaluation_models import (
    EvaluationModel,
    extract_features,
    hiring_ability_predictor,
    team_fit_predictor,
    promotion_readiness_predictor,
    hiring_success_predictor,
)
from app.model_registry import (
    EvaluationModelType,
    ModelPrediction,
    ModelVersion,
    get_production_model,
    register_model_version,
)
from app.signal_store import Signal, SignalType


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_registry():
    """Reset in-memory model registry stores before each test."""
    mr._memory_versions.clear()
    mr._memory_production.clear()
    mr._memory_version_lists.clear()
    yield
    mr._memory_versions.clear()
    mr._memory_production.clear()
    mr._memory_version_lists.clear()


def _make_signal(
    signal_type: SignalType,
    payload: dict | None = None,
    employer_id: str = "emp1",
) -> Signal:
    from datetime import datetime, timezone
    return Signal(
        signal_id="sig-" + signal_type.value,
        pseudonymous_id="pseudo123",
        signal_type=signal_type,
        payload=payload or {"data": "mock"},
        source_system="test",
        collected_at=datetime.now(timezone.utc).isoformat(),
        consent_version="1.0",
        employer_id=employer_id,
    )


def _mock_llm_score(score: float):
    """Return a context manager that patches complete_json to return a given score."""
    return patch(
        "app.evaluation_models.complete_json",
        return_value={"score": score, "reasoning": "mock reasoning"},
    )


# ---------------------------------------------------------------------------
# Predictor instances
# ---------------------------------------------------------------------------

class TestPredictorInstances:
    def test_hiring_ability_predictor_exists(self):
        assert isinstance(hiring_ability_predictor, EvaluationModel)
        assert hiring_ability_predictor.model_type == EvaluationModelType.HIRING_ABILITY

    def test_team_fit_predictor_exists(self):
        assert isinstance(team_fit_predictor, EvaluationModel)
        assert team_fit_predictor.model_type == EvaluationModelType.TEAM_FIT

    def test_promotion_readiness_predictor_exists(self):
        assert isinstance(promotion_readiness_predictor, EvaluationModel)
        assert promotion_readiness_predictor.model_type == EvaluationModelType.PROMOTION_READINESS

    def test_hiring_success_predictor_exists(self):
        assert isinstance(hiring_success_predictor, EvaluationModel)
        assert hiring_success_predictor.model_type == EvaluationModelType.HIRING_SUCCESS


# ---------------------------------------------------------------------------
# Auto-seeding
# ---------------------------------------------------------------------------

class TestAutoSeeding:
    def test_auto_seed_creates_v1_for_all_types(self):
        """After _seed_registry, all four model types have a production model."""
        em._seed_registry()
        for model_type in EvaluationModelType:
            prod = get_production_model(model_type)
            assert prod.version == 1
            assert prod.accuracy == 0.7
            assert prod.is_production is True

    def test_auto_seed_is_idempotent(self):
        """Calling _seed_registry twice does not raise and does not change existing models."""
        em._seed_registry()
        em._seed_registry()
        for model_type in EvaluationModelType:
            prod = get_production_model(model_type)
            assert prod.version == 1

    def test_get_or_seed_creates_model_when_registry_empty(self):
        """_get_or_seed_production_model() creates a default when registry is empty."""
        model = EvaluationModel(EvaluationModelType.TEAM_FIT)
        mv = model._get_or_seed_production_model()
        assert mv.version == 1
        assert mv.is_production is True


# ---------------------------------------------------------------------------
# predict() — ModelPrediction structure
# ---------------------------------------------------------------------------

class TestPredictOutput:
    def test_returns_model_prediction_type(self):
        with _mock_llm_score(0.75):
            pred = hiring_ability_predictor.predict("eng1")
        assert isinstance(pred, ModelPrediction)

    def test_score_is_float(self):
        with _mock_llm_score(0.6):
            pred = hiring_ability_predictor.predict("eng1")
        assert isinstance(pred.score, float)

    def test_model_version_matches_production(self):
        em._seed_registry()
        with _mock_llm_score(0.5):
            pred = team_fit_predictor.predict("eng1")
        prod = get_production_model(EvaluationModelType.TEAM_FIT)
        assert pred.model_version == prod.version

    def test_model_type_matches_predictor(self):
        with _mock_llm_score(0.5):
            pred = promotion_readiness_predictor.predict("eng1")
        assert pred.model_type == EvaluationModelType.PROMOTION_READINESS

    def test_confidence_interval_is_tuple_of_two_floats(self):
        with _mock_llm_score(0.5):
            pred = hiring_success_predictor.predict("eng1")
        ci = pred.confidence_interval
        assert isinstance(ci, tuple)
        assert len(ci) == 2
        assert isinstance(ci[0], float)
        assert isinstance(ci[1], float)

    def test_confidence_interval_lower_le_upper(self):
        with _mock_llm_score(0.5):
            pred = hiring_ability_predictor.predict("eng1")
        lower, upper = pred.confidence_interval
        assert lower <= upper

    def test_confidence_interval_is_score_plus_minus_0_1(self):
        with _mock_llm_score(0.5):
            pred = hiring_ability_predictor.predict("eng1")
        lower, upper = pred.confidence_interval
        assert abs(lower - 0.4) < 1e-9
        assert abs(upper - 0.6) < 1e-9


# ---------------------------------------------------------------------------
# predict() — score clamping
# ---------------------------------------------------------------------------

class TestScoreClamping:
    def test_score_never_below_zero(self):
        with _mock_llm_score(-0.5):
            pred = hiring_ability_predictor.predict("eng1")
        assert pred.score >= 0.0

    def test_score_never_above_one(self):
        with _mock_llm_score(1.5):
            pred = hiring_ability_predictor.predict("eng1")
        assert pred.score <= 1.0

    def test_ci_lower_clamped_at_zero_for_low_score(self):
        with _mock_llm_score(0.05):
            pred = hiring_ability_predictor.predict("eng1")
        lower, _ = pred.confidence_interval
        assert lower >= 0.0

    def test_ci_upper_clamped_at_one_for_high_score(self):
        with _mock_llm_score(0.95):
            pred = hiring_ability_predictor.predict("eng1")
        _, upper = pred.confidence_interval
        assert upper <= 1.0


# ---------------------------------------------------------------------------
# predict() — LLM error fallback
# ---------------------------------------------------------------------------

class TestLLMErrorFallback:
    def test_llm_error_returns_default_score_0_5(self):
        from app.llm.client import LLMError
        with patch("app.evaluation_models.complete_json", side_effect=LLMError("timeout")):
            pred = hiring_ability_predictor.predict("eng1")
        assert pred.score == 0.5

    def test_bad_json_score_field_returns_0_5(self):
        with patch("app.evaluation_models.complete_json", return_value={"reasoning": "no score"}):
            # score key missing → defaults to 0.5 via dict.get("score", 0.5)
            pred = hiring_ability_predictor.predict("eng1")
        assert pred.score == 0.5

    def test_non_numeric_score_returns_0_5(self):
        with patch("app.evaluation_models.complete_json", return_value={"score": "high"}):
            pred = hiring_ability_predictor.predict("eng1")
        assert pred.score == 0.5

    def test_empty_response_returns_0_5(self):
        with patch("app.evaluation_models.complete_json", return_value={}):
            pred = hiring_ability_predictor.predict("eng1")
        assert pred.score == 0.5


# ---------------------------------------------------------------------------
# predict() — signals and context
# ---------------------------------------------------------------------------

class TestPredictWithSignals:
    def test_predict_with_empty_signals_list(self):
        with _mock_llm_score(0.5):
            pred = hiring_ability_predictor.predict("eng1", signals=[])
        assert 0.0 <= pred.score <= 1.0

    def test_predict_with_none_signals(self):
        with _mock_llm_score(0.5):
            pred = hiring_ability_predictor.predict("eng1", signals=None)
        assert 0.0 <= pred.score <= 1.0

    def test_predict_passes_context_to_llm(self):
        captured_user_content = []

        def mock_complete(system_prompt, user_content, stage=None):
            captured_user_content.append(user_content)
            return {"score": 0.7, "reasoning": "ok"}

        with patch("app.evaluation_models.complete_json", side_effect=mock_complete):
            hiring_ability_predictor.predict(
                "eng1",
                context={"historical_score": 0.8, "previous_applications": 2},
            )

        assert len(captured_user_content) == 1
        payload = json.loads(captured_user_content[0])
        assert "extra_context" in payload
        assert payload["extra_context"]["historical_score"] == 0.8

    def test_predict_with_signals_increments_feature_counts(self):
        signals = [
            _make_signal(SignalType.COMMIT_METADATA),
            _make_signal(SignalType.COMMIT_METADATA),
            _make_signal(SignalType.PR_REVIEW_QUALITY),
        ]
        captured = []

        def mock_complete(system_prompt, user_content, stage=None):
            captured.append(json.loads(user_content))
            return {"score": 0.6, "reasoning": "ok"}

        with patch("app.evaluation_models.complete_json", side_effect=mock_complete):
            hiring_ability_predictor.predict("eng1", signals=signals)

        feats = captured[0]
        assert feats["commit_count"] == 2
        assert feats["pr_reviews"] == 1

    def test_predict_uses_registered_production_version(self):
        """If a higher-version model is promoted, predict uses that version."""
        em._seed_registry()
        from datetime import datetime, timezone
        mv2 = ModelVersion(
            model_type=EvaluationModelType.HIRING_ABILITY,
            version=2,
            accuracy=0.85,
            promoted_at=datetime.now(timezone.utc).isoformat(),
            weights_uri="",
            is_production=False,
        )
        register_model_version(mv2)
        from app.model_registry import promote_model
        promote_model(EvaluationModelType.HIRING_ABILITY, 2)

        with _mock_llm_score(0.7):
            pred = hiring_ability_predictor.predict("eng1")
        assert pred.model_version == 2


# ---------------------------------------------------------------------------
# extract_features
# ---------------------------------------------------------------------------

class TestExtractFeatures:
    def test_empty_signals_returns_zero_counts(self):
        feats = extract_features([], EvaluationModelType.HIRING_ABILITY)
        assert feats["total_signals"] == 0
        assert feats["coding_sessions"] == 0
        assert feats["commit_count"] == 0

    def test_hiring_ability_counts_coding_sessions(self):
        signals = [_make_signal(SignalType.CODING_SESSION)] * 3
        feats = extract_features(signals, EvaluationModelType.HIRING_ABILITY)
        assert feats["coding_sessions"] == 3

    def test_team_fit_counts_collaboration(self):
        signals = [_make_signal(SignalType.COLLABORATION_FREQUENCY)] * 5
        feats = extract_features(signals, EvaluationModelType.TEAM_FIT)
        assert feats["collaboration_events"] == 5

    def test_promotion_readiness_includes_avg_performance(self):
        signals = [
            _make_signal(SignalType.JOB_PERFORMANCE_RATING, payload={"score": 0.8}),
            _make_signal(SignalType.JOB_PERFORMANCE_RATING, payload={"score": 0.9}),
        ]
        feats = extract_features(signals, EvaluationModelType.PROMOTION_READINESS)
        assert feats["performance_ratings"] == 2
        assert abs(feats["avg_performance_score"] - 0.85) < 1e-9

    def test_hiring_success_counts_onboarding_events(self):
        signals = [_make_signal(SignalType.ONBOARDING_TASK_COMPLETION)] * 4
        feats = extract_features(signals, EvaluationModelType.HIRING_SUCCESS)
        assert feats["onboarding_events"] == 4

    def test_all_model_types_produce_features(self):
        signals = [
            _make_signal(SignalType.COMMIT_METADATA),
            _make_signal(SignalType.COLLABORATION_FREQUENCY),
        ]
        for model_type in EvaluationModelType:
            feats = extract_features(signals, model_type)
            assert "total_signals" in feats
            assert feats["total_signals"] == 2
