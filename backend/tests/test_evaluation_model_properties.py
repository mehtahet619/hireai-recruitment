"""Property-based tests for EvaluationModel.predict() (Task 3.4).

Property tested:
  For any call to an Evaluation_Model predict(), the returned ModelPrediction
  has:
    1. score in [0.0, 1.0]
    2. a valid model_version (positive integer)
    3. a confidence_interval tuple where lower <= upper

# Feature: engineering-lifecycle-platform, Property: Evaluation_Model prediction invariants
Validates: Requirements 2.6
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import app.model_registry as mr
from app.evaluation_models import EvaluationModel
from app.model_registry import EvaluationModelType
from app.signal_store import Signal, SignalType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clear_stores() -> None:
    """Reset all in-memory model registry stores before each Hypothesis example."""
    mr._memory_versions.clear()
    mr._memory_production.clear()
    mr._memory_version_lists.clear()


def _make_signal(signal_type: SignalType, employer_id: str = "emp-test") -> Signal:
    return Signal(
        signal_id=f"sig-{signal_type.value}-prop",
        pseudonymous_id="pseudo-prop-test",
        signal_type=signal_type,
        payload={"data": "test"},
        source_system="hypothesis",
        collected_at=datetime.now(timezone.utc).isoformat(),
        consent_version="1.0",
        employer_id=employer_id,
    )


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

signal_type_strategy = st.sampled_from(list(SignalType))

signal_strategy = signal_type_strategy.map(_make_signal)

signals_strategy = st.lists(signal_strategy, min_size=0, max_size=5)


# ---------------------------------------------------------------------------
# Property: Evaluation_Model prediction invariants
#
# For any EvaluationModelType, engineer_id, LLM score (including out-of-range
# values to test clamping), and list of Signal objects:
#   1. returned score is in [0.0, 1.0]
#   2. model_version is a positive integer
#   3. confidence_interval is a (lower, upper) tuple with lower <= upper
#
# Validates: Requirements 2.6
# ---------------------------------------------------------------------------

# Feature: engineering-lifecycle-platform, Property: Evaluation_Model prediction invariants
@given(
    model_type=st.sampled_from(list(EvaluationModelType)),
    engineer_id=st.text(min_size=1),
    llm_score=st.floats(
        min_value=-0.5,
        max_value=1.5,
        allow_nan=False,
        allow_infinity=False,
    ),
    signals=signals_strategy,
)
@settings(max_examples=200)
def test_evaluation_model_prediction_invariants(
    model_type: EvaluationModelType,
    engineer_id: str,
    llm_score: float,
    signals: list[Signal],
) -> None:
    """Property: predict() always returns a ModelPrediction satisfying all three invariants.

    Validates: Requirements 2.6
    """
    # Clear registry so each example starts from a clean state
    _clear_stores()

    # Create a fresh EvaluationModel per test to avoid shared registry state
    model = EvaluationModel(model_type)

    # Mock complete_json to return the hypothesis-generated llm_score.
    # This includes out-of-range values (-0.5 to 1.5) to exercise clamping logic.
    with patch(
        "app.evaluation_models.complete_json",
        return_value={"score": llm_score, "reasoning": "test"},
    ):
        prediction = model.predict(engineer_id=engineer_id, signals=signals)

    # --- Invariant 1: score must be in [0.0, 1.0] ---
    assert 0.0 <= prediction.score <= 1.0, (
        f"score {prediction.score} is out of [0.0, 1.0] "
        f"(llm_score={llm_score}, model_type={model_type})"
    )

    # --- Invariant 2: model_version must be a positive integer ---
    assert isinstance(prediction.model_version, int), (
        f"model_version must be an int, got {type(prediction.model_version)} "
        f"(model_type={model_type})"
    )
    assert prediction.model_version > 0, (
        f"model_version must be positive, got {prediction.model_version} "
        f"(model_type={model_type})"
    )

    # --- Invariant 3: confidence_interval lower <= upper ---
    ci = prediction.confidence_interval
    assert isinstance(ci, tuple), (
        f"confidence_interval must be a tuple, got {type(ci)} "
        f"(model_type={model_type})"
    )
    assert len(ci) == 2, (
        f"confidence_interval must have exactly 2 elements, got {len(ci)} "
        f"(model_type={model_type})"
    )
    lower, upper = ci
    assert lower <= upper, (
        f"confidence_interval lower ({lower}) must be <= upper ({upper}) "
        f"(score={prediction.score}, model_type={model_type})"
    )
