"""Payroll module — compensation records, payroll runs, and payslips (Valkey or memory)."""
from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from typing import Optional

from .config import get_settings

# ---------------------------------------------------------------------------
# In-memory fallback store
# ---------------------------------------------------------------------------
_memory_store: dict[str, str] = {}

PAYROLL_TTL = 60 * 60 * 24 * 365 * 7  # 7 years (payroll records retained long-term)

VALID_PAY_FREQUENCIES = {"monthly", "bi-weekly", "weekly"}


def _valkey():
    settings = get_settings()
    if not settings.valkey_url:
        return None
    import valkey
    return valkey.from_url(settings.valkey_url, decode_responses=True)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class PayrollValidationError(ValueError):
    """Raised when a compensation record contains missing or invalid fields."""

    def __init__(self, engineer_id: str, field_name: str, message: str):
        self.engineer_id = engineer_id
        self.field_name = field_name
        self.message = message
        super().__init__(
            json.dumps({"engineer_id": engineer_id, "field": field_name, "message": message})
        )


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class CompensationRecord:
    record_id: str
    engineer_id: str
    employer_id: str
    base_salary: float
    currency: str
    pay_frequency: str          # monthly | bi-weekly | weekly
    effective_date: str         # ISO-8601 date string YYYY-MM-DD
    deductions: list[dict]      # [{name, type, amount | pct}]


@dataclass
class Payslip:
    payslip_id: str
    engineer_id: str
    run_id: str
    gross_pay: float
    deductions_detail: list[dict]
    net_pay: float
    currency: str
    period_start: str           # ISO-8601 date string
    period_end: str             # ISO-8601 date string


@dataclass
class PayrollRun:
    run_id: str
    employer_id: str
    initiated_by: str
    initiated_at: str           # ISO-8601 UTC
    status: str                 # pending | completed | failed
    payslips: list[Payslip]
    total_gross: float
    completed_at: Optional[str] = None   # ISO-8601 UTC, None until completed


# ---------------------------------------------------------------------------
# Storage key helpers
# ---------------------------------------------------------------------------

def _compensation_key(employer_id: str, engineer_id: str) -> str:
    return f"compensation:{employer_id}:{engineer_id}"


def _employer_compensations_key(employer_id: str) -> str:
    return f"employer_compensations:{employer_id}"


def _payroll_run_key(run_id: str) -> str:
    return f"payroll_run:{run_id}"


def _employer_payroll_runs_key(employer_id: str) -> str:
    return f"employer_payroll_runs:{employer_id}"


def _payroll_audit_log_key(run_id: str) -> str:
    return f"payroll_audit_log:{run_id}"


# ---------------------------------------------------------------------------
# Generic get/set helpers
# ---------------------------------------------------------------------------

def _store_get(key: str) -> str | None:
    client = _valkey()
    if client:
        return client.get(key)
    return _memory_store.get(key)


def _store_set(key: str, value: str) -> None:
    client = _valkey()
    if client:
        client.setex(key, PAYROLL_TTL, value)
    else:
        _memory_store[key] = value


def _store_get_list(key: str) -> list[str]:
    raw = _store_get(key)
    if not raw:
        return []
    return json.loads(raw)


def _store_append_to_list(key: str, item: str) -> None:
    existing = _store_get_list(key)
    if item not in existing:
        existing.append(item)
    _store_set(key, json.dumps(existing))


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def _serialize_payslip(ps: Payslip) -> dict:
    return asdict(ps)


def _deserialize_payslip(data: dict) -> Payslip:
    return Payslip(
        payslip_id=data["payslip_id"],
        engineer_id=data["engineer_id"],
        run_id=data["run_id"],
        gross_pay=data["gross_pay"],
        deductions_detail=data["deductions_detail"],
        net_pay=data["net_pay"],
        currency=data["currency"],
        period_start=data["period_start"],
        period_end=data["period_end"],
    )


def _serialize_run(run: PayrollRun) -> str:
    d = asdict(run)
    return json.dumps(d)


def _deserialize_run(raw: str) -> PayrollRun:
    d = json.loads(raw)
    d["payslips"] = [_deserialize_payslip(ps) for ps in d.get("payslips", [])]
    return PayrollRun(**d)


def _serialize_compensation(record: CompensationRecord) -> str:
    return json.dumps(asdict(record))


def _deserialize_compensation(raw: str) -> CompensationRecord:
    d = json.loads(raw)
    return CompensationRecord(**d)


# ---------------------------------------------------------------------------
# Compensation CRUD
# ---------------------------------------------------------------------------

