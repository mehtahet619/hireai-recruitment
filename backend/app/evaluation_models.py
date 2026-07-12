"""Phase-1 Evaluation Models — LLM-backed predictors for the Flywheel.

Each predictor is an instance of EvaluationModel bound to a specific
EvaluationModelType.  The predict() method:

1. Looks up (or seeds) the production ModelVersion in the Model_Registry.
2. Extracts relevant Signal features from the provided signals list.
3. Calls LLMClient.complete_json() with a specialised system prompt and the
   extracted features as the user message.
4. Parses the JSON response for a ``score`` field (float 0.0–1.0).
5. Returns a ModelPrediction with the score, model_version, and a ±0.1
   confidence interval clamped to [0.0, 1.0].

Auto-seeding
------------
On module load, a default ModelVersion(version=1, accuracy=0.7) is registered
for each EvaluationModelType that has no production model yet.  This makes the
module self-contained for fresh deployments and tests.

Requirements: 2.5, 2.6
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .llm.client import LLMError, complete_json
from .model_registry import (
    EvaluationModelType,
    ModelPrediction,
    ModelVersion,
    get_production_model,
    register_model_version,
)
from .signal_store import Signal, SignalType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Signal feature extraction
# ---------------------------------------------------------------------------

def extract_features(signals: list[Signal], model_type: EvaluationModelType) -> dict[str, Any]:
    """Extract aggregated features from a list of Signals for a given model type.

    Returns a dict that is serialised and sent as context to the LLM.  Each
    model type emphasises different signal categories.
    """
    counts: dict[str, int] = {}
    for sig in signals:
        key = sig.signal_type.value
        counts[key] = counts.get(key, 0) + 1

    # --- Shared metrics available to all models ---
    features: dict[str, Any] = {
        "total_signals": len(signals),
        "signal_type_counts": counts,
    }

    # --- Model-specific feature aggregation ---
    if model_type == EvaluationModelType.HIRING_ABILITY:
        # Focus on coding, commits, PRs, and interview signals
        relevant = [
            SignalType.CODING_SESSION,
            SignalType.COMMIT_METADATA,
            SignalType.PR_REVIEW_QUALITY,
            SignalType.INTERVIEW_TRANSCRIPT_EMBEDDING,
            SignalType.DEBUGGING_TRACE,
            SignalType.AI_PROMPT_CATEGORY,
        ]
        features["relevant_signal_types"] = [s.value for s in relevant]
        features["coding_sessions"] = counts.get(SignalType.CODING_SESSION.value, 0)
        features["commit_count"] = counts.get(SignalType.COMMIT_METADATA.value, 0)
        features["pr_reviews"] = counts.get(SignalType.PR_REVIEW_QUALITY.value, 0)
        features["interview_signals"] = counts.get(
            SignalType.INTERVIEW_TRANSCRIPT_EMBEDDING.value, 0
        )
        features["debugging_traces"] = counts.get(SignalType.DEBUGGING_TRACE.value, 0)
        features["ai_prompt_signals"] = counts.get(SignalType.AI_PROMPT_CATEGORY.value, 0)

    elif model_type == EvaluationModelType.TEAM_FIT:
        # Focus on collaboration and communication signals
        relevant = [
            SignalType.COLLABORATION_FREQUENCY,
            SignalType.PR_REVIEW_QUALITY,
            SignalType.ARCHITECTURE_DECISION_TAG,
            SignalType.ONBOARDING_TASK_COMPLETION,
        ]
        features["relevant_signal_types"] = [s.value for s in relevant]
        features["collaboration_events"] = counts.get(
            SignalType.COLLABORATION_FREQUENCY.value, 0
        )
        features["pr_reviews"] = counts.get(SignalType.PR_REVIEW_QUALITY.value, 0)
        features["architecture_decisions"] = counts.get(
            SignalType.ARCHITECTURE_DECISION_TAG.value, 0
        )
        features["onboarding_completions"] = counts.get(
            SignalType.ONBOARDING_TASK_COMPLETION.value, 0
        )

    elif model_type == EvaluationModelType.PROMOTION_READINESS:
        # Focus on performance, mentorship, and growth signals
        relevant = [
            SignalType.JOB_PERFORMANCE_RATING,
            SignalType.COMMIT_METADATA,
            SignalType.ARCHITECTURE_DECISION_TAG,
            SignalType.PR_REVIEW_QUALITY,
            SignalType.COLLABORATION_FREQUENCY,
            SignalType.ONBOARDING_COMPLETION_SUMMARY,
        ]
        features["relevant_signal_types"] = [s.value for s in relevant]
        features["performance_ratings"] = counts.get(
            SignalType.JOB_PERFORMANCE_RATING.value, 0
        )
        features["architecture_contributions"] = counts.get(
            SignalType.ARCHITECTURE_DECISION_TAG.value, 0
        )
        features["commit_count"] = counts.get(SignalType.COMMIT_METADATA.value, 0)
        features["pr_reviews"] = counts.get(SignalType.PR_REVIEW_QUALITY.value, 0)
        features["collaboration_events"] = counts.get(
            SignalType.COLLABORATION_FREQUENCY.value, 0
        )
        # Include payload summaries from performance ratings if available
        perf_payloads = [
            sig.payload for sig in signals
            if sig.signal_type == SignalType.JOB_PERFORMANCE_RATING
        ]
        if perf_payloads:
            scores = [
                float(p["score"])
                for p in perf_payloads
                if "score" in p and isinstance(p.get("score"), (int, float))
            ]
            if scores:
                features["avg_performance_score"] = sum(scores) / len(scores)
                features["max_performance_score"] = max(scores)
                features["min_performance_score"] = min(scores)

    elif model_type == EvaluationModelType.HIRING_SUCCESS:
        # Focus on long-term performance and retention signals after hire
        relevant = [
            SignalType.JOB_PERFORMANCE_RATING,
            SignalType.ONBOARDING_COMPLETION_SUMMARY,
            SignalType.ONBOARDING_TASK_COMPLETION,
            SignalType.COLLABORATION_FREQUENCY,
            SignalType.COMMIT_METADATA,
            SignalType.PR_REVIEW_QUALITY,
        ]
        features["relevant_signal_types"] = [s.value for s in relevant]
        features["performance_ratings"] = counts.get(
            SignalType.JOB_PERFORMANCE_RATING.value, 0
        )
        features["onboarding_events"] = counts.get(
            SignalType.ONBOARDING_TASK_COMPLETION.value, 0
        )
        features["onboarding_completions"] = counts.get(
            SignalType.ONBOARDING_COMPLETION_SUMMARY.value, 0
        )
        features["collaboration_events"] = counts.get(
            SignalType.COLLABORATION_FREQUENCY.value, 0
        )
        features["commit_count"] = counts.get(SignalType.COMMIT_METADATA.value, 0)
        features["pr_reviews"] = counts.get(SignalType.PR_REVIEW_QUALITY.value, 0)

    return features


# ---------------------------------------------------------------------------
# Base EvaluationModel class
# ---------------------------------------------------------------------------

class EvaluationModel:
    """LLM-backed evaluation model for a specific EvaluationModelType.

    Parameters
    ----------
    model_type:
        The type of evaluation this model performs.
    """

    def __init__(self, model_type: EvaluationModelType) -> None:
        self.model_type = model_type

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_or_seed_production_model(self) -> ModelVersion:
        """Return the production ModelVersion, registering a default v1 if none exists."""
        try:
            return get_production_model(self.model_type)
        except KeyError:
            # No production model registered yet — seed a default v1
            default_mv = ModelVersion(
                model_type=self.model_type,
                version=1,
                accuracy=0.7,
                promoted_at=datetime.now(timezone.utc).isoformat(),
                weights_uri="",
                is_production=True,
            )
            try:
                register_model_version(default_mv)
            except ValueError:
                # Another thread may have registered it concurrently — fetch it
                pass
            return get_production_model(self.model_type)

    def _build_system_prompt(self) -> str:
        return (
            f"You are an AI evaluation model for {self.model_type.value}. "
            "Analyze the provided engineering signals and return a JSON object with: "
            '{\"score\": <float 0.0-1.0>, \"reasoning\": \"<brief reasoning>\"}'
        )

    def _call_llm(self, features: dict[str, Any]) -> float:
        """Call the LLM with the extracted features and return a score in [0.0, 1.0]."""
        system_prompt = self._build_system_prompt()
        user_content = json.dumps(features)
        try:
            response = complete_json(
                system_prompt=system_prompt,
                user_content=user_content,
                stage=f"evaluation_model_{self.model_type.value}",
            )
            raw_score = response.get("score", 0.5)
            score = float(raw_score)
            # Clamp to valid range
            return max(0.0, min(1.0, score))
        except (LLMError, ValueError, TypeError, KeyError) as exc:
            logger.warning(
                "EvaluationModel(%s): LLM call failed, defaulting to 0.5. Error: %s",
                self.model_type.value,
                exc,
            )
            return 0.5

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def predict(
        self,
        engineer_id: str,
        signals: list[Signal] | None = None,
        context: dict | None = None,
    ) -> ModelPrediction:
        """Run inference for the given engineer and return a ModelPrediction.

        Parameters
        ----------
        engineer_id:
            The identifier of the engineer being evaluated (used for logging
            and any future retrieval; not sent to the LLM directly).
        signals:
            Optional list of Signal objects collected for this engineer.
            If None or empty, feature extraction returns zero-counts which
            will bias the LLM toward a neutral 0.5 score.
        context:
            Optional additional key/value context merged into the feature dict
            before sending to the LLM (e.g. historical scores from the hiring
            pipeline — Requirement 3.6).

        Returns
        -------
        ModelPrediction
            score in [0.0, 1.0], model_version, confidence_interval,
            and model_type (Requirements 2.5, 2.6).
        """
        # a) Get production model version
        prod_mv = self._get_or_seed_production_model()

        # b) Extract signal features
        signal_list: list[Signal] = signals or []
        features = extract_features(signal_list, self.model_type)
        features["engineer_id_hint"] = f"engineer:{hash(engineer_id) % 10000:04d}"  # obfuscated

        # c) Merge extra context if provided
        if context:
            features["extra_context"] = context

        # d) Call LLM and parse score
        score = self._call_llm(features)

        # e) Build confidence interval ±0.1, clamped to [0.0, 1.0]
        ci_lower = max(0.0, score - 0.1)
        ci_upper = min(1.0, score + 0.1)

        # f) Return ModelPrediction
        return ModelPrediction(
            score=score,
            model_version=prod_mv.version,
            confidence_interval=(ci_lower, ci_upper),
            model_type=self.model_type,
        )


# ---------------------------------------------------------------------------
# Concrete predictor instances (Phase-1)
# ---------------------------------------------------------------------------

hiring_ability_predictor = EvaluationModel(EvaluationModelType.HIRING_ABILITY)
team_fit_predictor = EvaluationModel(EvaluationModelType.TEAM_FIT)
promotion_readiness_predictor = EvaluationModel(EvaluationModelType.PROMOTION_READINESS)
hiring_success_predictor = EvaluationModel(EvaluationModelType.HIRING_SUCCESS)


# ---------------------------------------------------------------------------
# Auto-seed the model registry on module load
# ---------------------------------------------------------------------------
# Called here (at import time) so that all four predictors have a default
# production model even if the registry is empty.  Idempotent — if a model
# is already registered the KeyError is silently ignored.

def _seed_registry() -> None:
    """Register a default v1 for each model type if none exists."""
    for model_type in EvaluationModelType:
        try:
            get_production_model(model_type)
        except KeyError:
            mv = ModelVersion(
                model_type=model_type,
                version=1,
                accuracy=0.7,
                promoted_at=datetime.now(timezone.utc).isoformat(),
                weights_uri="",
                is_production=True,
            )
            try:
                register_model_version(mv)
            except ValueError:
                pass  # Already registered by another import or concurrent call


_seed_registry()
