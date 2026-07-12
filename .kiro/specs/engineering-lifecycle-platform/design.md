# Design Document: Engineering Lifecycle Platform

## Overview

This document describes the technical design for expanding HireAI into a full engineering lifecycle platform. The existing system covers job postings, AI interviews (the "Aria" interviewer), candidate proctoring, and an employer dashboard backed by a FastAPI/Python backend with Valkey (Redis-compatible) session storage and a React frontend.

The expansion adds six new Lifecycle_Modules — Onboarding, Payroll, Performance, Compliance, Analytics, and Integrations — unified by the Flywheel, a proprietary Signal collection and model-training loop that is the platform's core competitive moat.

The design reuses all existing patterns: FastAPI routes, Valkey/in-memory storage, the `LLMClient`, Pydantic schemas, and the React SPA. New modules are additive and do not break existing hiring flows.

---

## Architecture

### High-Level Component Map

```
┌─────────────────────────────────────────────────────────────────────┐
│                          React SPA (Frontend)                        │
│  EmployerDashboard  │  EngineerPortal  │  AdminPortal               │
└────────────────────────────────┬────────────────────────────────────┘
                                 │ REST (JWT)
┌────────────────────────────────▼────────────────────────────────────┐
│                        FastAPI Backend                               │
│  /api/hiring  /api/onboarding  /api/payroll  /api/performance       │
│  /api/compliance  /api/analytics  /api/signals  /api/integrations   │
└───┬──────┬──────────┬──────────┬───────────────┬────────────────────┘
    │      │          │          │               │
    ▼      ▼          ▼          ▼               ▼
 Valkey  Signal    Training   LLM Client    Integration
 Store   Store     Pipeline   (Gemini/      Connectors
(state) (append-  (async bg)  Mistral)    (GH/Jira/Slack)
         only)
```

### Request Flow — Signal Ingestion

```
Integration_Connector → /api/signals/ingest
  → Signal_Processor (normalize + anonymize)
  → Signal_Store.append()
  → async: Training_Pipeline.check_trigger()
```

### Request Flow — Evaluation_Model Inference

```
/api/hiring/complete or /api/performance/cycle/evaluate
  → Model_Registry.get_production_model(type)
  → Evaluation_Model.predict(features)
  → return {score, model_version, confidence_interval}
```

---

## Components and Interfaces

### 1. Signal_Processor

Normalizes raw integration events into typed Signal records before writing to the Signal_Store. Each signal type has a schema that the processor validates against.

```python
class SignalType(str, Enum):
    CODING_SESSION = "coding_session"
    DEBUGGING_TRACE = "debugging_trace"
    AI_PROMPT_CATEGORY = "ai_prompt_category"
    COMMIT_METADATA = "commit_metadata"
    PR_REVIEW_QUALITY = "pr_review_quality"
    INTERVIEW_TRANSCRIPT_EMBEDDING = "interview_transcript_embedding"
    ARCHITECTURE_DECISION_TAG = "architecture_decision_tag"
    ONBOARDING_TASK_COMPLETION = "onboarding_task_completion"
    COLLABORATION_FREQUENCY = "collaboration_frequency"
    JOB_PERFORMANCE_RATING = "job_performance_rating"
    ONBOARDING_COMPLETION_SUMMARY = "onboarding_completion_summary"
    CONSENT_CHANGE_AUDIT = "consent_change_audit"

@dataclass
class Signal:
    signal_id: str          # uuid
    pseudonymous_id: str    # HMAC(engineer_id, platform_secret) — not reversible
    signal_type: SignalType
    payload: dict           # anonymized, schema-validated
    source_system: str      # e.g. "github", "platform_interview"
    collected_at: str       # ISO-8601 UTC
    consent_version: str    # version of consent when collected
    employer_id: str        # for tenant isolation
```

### 2. Signal_Store

Append-only, tenant-isolated storage. Backed by Valkey sorted sets (score = timestamp epoch) for time-range queries. Falls back to in-memory for local dev.

```python
def append_signal(signal: Signal) -> None
def query_signals(pseudonymous_id: str, signal_type: SignalType | None, since: datetime, until: datetime) -> list[Signal]
def revoke_signals(pseudonymous_id: str) -> int          # marks revoked, returns count
def erase_pii_linkage(engineer_id: str) -> None          # drops id→pseudonymous_id mapping
def get_signal_count(employer_id: str | None) -> int
```

### 3. Consent_Manager

