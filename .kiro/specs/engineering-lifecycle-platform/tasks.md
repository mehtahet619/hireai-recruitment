
+-Implementation Plan: Engineering Lifecycle Platform

## Overview

Incremental expansion of HireAI into a full engineering lifecycle platform. Each task builds on the previous, wiring modules together as they are completed. All new code follows existing patterns: FastAPI routes, `@dataclass` + Valkey/memory storage, Pydantic schemas, and the React SPA.

## Tasks

- [x] 1. Consent and Signal foundation
  - [x] 1.1 Implement ConsentRecord dataclass, Consent_Manager (grant_consent, revoke_consent, get_consent, has_active_consent), and Valkey/memory storage in `backend/app/consent_store.py`
    - _Requirements: 1.1, 1.2, 10.5_
  - [x] 1.2 Write property test for consent gating Signal ingestion (Property 1) and consent revocation blocking new Signals (Property 4)
    - **Property 1: Consent gates Signal ingestion**
    - **Property 4: Consent revocation stops new Signals**
    - **Validates: Requirements 1.1, 1.2**
  - [x] 1.3 Implement Signal dataclass (with SignalType enum), Signal_Processor (normalize + consent check), and Signal_Store (append_signal, query_signals, revoke_signals, erase_pii_linkage, get_signal_count) in `backend/app/signal_store.py`
    - Signal payload must strip engineer name, email, and employee ID before storage
    - Pseudonymous ID = HMAC(engineer_id, settings.secret_key)
    - _Requirements: 1.3, 1.4, 1.5, 1.6_
  - [x] 1.4 Write property test for Signal anonymization — no PII in payload (Property 2)
    - **Property 2: Signal anonymization — no PII in payload**
    - **Validates: Requirements 1.3**
  - [x] 1.5 Write property test for Signal immutability (read-after-write returns identical record) (Property 3) and Signal serialization round-trip (Property 12)
    - **Property 3: Signal immutability**
    - **Property 12: Signal serialization round-trip**
    - **Validates: Requirements 1.4, 1.6**
  - [x] 1.6 Add POST `/api/signals/ingest` and GET `/api/signals/me` (engineer self-service) FastAPI routes with schemas in `backend/app/schemas.py`; add signal ingest call to existing `/api/apply/complete` endpoint (interview_transcript_embedding signal)
    - _Requirements: 1.6, 3.4_
  - [x] 1.7 Write example test: after completing an interview, an interview_transcript_embedding Signal exists in the Signal_Store for the applicant
    - **Validates: Requirements 3.4**

- [ ] 2. Checkpoint — core signal pipeline
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Model Registry and Evaluation Models
  - [x] 3.1 Implement ModelVersion dataclass, ModelPrediction dataclass, EvaluationModelType enum, and Model_Registry (register_model_version, get_production_model, promote_model, rollback_model, list_model_versions) in `backend/app/model_registry.py`
    - promote_model returns False without replacing production if candidate accuracy < current
    - Store at least 2 previous versions per model type
    - _Requirements: 2.2, 2.3, 2.4_
  - [x] 3.2 Write property test for model promotion accuracy gate (Property 5) and version monotonicity (Property 6)
    - **Property 5: Model promotion requires accuracy improvement**
    - **Property 6: Model version monotonicity**
    - **Validates: Requirements 2.2, 2.3**
  - [x] 3.3 Implement four Phase-1 Evaluation_Models as LLM-backed predictors (using existing LLMClient) in `backend/app/evaluation_models.py`: hiring_ability_predictor, team_fit_predictor, promotion_readiness_predictor, hiring_success_predictor
    - Each model extracts relevant Signal features for the engineer and adds them as context to a specialized system prompt
    - Returns ModelPrediction with score (0.0–1.0), model_version, and confidence_interval
    - _Requirements: 2.5, 2.6_
  - [x] 3.4 Write property test: for any call to an Evaluation_Model predict(), the returned ModelPrediction has score in [0,1], a valid model_version, and a confidence_interval tuple where lower <= upper
    - **Validates: Requirements 2.6**
  - [x] 3.5 Extend `/api/apply/complete` to call hiring_ability_predictor and store the ModelPrediction in the Application record's new `evaluation_model_score` field; extend the `/api/employer/applicants/{id}` response to include both the LLM score and the model score with confidence interval
    - _Requirements: 3.1, 3.2, 3.5_

