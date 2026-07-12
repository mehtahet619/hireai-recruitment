# Requirements Document

## Introduction

This document defines the requirements for expanding the existing HireAI platform into a full-stack B2B engineering lifecycle platform. The platform already covers job postings, AI-driven candidate interviews, proctoring, and an employer dashboard. This expansion adds onboarding, payroll, performance management, compliance, workforce analytics, and — critically — a proprietary data flywheel that continuously improves AI evaluation models using anonymized, consent-based engineering behavioral signals. The goal is to transform HireAI from an AI recruiting tool into the operating system for engineering organizations, creating a defensible long-term moat through proprietary data network effects.

## Glossary

- **Platform**: The HireAI engineering lifecycle platform.
- **Employer**: A B2B customer company that uses the Platform to manage its engineering workforce.
- **Engineer**: An employee or candidate tracked by the Platform within an Employer's organization.
- **Signal**: An anonymized, consent-based behavioral data point collected from an Engineer during their lifecycle (e.g., commit, AI prompt, PR review, debugging trace).
- **Flywheel**: The proprietary data collection and model-training loop that continuously improves Platform AI models as more Signals are collected.
- **Evaluation_Model**: A specialized AI model trained on Flywheel data to predict engineering ability, team fit, promotion readiness, or hiring success.
- **Lifecycle_Module**: A discrete functional area of the Platform: Hiring, Onboarding, Payroll, Performance, Compliance, or Analytics.
- **Consent_Record**: A persisted, auditable record of an Engineer's explicit consent to Signal collection.
- **Signal_Store**: The append-only, anonymized data store that holds all collected Signals.
- **Analytics_Engine**: The component that produces workforce insights and trend reports from Signal and performance data.
- **Integration_Connector**: A configurable adapter that connects the Platform to an external system (GitHub, Jira, Slack, HRIS, payroll providers, etc.).
- **Onboarding_Plan**: A structured sequence of tasks, milestones, and resources assigned to a new Engineer.
- **Payroll_Run**: A processed payroll cycle that calculates gross pay, deductions, and net pay for a set of Engineers.
- **Performance_Cycle**: A configured review period (e.g., quarterly, annual) that produces structured performance assessments.
- **Compliance_Rule**: A configurable rule derived from a jurisdiction's labor law or internal policy that the Platform enforces or monitors.

---

## Requirements

### Requirement 1: Data Flywheel — Signal Collection

**User Story:** As a Platform administrator, I want to continuously collect anonymized, consent-based engineering behavioral signals, so that the Platform's AI models can improve over time and create a defensible competitive moat.

#### Acceptance Criteria

1. WHEN an Engineer grants consent to Signal collection, THE Platform SHALL create a Consent_Record that includes the Engineer's identifier, the categories of Signals consented to, the timestamp, and the consent version.
2. WHEN an Engineer revokes consent, THE Platform SHALL stop collecting new Signals for that Engineer within 24 hours and mark all existing Signals for that Engineer as revoked in the Signal_Store.
3. THE Signal_Store SHALL store each Signal as an anonymized record that contains a pseudonymous Engineer identifier, signal type, signal payload, source system, and collection timestamp, and SHALL NOT store any personally identifiable information in the signal payload.
4. WHEN a Signal is ingested, THE Signal_Store SHALL append the Signal with an immutable record that cannot be modified or deleted except by explicit data-erasure requests covered under Requirement 10.
5. THE Platform SHALL support Signal types including: coding session duration, debugging trace summary, AI prompt category, commit metadata, pull request review quality indicator, interview transcript embedding, architecture decision record tag, onboarding task completion event, collaboration frequency metric, and long-term job performance rating.
6. WHEN an Integration_Connector emits a raw event, THE Signal_Processor SHALL transform it into a normalized Signal before writing to the Signal_Store.

---

### Requirement 2: Data Flywheel — Model Training Pipeline

**User Story:** As a Platform AI engineer, I want to train and update Evaluation_Models using accumulated Signals, so that prediction accuracy improves continuously as the dataset grows.

