"""Employer and Job persistence.

Storage priority:
  1. Supabase Postgres (SUPABASE_DB_URL set)  — persistent, horizontally scalable
  2. Valkey (VALKEY_URL set)                  — persistent, single-node
  3. In-memory dict                           — local dev / test only

All three back-ends expose the same Python API so callers are unaware of which
is active.
"""
from __future__ import annotations

import json
import uuid
import hashlib
import hmac
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any

from .config import get_settings

# ── in-memory fallback ────────────────────────────────────────────────────────
_memory_employers: dict[str, str] = {}
_memory_jobs: dict[str, str] = {}
_memory_applications: dict[str, str] = {}

EMPLOYER_TTL = 60 * 60 * 24 * 365  # 1 year (for Valkey only)

PLANS = {
    "starter":    {"name": "Starter",    "price": 99,   "job_limit": 3},
    "growth":     {"name": "Growth",     "price": 199,  "job_limit": 20},
    "enterprise": {"name": "Enterprise", "price": None, "job_limit": None},
}


# ── backend selectors ─────────────────────────────────────────────────────────

def _db():
    """Return a psycopg2 connection or None."""
    from .db import get_conn
    return get_conn()


def _valkey():
    s = get_settings()
    if not s.valkey_url:
        return None
    import valkey
    return valkey.from_url(s.valkey_url, decode_responses=True)


# ── password helpers ──────────────────────────────────────────────────────────

def _hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


def _check_password(pw: str, hashed: str) -> bool:
    return hmac.compare_digest(_hash_password(pw), hashed)


# ── Employer dataclass ────────────────────────────────────────────────────────

@dataclass
class Employer:
    employer_id: str
    email: str
    password_hash: str
    company_name: str
    plan: str = "free"
    plan_expires_at: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def _row_to_employer(row: dict) -> Employer:
    return Employer(
        employer_id=str(row["id"]),
        email=row["email"],
        password_hash=row["hashed_password"],
        company_name=row["company_name"],
        plan=row.get("plan", "free"),
        plan_expires_at=row.get("plan_expires_at"),
        created_at=str(row.get("created_at", "")),
    )


# ── Employer CRUD ─────────────────────────────────────────────────────────────

def create_employer(email: str, password: str, company_name: str) -> Employer:
    email = email.lower()
    conn = _db()
    if conn:
        from psycopg2 import IntegrityError
        from .db import execute
        try:
            row = execute(
                """INSERT INTO employers (id, email, hashed_password, company_name)
                   VALUES (%s, %s, %s, %s)
                   RETURNING id, email, hashed_password, company_name, plan,
                             plan_expires_at, created_at""",
                (str(uuid.uuid4()), email, _hash_password(password), company_name),
                fetch="one",
            )
        except IntegrityError:
            raise ValueError("Email already registered")
        return _row_to_employer(row)

    # Valkey / memory fallback
    client = _valkey()
    email_key = f"employer_email:{email}"
    if client:
        if client.get(email_key):
            raise ValueError("Email already registered")
    else:
        if email_key in _memory_employers:
            raise ValueError("Email already registered")

    emp = Employer(employer_id=str(uuid.uuid4()), email=email,
                   password_hash=_hash_password(password), company_name=company_name)
    _save_employer(emp)
    return emp


def get_employer(employer_id: str) -> Employer | None:
    conn = _db()
    if conn:
        from .db import execute
        row = execute(
            "SELECT id, email, hashed_password, company_name, plan, plan_expires_at, created_at "
            "FROM employers WHERE id = %s",
            (employer_id,), fetch="one",
        )
        return _row_to_employer(row) if row else None

    client = _valkey()
    key = f"employer:{employer_id}"
    raw = client.get(key) if client else _memory_employers.get(key)
    return Employer(**json.loads(raw)) if raw else None


def get_employer_by_email(email: str) -> Employer | None:
    conn = _db()
    if conn:
        from .db import execute
        row = execute(
            "SELECT id, email, hashed_password, company_name, plan, plan_expires_at, created_at "
            "FROM employers WHERE email = %s",
            (email.lower(),), fetch="one",
        )
        return _row_to_employer(row) if row else None

    client = _valkey()
    email_key = f"employer_email:{email.lower()}"
    if client:
        eid = client.get(email_key)
        raw = client.get(f"employer:{eid}") if eid else None
    else:
        eid = _memory_employers.get(email_key)
        raw = _memory_employers.get(f"employer:{eid}") if eid else None
    return Employer(**json.loads(raw)) if raw else None