- [x] 4. Onboarding Module
  - [x] 4.1 Implement OnboardingTask, OnboardingTemplate, and OnboardingPlan dataclasses with Valkey/memory storage in `backend/app/onboarding_store.py`; implement create_plan_from_template, complete_task, get_overdue_tasks
    - _Requirements: 4.1, 4.2, 4.3, 4.4_
  - [x] 4.2 Write property test for onboarding task completion idempotence (Property 10)
    - **Property 10: Onboarding task completion is idempotent**
    - **Validates: Requirements 4.3**
  - [x] 4.3 Write property test for overdue task detection completeness (Property 11)
    - **Property 11: Overdue task detection covers all tenants**
    - **Validates: Requirements 4.4**
  - [x] 4.4 Add FastAPI routes: POST `/api/employer/onboarding/templates`, GET/PATCH `/api/employer/onboarding/templates/{id}`, POST `/api/onboarding/plans`, GET `/api/onboarding/plans/{plan_id}`, POST `/api/onboarding/plans/{plan_id}/tasks/{task_id}/complete`; wire complete_task to emit onboarding_task_completion Signal
    - _Requirements: 4.1, 4.2, 4.3, 4.5, 4.6_
  - [x] 4.5 Add an Onboarding tab to the React EmployerDashboard showing per-engineer onboarding progress (completed / pending / overdue tasks, days since hire)
    - _Requirements: 4.5_

- [ ] 5. Payroll Module
  - [x] 5.1 Implement CompensationRecord, PayrollRun, and Payslip dataclasses with Valkey/memory storage in `backend/app/payroll_store.py`; implement initiate_run (validates all compensation records before producing any payslips), calculate_payslip (gross = pro-rated base, net = gross - deductions), complete_run
    - _Requirements: 5.1, 5.2, 5.3, 5.5, 5.6_
  - [ ] 5.2 Write property test for payslip gross equals pro-rated salary (Property 7) and net equals gross minus deductions (Property 8)
    - **Property 7: Payslip gross = sum of compensation components**
    - **Property 8: Payslip net = gross minus deductions**
    - **Validates: Requirements 5.2**
  - [x] 5.3 Write property test for invalid compensation field rejecting the Payroll_Run (Property 9)
    - **Property 9: Invalid compensation field rejects the Payroll_Run**
    - **Validates: Requirements 5.5**
  - [x] 5.4 Add FastAPI routes: POST/GET `/api/employer/compensation`, POST `/api/employer/payroll/runs`, GET `/api/employer/payroll/runs/{run_id}`, GET `/api/employer/payroll/runs/{run_id}/payslips`; append immutable audit log entry on each run
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.6_
  - [x] 5.5 Add a Payroll tab to the React EmployerDashboard with compensation record management and payroll run initiation/results view
    - _Requirements: 5.1, 5.3_

- [ ] 6. Checkpoint — onboarding and payroll
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 7. Performance Management Module
  - [x] 7.1 Implement PerformanceCycle, PerformanceReview dataclasses with Valkey/memory storage in `backend/app/performance_store.py`; implement activate_cycle, submit_review (normalizes score from form responses), evaluate_cycle (calls promotion_readiness_predictor for each participant)
    - _Requirements: 6.1, 6.2, 6.3, 6.4_
  - [x] 7.2 Write property test: for any submitted PerformanceReview, a job_performance_rating Signal is written to the Signal_Store with the reviewee's pseudonymous_id
    - **Validates: Requirements 6.3**
  - [x] 7.3 Add FastAPI routes: POST/GET `/api/employer/performance/cycles`, POST `/api/employer/performance/cycles/{id}/activate`, POST `/api/employer/performance/cycles/{id}/reviews`, GET `/api/employer/performance/cycles/{id}/results`
    - Wire submit_review to emit job_performance_rating Signal
    - Wire evaluate_cycle to call promotion_readiness_predictor and store predictions on the cycle
    - Emit notification (stored alert record) when promotion_readiness score exceeds employer-configured threshold
    - _Requirements: 6.2, 6.3, 6.4, 6.5, 6.6_
  - [~] 7.4 Add a Performance tab to the React EmployerDashboard showing cycle list, score distributions, and promotion readiness predictions
    - _Requirements: 6.5_

- [ ] 8. Compliance Module
  - [~] 8.1 Implement ComplianceRule and ComplianceAlert dataclasses with Valkey/memory storage in `backend/app/compliance_store.py`; implement evaluate_rules (evaluates trigger_condition DSL against work data), resolve_alert; pre-seed rule templates for US federal, UK, and India jurisdictions
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_
  - [~] 8.2 Write property test for compliance alert generated for every rule violation (Property 13)
    - **Property 13: Compliance alert generated for every rule violation**
    - **Validates: Requirements 7.2**
  - [~] 8.3 Add FastAPI routes: POST/GET `/api/employer/compliance/rules`, GET `/api/employer/compliance/alerts`, PATCH `/api/employer/compliance/alerts/{id}/resolve`; wire data privacy rules to initiate data review workflow on trigger
    - _Requirements: 7.1, 7.2, 7.3, 7.5, 7.6_
  - [~] 8.4 Add a Compliance tab to the React EmployerDashboard showing open alerts (prominently surfaced), resolved alerts, and rule configuration
    - _Requirements: 7.6_