#### Acceptance Criteria

1. THE Platform SHALL maintain a Training_Pipeline that periodically retrains Evaluation_Models using data from the Signal_Store.
2. WHEN a new Evaluation_Model version is trained, THE Training_Pipeline SHALL evaluate it against a held-out validation set and SHALL only promote the new version to production if its accuracy metric equals or exceeds the current production model's accuracy metric.
3. THE Platform SHALL version each Evaluation_Model with a monotonically increasing version number and retain at least the two previous versions for rollback.
4. WHEN a production Evaluation_Model is replaced, THE Platform SHALL log the old version, new version, accuracy delta, and promotion timestamp.
5. THE Platform SHALL provide at least the following Evaluation_Model types: hiring_ability_predictor, team_fit_predictor, promotion_readiness_predictor, and hiring_success_predictor.
6. WHEN an Evaluation_Model is invoked for inference, THE Platform SHALL return the prediction score, the model version used, and a confidence interval.

---

### Requirement 3: Hiring — Expanded AI Interview and Evaluation

**User Story:** As an Employer, I want AI-driven interviews that use proprietary Evaluation_Models rather than generic LLMs, so that candidate assessments become more accurate over time.

#### Acceptance Criteria

1. WHEN an interview session is completed, THE Platform SHALL invoke the hiring_ability_predictor Evaluation_Model to supplement the base LLM score.
2. WHEN the hiring_ability_predictor produces a prediction, THE Platform SHALL store the prediction alongside the existing LLM score in the Application record and surface both scores in the Employer dashboard.
3. THE Platform SHALL support structured interview rubrics that Employers configure per job role, covering technical depth, communication, and problem-solving dimensions.
4. WHEN an interview transcript is saved, THE Platform SHALL generate a Signal of type interview_transcript_embedding and write it to the Signal_Store, subject to the Engineer's Consent_Record.
5. WHEN an Employer views an applicant, THE Platform SHALL display the AI score, the Evaluation_Model score, the confidence interval, and the configurable interview rubric scores side by side.
6. IF a candidate's Signal history from previous applications on the Platform exists and the candidate has an active Consent_Record, THEN THE Platform SHALL incorporate historical Signal context into the hiring_ability_predictor inference call.

---

### Requirement 4: Onboarding Module

**User Story:** As an Employer, I want to automate and track engineer onboarding, so that new hires reach full productivity faster and onboarding data feeds the Flywheel.

#### Acceptance Criteria

1. WHEN an Application is moved to status "hired", THE Platform SHALL automatically create an Onboarding_Plan for the Engineer using a template configured by the Employer.
2. THE Platform SHALL allow Employers to create, edit, and version Onboarding_Plan templates that contain ordered tasks with titles, descriptions, due-date offsets from hire date, and assigned roles.
3. WHEN an Engineer completes an onboarding task, THE Platform SHALL record the completion timestamp, mark the task done, and emit an onboarding_task_completion Signal to the Signal_Store.
4. WHEN an onboarding task is overdue by more than 24 hours, THE Platform SHALL notify the Engineer and their assigned manager via the notification channel configured by the Employer.
5. THE Platform SHALL display an onboarding progress dashboard for each Engineer showing completed tasks, pending tasks, overdue tasks, and days since hire.
6. WHEN an Onboarding_Plan is fully completed, THE Platform SHALL emit a summary Signal of type onboarding_completion_summary containing the total days to completion and task completion rates.

---

### Requirement 5: Payroll Module

**User Story:** As an Employer, I want to run payroll for engineers directly within the Platform, so that compensation data is available for analytics and the full lifecycle is managed in one place.

#### Acceptance Criteria

