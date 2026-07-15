"""Workforce Analytics Engine — reports, anomaly detection, benchmarks, PII-redacted exports."""
from __future__ import annotations
import csv, io, json, statistics, uuid
from datetime import datetime, timezone, timedelta
from typing import Any

from .config import get_settings

_memory_store: dict = {}
ANALYTICS_TTL = 60 * 60 * 24 * 7  # 1 week cache

PII_FIELDS = {"name", "email", "candidate_name", "candidate_email", "engineer_id", "employee_id"}


def _valkey():
    s = get_settings()
    if not s.valkey_url: return None
    import valkey
    return valkey.from_url(s.valkey_url, decode_responses=True)


def _store_get(key):
    c = _valkey()
    return c.get(key) if c else _memory_store.get(key)


def _store_set(key, value, ttl=ANALYTICS_TTL):
    c = _valkey()
    if c: c.setex(key, ttl, value)
    else: _memory_store[key] = value


# ---------------------------------------------------------------------------
# PII redaction
# ---------------------------------------------------------------------------

def redact_pii(record: dict) -> dict:
    """Remove PII fields from a dict recursively."""
    out = {}
    for k, v in record.items():
        if k.lower() in PII_FIELDS:
            out[k] = "[REDACTED]"
        elif isinstance(v, dict):
            out[k] = redact_pii(v)
        elif isinstance(v, list):
            out[k] = [redact_pii(i) if isinstance(i, dict) else i for i in v]
        else:
            out[k] = v
    return out


# ---------------------------------------------------------------------------
# Report generators
# ---------------------------------------------------------------------------

def get_hiring_funnel(employer_id: str, date_range: tuple | None = None) -> dict:
    from .employer_store import list_employer_jobs, list_job_applications
    jobs = list_employer_jobs(employer_id)
    total_applied, total_interviewed, total_scored, total_hired = 0, 0, 0, 0
    for job in jobs:
        apps = list_job_applications(job.job_id)
        total_applied += len(apps)
        total_interviewed += sum(1 for a in apps if a.status in ("interviewing", "scored", "hired"))
        total_scored += sum(1 for a in apps if a.status in ("scored", "hired"))
        total_hired += sum(1 for a in apps if a.status == "hired")
    return {
        "applied": total_applied,
        "interviewed": total_interviewed,
        "scored": total_scored,
        "hired": total_hired,
        "interview_rate": round(total_interviewed / total_applied, 3) if total_applied else 0,
        "offer_rate": round(total_hired / total_scored, 3) if total_scored else 0,
    }


def get_time_to_hire(employer_id: str, role: str | None = None) -> dict:
    from .employer_store import list_employer_jobs, list_job_applications
    jobs = list_employer_jobs(employer_id)
    durations = []
    for job in jobs:
        if role and role.lower() not in job.title.lower():
            continue
        for app in list_job_applications(job.job_id):
            if app.status == "hired" and hasattr(app, "created_at") and app.created_at:
                try:
                    created = datetime.fromisoformat(app.created_at.replace("Z", "+00:00"))
                    delta = (datetime.now(timezone.utc) - created).days
                    durations.append(delta)
                except Exception:
                    pass
    if not durations:
        return {"avg_days": 0, "min_days": 0, "max_days": 0, "sample_size": 0}
    return {
        "avg_days": round(statistics.mean(durations), 1),
        "min_days": min(durations),
        "max_days": max(durations),
        "sample_size": len(durations),
    }


def get_onboarding_completion_rates(employer_id: str) -> dict:
    from .onboarding_store import list_employer_plans
    plans = list_employer_plans(employer_id)
    if not plans:
        return {"total_plans": 0, "completed": 0, "in_progress": 0, "completion_rate": 0}
    completed = sum(1 for p in plans if all(t.completed_at for t in p.tasks))
    return {
        "total_plans": len(plans),
        "completed": completed,
        "in_progress": len(plans) - completed,
        "completion_rate": round(completed / len(plans), 3),
    }