def authenticate_employer(email: str, password: str) -> Employer | None:
    emp = get_employer_by_email(email)
    return emp if emp and _check_password(password, emp.password_hash) else None


def _save_employer(emp: Employer) -> None:
    conn = _db()
    if conn:
        from .db import execute
        execute(
            """INSERT INTO employers (id, email, hashed_password, company_name, plan, plan_expires_at)
               VALUES (%s, %s, %s, %s, %s, %s)
               ON CONFLICT (id) DO UPDATE
               SET email = EXCLUDED.email,
                   hashed_password = EXCLUDED.hashed_password,
                   company_name = EXCLUDED.company_name,
                   plan = EXCLUDED.plan,
                   plan_expires_at = EXCLUDED.plan_expires_at""",
            (emp.employer_id, emp.email, emp.password_hash,
             emp.company_name, emp.plan, emp.plan_expires_at),
        )
        return

    payload = json.dumps(asdict(emp))
    client = _valkey()
    if client:
        client.setex(f"employer:{emp.employer_id}", EMPLOYER_TTL, payload)
        client.setex(f"employer_email:{emp.email}", EMPLOYER_TTL, emp.employer_id)
    else:
        _memory_employers[f"employer:{emp.employer_id}"] = payload
        _memory_employers[f"employer_email:{emp.email}"] = emp.employer_id


def activate_plan(employer_id: str, plan: str) -> Employer:
    emp = get_employer(employer_id)
    if not emp:
        raise ValueError("Employer not found")
    emp.plan = plan
    emp.plan_expires_at = (datetime.now(timezone.utc) + timedelta(days=31)).isoformat()
    _save_employer(emp)
    return emp


# ── Job dataclass ─────────────────────────────────────────────────────────────

@dataclass
class Job:
    job_id: str
    employer_id: str
    title: str
    description: str
    location: str
    employment_type: str
    is_active: bool
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    application_count: int = 0


def _row_to_job(row: dict) -> Job:
    return Job(
        job_id=str(row["id"]),
        employer_id=str(row["employer_id"]),
        title=row["title"],
        description=row.get("description") or "",
        location=row.get("location", "Remote"),
        employment_type=row.get("employment_type", "full-time"),
        is_active=row.get("is_active", True),
        created_at=str(row.get("created_at", "")),
        application_count=row.get("application_count", 0),
    )


# ── Job CRUD ──────────────────────────────────────────────────────────────────

def create_job(employer_id: str, title: str, description: str,
               location: str = "Remote", employment_type: str = "full-time") -> Job:
    job_id = str(uuid.uuid4())
    conn = _db()
    if conn:
        from .db import execute
        row = execute(
            """INSERT INTO job_listings
               (id, employer_id, title, description, location, employment_type, is_active, application_count)
               VALUES (%s, %s, %s, %s, %s, %s, true, 0)
               RETURNING id, employer_id, title, description, location, employment_type,
                         is_active, application_count, created_at""",
            (job_id, employer_id, title, description, location, employment_type),
            fetch="one",
        )
        return _row_to_job(row)

    job = Job(job_id=job_id, employer_id=employer_id, title=title,
              description=description, location=location,
              employment_type=employment_type, is_active=True)
    _save_job(job)
    client = _valkey()
    emp_jobs_key = f"employer_jobs:{employer_id}"
    if client:
        client.sadd(emp_jobs_key, job_id)
    else:
        ids = json.loads(_memory_jobs.get(emp_jobs_key, "[]"))
        ids.append(job_id)
        _memory_jobs[emp_jobs_key] = json.dumps(ids)
    return job


def _save_job(job: Job) -> None:
    conn = _db()
    if conn:
        from .db import execute
        execute(
            """INSERT INTO job_listings
               (id, employer_id, title, description, location, employment_type,
                is_active, application_count)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (id) DO UPDATE
               SET title = EXCLUDED.title,
                   description = EXCLUDED.description,
                   location = EXCLUDED.location,
                   employment_type = EXCLUDED.employment_type,
                   is_active = EXCLUDED.is_active,
                   application_count = EXCLUDED.application_count,
                   updated_at = now()""",
            (job.job_id, job.employer_id, job.title, job.description,
             job.location, job.employment_type, job.is_active, job.application_count),
        )
        return

    payload = json.dumps(asdict(job))
    client = _valkey()
    if client:
        client.set(f"job:{job.job_id}", payload)
    else:
        _memory_jobs[f"job:{job.job_id}"] = payload