1. THE Platform SHALL allow Employers to configure Engineer compensation records containing base salary, currency, pay frequency (monthly, bi-weekly, weekly), and effective date.
2. WHEN a Payroll_Run is initiated by an Employer, THE Payroll_Engine SHALL calculate gross pay, apply configured deductions (tax withholding, benefits), and produce a net pay figure for each Engineer in the run.
3. WHEN a Payroll_Run is completed, THE Platform SHALL generate a payslip record for each Engineer and make it accessible to both the Engineer and the Employer.
4. THE Platform SHALL support integration with at least one external payroll provider via an Integration_Connector, allowing payroll data to be exported in a standard format.
5. IF a Payroll_Run contains a compensation record with a missing or invalid field, THEN THE Payroll_Engine SHALL reject the run and return a descriptive error identifying the invalid field and the affected Engineer.
6. THE Platform SHALL maintain an immutable audit log of all Payroll_Runs including initiator, run timestamp, total gross pay, and completion status.

---

### Requirement 6: Performance Management Module

**User Story:** As an Employer, I want to run structured performance cycles with AI-assisted assessments, so that engineering talent decisions are data-driven and feed the Flywheel.

#### Acceptance Criteria

1. THE Platform SHALL allow Employers to configure Performance_Cycles with a name, start date, end date, participant list, and review form template.
2. WHEN a Performance_Cycle reaches its start date, THE Platform SHALL activate the cycle and notify all participants and reviewers.
3. WHEN a reviewer submits a performance review, THE Platform SHALL store the review, compute a normalized score from the review form, and emit a job_performance_rating Signal to the Signal_Store.
4. WHEN a Performance_Cycle ends, THE Platform SHALL invoke the promotion_readiness_predictor Evaluation_Model for each participating Engineer and attach the prediction to the cycle results.
5. THE Platform SHALL display an aggregate performance dashboard per Performance_Cycle showing score distributions, top performers, and promotion readiness predictions.
6. WHEN an Engineer's promotion_readiness_predictor score exceeds the threshold configured by the Employer, THE Platform SHALL generate a promotion recommendation notification to the Engineer's manager.

---

### Requirement 7: Compliance Module

**User Story:** As an Employer, I want the Platform to monitor and enforce configurable labor compliance rules, so that I can reduce legal risk across multiple jurisdictions.

#### Acceptance Criteria

1. THE Platform SHALL allow Employers to configure Compliance_Rules that specify a rule name, jurisdiction, rule category (working hours, leave entitlements, data privacy, pay equity), trigger condition, and notification recipients.
2. WHEN an Engineer's recorded work data violates a configured Compliance_Rule, THE Compliance_Engine SHALL generate a compliance alert containing the rule name, violation severity, affected Engineer (pseudonymized in alerts visible to non-HR roles), and recommended action.
3. THE Platform SHALL maintain an immutable Compliance_Log of all generated alerts, their resolution status, and the timestamps of status changes.
4. THE Platform SHALL provide pre-configured Compliance_Rule templates for at least three jurisdictions: US (federal), UK, and India.
5. WHEN a data privacy Compliance_Rule is triggered (such as a data retention period expiring), THE Platform SHALL initiate an automated data review workflow and notify the configured Data_Privacy_Officer recipient.
6. WHILE a compliance alert is in an unresolved state, THE Platform SHALL surface it prominently in the Employer's compliance dashboard.

---

### Requirement 8: Workforce Analytics Module

**User Story:** As an Employer, I want AI-powered workforce analytics and trend reports, so that I can make strategic engineering hiring and talent decisions.

#### Acceptance Criteria

1. THE Analytics_Engine SHALL produce the following standard reports: hiring funnel conversion rates, time-to-hire by role, onboarding completion rates, performance score distributions, attrition risk scores, and team composition by skill cluster.
2. WHEN an Employer requests a report, THE Analytics_Engine SHALL aggregate data from the Signal_Store and application/performance records and return results within 30 seconds for datasets up to 10,000 Engineers.
3. THE Platform SHALL allow Employers to configure custom analytics dashboards by selecting metrics, filters (date range, team, role, location), and visualization type (table, bar chart, line chart).
4. WHEN the Analytics_Engine detects an anomaly in a workforce metric (such as a statistically significant spike in attrition risk scores), THE Platform SHALL generate an anomaly alert and surface it in the Employer's analytics dashboard.
5. THE Platform SHALL provide a benchmark comparison feature that compares an Employer's anonymized aggregate metrics against Platform-wide industry benchmarks derived from consented, aggregated Signal data.
6. WHEN an Employer exports a report, THE Platform SHALL produce a file in CSV or JSON format and SHALL redact any personally identifiable information from the export.