- [ ] 9. Integration Connectors
  - [~] 9.1 Implement BaseConnector ABC and IntegrationConnector dataclass in `backend/app/integrations/base.py`; implement GitHubConnector, JiraConnector, SlackConnector, and HRISWebhookConnector in separate files under `backend/app/integrations/`
    - Each connector implements validate_credentials, pull_events, normalize_event
    - Retry logic: 3 attempts with exponential back-off; mark as degraded on third failure
    - _Requirements: 9.1, 9.2, 9.3, 9.4_
  - [~] 9.2 Write example-based tests for each connector's normalize_event using fixture payloads (GitHub push event, Jira issue resolved event, Slack channel message event, HRIS webhook payload)
    - **Validates: Requirements 9.1, 9.3**
  - [~] 9.3 Add FastAPI routes: POST `/api/employer/integrations`, GET `/api/employer/integrations`, POST `/api/employer/integrations/{id}/validate`, PATCH `/api/employer/integrations/{id}` (enable/disable); background task polls active connectors and calls Signal_Processor
    - _Requirements: 9.2, 9.3, 9.4, 9.5, 9.6_
  - [~] 9.4 Add an Integrations tab to the React EmployerDashboard showing connector health (status, last sync, error count), connector configuration, and enable/disable controls
    - _Requirements: 9.5_

- [ ] 10. Workforce Analytics Module
  - [~] 10.1 Implement Analytics_Engine in `backend/app/analytics_engine.py` with functions: get_hiring_funnel, get_time_to_hire, get_onboarding_completion_rates, get_performance_distributions, get_attrition_risk_scores, get_team_composition, get_anomalies, get_benchmark_comparison; implement report export (CSV and JSON) with PII redaction
    - Anomaly detection: flag metric values more than 2 standard deviations from the rolling mean
    - Benchmark comparison: aggregate anonymized employer metrics across the platform
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_
  - [~] 10.2 Write property test for analytics export PII redaction (Property 14)
    - **Property 14: Analytics report redacts PII on export**
    - **Validates: Requirements 8.6**
  - [~] 10.3 Add FastAPI routes: GET `/api/employer/analytics/{report_type}`, GET `/api/employer/analytics/{report_type}/export`, GET `/api/employer/analytics/anomalies`, GET `/api/employer/analytics/benchmarks`
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_
  - [~] 10.4 Add an Analytics tab to the React EmployerDashboard with standard report views, custom dashboard configuration, anomaly alert panel, and export button
    - _Requirements: 8.3, 8.4_

- [ ] 11. Engineer Privacy Portal
  - [~] 11.1 Add GET `/api/engineer/signals` (returns own Signals paginated by type and date), POST `/api/engineer/consent` (grant/update), DELETE `/api/engineer/consent` (revoke), POST `/api/engineer/erasure-request` FastAPI routes; implement erasure logic: erase_pii_linkage drops engineer_id → pseudonymous_id mapping so signals become unattributable
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.6_
  - [~] 11.2 Write property test for data erasure leaving no recoverable PII linkage (Properties from Requirements 10.2 and 10.3 combined)
    - For any engineer_id, after erase_pii_linkage, querying by engineer_id returns zero signals AND total signal count in store is unchanged
    - **Validates: Requirements 10.2, 10.3**
  - [~] 11.3 Add a minimal Engineer Privacy Portal view in the React frontend accessible via `/privacy` route, showing consent status, signal categories, and erasure request button
    - _Requirements: 10.1, 10.4_

- [ ] 12. Flywheel Metrics and Admin Dashboard
  - [~] 12.1 Implement Flywheel_Metrics aggregation in `backend/app/flywheel_metrics.py`: total Signal count, 30-day Signal count, active Consent_Records count, Evaluation_Model accuracy trend per type; detect milestone thresholds and write to audit log
    - _Requirements: 11.1, 11.2, 11.4_
  - [~] 12.2 Add FastAPI routes: GET `/api/admin/flywheel` (platform admin only), GET `/api/employer/platform-health` (anonymized, employer-visible summary)
    - _Requirements: 11.1, 11.3_
  - [~] 12.3 Add a Flywheel / Platform Health section to the React EmployerDashboard showing model accuracy tier, platform participant count, and the employer's Flywheel contribution score
    - _Requirements: 11.3, 11.4_

- [ ] 13. Final checkpoint — full platform integration
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- All tasks are required for comprehensive coverage
- Each task references specific requirements for traceability
- Property tests use `pytest` + `hypothesis` with `max_examples=200`
- Each property test is tagged with `# Feature: engineering-lifecycle-platform, Property N: <title>`
- The existing hiring pipeline (`/api/apply`, `/api/apply/message`, `/api/apply/complete`) is modified only at task 1.6 and 3.5; all other existing routes are untouched
