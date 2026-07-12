# Contributing to HireAI Engineering Lifecycle Platform

Thanks for your interest in contributing. This is an open-contribution project — all skill levels welcome.

---

## Ground rules

- Be respectful and constructive in all discussions
- One feature or fix per pull request — keep PRs focused
- Write tests for any new functionality (unit + property-based where applicable)
- Follow the existing code patterns: FastAPI routes, `@dataclass` + Valkey/memory storage, Pydantic schemas, React SPA

---

## How to contribute

### 1. Fork and clone

```bash
git clone https://github.com/<your-username>/hireai-recruitment.git
```

### 2. Set up locally

```bash
# Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # no API key needed — runs in mock mode
uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

### 3. Pick an issue

- Look for issues labelled **`good first issue`** or **`help wanted`**
- Comment on the issue to claim it before starting work
- If you have an idea not covered by an existing issue, open one first to discuss

### 4. Branch naming

```
feat/short-description
fix/short-description
docs/short-description
```

### 5. Commit message format

All commits **must** follow this format (enforced by CI):

```
[ADD] module: short description (max 80 chars)
[FIX] module: short description
[IMP] module: short description (improvement/refactor)
```

Examples:
```
[ADD] compliance: add UK jurisdiction rule templates
[FIX] payroll: handle zero-deduction edge case in net pay calc
[IMP] signal_store: reduce memory footprint of query_signals
```

### 6. Open a pull request

- Target branch: `main`
- Fill out the PR template
- A Gemini AI review will run automatically and leave comments
- A human maintainer will do a final review before merging

---

## What not to do

- Don't open a PR that re-implements existing functionality in a different style
- Don't submit a PR that breaks existing tests
- Don't add dependencies without discussion — open an issue first
- Don't copy this codebase and launch a competing service (see LICENSE)

---

## Project structure

```
backend/app/          Python modules (stores, routes, models)
backend/tests/        pytest + Hypothesis tests
frontend/src/         React components + API client
.kiro/specs/          Spec-driven development artifacts
.github/              CI workflows + issue templates
```

## Questions?

Open a [Discussion](https://github.com/mehtahet619/hireai-recruitment/discussions) or drop a comment on any issue.
