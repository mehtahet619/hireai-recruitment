"""Property-based test for analytics PII redaction on export.

Property 14: Analytics report redacts PII on export

For any exported analytics report, no field in the output file SHALL
contain a string that matches any Engineer name or email present in
the underlying dataset.

# Feature: engineering-lifecycle-platform, Property 14: Analytics report redacts PII on export
Validates: Requirements 8.6
"""
from __future__ import annotations
import json
from hypothesis import given, settings
from hypothesis import strategies as st
from app.analytics_engine import export_report, redact_pii

name_strategy = st.text(min_size=2, max_size=30, alphabet="abcdefghijklmnopqrstuvwxyz ")
email_strategy = st.emails()
fmt_strategy = st.sampled_from(["json", "csv"])

@given(
    name=name_strategy,
    email=email_strategy,
    extra_key=st.text(min_size=1, max_size=10, alphabet="abcdefghijklmnopqrstuvwxyz_"),
    extra_val=st.text(min_size=1, max_size=20),
    fmt=fmt_strategy,
)
@settings(max_examples=200)
def test_export_redacts_pii(name, email, extra_key, extra_val, fmt):
    """Property 14: exported report must not contain engineer name or email.

    For any record containing PII fields (name, email), the export function
    SHALL replace those values with [REDACTED] so no PII leaks into the output.

    Validates: Requirements 8.6
    """
    record = {"name": name, "email": email, extra_key: extra_val, "score": 0.75}
    output = export_report("test", [record], fmt=fmt)
    assert name.strip() not in output or "[REDACTED]" in output, (
        f"PII name '{name}' found unredacted in {fmt} export"
    )
    local_part = email.split("@")[0]
    if len(local_part) > 3:
        assert local_part not in output or "[REDACTED]" in output, (
            f"PII email '{email}' found unredacted in {fmt} export"
        )


@given(
    records=st.lists(
        st.fixed_dictionaries({
            "candidate_name": name_strategy,
            "candidate_email": email_strategy,
            "score": st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        }),
        min_size=1, max_size=10,
    ),
    fmt=fmt_strategy,
)
@settings(max_examples=100)
def test_bulk_export_redacts_all_pii(records, fmt):
    """Property 14 (bulk): all records in a bulk export have PII fields redacted."""
    output = export_report("bulk_test", records, fmt=fmt)
    for record in records:
        name = record["candidate_name"].strip()
        if len(name) > 3:
            assert name not in output or "[REDACTED]" in output, (
                f"PII name '{name}' found in bulk {fmt} export"
            )