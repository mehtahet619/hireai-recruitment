# Engineering Lifecycle Platform (HireAI)

A full-stack B2B platform for engineering organizations — from AI-powered hiring through onboarding, payroll, and workforce analytics, with a proprietary data flywheel that continuously improves AI evaluation models.

```
Hiring ──► Onboarding ──► Payroll ──► Performance ──► Analytics
              ↕                ↕             ↕
         Signal Store ──► Evaluation Models ──► Flywheel
```

## What's in the platform

### Core Modules (implemented)

| Module | Description |
|--------|-------------|
| **Hiring** | AI-driven interviews ("Aria"), resume analysis, candidate scoring, employer dashboard |
| **Signal Store** | Anonymized, consent-based behavioral data collection with HMAC pseudonymization and PII stripping |
| **Consent Manager** | Engineer-controlled consent records; revocation stops new signal ingestion within 24 h |
| **Model Registry** | Versioned Evaluation_Models with accuracy-gated promotion and rollback |
| **Evaluation Models** | 4 LLM-backed predictors: `hiring_ability`, `team_fit`, `promotion_readiness`, `hiring_success` |
| **Onboarding** | Employer-configurable onboarding plans, overdue task detection, progress dashboard |
| **Payroll** | Compensation records, payroll run initiation with validation-first approach, immutable audit log |

### Upcoming Modules (in-progress spec)

Performance Management, Compliance, Workforce Analytics, Integration Connectors (GitHub, Jira, Slack, HRIS), Engineer Privacy Portal, Flywheel Metrics Dashboard.

---

## Tech stack

- **Backend:** FastAPI + Python, Valkey (Redis-compatible) or in-memory storage, Gemini/Mistral LLM
- **Frontend:** React (Vite) SPA
- **Testing:** pytest + Hypothesis (property-based tests) covering 14 correctness properties

---

## Quick start

### 1. Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # add GEMINI_API_KEY or MISTRAL_API_KEY for real LLM
uvicorn app.main:app --reload --port 8000
```

Without an API key the backend runs in **MOCK mode** automatically.

Health check: `curl http://localhost:8000/api/health`

### 2. Frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173  (proxies /api → http://localhost:8000)
```

---

## Running tests

```bash
cd backend
source .venv/bin/activate
USE_MOCK_LLM=true pytest tests/ -v
```

Property-based tests use [Hypothesis](https://hypothesis.readthedocs.io/) with `max_examples=200`. They cover the 14 correctness properties from the spec.

---

## Deploy (production)

Uses **Render** (backend + frontend) with **Valkey** (sessions/storage) and **Cloudflare R2** (video + reviews).

### 1. Create free persistence services

| Service | What to copy |
|---------|--------------|
| [Render Valkey](https://render.com/docs/valkey) | `VALKEY_URL` |
| [Cloudflare R2](https://dash.cloudflare.com) | `S3_ENDPOINT`, `S3_BUCKET`, keys |

### 2. Deploy on Render

1. Render Dashboard → **New** → **Blueprint**
2. Connect your fork of this repo
3. Set secret env vars: `GEMINI_API_KEY` (or `MISTRAL_API_KEY`), `JWT_SECRET`, `VALKEY_URL`, `S3_*`
4. Click **Apply**

`render.yaml` wires `VITE_API_BASE` and `CORS_ORIGINS` between services automatically.

---

## API reference

### Core pipeline
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/health` | Status + mock/model info |
| POST | `/api/jd/parse` | JD → requirements |
| POST | `/api/resume/analyze` | Resume analysis |
| POST | `/api/pipeline/run` | Full pipeline (parse + analyze + questions + score) |

### Employer auth & jobs
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/employer/register` | Register employer |
| POST | `/api/employer/login` | Login |
| POST/GET | `/api/employer/jobs` | Create / list jobs |
| POST | `/api/apply` | Candidate applies + starts AI interview |
| POST | `/api/apply/complete` | Complete interview, get scores + model prediction |

### Signal & Consent
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/signals/ingest` | Ingest a signal (requires consent) |
| GET | `/api/signals/me` | Engineer's own signals |
| POST | `/api/engineer/consent` | Grant consent |
| DELETE | `/api/engineer/consent` | Revoke consent |

### Onboarding
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/employer/onboarding/templates` | Create template |
| GET/PATCH | `/api/employer/onboarding/templates/{id}` | Get / update template |
| POST | `/api/onboarding/plans` | Create plan from template |
| GET | `/api/onboarding/plans/{id}` | Get plan |
| POST | `/api/onboarding/plans/{id}/tasks/{task_id}/complete` | Mark task done |

### Payroll
| Method | Path | Purpose |
|--------|------|---------|
| POST/GET | `/api/employer/compensation` | Create / list compensation records |
| POST | `/api/employer/payroll/runs` | Initiate + complete a payroll run |
| GET | `/api/employer/payroll/runs` | List all runs |
| GET | `/api/employer/payroll/runs/{id}` | Get specific run |
| GET | `/api/employer/payroll/runs/{id}/payslips` | Get payslips |

Interactive docs at `http://localhost:8000/docs`.

---

## Layout

```
backend/
  app/
    main.py              FastAPI app + all routes
    config.py            env/config
    schemas.py           Pydantic request/response models
    consent_store.py     ConsentRecord, Consent_Manager, SignalType enum
    signal_store.py      Signal dataclass, Signal_Processor, Signal_Store
    model_registry.py    ModelVersion, ModelPrediction, Model_Registry
    evaluation_models.py 4 LLM-backed predictors
    onboarding_store.py  OnboardingTemplate, OnboardingPlan, task completion
    payroll_store.py     CompensationRecord, PayrollRun, Payslip, validation
    employer_store.py    Employer, Job, Application CRUD
    llm/
      client.py          Gemini/Mistral call + mock fallback
      mock.py            deterministic offline responses
    pipeline/stages.py   interview pipeline stages
    prompts/             agent prompt library (.md files)
  tests/                 pytest + Hypothesis test suite
  requirements.txt
  .env.example
frontend/
  src/
    EmployerDashboard.jsx  Jobs / Onboarding / Payroll tabs
    App.jsx                SPA routing
    api.js                 fetch wrapper for all API calls
  vite.config.js           dev proxy to backend
.kiro/specs/              spec-driven development artifacts
  engineering-lifecycle-platform/
    requirements.md
    design.md
    tasks.md
```
