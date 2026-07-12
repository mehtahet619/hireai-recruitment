"""Unit tests for backend/app/payroll_store.py."""
from __future__ import annotations

import json
import uuid
from datetime import date

import pytest

from app.payroll_store import (
    CompensationRecord,
    PayrollRun,
    PayrollValidationError,
    Payslip,
    calculate_payslip,
    complete_run,
    get_audit_log,
    get_compensation,
    get_payroll_run,
    initiate_run,
    list_employer_compensations,
    save_compensation,
    _memory_store,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _new_employer_id() -> str:
    return f"emp-{uuid.uuid4()}"


def _new_engineer_id() -> str:
    return f"eng-{uuid.uuid4()}"


def _compensation(
    engineer_id: str | None = None,
    employer_id: str | None = None,
    base_salary: float = 60_000.0,
    currency: str = "USD",
    pay_frequency: str = "monthly",
    deductions: list | None = None,
) -> CompensationRecord:
    return CompensationRecord(
        record_id=str(uuid.uuid4()),
        engineer_id=engineer_id or _new_engineer_id(),
        employer_id=employer_id or _new_employer_id(),
        base_salary=base_salary,
        currency=currency,
        pay_frequency=pay_frequency,
        effective_date="2024-01-01",
        deductions=deductions or [],
    )


# ---------------------------------------------------------------------------
# CompensationRecord save / get
# ---------------------------------------------------------------------------

class TestCompensationCRUD:
    def test_save_and_get_roundtrip(self):
        record = _compensation()
        save_compensation(record)
        fetched = get_compensation(record.employer_id, record.engineer_id)
        assert fetched is not None
        assert fetched.record_id == record.record_id
        assert fetched.engineer_id == record.engineer_id
        assert fetched.base_salary == record.base_salary
        assert fetched.currency == record.currency
        assert fetched.pay_frequency == record.pay_frequency

    def test_get_nonexistent_returns_none(self):
        result = get_compensation("no-employer", "no-engineer")
        assert result is None

    def test_overwrite_compensation(self):
        """Saving twice for the same (employer, engineer) updates the record."""
        employer_id = _new_employer_id()
        engineer_id = _new_engineer_id()
        record1 = _compensation(engineer_id=engineer_id, employer_id=employer_id, base_salary=50_000.0)
        save_compensation(record1)
        record2 = _compensation(engineer_id=engineer_id, employer_id=employer_id, base_salary=70_000.0)
        save_compensation(record2)
        fetched = get_compensation(employer_id, engineer_id)
        assert fetched.base_salary == 70_000.0

    def test_list_employer_compensations(self):
        employer_id = _new_employer_id()
        eng1, eng2 = _new_engineer_id(), _new_engineer_id()
        save_compensation(_compensation(engineer_id=eng1, employer_id=employer_id))
        save_compensation(_compensation(engineer_id=eng2, employer_id=employer_id))
        records = list_employer_compensations(employer_id)
        engineer_ids = {r.engineer_id for r in records}
        assert eng1 in engineer_ids
        assert eng2 in engineer_ids

    def test_list_employer_compensations_empty(self):
        records = list_employer_compensations(_new_employer_id())
        assert records == []


# ---------------------------------------------------------------------------
# calculate_payslip — gross and net calculations
# ---------------------------------------------------------------------------

class TestCalculatePayslip:
    PERIOD = (date(2024, 1, 1), date(2024, 1, 31))

    def test_monthly_gross_equals_base_salary(self):
        comp = _compensation(base_salary=6_000.0, pay_frequency="monthly")
        ps = calculate_payslip(comp, self.PERIOD)
        assert ps.gross_pay == 6_000.0

    def test_biweekly_gross(self):
        comp = _compensation(base_salary=52_000.0, pay_frequency="bi-weekly")
        ps = calculate_payslip(comp, self.PERIOD)
        expected = round(52_000.0 * 12 / 26, 2)
        assert abs(ps.gross_pay - expected) <= 0.01

    def test_weekly_gross(self):
        comp = _compensation(base_salary=52_000.0, pay_frequency="weekly")
        ps = calculate_payslip(comp, self.PERIOD)
        expected = round(52_000.0 * 12 / 52, 2)
        assert abs(ps.gross_pay - expected) <= 0.01

    def test_fixed_deduction(self):
        deductions = [{"name": "Health", "type": "benefit", "amount": 500.0}]
        comp = _compensation(base_salary=5_000.0, pay_frequency="monthly", deductions=deductions)
        ps = calculate_payslip(comp, self.PERIOD)
        assert ps.gross_pay == 5_000.0
        assert ps.net_pay == 4_500.0

    def test_percentage_deduction(self):
        deductions = [{"name": "Tax", "type": "tax", "pct": 20.0}]
        comp = _compensation(base_salary=5_000.0, pay_frequency="monthly", deductions=deductions)
        ps = calculate_payslip(comp, self.PERIOD)
        assert ps.gross_pay == 5_000.0
        assert abs(ps.net_pay - 4_000.0) <= 0.01

    def test_combined_deductions(self):
        deductions = [
            {"name": "Tax", "type": "tax", "pct": 20.0},
            {"name": "Health", "type": "benefit", "amount": 200.0},
        ]
        comp = _compensation(base_salary=5_000.0, pay_frequency="monthly", deductions=deductions)
        ps = calculate_payslip(comp, self.PERIOD)
        # gross = 5000, tax = 1000, health = 200, net = 3800
        assert abs(ps.net_pay - 3_800.0) <= 0.01

    def test_net_pay_clamped_to_zero(self):
        """Excessive deductions should not result in negative net pay."""
        deductions = [{"name": "Huge deduction", "type": "other", "amount": 100_000.0}]
        comp = _compensation(base_salary=1_000.0, pay_frequency="monthly", deductions=deductions)
        ps = calculate_payslip(comp, self.PERIOD)
        assert ps.net_pay == 0.0

    def test_no_deductions(self):
        comp = _compensation(base_salary=4_000.0, pay_frequency="monthly", deductions=[])
        ps = calculate_payslip(comp, self.PERIOD)
        assert ps.gross_pay == ps.net_pay

    def test_payslip_period_stored(self):
        comp = _compensation(pay_frequency="monthly")
        period = (date(2024, 3, 1), date(2024, 3, 31))
        ps = calculate_payslip(comp, period)
        assert ps.period_start == "2024-03-01"
        assert ps.period_end == "2024-03-31"

    def test_payslip_currency_matches_compensation(self):
        comp = _compensation(currency="GBP", pay_frequency="monthly")
        ps = calculate_payslip(comp, self.PERIOD)
        assert ps.currency == "GBP"

    def test_net_equals_gross_minus_sum_of_deductions(self):
        """Property: net_pay == gross_pay - sum of applied deduction amounts."""
        deductions = [
            {"name": "Tax", "type": "tax", "pct": 15.0},
            {"name": "Pension", "type": "benefit", "amount": 300.0},
        ]
        comp = _compensation(base_salary=6_000.0, pay_frequency="monthly", deductions=deductions)
        ps = calculate_payslip(comp, self.PERIOD)
        applied_sum = sum(d["_applied_amount"] for d in ps.deductions_detail)
        assert abs(ps.net_pay - (ps.gross_pay - applied_sum)) <= 0.01


# ---------------------------------------------------------------------------
# initiate_run — validation rejects invalid records
# ---------------------------------------------------------------------------

class TestInitiateRun:
    def test_rejects_zero_base_salary(self):
        employer_id = _new_employer_id()
        record = _compensation(employer_id=employer_id, base_salary=0.0)
        save_compensation(record)
        with pytest.raises(PayrollValidationError) as exc_info:
            initiate_run(employer_id, "admin-1")
        err = exc_info.value
        assert err.engineer_id == record.engineer_id
        assert err.field_name == "base_salary"

    def test_rejects_negative_base_salary(self):
        employer_id = _new_employer_id()
        record = _compensation(employer_id=employer_id, base_salary=-100.0)
        save_compensation(record)
        with pytest.raises(PayrollValidationError) as exc_info:
            initiate_run(employer_id, "admin-1")
        assert exc_info.value.field_name == "base_salary"

    def test_rejects_none_currency(self):
        employer_id = _new_employer_id()
        record = _compensation(employer_id=employer_id, currency=None)
        save_compensation(record)
        with pytest.raises(PayrollValidationError) as exc_info:
            initiate_run(employer_id, "admin-1")
        assert exc_info.value.field_name == "currency"

    def test_rejects_empty_currency(self):
        employer_id = _new_employer_id()
        record = _compensation(employer_id=employer_id, currency="")
        save_compensation(record)
        with pytest.raises(PayrollValidationError) as exc_info:
            initiate_run(employer_id, "admin-1")
        assert exc_info.value.field_name == "currency"

    def test_rejects_invalid_pay_frequency(self):
        employer_id = _new_employer_id()
        record = _compensation(employer_id=employer_id, pay_frequency="quarterly")
        save_compensation(record)
        with pytest.raises(PayrollValidationError) as exc_info:
            initiate_run(employer_id, "admin-1")
        assert exc_info.value.field_name == "pay_frequency"

    def test_failed_run_saved_on_validation_error(self):
        """When validation fails the run is persisted with status 'failed'."""
        employer_id = _new_employer_id()
        record = _compensation(employer_id=employer_id, base_salary=0.0)
        save_compensation(record)
        with pytest.raises(PayrollValidationError):
            initiate_run(employer_id, "admin-1")
        # Find the failed run
        from app.payroll_store import list_employer_payroll_runs
        runs = list_employer_payroll_runs(employer_id)
        assert len(runs) == 1
        assert runs[0].status == "failed"

    def test_failed_run_produces_no_payslips(self):
        """No payslips should be produced when validation fails."""
        employer_id = _new_employer_id()
        # One valid, one invalid record
        valid_record = _compensation(employer_id=employer_id, base_salary=5_000.0)
        invalid_record = _compensation(employer_id=employer_id, base_salary=0.0)
        save_compensation(valid_record)
        save_compensation(invalid_record)
        with pytest.raises(PayrollValidationError):
            initiate_run(employer_id, "admin-1")
        from app.payroll_store import list_employer_payroll_runs
        runs = list_employer_payroll_runs(employer_id)
        assert len(runs) == 1
        assert runs[0].payslips == []

    def test_successful_run_produces_payslips(self):
        employer_id = _new_employer_id()
        eng1, eng2 = _new_engineer_id(), _new_engineer_id()
        save_compensation(_compensation(engineer_id=eng1, employer_id=employer_id, base_salary=6_000.0))
        save_compensation(_compensation(engineer_id=eng2, employer_id=employer_id, base_salary=5_000.0))
        run = initiate_run(employer_id, "admin-1")
        assert run.status == "pending"
        assert len(run.payslips) == 2
        assert run.total_gross == pytest.approx(11_000.0, abs=0.01)

    def test_payslips_have_correct_run_id(self):
        employer_id = _new_employer_id()
        save_compensation(_compensation(employer_id=employer_id, base_salary=4_000.0))
        run = initiate_run(employer_id, "admin-1")
        for ps in run.payslips:
            assert ps.run_id == run.run_id

    def test_error_message_is_json_serializable(self):
        employer_id = _new_employer_id()
        record = _compensation(employer_id=employer_id, base_salary=0.0)
        save_compensation(record)
        with pytest.raises(PayrollValidationError) as exc_info:
            initiate_run(employer_id, "admin-1")
        # The str() of the error should be valid JSON with required keys
        payload = json.loads(str(exc_info.value))
        assert "engineer_id" in payload
        assert "field" in payload
        assert "message" in payload

    def test_empty_employer_has_no_run_payslips(self):
        employer_id = _new_employer_id()
        run = initiate_run(employer_id, "admin-1")
        assert run.status == "pending"
        assert run.payslips == []
        assert run.total_gross == 0.0


# ---------------------------------------------------------------------------
# complete_run — status and audit log
# ---------------------------------------------------------------------------

class TestCompleteRun:
    def test_complete_sets_status_and_timestamp(self):
        employer_id = _new_employer_id()
        save_compensation(_compensation(employer_id=employer_id, base_salary=5_000.0))
        run = initiate_run(employer_id, "admin-1")
        completed = complete_run(run.run_id)
        assert completed.status == "completed"
        assert completed.completed_at is not None

    def test_complete_creates_audit_log(self):
        employer_id = _new_employer_id()
        save_compensation(_compensation(employer_id=employer_id, base_salary=4_500.0))
        run = initiate_run(employer_id, "admin-1")
        complete_run(run.run_id)
        audit = get_audit_log(run.run_id)
        assert audit is not None
        assert audit["run_id"] == run.run_id
        assert audit["status"] == "completed"
        assert audit["employer_id"] == employer_id

    def test_audit_log_contains_initiator(self):
        employer_id = _new_employer_id()
        save_compensation(_compensation(employer_id=employer_id, base_salary=4_000.0))
        run = initiate_run(employer_id, "initiator-xyz")
        complete_run(run.run_id)
        audit = get_audit_log(run.run_id)
        assert audit["initiated_by"] == "initiator-xyz"

    def test_audit_log_contains_total_gross(self):
        employer_id = _new_employer_id()
        save_compensation(_compensation(employer_id=employer_id, base_salary=6_000.0))
        run = initiate_run(employer_id, "admin-1")
        complete_run(run.run_id)
        audit = get_audit_log(run.run_id)
        assert audit["total_gross"] == pytest.approx(6_000.0, abs=0.01)

    def test_complete_run_not_found_raises(self):
        with pytest.raises(ValueError, match="not found"):
            complete_run("nonexistent-run-id")

    def test_complete_persists_run(self):
        employer_id = _new_employer_id()
        save_compensation(_compensation(employer_id=employer_id, base_salary=3_000.0))
        run = initiate_run(employer_id, "admin-1")
        complete_run(run.run_id)
        reloaded = get_payroll_run(run.run_id)
        assert reloaded.status == "completed"
        assert reloaded.completed_at is not None

    def test_audit_log_has_payslip_count(self):
        employer_id = _new_employer_id()
        eng1, eng2 = _new_engineer_id(), _new_engineer_id()
        save_compensation(_compensation(engineer_id=eng1, employer_id=employer_id, base_salary=4_000.0))
        save_compensation(_compensation(engineer_id=eng2, employer_id=employer_id, base_salary=5_000.0))
        run = initiate_run(employer_id, "admin-1")
        complete_run(run.run_id)
        audit = get_audit_log(run.run_id)
        assert audit["payslip_count"] == 2
