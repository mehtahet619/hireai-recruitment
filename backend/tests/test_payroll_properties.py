"""Property-based tests for the Payroll module (Task 5.2).

Properties tested:
  Property 7: Payslip gross = sum of compensation components

    For any CompensationRecord and pay period, the gross_pay in the resulting
    Payslip SHALL equal the pro-rated base salary for that period, with an
    absolute tolerance of 0.01 in the configured currency.

  Property 8: Payslip net = gross minus deductions

    For any Payslip, net_pay SHALL equal gross_pay minus the sum of all
    deduction amounts in deductions_detail, with an absolute tolerance of
    0.01 in the configured currency.

# Feature: engineering-lifecycle-platform, Property 7: Payslip gross = sum of compensation components
# Feature: engineering-lifecycle-platform, Property 8: Payslip net = gross minus deductions
Validates: Requirements 5.2
"""
from __future__ import annotations

import uuid
from datetime import date

from hypothesis import given, settings
from hypothesis import strategies as st

from app.payroll_store import (
    CompensationRecord,
    _memory_store,
    calculate_payslip,
)

# ---------------------------------------------------------------------------
# Fixed pay period for all tests
# ---------------------------------------------------------------------------

PERIOD = (date(2024, 1, 1), date(2024, 1, 31))

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Base salary: positive, finite float up to 10 million
base_salary_strategy = st.floats(
    min_value=0.01,
    max_value=10_000_000,
    allow_nan=False,
    allow_infinity=False,
)

# Pay frequency: one of the three supported values
pay_frequency_strategy = st.sampled_from(["monthly", "bi-weekly", "weekly"])

# A single deduction as a fixed-amount or percentage entry
_fixed_deduction_strategy = st.fixed_dictionaries({
    "name": st.just("deduction"),
    "type": st.just("benefit"),
    "amount": st.floats(min_value=0.0, max_value=1_000_000, allow_nan=False, allow_infinity=False),
})

_pct_deduction_strategy = st.fixed_dictionaries({
    "name": st.just("deduction"),
    "type": st.just("tax"),
    "pct": st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
})

deductions_strategy = st.lists(
    st.one_of(_fixed_deduction_strategy, _pct_deduction_strategy),
    min_size=0,
    max_size=5,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _expected_gross(base_salary: float, pay_frequency: str) -> float:
    """Return the expected pro-rated gross pay for the given frequency."""
    if pay_frequency == "monthly":
        return base_salary
    elif pay_frequency == "bi-weekly":
        return base_salary * 12 / 26
    elif pay_frequency == "weekly":
        return base_salary * 12 / 52
    raise ValueError(f"Unknown pay_frequency: {pay_frequency}")


def _make_comp(base_salary: float, pay_frequency: str, deductions: list[dict]) -> CompensationRecord:
    return CompensationRecord(
        record_id=str(uuid.uuid4()),
        engineer_id=str(uuid.uuid4()),
        employer_id=str(uuid.uuid4()),
        base_salary=base_salary,
        currency="USD",
        pay_frequency=pay_frequency,
        effective_date="2024-01-01",
        deductions=deductions,
    )


# ---------------------------------------------------------------------------
# Property 7: Payslip gross = pro-rated salary
#
# For any CompensationRecord and pay period, the gross_pay in the resulting
# Payslip SHALL equal the pro-rated base salary for that period, with an
# absolute tolerance of 0.01 in the configured currency.
#
# Feature: engineering-lifecycle-platform, Property 7: Payslip gross = sum of compensation components
# Validates: Requirements 5.2
# ---------------------------------------------------------------------------

@given(
    base_salary=base_salary_strategy,
    pay_frequency=pay_frequency_strategy,
    deductions=deductions_strategy,
)
@settings(max_examples=200)
def test_payslip_gross_equals_prorated_salary(
    base_salary: float,
    pay_frequency: str,
    deductions: list[dict],
) -> None:
    """Property 7: gross_pay equals the pro-rated base salary for the pay frequency.

    The gross is independent of deductions; it depends only on base_salary and
    pay_frequency according to the formula:
      monthly:   gross = base_salary
      bi-weekly: gross = base_salary * 12 / 26
      weekly:    gross = base_salary * 12 / 52

    Validates: Requirements 5.2
    """
    _memory_store.clear()

    comp = _make_comp(base_salary, pay_frequency, deductions)
    payslip = calculate_payslip(comp, PERIOD)

    expected = _expected_gross(base_salary, pay_frequency)

    assert abs(payslip.gross_pay - expected) <= 0.01, (
        f"gross_pay mismatch: got {payslip.gross_pay}, expected {expected} "
        f"(base_salary={base_salary}, pay_frequency={pay_frequency!r})"
    )


# ---------------------------------------------------------------------------
# Property 8: Payslip net = gross minus deductions
#
# For any Payslip, net_pay SHALL equal gross_pay minus the sum of all
# deduction amounts in deductions_detail, with an absolute tolerance of
# 0.01 in the configured currency. net_pay is clamped to 0.
#
# Feature: engineering-lifecycle-platform, Property 8: Payslip net = gross minus deductions
# Validates: Requirements 5.2
# ---------------------------------------------------------------------------

@given(
    base_salary=base_salary_strategy,
    pay_frequency=pay_frequency_strategy,
    deductions=deductions_strategy,
)
@settings(max_examples=200)
def test_payslip_net_equals_gross_minus_deductions(
    base_salary: float,
    pay_frequency: str,
    deductions: list[dict],
) -> None:
    """Property 8: net_pay equals gross_pay minus sum of applied deduction amounts, clamped to 0.

    For every deduction entry in deductions_detail, _applied_amount holds the
    actual amount subtracted. The net_pay must satisfy:

        net_pay == max(0, gross_pay - sum(_applied_amount for each deduction))

    Validates: Requirements 5.2
    """
    _memory_store.clear()

    comp = _make_comp(base_salary, pay_frequency, deductions)
    payslip = calculate_payslip(comp, PERIOD)

    total_deductions = sum(d["_applied_amount"] for d in payslip.deductions_detail)
    expected_net = max(0.0, payslip.gross_pay - total_deductions)

    assert abs(payslip.net_pay - expected_net) <= 0.01, (
        f"net_pay mismatch: got {payslip.net_pay}, expected {expected_net} "
        f"(gross_pay={payslip.gross_pay}, total_deductions={total_deductions})"
    )
