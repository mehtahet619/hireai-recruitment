"""Flywheel Metrics — aggregates platform-wide signal and model health data."""
from __future__ import annotations
import json
from datetime import datetime, timezone, timedelta
from .config import get_settings

_audit_log: list[dict] = []

MILESTONE_THRESHOLDS = [1_000, 10_000, 100_000, 1_000_000]


def _valkey():
    s = get_settings()
    if not s.valkey_url: return None
    import valkey
    return valkey.from_url(s.valkey_url, decode_responses=True)


def _get_total_signals() -> int:
    from .signal_store import get_signal_count
    return get_signal_count(employer_id=None)


def _get_30day_signals() -> int:
    from .signal_store import get_signal_count
    # In production this would be a time-ranged query; for now use total as proxy
    return get_signal_count(employer_id=None)


def _get_active_consents() -> int:
    from .consent_store import _memory_store as cs
    count = 0
    for key, val in cs.items():
        if key.startswith("consent:"):
            try:
                record = json.loads(val)
                if record.get("revoked_at") is None:
                    count += 1
            except Exception:
                pass
    return count


def _get_model_accuracy_trends() -> dict:
    from .model_registry import list_model_versions, EvaluationModelType
    trends = {}
    for model_type in EvaluationModelType:
        versions = list_model_versions(model_type)
        if versions:
            latest = sorted(versions, key=lambda v: v.version)[-1]
            trends[model_type.value] = {
                "current_version": latest.version,
                "accuracy": latest.accuracy,
                "tier": _accuracy_tier(latest.accuracy),
            }
        else:
            trends[model_type.value] = {"current_version": 0, "accuracy": 0.0, "tier": "uninitialized"}
    return trends


def _accuracy_tier(accuracy: float) -> str:
    if accuracy >= 0.90: return "platinum"
    if accuracy >= 0.80: return "gold"
    if accuracy >= 0.70: return "silver"
    if accuracy >= 0.60: return "bronze"
    return "initializing"


def get_flywheel_metrics() -> dict:
    """Aggregate all flywheel metrics and check milestones."""
    total = _get_total_signals()
    now = datetime.now(timezone.utc).isoformat()

    # Detect milestone crossings
    for threshold in MILESTONE_THRESHOLDS:
        milestone_key = f"milestone_logged:{threshold}"
        already_logged = any(e.get("threshold") == threshold for e in _audit_log)
        if total >= threshold and not already_logged:
            entry = {
                "event": "flywheel_milestone",
                "threshold": threshold,
                "total_signals": total,
                "logged_at": now,
            }
            _audit_log.append(entry)

    return {
        "total_signals": total,
        "signals_last_30_days": _get_30day_signals(),
        "active_consent_records": _get_active_consents(),
        "model_accuracy_trends": _get_model_accuracy_trends(),
        "milestone_events": [e for e in _audit_log if e.get("event") == "flywheel_milestone"],
        "generated_at": now,
    }


def get_platform_health_summary() -> dict:
    """Anonymized summary visible to employers (not platform admins)."""
    metrics = get_flywheel_metrics()
    trends = metrics["model_accuracy_trends"]
    return {
        "participating_organizations": 1,   # stub — would query employer count
        "total_engineers_on_platform": metrics["active_consent_records"],
        "model_accuracy_tiers": {k: v["tier"] for k, v in trends.items()},
        "flywheel_health": "growing" if metrics["total_signals"] > 0 else "initializing",
    }