def get_job(job_id: str) -> Job | None:
    conn = _db()
    if conn:
        from .db import execute
        row = execute(
            "SELECT id, employer_id, title, description, location, employment_type, "
            "is_active, application_count, created_at FROM job_listings WHERE id = %s",
            (job_id,), fetch="one",
        )
        return _row_to_job(row) if row else None

    client = _valkey()
    raw = client.get(f"job:{job_id}") if client else _memory_jobs.get(f"job:{job_id}")
    return Job(**json.loads(raw)) if raw else None


def update_job(job: Job) -> None:
    _save_job(job)


def list_jobs(active_only: bool = True) -> list[Job]:
    conn = _db()
    if conn:
        from .db import execute
        sql = ("SELECT id, employer_id, title, description, location, employment_type, "
               "is_active, application_count, created_at FROM job_listings")
        if active_only:
            sql += " WHERE is_active = true"
        sql += " ORDER BY created_at DESC"
        rows = execute(sql, fetch="all") or []
        return [_row_to_job(r) for r in rows]

    client = _valkey()
    jobs = []
    src = (list(client.keys("job:*")) if client else
           [k for k in _memory_jobs if k.startswith("job:") and "employer_jobs" not in k])
    for k in src:
        if "employer_jobs" in k:
            continue
        raw = client.get(k) if client else _memory_jobs.get(k)
        if raw:
            try:
                j = Job(**json.loads(raw))
                if not active_only or j.is_active:
                    jobs.append(j)
            except Exception:
                pass
    return sorted(jobs, key=lambda j: j.created_at, reverse=True)


def list_employer_jobs(employer_id: str) -> list[Job]:
    conn = _db()
    if conn:
        from .db import execute
        rows = execute(
            "SELECT id, employer_id, title, description, location, employment_type, "
            "is_active, application_count, created_at "
            "FROM job_listings WHERE employer_id = %s ORDER BY created_at DESC",
            (employer_id,), fetch="all",
        ) or []
        return [_row_to_job(r) for r in rows]

    client = _valkey()
    emp_jobs_key = f"employer_jobs:{employer_id}"
    job_ids = (list(client.smembers(emp_jobs_key)) if client
               else json.loads(_memory_jobs.get(emp_jobs_key, "[]")))
    jobs = [j for jid in job_ids if (j := get_job(jid))]
    return sorted(jobs, key=lambda j: j.created_at, reverse=True)


# ── Application dataclass ─────────────────────────────────────────────────────

@dataclass
class Application:
    application_id: str
    job_id: str
    employer_id: str
    candidate_name: str
    candidate_email: str
    resume: str
    session_id: str | None = None
    review_id: str | None = None
    score: dict[str, Any] | None = None
    feedback: dict[str, Any] | None = None
    status: str = "applied"
    evaluation_model_score: dict | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def _row_to_app(row: dict) -> Application:
    return Application(
        application_id=str(row["id"]),
        job_id=str(row["job_id"]),
        employer_id=str(row["employer_id"]),
        candidate_name=row["candidate_name"],
        candidate_email=row["candidate_email"],
        resume=row.get("resume", ""),
        session_id=row.get("session_id"),
        review_id=row.get("review_id"),
        score=row.get("score"),
        feedback=row.get("feedback"),
        status=row.get("status", "applied"),
        evaluation_model_score=row.get("evaluation_model_score"),
        created_at=str(row.get("created_at", "")),
    )


# ── Application CRUD ──────────────────────────────────────────────────────────

