"""Employer and Job persistence (Redis or memory)."""
from __future__ import annotations

import json
import uuid
import hashlib
import hmac
from dataclasses import asdict, dataclass, field
from typing import Any
from datetime import datetime, timezone

from .config import get_settings

_memory_employers: dict[str, str] = {}
_memory_jobs: dict[str, str] = {}
_memory_applications: dict[str, str] = {}

EMPLOYER_TTL = 60 * 60 * 24 * 365  # 1 year


def _redis():
    settings = get_settings()
    if not settings.redis_url:
        return None
    import redis
    return redis.from_url(settings.redis_url, decode_responses=True)


# ---------- helpers ----------

def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def _check_password(password: str, hashed: str) -> bool:
    return hmac.compare_digest(_hash_password(password), hashed)


# ---------- Employer ----------

@dataclass
class Employer:
    employer_id: str
    email: str
    password_hash: str
    company_name: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def _emp_key(employer_id: str) -> str:
    return f"employer:{employer_id}"


def _emp_email_key(email: str) -> str:
    return f"employer_email:{email.lower()}"


def create_employer(email: str, password: str, company_name: str) -> Employer:
    client = _redis()
    email_key = _emp_email_key(email)
    # check duplicate
    if client:
        if client.get(email_key):
            raise ValueError("Email already registered")
    else:
        if email_key in _memory_employers:
            raise ValueError("Email already registered")

    emp = Employer(
        employer_id=str(uuid.uuid4()),
        email=email.lower(),
        password_hash=_hash_password(password),
        company_name=company_name,
    )
    payload = json.dumps(asdict(emp))
    if client:
        client.setex(_emp_key(emp.employer_id), EMPLOYER_TTL, payload)
        client.setex(email_key, EMPLOYER_TTL, emp.employer_id)
    else:
        _memory_employers[_emp_key(emp.employer_id)] = payload
        _memory_employers[email_key] = emp.employer_id
    return emp


def get_employer_by_email(email: str) -> Employer | None:
    client = _redis()
    email_key = _emp_email_key(email)
    if client:
        eid = client.get(email_key)
        if not eid:
            return None
        raw = client.get(_emp_key(eid))
    else:
        eid = _memory_employers.get(email_key)
        if not eid:
            return None
        raw = _memory_employers.get(_emp_key(eid))
    if not raw:
        return None
    return Employer(**json.loads(raw))


def get_employer(employer_id: str) -> Employer | None:
    client = _redis()
    raw = client.get(_emp_key(employer_id)) if client else _memory_employers.get(_emp_key(employer_id))
    if not raw:
        return None
    return Employer(**json.loads(raw))


def authenticate_employer(email: str, password: str) -> Employer | None:
    emp = get_employer_by_email(email)
    if emp and _check_password(password, emp.password_hash):
        return emp
    return None


# ---------- Job ----------

@dataclass
class Job:
    job_id: str
    employer_id: str
    title: str
    description: str
    location: str
    employment_type: str  # full-time, part-time, contract
    is_active: bool
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    application_count: int = 0


def _job_key(job_id: str) -> str:
    return f"job:{job_id}"


def _employer_jobs_key(employer_id: str) -> str:
    return f"employer_jobs:{employer_id}"


def create_job(employer_id: str, title: str, description: str,
               location: str = "Remote", employment_type: str = "full-time") -> Job:
    job = Job(
        job_id=str(uuid.uuid4()),
        employer_id=employer_id,
        title=title,
        description=description,
        location=location,
        employment_type=employment_type,
        is_active=True,
    )
    _save_job(job)
    # add to employer's job list
    client = _redis()
    emp_jobs_key = _employer_jobs_key(employer_id)
    if client:
        client.sadd(emp_jobs_key, job.job_id)
    else:
        existing = json.loads(_memory_jobs.get(emp_jobs_key, "[]"))
        existing.append(job.job_id)
        _memory_jobs[emp_jobs_key] = json.dumps(existing)
    return job


