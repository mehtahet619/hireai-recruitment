"""Property-based tests for Model Registry (Task 3.2).

Properties tested:
  Property 5: Model promotion requires accuracy improvement
  Property 6: Model version monotonicity

Both properties use pytest + hypothesis with max_examples=200.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import app.model_registry as mr
from app.model_registry import (
    EvaluationModelType,
    ModelVersion,
    promote_model,
    register_model_version,
    list_model_versions,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clear_stores() -> None:
    """Reset all in-memory stores. Called at the start of each Hypothesis example."""
    mr._memory_versions.clear()
    mr._memory_production.clear()
    mr._memory_version_lists.clear()


def _make_mv(
    version: int,
    accuracy: float,
    model_type: EvaluationModelType = EvaluationModelType.HIRING_ABILITY,
) -> ModelVersion:
    return ModelVersion(
        model_type=model_type,
        version=version,
        accuracy=accuracy,
        promoted_at=datetime.now(timezone.utc).isoformat(),
        weights_uri=f"s3://models/{model_type.value}/v{version}.pkl",
        is_production=False,
    )


# ---------------------------------------------------------------------------
# Property 5: Model promotion requires accuracy improvement
#
# For any candidate Evaluation_Model version and any existing production model
# of the same type, promote_model SHALL return False (reject promotion) when
# the candidate version's accuracy is strictly less than the current
# production model's accuracy.
#
# Validates: Requirements 2.2
# ---------------------------------------------------------------------------

# Feature: engineering-lifecycle-platform, Property 5: Model promotion requires accuracy improvement
@given(
    model_type=st.sampled_from(list(EvaluationModelType)),
    current_accuracy=st.floats(
        min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False
    ),
    candidate_accuracy=st.floats(
        min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False
    ),
)
@settings(max_examples=200)
def test_promote_model_rejects_lower_accuracy(
    model_type: EvaluationModelType,
    current_accuracy: float,
    candidate_accuracy: float,
):
    """Property 5: promote_model returns False when candidate accuracy < production accuracy."""
    # Clear stores at the start of each Hypothesis example
    _clear_stores()

    # Only test the case where candidate is strictly less accurate
    if candidate_accuracy >= current_accuracy:
        return  # not the scenario we're testing; skip without failing

    # Register the production model (version 1) and the candidate (version 2)
    production_mv = _make_mv(version=1, accuracy=current_accuracy, model_type=model_type)
    candidate_mv = _make_mv(version=2, accuracy=candidate_accuracy, model_type=model_type)

    register_model_version(production_mv)   # auto-promoted as first version
    register_model_version(candidate_mv)

    # Attempt to promote the lower-accuracy candidate
    result = promote_model(model_type, 2)

    # The promotion MUST be rejected
    assert result is False, (
        f"promote_model should return False when candidate accuracy "
        f"({candidate_accuracy}) < production accuracy ({current_accuracy}), "
        f"but returned True."
    )


# ---------------------------------------------------------------------------
# Property 6: Model version monotonicity
#
# For any sequence of registered ModelVersion objects for the same model_type,
# the version numbers SHALL be strictly increasing (each new registration has
# a version number greater than all previously registered versions for that
# type).
#
# Validates: Requirements 2.3
# ---------------------------------------------------------------------------

# Feature: engineering-lifecycle-platform, Property 6: Model version monotonicity
@given(
    model_type=st.sampled_from(list(EvaluationModelType)),
    first_version=st.integers(min_value=1, max_value=500),
    bad_version_offset=st.integers(min_value=0, max_value=499),
)
@settings(max_examples=200)
def test_register_version_rejects_non_monotonic(
    model_type: EvaluationModelType,
    first_version: int,
    bad_version_offset: int,
):
    """Property 6 (negative): registering a version <= max existing version raises ValueError."""
    # Clear stores at the start of each Hypothesis example
    _clear_stores()

    # Register the first version
    mv1 = _make_mv(version=first_version, accuracy=0.80, model_type=model_type)
    register_model_version(mv1)

    # Attempt to register a version that is NOT strictly greater.
    # bad_version_offset=0  → bad_version == first_version  (duplicate)
    # bad_version_offset>0  → bad_version <  first_version  (regression)
    bad_version = first_version - bad_version_offset

    bad_mv = _make_mv(version=bad_version, accuracy=0.85, model_type=model_type)

    with pytest.raises(ValueError):
        register_model_version(bad_mv)


# Feature: engineering-lifecycle-platform, Property 6: Model version monotonicity
@given(
    model_type=st.sampled_from(list(EvaluationModelType)),
    version_gaps=st.lists(
        st.integers(min_value=1, max_value=100),
        min_size=2,
        max_size=10,
    ),
)
@settings(max_examples=200)
def test_registered_versions_are_strictly_increasing(
    model_type: EvaluationModelType,
    version_gaps: list[int],
):
    """Property 6 (positive): after N successful registrations, listed versions are strictly increasing."""
    # Clear stores at the start of each Hypothesis example
    _clear_stores()

    # Build a strictly-increasing sequence from positive gaps (all gaps >= 1)
    versions: list[int] = []
    current = 0
    for gap in version_gaps:
        current += gap
        versions.append(current)

    # Register all versions in order
    for v in versions:
        mv = _make_mv(version=v, accuracy=0.80, model_type=model_type)
        register_model_version(mv)

    # Retrieve and verify monotonicity
    stored = list_model_versions(model_type)
    stored_versions = [mv.version for mv in stored]

    # Every consecutive pair must be strictly increasing
    for i in range(len(stored_versions) - 1):
        assert stored_versions[i] < stored_versions[i + 1], (
            f"Version list is not strictly increasing at index {i}: "
            f"{stored_versions[i]} >= {stored_versions[i + 1]} in {stored_versions}"
        )
