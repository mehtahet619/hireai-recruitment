# AI Recruiter

Full-stack reference implementation of a prompt-driven recruiting pipeline:

```
Job Description ──► parse ──► Resume ──► analyze ──► questions ──► score ──► summary
```

- **Backend:** FastAPI, Google Gemini provider, with a deterministic **mock mode** so it
  runs with no API key.
- **Frontend:** minimal React (Vite) UI that runs the whole pipeline and shows the score,
  requirement matches, screening questions, and recruiter summary.
- **Prompts:** the agent prompts live in `backend/app/prompts/` (system, personality,
  resume analyzer, JD parser, question generator, interview, feedback, score agent,
  guardrails). See `backend/app/prompts/README.md`.

Design principles: evidence-over-inference, job-relatedness, human-in-the-loop, a
protected-characteristic **bias firewall**, prompt-injection defense, and deterministic,
auditable scoring. This is a reference implementation, **not legal advice** — configure
notice/retention/audit per your jurisdiction.

---

## Quick start

### 1. Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # optional: add GEMINI_API_KEY for real evaluations
uvicorn app.main:app --reload --port 8000
```

Without an API key the backend runs in **MOCK mode** automatically. To use Gemini, set
`GEMINI_API_KEY` in `backend/.env` (get one at https://aistudio.google.com/app/apikey).
Force mock with `USE_MOCK_LLM=true`.

Health check: `curl http://localhost:8000/api/health`

### 2. Frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173  (proxies /api → http://localhost:8000)
```

Open http://localhost:5173, paste a JD and resume, click **Run pipeline**.

---

## Deploy (production)

Uses **Render** (backend + frontend) with **Valkey** (sessions) and **Cloudflare R2** (video + reviews).

### 1. Create free persistence services

| Service | Sign up | What to copy |
|---------|---------|--------------|
| [Render Valkey](https://render.com/docs/valkey) or any Valkey host | Free instance | `VALKEY_URL` |
| [Cloudflare R2](https://dash.cloudflare.com) | Create bucket + API token | `S3_ENDPOINT`, `S3_BUCKET`, keys |

R2 endpoint format: `https://<account_id>.r2.cloudflarestorage.com`

### 2. Deploy on Render

1. Go to [Render Dashboard](https://dashboard.render.com) → **New** → **Blueprint**
2. Connect repo: `https://github.com/mehtahet619/ai-recruiter`
3. Set secret env vars when prompted:
   - `GEMINI_API_KEY` or `MISTRAL_API_KEY`
   - `JWT_SECRET`
   - `VALKEY_URL`
   - `S3_ENDPOINT`, `S3_BUCKET`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`
   - `S3_PUBLIC_BASE` (optional, R2 public bucket URL)
4. Click **Apply** — Render deploys API + static frontend automatically

`render.yaml` wires `VITE_API_BASE` and `CORS_ORIGINS` between services.

Verify: `GET https://<your-api>.onrender.com/api/health` should show:
```json
{"session_backend":"valkey","storage_backend":"s3",...}
```

---

## API

| Method | Path | Body | Purpose |
|---|---|---|---|
| GET | `/api/health` | — | status + mock/model |
| POST | `/api/jd/parse` | `{job_description}` | JD → requirements |
| POST | `/api/resume/analyze` | `{resume, requirements, candidate_id}` | resume analysis |
| POST | `/api/questions/generate` | `{requirements, candidate_id?}` | screening questions |
| POST | `/api/score` | `{resume_analysis, interview_assessments?, recruiter_weights?}` | score |
| POST | `/api/feedback` | `{score, resume_analysis?, authorize_candidate_message?}` | summary |
| POST | `/api/pipeline/run` | `{job_description, resume, candidate_id}` | full pipeline |

Interactive docs at `http://localhost:8000/docs`.

---

## Tests

```bash
cd backend && source .venv/bin/activate
pip install pytest
USE_MOCK_LLM=true pytest
```

---

## Layout

```
backend/
  app/
    main.py            FastAPI app + routes
    config.py          env/config (+ mock detection)
    prompts_loader.py  composes system prompt from prompt files
    prompts/           the agent prompt library (.md)
    llm/
      client.py        Gemini call (JSON mode) + mock fallback
      mock.py          deterministic offline responses
    pipeline/stages.py each stage: build prompt → call LLM → JSON
    schemas.py         pydantic request/response models
  requirements.txt
  .env.example
frontend/
  src/App.jsx          single-page UI
  src/api.js           fetch wrapper
  vite.config.js       dev proxy to backend
```
