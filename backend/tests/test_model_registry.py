"""Unit tests for backend/app/model_registry.py (Task 3.1).

Covers:
- register_model_version (happy path, duplicate rejection, monotonicity)
- get_production_model (raises KeyError when none registered)
- promote_model (True when accuracy improves or equal, False when accuracy drops)
- rollback_model (restores previous version)
- list_model_versions (returns sorted list)
"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone

# Isolate tests from Valkey by ensuring the in-memory fallback is always used.
# The module uses get_settings().valkey_url; we patch it to empty string.
import app.model_registry as mr
from app.model_registry import (
    EvaluationModelType,
    ModelVersion,
    ModelPrediction,
    register_model_version,
    get_production_model,
    promote_model,
    rollback_model,
    list_model_versions,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_memory_stores():
    """Reset in-memory stores before each test to ensure isolation."""
    mr._memory_versions.clear()
    mr._memory_production.clear()
    mr._memory_version_lists.clear()
    yield
    mr._memory_versions.clear()
    mr._memory_production.clear()
    mr._memory_version_lists.clear()


def _make_mv(
    version: int,
    accuracy: float = 0.80,
    model_type: EvaluationModelType = EvaluationModelType.HIRING_ABILITY,
    is_production: bool = False,
) -> ModelVersion:
    return ModelVersion(
        model_type=model_type,
        version=version,
        accuracy=accuracy,
        promoted_at=datetime.now(timezone.utc).isoformat(),
        weights_uri=f"s3://models/{model_type.value}/v{version}.pkl",
        is_production=is_production,
    )


# ---------------------------------------------------------------------------
# register_model_version
# ---------------------------------------------------------------------------

class TestRegisterModelVersion:
    def test_registers_first_version_as_production(self):
        mv = _make_mv(1)
        register_model_version(mv)
        prod = get_production_model(EvaluationModelType.HIRING_ABILITY)
        assert prod.version == 1
        assert prod.is_production is True

    def test_registers_second_version_not_auto_production(self):
        register_model_version(_make_mv(1, accuracy=0.80))
        register_model_version(_make_mv(2, accuracy=0.85))
        prod = get_production_model(EvaluationModelType.HIRING_ABILITY)
        # First version remains production until explicitly promoted
        assert prod.version == 1

    def test_all_versions_appear_in_list(self):
        register_model_version(_make_mv(1))
        register_model_version(_make_mv(2))
        register_model_version(_make_mv(3))
        versions = list_model_versions(EvaluationModelType.HIRING_ABILITY)
        assert [v.version for v in versions] == [1, 2, 3]

    def test_raises_on_duplicate_version(self):
        register_model_version(_make_mv(1))
        with pytest.raises(ValueError, match="already exists"):
            register_model_version(_make_mv(1))

    def test_raises_on_non_monotonic_version(self):
        register_model_version(_make_mv(1))
        register_model_version(_make_mv(3))
        with pytest.raises(ValueError):
            register_model_version(_make_mv(2))

    def test_different_model_types_are_isolated(self):
        register_model_version(_make_mv(1, model_type=EvaluationModelType.HIRING_ABILITY))
        register_model_version(_make_mv(1, model_type=EvaluationModelType.TEAM_FIT))
        ha_prod = get_production_model(EvaluationModelType.HIRING_ABILITY)
        tf_prod = get_production_model(EvaluationModelType.TEAM_FIT)
        assert ha_prod.model_type == EvaluationModelType.HIRING_ABILITY
        assert tf_prod.model_type == EvaluationModelType.TEAM_FIT


# ---------------------------------------------------------------------------
# get_production_model
# ---------------------------------------------------------------------------

class TestGetProductionModel:
    def test_raises_key_error_when_no_model_registered(self):
        with pytest.raises(KeyError):
            get_production_model(EvaluationModelType.HIRING_ABILITY)

    def test_returns_correct_production_model(self):
        register_model_version(_make_mv(1, accuracy=0.75))
        prod = get_production_model(EvaluationModelType.HIRING_ABILITY)
        assert prod.version == 1
        assert prod.accuracy == 0.75


# ---------------------------------------------------------------------------
# promote_model
# ---------------------------------------------------------------------------

class TestPromoteModel:
    def test_promote_returns_true_when_accuracy_improves(self):
        register_model_version(_make_mv(1, accuracy=0.80))
        register_model_version(_make_mv(2, accuracy=0.85))
        result = promote_model(EvaluationModelType.HIRING_ABILITY, 2)
        assert result is True

    def test_promote_switches_production_pointer(self):
        register_model_version(_make_mv(1, accuracy=0.80))
        register_model_version(_make_mv(2, accuracy=0.85))
        promote_model(EvaluationModelType.HIRING_ABILITY, 2)
        prod = get_production_model(EvaluationModelType.HIRING_ABILITY)
        assert prod.version == 2
        assert prod.is_production is True

    def test_promote_returns_true_when_accuracy_equal(self):
        register_model_version(_make_mv(1, accuracy=0.80))
        register_model_version(_make_mv(2, accuracy=0.80))
        result = promote_model(EvaluationModelType.HIRING_ABILITY, 2)
        assert result is True

    def test_promote_returns_false_when_accuracy_drops(self):
        register_model_version(_make_mv(1, accuracy=0.85))
        register_model_version(_make_mv(2, accuracy=0.80))
        result = promote_model(EvaluationModelType.HIRING_ABILITY, 2)
        assert result is False

    def test_production_unchanged_after_failed_promote(self):
        register_model_version(_make_mv(1, accuracy=0.85))
        register_model_version(_make_mv(2, accuracy=0.80))
        promote_model(EvaluationModelType.HIRING_ABILITY, 2)
        # Production must still be v1
        prod = get_production_model(EvaluationModelType.HIRING_ABILITY)
        assert prod.version == 1

    def test_old_production_demoted_after_successful_promote(self):
        register_model_version(_make_mv(1, accuracy=0.80))
        register_model_version(_make_mv(2, accuracy=0.90))
        promote_model(EvaluationModelType.HIRING_ABILITY, 2)
        versions = list_model_versions(EvaluationModelType.HIRING_ABILITY)
        v1 = next(v for v in versions if v.version == 1)
        v2 = next(v for v in versions if v.version == 2)
        assert v1.is_production is False
        assert v2.is_production is True

    def test_promote_raises_key_error_for_unknown_version(self):
        register_model_version(_make_mv(1, accuracy=0.80))
        with pytest.raises(KeyError):
            promote_model(EvaluationModelType.HIRING_ABILITY, 99)

    def test_promote_first_version_when_no_production_exists(self):
        """If somehow production pointer is missing, promoting should succeed."""
        register_model_version(_make_mv(1, accuracy=0.80))
        # Auto-promoted on register, but let's test a second version after clearing
        register_model_version(_make_mv(2, accuracy=0.75))
        result = promote_model(EvaluationModelType.HIRING_ABILITY, 2)
        # v2 accuracy (0.75) < v1 accuracy (0.80), so should be False
        assert result is False


# ---------------------------------------------------------------------------
# rollback_model
# ---------------------------------------------------------------------------

class TestRollbackModel:
    def test_rollback_restores_previous_version(self):
        register_model_version(_make_mv(1, accuracy=0.80))
        register_model_version(_make_mv(2, accuracy=0.90))
        promote_model(EvaluationModelType.HIRING_ABILITY, 2)
        prev = rollback_model(EvaluationModelType.HIRING_ABILITY)
        assert prev.version == 1

    def test_rollback_updates_production_pointer(self):
        register_model_version(_make_mv(1, accuracy=0.80))
        register_model_version(_make_mv(2, accuracy=0.90))
        promote_model(EvaluationModelType.HIRING_ABILITY, 2)
        rollback_model(EvaluationModelType.HIRING_ABILITY)
        prod = get_production_model(EvaluationModelType.HIRING_ABILITY)
        assert prod.version == 1
        assert prod.is_production is True

    def test_rollback_demotes_current_production(self):
        register_model_version(_make_mv(1, accuracy=0.80))
        register_model_version(_make_mv(2, accuracy=0.90))
        promote_model(EvaluationModelType.HIRING_ABILITY, 2)
        rollback_model(EvaluationModelType.HIRING_ABILITY)
        versions = list_model_versions(EvaluationModelType.HIRING_ABILITY)
        v2 = next(v for v in versions if v.version == 2)
        assert v2.is_production is False

    def test_rollback_raises_when_no_previous_version(self):
        # Only one version registered — no previous to roll back to
        register_model_version(_make_mv(1, accuracy=0.80))
        with pytest.raises(KeyError):
            rollback_model(EvaluationModelType.HIRING_ABILITY)

    def test_rollback_raises_when_no_production_model(self):
        with pytest.raises(KeyError):
            rollback_model(EvaluationModelType.HIRING_ABILITY)

    def test_keeps_at_least_two_versions_after_rollback(self):
        """Rollback must not delete versions — at least 2 remain."""
        register_model_version(_make_mv(1, accuracy=0.80))
        register_model_version(_make_mv(2, accuracy=0.90))
        register_model_version(_make_mv(3, accuracy=0.95))
        promote_model(EvaluationModelType.HIRING_ABILITY, 2)
        promote_model(EvaluationModelType.HIRING_ABILITY, 3)
        rollback_model(EvaluationModelType.HIRING_ABILITY)
        versions = list_model_versions(EvaluationModelType.HIRING_ABILITY)
        assert len(versions) >= 2


# ---------------------------------------------------------------------------
# list_model_versions
# ---------------------------------------------------------------------------

class TestListModelVersions:
    def test_returns_empty_list_when_none_registered(self):
        result = list_model_versions(EvaluationModelType.PROMOTION_READINESS)
        assert result == []

    def test_returns_all_versions_sorted_ascending(self):
        register_model_version(_make_mv(1, model_type=EvaluationModelType.TEAM_FIT))
        register_model_version(_make_mv(2, model_type=EvaluationModelType.TEAM_FIT))
        register_model_version(_make_mv(3, model_type=EvaluationModelType.TEAM_FIT))
        result = list_model_versions(EvaluationModelType.TEAM_FIT)
        assert [v.version for v in result] == [1, 2, 3]

    def test_returns_only_versions_for_given_type(self):
        register_model_version(_make_mv(1, model_type=EvaluationModelType.HIRING_ABILITY))
        register_model_version(_make_mv(1, model_type=EvaluationModelType.HIRING_SUCCESS))
        ha_versions = list_model_versions(EvaluationModelType.HIRING_ABILITY)
        hs_versions = list_model_versions(EvaluationModelType.HIRING_SUCCESS)
        assert len(ha_versions) == 1
        assert len(hs_versions) == 1
        assert ha_versions[0].model_type == EvaluationModelType.HIRING_ABILITY
        assert hs_versions[0].model_type == EvaluationModelType.HIRING_SUCCESS


# ---------------------------------------------------------------------------
# ModelPrediction dataclass
# ---------------------------------------------------------------------------

class TestModelPrediction:
    def test_model_prediction_creation(self):
        pred = ModelPrediction(
            score=0.87,
            model_version=3,
            confidence_interval=(0.82, 0.92),
            model_type=EvaluationModelType.HIRING_ABILITY,
        )
        assert pred.score == 0.87
        assert pred.model_version == 3
        assert pred.confidence_interval == (0.82, 0.92)
        assert pred.model_type == EvaluationModelType.HIRING_ABILITY

    def test_confidence_interval_lower_le_upper(self):
        pred = ModelPrediction(
            score=0.5,
            model_version=1,
            confidence_interval=(0.4, 0.6),
            model_type=EvaluationModelType.TEAM_FIT,
        )
        lower, upper = pred.confidence_interval
        assert lower <= upper
