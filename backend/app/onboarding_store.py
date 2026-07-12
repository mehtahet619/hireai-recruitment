"""Onboarding module — templates, plans, and task management (Valkey or memory)."""
from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from .config import get_settings

# ---------------------------------------------------------------------------
# In-memory fallback stores
# ---------------------------------------------------------------------------
_memory_store: dict[str, str] = {}

ONBOARDING_TTL = 60 * 60 * 24 * 365 * 2  # 2 years


def _valkey():
    settings = get_settings()
    if not settings.valkey_url:
        return None
    import valkey
    return valkey.from_url(settings.valkey_url, decode_responses=True)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class OnboardingTask:
    task_id: str
    title: str
    description: str
    due_offset_days: int
    assigned_role: str
    completed_at: Optional[str] = None  # ISO-8601 UTC, None if not completed


@dataclass
class OnboardingTemplate:
    template_id: str
    employer_id: str
    name: str
    tasks: list[OnboardingTask]
    version: int = 1
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class OnboardingPlan:
    plan_id: str
    engineer_id: str
    employer_id: str
    template_id: str
    hire_date: str   # ISO-8601 date string YYYY-MM-DD
    tasks: list[OnboardingTask]
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ---------------------------------------------------------------------------
# Storage key helpers
# ---------------------------------------------------------------------------

def _plan_key(plan_id: str) -> str:
    return f"onboarding_plan:{plan_id}"


def _template_key(template_id: str) -> str:
    return f"onboarding_template:{template_id}"


def _employer_plans_key(employer_id: str) -> str:
    return f"employer_onboarding_plans:{employer_id}"


def _employer_templates_key(employer_id: str) -> str:
    return f"employer_onboarding_templates:{employer_id}"


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def _serialize_task(task: OnboardingTask) -> dict:
    return asdict(task)


def _deserialize_task(data: dict) -> OnboardingTask:
    return OnboardingTask(
        task_id=data["task_id"],
        title=data["title"],
        description=data["description"],
        due_offset_days=data["due_offset_days"],
        assigned_role=data["assigned_role"],
        completed_at=data.get("completed_at"),
    )


def _serialize_plan(plan: OnboardingPlan) -> str:
    d = asdict(plan)
    return json.dumps(d)


def _deserialize_plan(raw: str) -> OnboardingPlan:
    d = json.loads(raw)
    d["tasks"] = [_deserialize_task(t) for t in d.get("tasks", [])]
    return OnboardingPlan(**d)


def _serialize_template(template: OnboardingTemplate) -> str:
    d = asdict(template)
    return json.dumps(d)


def _deserialize_template(raw: str) -> OnboardingTemplate:
    d = json.loads(raw)
    d["tasks"] = [_deserialize_task(t) for t in d.get("tasks", [])]
    return OnboardingTemplate(**d)


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
        client.setex(key, ONBOARDING_TTL, value)
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
# Template CRUD
# ---------------------------------------------------------------------------

def save_template(template: OnboardingTemplate) -> None:
    """Persist an OnboardingTemplate (create or overwrite)."""
    _store_set(_template_key(template.template_id), _serialize_template(template))
    _store_append_to_list(_employer_templates_key(template.employer_id), template.template_id)


def get_template(template_id: str) -> OnboardingTemplate | None:
    raw = _store_get(_template_key(template_id))
    if not raw:
        return None
    return _deserialize_template(raw)


def list_employer_templates(employer_id: str) -> list[OnboardingTemplate]:
    template_ids = _store_get_list(_employer_templates_key(employer_id))
    templates = []
    for tid in template_ids:
        t = get_template(tid)
        if t:
            templates.append(t)
    templates.sort(key=lambda t: t.created_at, reverse=True)
    return templates


# ---------------------------------------------------------------------------
# Plan CRUD
# ---------------------------------------------------------------------------

def save_plan(plan: OnboardingPlan) -> None:
    """Persist an OnboardingPlan (create or overwrite)."""
    _store_set(_plan_key(plan.plan_id), _serialize_plan(plan))
    _store_append_to_list(_employer_plans_key(plan.employer_id), plan.plan_id)