---

### Requirement 9: Integration Connectors

**User Story:** As an Employer, I want the Platform to integrate with my existing engineering toolchain, so that Signals are collected automatically without manual data entry.

#### Acceptance Criteria

1. THE Platform SHALL provide Integration_Connectors for at least: GitHub (commits, PRs, code review activity), Jira (issue assignment, resolution time), Slack (collaboration frequency metric, anonymized), and a generic HRIS webhook.
2. WHEN an Integration_Connector is configured by an Employer, THE Platform SHALL validate the connection credentials and confirm connectivity before activating the connector.
3. WHEN an Integration_Connector emits an event, THE Platform SHALL process and ingest the resulting Signal within 60 seconds under normal load conditions.
4. IF an Integration_Connector fails to deliver an event after three consecutive retry attempts, THEN THE Platform SHALL mark the connector as degraded, log the failure, and notify the Employer's configured integration administrator.
5. THE Platform SHALL display a connector health dashboard showing each connector's status (active, degraded, disabled), last successful sync timestamp, and error count over the last 24 hours.
6. WHEN an Employer disables an Integration_Connector, THE Platform SHALL stop ingesting new Signals from that connector and retain all previously ingested Signals.

---

### Requirement 10: Data Privacy and Engineer Rights

**User Story:** As an Engineer, I want to control my data, view my collected Signals, and request erasure, so that I can trust the Platform with my behavioral information.

#### Acceptance Criteria

1. THE Platform SHALL provide Engineers with a self-service privacy portal where they can view all Signals collected about them, categorized by signal type and date range.
2. WHEN an Engineer submits a data erasure request, THE Platform SHALL complete the erasure of all personally identifiable linkages between the Engineer and their Signals within 30 days and confirm completion to the Engineer.
3. THE Platform SHALL ensure that after erasure, the pseudonymous Signal records remain in the Signal_Store in fully anonymized form with no recoverable linkage to the original Engineer, so that aggregate model training data is preserved.
4. THE Platform SHALL display to each Engineer, at consent grant time and on the privacy portal, a plain-language summary of what categories of Signals are collected, how they are used, and which Employers have access to their aggregated insights.
5. WHEN an Engineer's Consent_Record is updated (granted, scoped change, or revoked), THE Platform SHALL emit a consent_change_audit event to the immutable Compliance_Log.
6. THE Platform SHALL enforce role-based access controls such that only the Engineer themselves and authorized HR roles can view identified Signal records; all other roles see only anonymized aggregate data.

---

### Requirement 11: Network Effects and Platform Flywheel Reporting

**User Story:** As a Platform product owner, I want dashboards that quantify the Flywheel's growth and the resulting model accuracy improvements, so that I can demonstrate the competitive moat to investors and customers.

#### Acceptance Criteria

1. THE Platform SHALL maintain a Flywheel_Metrics dashboard visible to Platform administrators showing total Signals collected, Signals collected in the last 30 days, active Consent_Records, and Evaluation_Model accuracy trends over time.
2. WHEN the total Signal count crosses a configured milestone threshold, THE Platform SHALL generate a Flywheel milestone event and record it in the audit log.
3. THE Platform SHALL expose an anonymized, aggregated "Platform Health" summary to Employers (not Platform administrators) showing the number of participating organizations, total Engineers on the Platform, and the current accuracy tier of each Evaluation_Model type.
4. WHEN an Employer's dataset contributes Signals that improve an Evaluation_Model's accuracy by a measurable amount, THE Platform SHALL credit that Employer's "Flywheel contribution score" and surface it in the Employer dashboard as a trust signal.