def create_application(job_id: str, employer_id: str, candidate_name: str,
                        candidate_email: str, resume: str) -> Application:
    app_id = str(uuid.uuid4())
    conn = _db()
    if conn:
        from .db import execute
        row = execute(
            """INSERT INTO applications
               (id, job_id, employer_id, candidate_name, candidate_email, resume, status)
               VALUES (%s, %s, %s, %s, %s, %s, 'applied')
               RETURNING id, job_id, employer_id, candidate_name, candidate_email,
                         resume, session_id, review_id, score, feedback,
                         status, evaluation_model_score, created_at""",
            (app_id, job_id, employer_id, candidate_name, candidate_email, resume),
            fetch="one",
        )
        # increment job application_count
        execute("UPDATE job_listings SET application_count = application_count + 1 WHERE id = %s",
                (job_id,))
        return _row_to_app(row)

    app = Application(application_id=app_id, job_id=job_id, employer_id=employer_id,
                      candidate_name=candidate_name, candidate_email=candidate_email,
                      resume=resume)
    _save_application(app)
    client = _valkey()
    key = f"job_applications:{job_id}"
    if client:
        client.sadd(key, app_id)
    else:
        ids = json.loads(_memory_applications.get(key, "[]"))
        ids.append(app_id)
        _memory_applications[key] = json.dumps(ids)
    job = get_job(job_id)
    if job:
        job.application_count += 1
        _save_job(job)
    return app


def _save_application(app: Application) -> None:
    conn = _db()
    if conn:
        from .db import execute
        execute(
            """INSERT INTO applications
               (id, job_id, employer_id, candidate_name, candidate_email, resume,
                session_id, review_id, score, feedback, status, evaluation_model_score)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (id) DO UPDATE
               SET session_id = EXCLUDED.session_id,
                   review_id = EXCLUDED.review_id,
                   score = EXCLUDED.score,
                   feedback = EXCLUDED.feedback,
                   status = EXCLUDED.status,
                   evaluation_model_score = EXCLUDED.evaluation_model_score""",
            (app.application_id, app.job_id, app.employer_id,
             app.candidate_name, app.candidate_email, app.resume,
             app.session_id, app.review_id,
             json.dumps(app.score) if app.score else None,
             json.dumps(app.feedback) if app.feedback else None,
             app.status,
             json.dumps(app.evaluation_model_score) if app.evaluation_model_score else None),
        )
        return

    payload = json.dumps(asdict(app))
    client = _valkey()
    if client:
        client.set(f"application:{app.application_id}", payload)
    else:
        _memory_applications[f"application:{app.application_id}"] = payload


def get_application(application_id: str) -> Application | None:
    conn = _db()
    if conn:
        from .db import execute
        row = execute(
            "SELECT id, job_id, employer_id, candidate_name, candidate_email, resume, "
            "session_id, review_id, score, feedback, status, evaluation_model_score, created_at "
            "FROM applications WHERE id = %s",
            (application_id,), fetch="one",
        )
        return _row_to_app(row) if row else None

    client = _valkey()
    raw = (client.get(f"application:{application_id}") if client
           else _memory_applications.get(f"application:{application_id}"))
    return Application(**json.loads(raw)) if raw else None


def update_application(app: Application) -> None:
    _save_application(app)


def list_job_applications(job_id: str) -> list[Application]:
    conn = _db()
    if conn:
        from .db import execute
        rows = execute(
            "SELECT id, job_id, employer_id, candidate_name, candidate_email, resume, "
            "session_id, review_id, score, feedback, status, evaluation_model_score, created_at "
            "FROM applications WHERE job_id = %s ORDER BY created_at DESC",
            (job_id,), fetch="all",
        ) or []
        return [_row_to_app(r) for r in rows]

    client = _valkey()
    key = f"job_applications:{job_id}"
    app_ids = (list(client.smembers(key)) if client
               else json.loads(_memory_applications.get(key, "[]")))
    apps = [a for aid in app_ids if (a := get_application(aid))]
    return sorted(apps, key=lambda a: a.created_at, reverse=True)


# ── Plan helpers ──────────────────────────────────────────────────────────────

def employer_can_post_job(employer_id: str) -> tuple[bool, str]:
    emp = get_employer(employer_id)
    if not emp:
        return False, "Employer not found"
    # Check expiry for paid plans
    if emp.plan not in ("free", "enterprise") and emp.plan_expires_at:
        exp = datetime.fromisoformat(emp.plan_expires_at)
        if datetime.now(timezone.utc) > exp:
            emp.plan = "free"
            emp.plan_expires_at = None
            _save_employer(emp)
            return False, "plan_expired"
    if emp.plan == "enterprise":
        return True, ""
    limit = PLANS.get(emp.plan, {}).get("job_limit") or 1  # free = 1
    active = [j for j in list_employer_jobs(employer_id) if j.is_active]
    if len(active) >= limit:
        return False, "upgrade_required"
    return True, ""