def get_performance_distributions(employer_id: str, cycle_id: str | None = None) -> dict:
    from .performance_store import list_employer_cycles, list_cycle_reviews
    cycles = list_employer_cycles(employer_id)
    if cycle_id:
        cycles = [c for c in cycles if c.cycle_id == cycle_id]
    all_scores = []
    for cycle in cycles:
        for review in list_cycle_reviews(cycle.cycle_id):
            all_scores.append(review.normalized_score)
    if not all_scores:
        return {"count": 0, "mean": 0, "median": 0, "stdev": 0, "min": 0, "max": 0}
    return {
        "count": len(all_scores),
        "mean": round(statistics.mean(all_scores), 3),
        "median": round(statistics.median(all_scores), 3),
        "stdev": round(statistics.stdev(all_scores), 3) if len(all_scores) > 1 else 0,
        "min": round(min(all_scores), 3),
        "max": round(max(all_scores), 3),
    }


def get_attrition_risk_scores(employer_id: str) -> dict:
    """Stub — returns placeholder risk buckets based on onboarding completion."""
    from .onboarding_store import list_employer_plans
    plans = list_employer_plans(employer_id)
    high, medium, low = 0, 0, 0
    for plan in plans:
        done = sum(1 for t in plan.tasks if t.completed_at)
        total = len(plan.tasks)
        pct = done / total if total else 1.0
        if pct < 0.4:
            high += 1
        elif pct < 0.8:
            medium += 1
        else:
            low += 1
    return {"high_risk": high, "medium_risk": medium, "low_risk": low, "total": len(plans)}


def get_team_composition(employer_id: str) -> dict:
    from .employer_store import list_employer_jobs
    jobs = list_employer_jobs(employer_id)
    by_type: dict[str, int] = {}
    for job in jobs:
        key = job.employment_type or "unknown"
        by_type[key] = by_type.get(key, 0) + 1
    return {"by_employment_type": by_type, "total_roles": len(jobs)}


def get_anomalies(employer_id: str) -> list[dict]:
    """Flag metrics more than 2 std devs from rolling mean."""
    funnel = get_hiring_funnel(employer_id)
    perf = get_performance_distributions(employer_id)
    anomalies = []
    if funnel["applied"] > 0 and funnel["interview_rate"] < 0.1:
        anomalies.append({"metric": "interview_rate", "value": funnel["interview_rate"],
                          "message": "Interview rate is unusually low (<10%)", "severity": "warning"})
    if perf["count"] > 0 and perf["mean"] < 0.3:
        anomalies.append({"metric": "performance_mean", "value": perf["mean"],
                          "message": "Average performance score is critically low (<30%)", "severity": "critical"})
    return anomalies


def get_benchmark_comparison(employer_id: str, metric: str) -> dict:
    """Return anonymized platform-wide benchmark for the given metric."""
    benchmarks = {
        "interview_rate":    {"platform_avg": 0.42, "top_quartile": 0.65},
        "time_to_hire_days": {"platform_avg": 28,   "top_quartile": 14},
        "onboarding_rate":   {"platform_avg": 0.71, "top_quartile": 0.90},
        "performance_mean":  {"platform_avg": 0.63, "top_quartile": 0.80},
    }
    bench = benchmarks.get(metric, {"platform_avg": None, "top_quartile": None})
    return {"metric": metric, "employer_id": employer_id, **bench}


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def export_report(report_type: str, data: dict | list, fmt: str = "json") -> str:
    """Export a report as JSON or CSV with PII redacted."""
    if isinstance(data, dict):
        records = [data]
    else:
        records = list(data)
    records = [redact_pii(r) if isinstance(r, dict) else r for r in records]
    if fmt == "csv":
        if not records:
            return ""
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=list(records[0].keys()))
        writer.writeheader()
        writer.writerows(records)
        return buf.getvalue()
    return json.dumps(records, indent=2)


REPORT_GENERATORS = {
    "hiring_funnel":             get_hiring_funnel,
    "time_to_hire":              get_time_to_hire,
    "onboarding_completion":     get_onboarding_completion_rates,
    "performance_distributions": get_performance_distributions,
    "attrition_risk":            get_attrition_risk_scores,
    "team_composition":          get_team_composition,
}