```python
@dataclass
class ConsentRecord:
    consent_id: str
    engineer_id: str
    signal_categories: list[SignalType]
    granted_at: str
    consent_version: str
    revoked_at: str | None = None

def grant_consent(engineer_id: str, categories: list[SignalType]) -> ConsentRecord
def revoke_consent(engineer_id: str) -> ConsentRecord
def get_consent(engineer_id: str) -> ConsentRecord | None
def has_active_consent(engineer_id: str, signal_type: SignalType) -> bool
```

### 4. Model_Registry

Manages versioned Evaluation_Model metadata and the production pointer. The actual model weights are referenced by URI (S3 or local path). For Phase 1, models are thin wrappers that call specialized LLM prompts with Signal-derived features as context.

```python
@dataclass
class ModelVersion:
    model_type: EvaluationModelType   # hiring_ability | team_fit | promotion_readiness | hiring_success
    version: int                       # monotonically increasing
    accuracy: float                    # validation accuracy at promotion time
    promoted_at: str
    weights_uri: str
    is_production: bool

def register_model_version(mv: ModelVersion) -> None
def get_production_model(model_type: EvaluationModelType) -> ModelVersion
def promote_model(model_type: EvaluationModelType, new_version: int) -> bool  # returns False if accuracy < current
def rollback_model(model_type: EvaluationModelType) -> ModelVersion
def list_model_versions(model_type: EvaluationModelType) -> list[ModelVersion]

@dataclass
class ModelPrediction:
    score: float                   # 0.0 – 1.0
    model_version: int
    confidence_interval: tuple[float, float]
    model_type: EvaluationModelType
```

### 5. Onboarding_Store

```python
@dataclass
class OnboardingTask:
    task_id: str
    title: str
    description: str
    due_offset_days: int
    assigned_role: str
    completed_at: str | None = None

@dataclass
class OnboardingPlan:
    plan_id: str
    engineer_id: str
    employer_id: str
    template_id: str
    hire_date: str
    tasks: list[OnboardingTask]
    created_at: str

def create_plan_from_template(engineer_id: str, employer_id: str, template_id: str, hire_date: str) -> OnboardingPlan
def complete_task(plan_id: str, task_id: str) -> OnboardingPlan
def get_overdue_tasks(employer_id: str) -> list[tuple[OnboardingPlan, OnboardingTask]]
```

### 6. Payroll_Engine

```python
@dataclass
class CompensationRecord:
    record_id: str
    engineer_id: str
    employer_id: str
    base_salary: float
    currency: str
    pay_frequency: str   # monthly | bi-weekly | weekly
    effective_date: str
    deductions: list[dict]   # [{name, type, amount | pct}]

@dataclass
class PayrollRun:
    run_id: str
    employer_id: str
    initiated_by: str
    initiated_at: str
    status: str   # pending | completed | failed
    payslips: list[Payslip]
    total_gross: float
    completed_at: str | None = None

@dataclass
class Payslip:
    payslip_id: str
    engineer_id: str
    run_id: str
    gross_pay: float
    deductions_detail: list[dict]
    net_pay: float
    currency: str
    period_start: str
    period_end: str

def initiate_run(employer_id: str, initiator_id: str) -> PayrollRun
def calculate_payslip(comp: CompensationRecord, period: tuple[date, date]) -> Payslip
def complete_run(run_id: str) -> PayrollRun
```

### 7. Performance_Manager

```python
@dataclass
class PerformanceCycle:
    cycle_id: str
    employer_id: str
    name: str
    start_date: str
    end_date: str
    participant_ids: list[str]
    review_template: dict
    status: str   # draft | active | completed

@dataclass
class PerformanceReview:
    review_id: str
    cycle_id: str
    reviewer_id: str
    reviewee_id: str
    form_responses: dict
    normalized_score: float
    submitted_at: str

def activate_cycle(cycle_id: str) -> PerformanceCycle
def submit_review(cycle_id: str, reviewer_id: str, reviewee_id: str, responses: dict) -> PerformanceReview
def evaluate_cycle(cycle_id: str) -> list[ModelPrediction]   # calls promotion_readiness_predictor
```

### 8. Compliance_Engine

```python
@dataclass
class ComplianceRule:
    rule_id: str
    employer_id: str
    name: str
    jurisdiction: str
    category: str   # working_hours | leave | data_privacy | pay_equity
    trigger_condition: dict   # DSL: {"field": "weekly_hours", "op": "gt", "threshold": 48}
    severity: str   # info | warning | critical
    notification_recipients: list[str]

@dataclass
class ComplianceAlert:
    alert_id: str
    rule_id: str
    employer_id: str
    pseudonymous_engineer_id: str
    severity: str
    recommended_action: str
    status: str   # open | resolved
    created_at: str
    resolved_at: str | None = None

def evaluate_rules(employer_id: str) -> list[ComplianceAlert]
def resolve_alert(alert_id: str, resolver_id: str) -> ComplianceAlert
```