def save_compensation(record: CompensationRecord) -> None:
    """Persist a CompensationRecord (create or overwrite)."""
    key = _compensation_key(record.employer_id, record.engineer_id)
    _store_set(key, _serialize_compensation(record))
    # Track all engineer IDs for this employer
    _store_append_to_list(_employer_compensations_key(record.employer_id), record.engineer_id)


def get_compensation(employer_id: str, engineer_id: str) -> CompensationRecord | None:
    raw = _store_get(_compensation_key(employer_id, engineer_id))
    if not raw:
        return None
    return _deserialize_compensation(raw)


def list_employer_compensations(employer_id: str) -> list[CompensationRecord]:
    engineer_ids = _store_get_list(_employer_compensations_key(employer_id))
    records = []
    for eid in engineer_ids:
        r = get_compensation(employer_id, eid)
        if r:
            records.append(r)
    return records


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _validate_compensation_record(record: CompensationRecord) -> None:
    """
    Raise PayrollValidationError if the record contains any invalid field.

    Rules:
      - base_salary must be a positive number (not None, not <= 0, not non-numeric)
      - currency must be a non-empty string
      - pay_frequency must be one of "monthly", "bi-weekly", "weekly"
    """
    # Validate base_salary
    try:
        salary = float(record.base_salary)
    except (TypeError, ValueError):
        raise PayrollValidationError(
            record.engineer_id,
            "base_salary",
            "base_salary must be a positive number",
        )
    if salary <= 0:
        raise PayrollValidationError(
            record.engineer_id,
            "base_salary",
            "base_salary must be greater than zero",
        )

    # Validate currency
    if not record.currency or not str(record.currency).strip():
        raise PayrollValidationError(
            record.engineer_id,
            "currency",
            "currency must not be empty",
        )

    # Validate pay_frequency
    if record.pay_frequency not in VALID_PAY_FREQUENCIES:
        raise PayrollValidationError(
            record.engineer_id,
            "pay_frequency",
            f"pay_frequency must be one of {sorted(VALID_PAY_FREQUENCIES)}",
        )


# ---------------------------------------------------------------------------
# Payslip calculation
# ---------------------------------------------------------------------------

def calculate_payslip(comp: CompensationRecord, period: tuple[date, date]) -> Payslip:
    """
    Produce a Payslip for the given CompensationRecord and pay period.

    Gross pay is pro-rated based on pay_frequency:
      - monthly:   gross = base_salary (one calendar month)
      - bi-weekly: gross = base_salary * 12 / 26
      - weekly:    gross = base_salary * 12 / 52

    Deductions are applied in order:
      - Fixed amount deduction: {"amount": <float>, ...}
      - Percentage deduction:   {"pct": <float>, ...}  → deducts gross * pct / 100

    net_pay = gross - sum(deductions), clamped to 0.
    """
    period_start, period_end = period

    # Calculate gross pay based on pay frequency
    if comp.pay_frequency == "monthly":
        gross_pay = comp.base_salary
    elif comp.pay_frequency == "bi-weekly":
        gross_pay = comp.base_salary * 12 / 26
    elif comp.pay_frequency == "weekly":
        gross_pay = comp.base_salary * 12 / 52
    else:
        raise PayrollValidationError(
            comp.engineer_id,
            "pay_frequency",
            f"Unknown pay_frequency: {comp.pay_frequency}",
        )

    # Apply deductions
    deductions_detail = []
    total_deductions = 0.0
    for ded in comp.deductions:
        if "amount" in ded:
            deduction_amount = float(ded["amount"])
        elif "pct" in ded:
            deduction_amount = gross_pay * float(ded["pct"]) / 100
        else:
            deduction_amount = 0.0

        total_deductions += deduction_amount
        deductions_detail.append({**ded, "_applied_amount": deduction_amount})

    net_pay = max(0.0, gross_pay - total_deductions)

    return Payslip(
        payslip_id=str(uuid.uuid4()),
        engineer_id=comp.engineer_id,
        run_id="",          # will be set by initiate_run
        gross_pay=round(gross_pay, 2),
        deductions_detail=deductions_detail,
        net_pay=round(net_pay, 2),
        currency=comp.currency,
        period_start=period_start.isoformat(),
        period_end=period_end.isoformat(),
    )


# ---------------------------------------------------------------------------
# Payroll Run CRUD
# ---------------------------------------------------------------------------

def _save_payroll_run(run: PayrollRun) -> None:
    _store_set(_payroll_run_key(run.run_id), _serialize_run(run))