def _save_job(job: Job) -> None:
    payload = json.dumps(asdict(job))
    client = _redis()
    if client:
        client.set(_job_key(job.job_id), payload)
    else:
        _memory_jobs[_job_key(job.job_id)] = payload


def get_job(job_id: str) -> Job | None:
    client = _redis()
    raw = client.get(_job_key(job_id)) if client else _memory_jobs.get(_job_key(job_id))
    if not raw:
        return None
    return Job(**json.loads(raw))


def update_job(job: Job) -> None:
    _save_job(job)


def list_jobs(active_only: bool = True) -> list[Job]:
    client = _redis()
    jobs = []
    if client:
        keys = client.keys("job:*")
        for k in keys:
            if "employer_jobs" in k:
                continue
            raw = client.get(k)
            if raw:
                try:
                    j = Job(**json.loads(raw))
                    if not active_only or j.is_active:
                        jobs.append(j)
                except Exception:
                    pass
    else:
        for k, v in _memory_jobs.items():
            if k.startswith("job:") and "employer_jobs" not in k:
                try:
                    j = Job(**json.loads(v))
                    if not active_only or j.is_active:
                        jobs.append(j)
                except Exception:
                    pass
    jobs.sort(key=lambda j: j.created_at, reverse=True)
    return jobs


def list_employer_jobs(employer_id: str) -> list[Job]:
    client = _redis()
    emp_jobs_key = _employer_jobs_key(employer_id)
    if client:
        job_ids = list(client.smembers(emp_jobs_key))
    else:
        job_ids = json.loads(_memory_jobs.get(emp_jobs_key, "[]"))
    jobs = []
    for jid in job_ids:
        j = get_job(jid)
        if j:
            jobs.append(j)
    jobs.sort(key=lambda j: j.created_at, reverse=True)
    return jobs


# ---------- Application ----------

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
    status: str = "applied"  # applied | interviewing | scored | reviewed
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def _app_key(application_id: str) -> str:
    return f"application:{application_id}"


def _job_apps_key(job_id: str) -> str:
    return f"job_applications:{job_id}"


def create_application(job_id: str, employer_id: str, candidate_name: str,
                        candidate_email: str, resume: str) -> Application:
    app = Application(
        application_id=str(uuid.uuid4()),
        job_id=job_id,
        employer_id=employer_id,
        candidate_name=candidate_name,
        candidate_email=candidate_email,
        resume=resume,
    )
    _save_application(app)
    # link to job
    client = _redis()
    job_apps_key = _job_apps_key(job_id)
    if client:
        client.sadd(job_apps_key, app.application_id)
    else:
        existing = json.loads(_memory_applications.get(job_apps_key, "[]"))
        existing.append(app.application_id)
        _memory_applications[job_apps_key] = json.dumps(existing)
    # increment job application count
    job = get_job(job_id)
    if job:
        job.application_count += 1
        _save_job(job)
    return app


def _save_application(app: Application) -> None:
    payload = json.dumps(asdict(app))
    client = _redis()
    if client:
        client.set(_app_key(app.application_id), payload)
    else:
        _memory_applications[_app_key(app.application_id)] = payload


def get_application(application_id: str) -> Application | None:
    client = _redis()
    raw = (client.get(_app_key(application_id)) if client
           else _memory_applications.get(_app_key(application_id)))
    if not raw:
        return None
    data = json.loads(raw)
    return Application(**data)


def update_application(app: Application) -> None:
    _save_application(app)


def list_job_applications(job_id: str) -> list[Application]:
    client = _redis()
    job_apps_key = _job_apps_key(job_id)
    if client:
        app_ids = list(client.smembers(job_apps_key))
    else:
        app_ids = json.loads(_memory_applications.get(job_apps_key, "[]"))
    apps = []
    for aid in app_ids:
        a = get_application(aid)
        if a:
            apps.append(a)
    apps.sort(key=lambda a: a.created_at, reverse=True)
    return apps