### 9. Analytics_Engine

```python
def get_hiring_funnel(employer_id: str, date_range: tuple) -> dict
def get_time_to_hire(employer_id: str, role: str | None) -> dict
def get_onboarding_completion_rates(employer_id: str) -> dict
def get_performance_distributions(employer_id: str, cycle_id: str | None) -> dict
def get_attrition_risk_scores(employer_id: str) -> dict
def get_team_composition(employer_id: str) -> dict
def get_anomalies(employer_id: str) -> list[dict]
def get_benchmark_comparison(employer_id: str, metric: str) -> dict
```

### 10. Integration_Connector Framework

Each connector implements a common interface:

```python
class BaseConnector(ABC):
    connector_id: str
    employer_id: str
    status: str   # active | degraded | disabled
    last_sync_at: str | None

    @abstractmethod
    def validate_credentials(self, config: dict) -> bool

    @abstractmethod
    def pull_events(self, since: datetime) -> list[RawEvent]

    @abstractmethod
    def normalize_event(self, event: RawEvent) -> Signal | None
```

Concrete connectors: `GitHubConnector`, `JiraConnector`, `SlackConnector`, `HRISWebhookConnector`.

---

## Data Models

### Existing Models (unchanged, extended)

`Application` gains two new fields:
- `evaluation_model_score: dict | None` — prediction from hiring_ability_predictor
- `interview_rubric_scores: dict | None` — per-dimension rubric scores

`Employer` gains:
- `flywheel_contribution_score: float` — updated by Training_Pipeline

### New Models Summary

| Model | Primary Key | Store |
|---|---|---|
| Signal | signal_id | Valkey sorted set `signals:{employer_id}:{pseudonymous_id}` |
| ConsentRecord | consent_id | Valkey `consent:{engineer_id}` |
| ModelVersion | (model_type, version) | Valkey `model:{type}:{version}` |
| OnboardingPlan | plan_id | Valkey `onboarding:{plan_id}` |
| OnboardingTemplate | template_id | Valkey `onboarding_template:{template_id}` |
| CompensationRecord | record_id | Valkey `compensation:{engineer_id}` |
| PayrollRun | run_id | Valkey `payroll_run:{run_id}` |
| Payslip | payslip_id | Valkey `payslip:{payslip_id}` |
| PerformanceCycle | cycle_id | Valkey `perf_cycle:{cycle_id}` |
| PerformanceReview | review_id | Valkey `perf_review:{review_id}` |
| ComplianceRule | rule_id | Valkey `compliance_rule:{rule_id}` |
| ComplianceAlert | alert_id | Valkey `compliance_alert:{alert_id}` |
| IntegrationConnector | connector_id | Valkey `connector:{connector_id}` |

All models follow the existing pattern: `@dataclass` + `json.dumps(asdict(model))` + Valkey / in-memory fallback.

---

## Correctness Properties

A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.

### Property 1: Consent gates Signal ingestion

*For any* Engineer and Signal type, if the Engineer does not have an active Consent_Record covering that Signal type, then calling `append_signal` for that Engineer SHALL return an error and the Signal_Store SHALL not contain the new signal.

**Validates: Requirements 1.1, 1.2**

---

### Property 2: Signal anonymization — no PII in payload

*For any* Signal written to the Signal_Store, the signal payload field SHALL contain no string that matches the originating Engineer's name, email address, or employee ID.

**Validates: Requirements 1.3**

---

### Property 3: Signal immutability

*For any* Signal appended to the Signal_Store with a given signal_id, a subsequent read of that signal_id SHALL return a record identical to the one written (same type, payload, pseudonymous_id, collected_at).

**Validates: Requirements 1.4**

---

### Property 4: Consent revocation stops new Signals

*For any* Engineer who has revoked consent, all calls to `append_signal` for that Engineer after revocation SHALL be rejected and the Signal_Store count for that Engineer SHALL not increase.

**Validates: Requirements 1.2**

---

### Property 5: Model promotion requires accuracy improvement

*For any* candidate Evaluation_Model version and any existing production model of the same type, `promote_model` SHALL return False (reject promotion) when the candidate version's accuracy is strictly less than the current production model's accuracy.

**Validates: Requirements 2.2**

---

### Property 6: Model version monotonicity

*For any* sequence of registered ModelVersion objects for the same model_type, the version numbers SHALL be strictly increasing (each new registration has a version number greater than all previously registered versions for that type).

