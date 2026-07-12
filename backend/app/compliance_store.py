"""Compliance module."""
from __future__ import annotations
import json, uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Optional
from .config import get_settings

_memory_store: dict = {}
COMPLIANCE_TTL = 60 * 60 * 24 * 365 * 7

def _valkey():
    s = get_settings()
    if not s.valkey_url:
        return None
    import valkey
    return valkey.from_url(s.valkey_url, decode_responses=True)

def _store_get(key):
    c = _valkey()
    return c.get(key) if c else _memory_store.get(key)

def _store_set(key, value):
    c = _valkey()
    if c:
        c.setex(key, COMPLIANCE_TTL, value)
    else:
        _memory_store[key] = value

def _store_get_list(key):
    raw = _store_get(key)
    return json.loads(raw) if raw else []

def _store_append_list(key, item):
    lst = _store_get_list(key)
    if item not in lst:
        lst.append(item)
    _store_set(key, json.dumps(lst))

@dataclass
class ComplianceRule:
    rule_id: str
    employer_id: str
    name: str
    jurisdiction: str
    category: str
    trigger_condition: dict
    severity: str
    notification_recipients: list
    is_template: bool = False

@dataclass
class ComplianceAlert:
    alert_id: str
    rule_id: str
    employer_id: str
    pseudonymous_engineer_id: str
    severity: str
    recommended_action: str
    status: str
    created_at: str
    resolved_at: Optional[str] = None
    resolved_by: Optional[str] = None

def save_rule(rule):
    _store_set(f"compliance_rule:{rule.rule_id}", json.dumps(asdict(rule)))
    _store_append_list(f"employer_compliance_rules:{rule.employer_id}", rule.rule_id)

def get_rule(rule_id):
    raw = _store_get(f"compliance_rule:{rule_id}")
    return ComplianceRule(**json.loads(raw)) if raw else None

def list_employer_rules(employer_id):
    return [r for rid in _store_get_list(f"employer_compliance_rules:{employer_id}") if (r := get_rule(rid))]

def save_alert(alert):
    _store_set(f"compliance_alert:{alert.alert_id}", json.dumps(asdict(alert)))
    _store_append_list(f"employer_compliance_alerts:{alert.employer_id}", alert.alert_id)

def get_alert(alert_id):
    raw = _store_get(f"compliance_alert:{alert_id}")
    return ComplianceAlert(**json.loads(raw)) if raw else None

def list_employer_alerts(employer_id):
    alerts = [a for aid in _store_get_list(f"employer_compliance_alerts:{employer_id}") if (a := get_alert(aid))]
    alerts.sort(key=lambda a: (0 if a.status == "open" else 1, a.created_at))
    return alerts

def resolve_alert(alert_id, resolver_id):
    alert = get_alert(alert_id)
    if not alert:
        raise ValueError(f"Alert not found: {alert_id}")
    alert.status = "resolved"
    alert.resolved_at = datetime.now(timezone.utc).isoformat()
    alert.resolved_by = resolver_id
    save_alert(alert)
    return alert

def _evaluate_condition(condition, work_data):
    field, op = condition.get("field", ""), condition.get("op", "")
    threshold, value = condition.get("threshold"), work_data.get(field)
    if value is None or threshold is None:
        return False
    try:
        value, threshold = float(value), float(threshold)
    except (TypeError, ValueError):
        return False
    return {"gt": value > threshold, "gte": value >= threshold,
            "lt": value < threshold, "lte": value <= threshold,
            "eq": value == threshold, "neq": value != threshold}.get(op, False)

def _recommended_action(rule):
    return {"working_hours": "Review scheduled hours and adjust workload.",
            "leave": "Verify leave entitlement compliance with HR.",
            "data_privacy": "Initiate data review workflow and notify DPO.",
            "pay_equity": "Conduct pay equity audit."}.get(
        rule.category, "Review and remediate the compliance violation.")

def evaluate_rules(employer_id, work_data_by_engineer):
    alerts = []
    for rule in list_employer_rules(employer_id):
        for pseudo_id, work_data in work_data_by_engineer.items():
            if _evaluate_condition(rule.trigger_condition, work_data):
                alert = ComplianceAlert(
                    alert_id=str(uuid.uuid4()), rule_id=rule.rule_id,
                    employer_id=employer_id, pseudonymous_engineer_id=pseudo_id,
                    severity=rule.severity, recommended_action=_recommended_action(rule),
                    status="open", created_at=datetime.now(timezone.utc).isoformat(),
                )
                save_alert(alert)
                alerts.append(alert)
    return alerts

JURISDICTION_TEMPLATES = [
    {"name":"US FLSA — Overtime threshold","jurisdiction":"US_federal","category":"working_hours","trigger_condition":{"field":"weekly_hours","op":"gt","threshold":40},"severity":"warning"},
    {"name":"US FMLA — Leave entitlement","jurisdiction":"US_federal","category":"leave","trigger_condition":{"field":"leave_days_taken","op":"gt","threshold":60},"severity":"info"},
    {"name":"US Pay Equity — Gender pay gap","jurisdiction":"US_federal","category":"pay_equity","trigger_condition":{"field":"pay_gap_pct","op":"gt","threshold":20},"severity":"critical"},
    {"name":"UK Working Time Regulations — 48h limit","jurisdiction":"UK","category":"working_hours","trigger_condition":{"field":"weekly_hours","op":"gt","threshold":48},"severity":"critical"},
    {"name":"UK Annual Leave — Minimum entitlement","jurisdiction":"UK","category":"leave","trigger_condition":{"field":"leave_days_remaining","op":"lt","threshold":0},"severity":"warning"},
    {"name":"UK GDPR — Data retention period","jurisdiction":"UK","category":"data_privacy","trigger_condition":{"field":"data_age_days","op":"gt","threshold":730},"severity":"critical"},
    {"name":"India Factories Act — Weekly hours","jurisdiction":"India","category":"working_hours","trigger_condition":{"field":"weekly_hours","op":"gt","threshold":48},"severity":"warning"},
    {"name":"India Maternity Benefit Act — Leave","jurisdiction":"India","category":"leave","trigger_condition":{"field":"maternity_leave_days","op":"lt","threshold":26},"severity":"critical"},
    {"name":"India PDPB — Data retention","jurisdiction":"India","category":"data_privacy","trigger_condition":{"field":"data_age_days","op":"gt","threshold":365},"severity":"warning"},
]

def seed_templates(employer_id):
    seeded = []
    for tmpl in JURISDICTION_TEMPLATES:
        rule = ComplianceRule(
            rule_id=str(uuid.uuid4()), employer_id=employer_id,
            name=tmpl["name"], jurisdiction=tmpl["jurisdiction"],
            category=tmpl["category"], trigger_condition=tmpl["trigger_condition"],
            severity=tmpl["severity"], notification_recipients=[], is_template=True,
        )
        save_rule(rule)
        seeded.append(rule)
    return seeded