def get_payroll_run(run_id: str) -> PayrollRun | None:
    raw = _store_get(_payroll_run_key(run_id))
    if not raw:
        return None
    return _deserialize_run(raw)


def list_employer_payroll_runs(employer_id: str) -> list[PayrollRun]:
    run_ids = _store_get_list(_employer_payroll_runs_key(employer_id))
    runs = []
    for rid in run_ids:
        r = get_payroll_run(rid)
        if r:
            runs.append(r)
    runs.sort(key=lambda r: r.initiated_at, reverse=True)
    return runs


def get_payslips(run_id: str) -> list[Payslip]:
    run = get_payroll_run(run_id)
    if not run:
        return []
    return run.payslips


# ---------------------------------------------------------------------------
# Core business logic
# ---------------------------------------------------------------------------

def initiate_run(employer_id: str, initiator_id: str) -> PayrollRun:
    """
    Initiate a payroll run for all engineers with compensation records for
    the given employer.

    Validation-first: ALL compensation records are validated before any
    payslips are produced. If any record is invalid, the run is set to
    "failed" and a PayrollValidationError is raised.

    The pay period defaults to the current calendar month.

    Args:
        employer_id:  The employer for whom payroll is being run.
        initiator_id: The user ID that triggered the run.

    Returns:
        A PayrollRun with status "pending" and populated payslips.

    Raises:
        PayrollValidationError: If any compensation record is invalid.
    """
    now = datetime.now(timezone.utc)
    run_id = str(uuid.uuid4())

    # Derive pay period: first day to last day of current month
    today = now.date()
    period_start = today.replace(day=1)
    if today.month == 12:
        period_end = today.replace(year=today.year + 1, month=1, day=1)
    else:
        period_end = today.replace(month=today.month + 1, day=1)
    # period_end is first day of next month — subtract one day for last day of current month
    import calendar
    last_day = calendar.monthrange(today.year, today.month)[1]
    period_end = today.replace(day=last_day)

    run = PayrollRun(
        run_id=run_id,
        employer_id=employer_id,
        initiated_by=initiator_id,
        initiated_at=now.isoformat(),
        status="pending",
        payslips=[],
        total_gross=0.0,
        completed_at=None,
    )

    # Load all compensation records for this employer
    records = list_employer_compensations(employer_id)

    # --- Phase 1: Validate ALL records before producing any payslips ---
    for record in records:
        try:
            _validate_compensation_record(record)
        except PayrollValidationError:
            run.status = "failed"
            _save_payroll_run(run)
            _store_append_to_list(_employer_payroll_runs_key(employer_id), run_id)
            raise

    # --- Phase 2: All valid — produce payslips ---
    payslips = []
    total_gross = 0.0
    for record in records:
        payslip = calculate_payslip(record, (period_start, period_end))
        payslip.run_id = run_id
        payslips.append(payslip)
        total_gross += payslip.gross_pay

    run.payslips = payslips
    run.total_gross = round(total_gross, 2)

    _save_payroll_run(run)
    _store_append_to_list(_employer_payroll_runs_key(employer_id), run_id)
    return run


def complete_run(run_id: str) -> PayrollRun:
    """
    Mark a payroll run as completed and write an immutable audit log entry.

    Sets run.status = "completed" and run.completed_at = now (UTC).
    Writes an immutable audit log at key `payroll_audit_log:{run_id}`.

    Args:
        run_id: The ID of the PayrollRun to complete.

    Returns:
        The updated PayrollRun.

    Raises:
        ValueError: If the run is not found.
    """
    run = get_payroll_run(run_id)
    if run is None:
        raise ValueError(f"PayrollRun not found: {run_id}")

    now = datetime.now(timezone.utc)
    run.status = "completed"
    run.completed_at = now.isoformat()

    _save_payroll_run(run)

    # Write immutable audit log entry
    audit_entry = json.dumps({
        "run_id": run.run_id,
        "employer_id": run.employer_id,
        "initiated_by": run.initiated_by,
        "initiated_at": run.initiated_at,
        "completed_at": run.completed_at,
        "status": run.status,
        "total_gross": run.total_gross,
        "payslip_count": len(run.payslips),
    })
    _store_set(_payroll_audit_log_key(run_id), audit_entry)

    return run


def get_audit_log(run_id: str) -> dict | None:
    """Retrieve the immutable audit log entry for a payroll run."""
    raw = _store_get(_payroll_audit_log_key(run_id))
    if not raw:
        return None
    return json.loads(raw)