**Validates: Requirements 2.3**

---

### Property 7: Payslip gross = sum of compensation components

*For any* CompensationRecord and pay period, the gross_pay in the resulting Payslip SHALL equal the pro-rated base salary for that period, with an absolute tolerance of 0.01 in the configured currency.

**Validates: Requirements 5.2**

---

### Property 8: Payslip net = gross minus deductions

*For any* Payslip, net_pay SHALL equal gross_pay minus the sum of all deduction amounts in deductions_detail, with an absolute tolerance of 0.01 in the configured currency.

**Validates: Requirements 5.2**

---

### Property 9: Invalid compensation field rejects the Payroll_Run

*For any* Payroll_Run initiated where at least one CompensationRecord has a missing or invalid required field (null base_salary, unknown currency, invalid pay_frequency), the `initiate_run` function SHALL return an error before producing any Payslips and the run status SHALL be "failed".

**Validates: Requirements 5.5**

---

### Property 10: Onboarding task completion is idempotent

*For any* OnboardingPlan and task_id, calling `complete_task` twice with the same task_id SHALL result in the same final plan state as calling it once — the completed_at timestamp SHALL equal the first completion's timestamp and the task SHALL remain marked done.

**Validates: Requirements 4.3**

---

### Property 11: Overdue task detection covers all tenants

*For any* employer_id and any OnboardingTask whose due date (hire_date + due_offset_days) is strictly before the current date and whose completed_at is None, `get_overdue_tasks` SHALL include that task in its results.

**Validates: Requirements 4.4**

---

### Property 12: Signal serialization round-trip

*For any* valid Signal object, serializing it to JSON and deserializing it back SHALL produce an object equal to the original (same signal_id, signal_type, payload, pseudonymous_id, collected_at).

**Validates: Requirements 1.3, 1.6**

---

### Property 13: Compliance alert generated for every rule violation

*For any* employer_id and configured ComplianceRule, if the evaluated work data for an Engineer satisfies the rule's trigger_condition, then `evaluate_rules` SHALL include a ComplianceAlert for that rule and that Engineer's pseudonymous_id in its output.

**Validates: Requirements 7.2**

---

### Property 14: Analytics report redacts PII on export

*For any* exported analytics report, no field in the output file SHALL contain a string that matches any Engineer's name or email address present in the underlying dataset.

**Validates: Requirements 8.6**

---

## Error Handling

- All new FastAPI routes follow the existing pattern: catch `ValueError` → HTTP 400, catch generic `Exception` → HTTP 500 with `detail=str(e)`.
- `Signal_Processor` raises `ConsentError` (subclass of `ValueError`) when consent check fails, mapped to HTTP 403.
- `Payroll_Engine` raises `PayrollValidationError` with a structured `{engineer_id, field, message}` payload.
- `Model_Registry.promote_model` returns `False` (not an exception) to allow the Training_Pipeline to log and continue.
- `Integration_Connector` failures use exponential back-off (1s, 2s, 4s) before marking the connector as degraded and emitting a failure log entry.
- All compliance alerts and audit log entries are written with a best-effort pattern: if the primary store write succeeds but the audit log write fails, the operation is retried up to three times before raising an `AuditLogError`.

---

## Testing Strategy

### Dual Approach

**Unit tests** (pytest) cover specific examples, edge cases, and error conditions:
- Payroll calculation with known salary + deduction combinations
- Consent grant / revoke state transitions
- Model promotion decision logic with boundary accuracy values
- Compliance rule trigger evaluation with known datasets

**Property-based tests** (Hypothesis) validate universal properties across generated inputs:
- Each correctness property above maps to exactly one Hypothesis `@given` test
- Minimum 100 examples per property (Hypothesis default, settings can override)
- Each test is tagged with a comment: `# Feature: engineering-lifecycle-platform, Property N: <property_title>`

### Property-Based Testing Configuration

```python
from hypothesis import given, settings
from hypothesis import strategies as st

@given(st.builds(Signal, ...))
@settings(max_examples=200)
# Feature: engineering-lifecycle-platform, Property 12: Signal serialization round-trip
def test_signal_round_trip(signal: Signal):
    assert Signal(**json.loads(json.dumps(asdict(signal)))) == signal
```

### Testing Library

- **Python backend**: `pytest` + `hypothesis`
- **React frontend**: `vitest` + `@testing-library/react` (unit/component tests only; no property tests on frontend)

### Coverage Targets

- All 14 correctness properties covered by property-based tests
- All error-path branches covered by unit tests
- Integration connector normalization logic covered by example-based tests using fixture payloads from each source system
