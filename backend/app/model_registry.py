"""Model Registry — versioned Evaluation_Model metadata and production pointer.

Storage keys (Valkey or in-memory fallback):
  model:{model_type}:{version}       — individual ModelVersion JSON
  model_production:{model_type}      — current production version number (str)
  model_versions:{model_type}        — JSON list of registered version numbers (sorted ascending)
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .config import get_settings

# ---------------------------------------------------------------------------
# In-memory fallback stores
# ---------------------------------------------------------------------------
_memory_versions: dict[str, str] = {}   # key → JSON
_memory_production: dict[str, str] = {}  # model_type → version number as str
_memory_version_lists: dict[str, str] = {}  # model_type → JSON list of ints


# ---------------------------------------------------------------------------
# Enums and Dataclasses
# ---------------------------------------------------------------------------

class EvaluationModelType(str, Enum):
    HIRING_ABILITY = "hiring_ability"
    TEAM_FIT = "team_fit"
    PROMOTION_READINESS = "promotion_readiness"
    HIRING_SUCCESS = "hiring_success"


@dataclass
class ModelVersion:
    model_type: EvaluationModelType
    version: int          # monotonically increasing
    accuracy: float       # validation accuracy at promotion time
    promoted_at: str      # ISO-8601 UTC timestamp
    weights_uri: str
    is_production: bool


@dataclass
class ModelPrediction:
    score: float                              # 0.0 – 1.0
    model_version: int
    confidence_interval: tuple[float, float]
    model_type: EvaluationModelType


# ---------------------------------------------------------------------------
# Valkey helper
# ---------------------------------------------------------------------------

def _valkey() -> Any | None:
    settings = get_settings()
    if not settings.valkey_url:
        return None
    import valkey  # type: ignore
    return valkey.from_url(settings.valkey_url, decode_responses=True)


# ---------------------------------------------------------------------------
# Storage key helpers
# ---------------------------------------------------------------------------

def _version_key(model_type: str, version: int) -> str:
    return f"model:{model_type}:{version}"


def _production_key(model_type: str) -> str:
    return f"model_production:{model_type}"


def _versions_list_key(model_type: str) -> str:
    return f"model_versions:{model_type}"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _mv_to_dict(mv: ModelVersion) -> dict:
    d = asdict(mv)
    # EvaluationModelType enum → its string value for JSON serialisation
    d["model_type"] = mv.model_type.value
    return d


def _mv_from_dict(d: dict) -> ModelVersion:
    d = dict(d)
    d["model_type"] = EvaluationModelType(d["model_type"])
    return ModelVersion(**d)


def _load_version(model_type: str, version: int) -> ModelVersion | None:
    key = _version_key(model_type, version)
    client = _valkey()
    raw = client.get(key) if client else _memory_versions.get(key)
    if not raw:
        return None
    return _mv_from_dict(json.loads(raw))


def _save_version(mv: ModelVersion) -> None:
    key = _version_key(mv.model_type.value, mv.version)
    payload = json.dumps(_mv_to_dict(mv))
    client = _valkey()
    if client:
        client.set(key, payload)
    else:
        _memory_versions[key] = payload


def _get_version_list(model_type: str) -> list[int]:
    key = _versions_list_key(model_type)
    client = _valkey()
    raw = client.get(key) if client else _memory_version_lists.get(key)
    if not raw:
        return []
    return json.loads(raw)


def _save_version_list(model_type: str, versions: list[int]) -> None:
    key = _versions_list_key(model_type)
    payload = json.dumps(sorted(versions))
    client = _valkey()
    if client:
        client.set(key, payload)
    else:
        _memory_version_lists[key] = payload


def _get_production_version(model_type: str) -> int | None:
    key = _production_key(model_type)
    client = _valkey()
    raw = client.get(key) if client else _memory_production.get(key)
    if raw is None:
        return None
    return int(raw)


def _set_production_version(model_type: str, version: int) -> None:
    key = _production_key(model_type)
    val = str(version)
    client = _valkey()
    if client:
        client.set(key, val)
    else:
        _memory_production[key] = val


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def register_model_version(mv: ModelVersion) -> None:
    """Register a new ModelVersion.

    Raises ValueError if a version with the same (model_type, version) already
    exists, or if the new version number is not strictly greater than all
    previously registered versions for that model type.

    If no production model exists yet for this type, the registered model is
    automatically set as production.
    """
    mt = mv.model_type.value
    versions = _get_version_list(mt)

    # Duplicate check
    if mv.version in versions:
        raise ValueError(
            f"ModelVersion ({mt}, {mv.version}) already exists."
        )

    # Monotonicity check
    if versions and mv.version <= max(versions):
        raise ValueError(
            f"New version {mv.version} must be greater than the current maximum "
            f"version {max(versions)} for model type '{mt}'."
        )

    # Persist the version
    _save_version(mv)

    # Update the version list
    versions.append(mv.version)
    _save_version_list(mt, versions)

    # Auto-promote if this is the first model for this type
    if _get_production_version(mt) is None:
        mv.is_production = True
        _save_version(mv)
        _set_production_version(mt, mv.version)


def get_production_model(model_type: EvaluationModelType) -> ModelVersion:
    """Return the current production ModelVersion for the given type.

    Raises KeyError if no production model is registered.
    """
    mt = model_type.value
    prod_version = _get_production_version(mt)
    if prod_version is None:
        raise KeyError(f"No production model registered for type '{mt}'.")
    mv = _load_version(mt, prod_version)
    if mv is None:
        raise KeyError(
            f"Production pointer for '{mt}' points to version {prod_version} "
            "but that version record is missing."
        )
    return mv


def promote_model(model_type: EvaluationModelType, new_version: int) -> bool:
    """Attempt to promote new_version to production.

    Returns True if the promotion succeeds (new accuracy >= current production
    accuracy), False if it is rejected (new accuracy < current production
    accuracy).

    Raises KeyError if new_version is not registered.
    """
    mt = model_type.value
    candidate = _load_version(mt, new_version)
    if candidate is None:
        raise KeyError(
            f"Version {new_version} is not registered for model type '{mt}'."
        )

    current_prod_version = _get_production_version(mt)
    if current_prod_version is not None and current_prod_version != new_version:
        current = _load_version(mt, current_prod_version)
        if current is not None and candidate.accuracy < current.accuracy:
            # Reject: candidate is strictly less accurate than production
            return False

        # Demote the old production model
        if current is not None:
            current.is_production = False
            _save_version(current)

    # Promote the candidate
    candidate.is_production = True
    candidate.promoted_at = datetime.now(timezone.utc).isoformat()
    _save_version(candidate)
    _set_production_version(mt, new_version)
    return True


def rollback_model(model_type: EvaluationModelType) -> ModelVersion:
    """Roll back to the previous production version.

    Demotes the current production model and promotes the most recent previous
    version (i.e., the version immediately before the current production
    version in the sorted version list).

    Raises KeyError if there is no previous version to roll back to.
    """
    mt = model_type.value
    prod_version = _get_production_version(mt)
    if prod_version is None:
        raise KeyError(f"No production model registered for type '{mt}'.")

    versions = sorted(_get_version_list(mt))
    if prod_version not in versions:
        raise KeyError(
            f"Production pointer for '{mt}' points to version {prod_version} "
            "which is not in the version list."
        )

    prod_idx = versions.index(prod_version)
    if prod_idx == 0:
        raise KeyError(
            f"No previous version available to roll back to for type '{mt}'."
        )

    prev_version = versions[prod_idx - 1]
    prev_mv = _load_version(mt, prev_version)
    if prev_mv is None:
        raise KeyError(
            f"Previous version {prev_version} record is missing for type '{mt}'."
        )

    # Demote the current production model
    current = _load_version(mt, prod_version)
    if current is not None:
        current.is_production = False
        _save_version(current)

    # Promote the previous version
    prev_mv.is_production = True
    prev_mv.promoted_at = datetime.now(timezone.utc).isoformat()
    _save_version(prev_mv)
    _set_production_version(mt, prev_version)
    return prev_mv


def list_model_versions(model_type: EvaluationModelType) -> list[ModelVersion]:
    """Return all registered versions for the given model type, sorted ascending by version number."""
    mt = model_type.value
    versions = sorted(_get_version_list(mt))
    result = []
    for v in versions:
        mv = _load_version(mt, v)
        if mv is not None:
            result.append(mv)
    return result