def get_plan(plan_id: str) -> OnboardingPlan | None:
    raw = _store_get(_plan_key(plan_id))
    if not raw:
        return None
    return _deserialize_plan(raw)


def list_employer_plans(employer_id: str) -> list[OnboardingPlan]:
    plan_ids = _store_get_list(_employer_plans_key(employer_id))
    plans = []
    for pid in plan_ids:
        p = get_plan(pid)
        if p:
            plans.append(p)
    plans.sort(key=lambda p: p.created_at, reverse=True)
    return plans


# ---------------------------------------------------------------------------
# Core business logic
# ---------------------------------------------------------------------------

def create_plan_from_template(
    engineer_id: str,
    employer_id: str,
    template_id: str,
    hire_date: str,
) -> OnboardingPlan:
    """
    Load the template and create a new OnboardingPlan for the given engineer.

    Each template task is deep-copied with a fresh task_id and completed_at=None
    so that completing a task on one plan never affects the template or another plan.

    Args:
        engineer_id: The engineer being onboarded.
        employer_id: The employer creating the plan.
        template_id: ID of the OnboardingTemplate to use.
        hire_date: ISO-8601 date string (YYYY-MM-DD) representing the hire date.

    Returns:
        The newly created and persisted OnboardingPlan.

    Raises:
        ValueError: If the template does not exist.
    """
    template = get_template(template_id)
    if template is None:
        raise ValueError(f"Template not found: {template_id}")

    plan_tasks = [
        OnboardingTask(
            task_id=str(uuid.uuid4()),
            title=t.title,
            description=t.description,
            due_offset_days=t.due_offset_days,
            assigned_role=t.assigned_role,
            completed_at=None,
        )
        for t in template.tasks
    ]

    plan = OnboardingPlan(
        plan_id=str(uuid.uuid4()),
        engineer_id=engineer_id,
        employer_id=employer_id,
        template_id=template_id,
        hire_date=hire_date,
        tasks=plan_tasks,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    save_plan(plan)
    return plan


def complete_task(plan_id: str, task_id: str) -> OnboardingPlan:
    """
    Mark a task as completed on an OnboardingPlan.

    Idempotent: if the task is already completed, the existing completed_at
    timestamp is preserved (not overwritten).

    Args:
        plan_id: The plan containing the task.
        task_id: The task to mark as completed.

    Returns:
        The updated OnboardingPlan.

    Raises:
        ValueError: If the plan or task is not found.
    """
    plan = get_plan(plan_id)
    if plan is None:
        raise ValueError(f"Plan not found: {plan_id}")

    task_found = False
    for task in plan.tasks:
        if task.task_id == task_id:
            task_found = True
            if task.completed_at is None:
                # Only set completed_at on first completion
                task.completed_at = datetime.now(timezone.utc).isoformat()
            # else: already completed — leave timestamp unchanged (idempotent)
            break

    if not task_found:
        raise ValueError(f"Task not found: {task_id} in plan {plan_id}")

    save_plan(plan)
    return plan


def get_overdue_tasks(employer_id: str) -> list[tuple[OnboardingPlan, OnboardingTask]]:
    """
    Return all incomplete tasks whose due date is strictly before today (UTC).

    Due date for a task = hire_date + due_offset_days.
    A task is overdue if:
      - completed_at is None, AND
      - due_date < today (UTC)

    Args:
        employer_id: Tenant scope for the query.

    Returns:
        List of (OnboardingPlan, OnboardingTask) tuples for all overdue tasks.
    """
    today = date.today()  # UTC date
    plans = list_employer_plans(employer_id)
    overdue: list[tuple[OnboardingPlan, OnboardingTask]] = []

    for plan in plans:
        try:
            hire_date = date.fromisoformat(plan.hire_date)
        except ValueError:
            # Skip plans with malformed hire_date
            continue

        for task in plan.tasks:
            if task.completed_at is not None:
                continue  # already done
            due_date = hire_date + timedelta(days=task.due_offset_days)
            if due_date < today:
                overdue.append((plan, task))

    return overdue
