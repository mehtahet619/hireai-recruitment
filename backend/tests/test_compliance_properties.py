"""Property-based test for the Compliance module.

Property 13: Compliance alert generated for every rule violation

For any employer_id and configured ComplianceRule, if the evaluated work data
for an Engineer satisfies the rule's trigger_condition, then evaluate_rules
SHALL include a ComplianceAlert for that rule and that Engineer's
pseudonymous_id in its output.

# Feature: engineering-lifecycle-platform, Property 13: Compliance alert generated for every rule violation
Validates: Requirements 7.2
"""
from __future__ import annotations

import uuid

from hypothesis import given, settings
from hypothesis import strategies as st

from app.compliance_store import (
    ComplianceAlert,
    ComplianceRule,
    _memory_store,
    evaluate_rules,
    save_rule,
)

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

OPS = ["gt", "gte", "lt", "lte"]

# A threshold and a value that is guaranteed to satisfy the operator
def _violating_value(op: str, threshold: float) -> float:
    if op == "gt":
        return threshold + 1.0
    if op == "gte":
        return threshold
    if op == "lt":
        return threshold - 1.0
    if op == "lte":
        return threshold
    return threshold + 1.0


threshold_strategy = st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False)
op_strategy = st.sampled_from(OPS)
field_strategy = st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Ll",)))
severity_strategy = st.sampled_from(["info", "warning", "critical"])
category_strategy = st.sampled_from(["working_hours", "leave", "data_privacy", "pay_equity"])


# ---------------------------------------------------------------------------
# Property 13: Compliance alert generated for every rule violation
#
# Feature: engineering-lifecycle-platform, Property 13: Compliance alert generated for every rule violation
# Validates: Requirements 7.2
# ---------------------------------------------------------------------------

@given(
    field=field_strategy,
    op=op_strategy,
    threshold=threshold_strategy,
    severity=severity_strategy,
    category=category_strategy,
)
@settings(max_examples=200)
def test_compliance_alert_generated_for_every_violation(
    field: str,
    op: str,
    threshold: float,
    severity: str,
    category: str,
) -> None:
    """Property 13: evaluate_rules generates a ComplianceAlert for every engineer
    whose work data satisfies the rule's trigger_condition.

    For any configured ComplianceRule with a trigger_condition, and any engineer
    whose work_data satisfies that condition, the resulting alert list MUST
    contain an alert with matching rule_id and pseudonymous_engineer_id.

    Validates: Requirements 7.2
    """
    _memory_store.clear()

    employer_id = str(uuid.uuid4())
    pseudo_id = str(uuid.uuid4())

    # Create a rule that WILL be violated by the work data below
    rule = ComplianceRule(
        rule_id=str(uuid.uuid4()),
        employer_id=employer_id,
        name="test-rule",
        jurisdiction="test",
        category=category,
        trigger_condition={"field": field, "op": op, "threshold": threshold},
        severity=severity,
        notification_recipients=[],
    )
    save_rule(rule)

    # Construct work data that violates the rule
    violating_value = _violating_value(op, threshold)
    work_data = {pseudo_id: {field: violating_value}}

    alerts = evaluate_rules(employer_id, work_data)

    # There must be exactly one alert for this engineer and rule
    matching = [
        a for a in alerts
        if a.rule_id == rule.rule_id and a.pseudonymous_engineer_id == pseudo_id
    ]
    assert len(matching) >= 1, (
        f"Expected alert for rule {rule.rule_id} and engineer {pseudo_id}, "
        f"got alerts: {alerts}"
    )
    assert matching[0].status == "open"
    assert matching[0].severity == severity
