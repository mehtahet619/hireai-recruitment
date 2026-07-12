"""Property-based tests for the Onboarding module (Task 4.2).

Property tested:
  Property 10: Onboarding task completion is idempotent.

  For any OnboardingPlan and task_id, calling complete_task twice with the
  same task_id SHALL result in the same final plan state as calling it once:
    - completed_at timestamp SHALL equal the first completion's timestamp
    - the task SHALL remain marked done (completed_at is not None)

# Feature: engineering-lifecycle-platform, Property 10: Onboarding task completion is idempotent
Validates: Requirements 4.3
"""
from __future__ import annotations

import uuid

from hypothesis import given, settings
from hypothesis import strategies as st

from app.onboarding_store import (
    OnboardingTask,
    OnboardingTemplate,
    _memory_store,
    complete_task,
    create_plan_from_template,
    get_overdue_tasks,
    get_plan,
    save_template,
)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Valid ISO-8601 date strings (YYYY-MM-DD) in a reasonable range so that
# due-offset arithmetic never breaks serialization.
hire_date_strategy = st.dates(
    min_value=__import__("datetime").date(2020, 1, 1),
    max_value=__import__("datetime").date(2030, 12, 31),
).map(lambda d: d.isoformat())

# due_offset_days can be any non-negative integer (0 = due on hire date).
due_offset_days_strategy = st.integers(min_value=0, max_value=365)

# engineer_id / employer_id: non-empty printable strings, reasonable length.
identifier_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_"),
    min_size=1,
    max_size=40,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _setup_plan(engineer_id: str, hire_date: str, due_offset_days: int) -> tuple[str, str]:
    """
    Create a template with one task and a plan derived from it.

    Returns (plan_id, task_id).
    """
    employer_id = str(uuid.uuid4())

    task = OnboardingTask(
        task_id=str(uuid.uuid4()),
        title="Onboarding task",
        description="A task for property testing",
        due_offset_days=due_offset_days,
        assigned_role="engineer",
        completed_at=None,
    )
    template = OnboardingTemplate(
        template_id=str(uuid.uuid4()),
        employer_id=employer_id,
        name="Test Template",
        tasks=[task],
    )
    save_template(template)

    plan = create_plan_from_template(
        engineer_id=engineer_id,
        employer_id=employer_id,
        template_id=template.template_id,
        hire_date=hire_date,
    )

    return plan.plan_id, plan.tasks[0].task_id


# ---------------------------------------------------------------------------
# Property 10: Onboarding task completion is idempotent
#
# For any OnboardingPlan and task_id, calling complete_task twice with the
# same task_id SHALL result in the same final plan state as calling it once.
#
# Feature: engineering-lifecycle-platform, Property 10: Onboarding task completion is idempotent
# Validates: Requirements 4.3
# ---------------------------------------------------------------------------

@given(
    engineer_id=identifier_strategy,
    hire_date=hire_date_strategy,
    due_offset_days=due_offset_days_strategy,
)
@settings(max_examples=200)
def test_complete_task_idempotent(
    engineer_id: str,
    hire_date: str,
    due_offset_days: int,
) -> None:
    """Property 10: complete_task is idempotent.

    Calling complete_task a second time with the same task_id must not change
    the completed_at timestamp and the task must remain marked done.

    Validates: Requirements 4.3
    """
    # --- Setup: fresh store for every Hypothesis example ---
    _memory_store.clear()

    plan_id, task_id = _setup_plan(engineer_id, hire_date, due_offset_days)

    # --- First completion ---
    plan_after_first = complete_task(plan_id, task_id)
    task_after_first = next(t for t in plan_after_first.tasks if t.task_id == task_id)
    first_completed_at = task_after_first.completed_at

    # Sanity: first completion must have set a timestamp
    assert first_completed_at is not None, (
        "After the first complete_task call, completed_at must not be None"
    )

    # --- Second completion (idempotent call) ---
    plan_after_second = complete_task(plan_id, task_id)
    task_after_second = next(t for t in plan_after_second.tasks if t.task_id == task_id)
    second_completed_at = task_after_second.completed_at

    # --- Assertions ---

    # The completed_at timestamp must be unchanged after the second call.
    assert second_completed_at == first_completed_at, (
        f"completed_at changed after second complete_task call: "
        f"first={first_completed_at!r}, second={second_completed_at!r}"
    )

    # The task must still be marked done (completed_at is not None).
    assert second_completed_at is not None, (
        "Task must remain marked done after idempotent second call"
    )

    # The persisted plan must also reflect the stable timestamp.
    persisted = get_plan(plan_id)
    assert persisted is not None, "Plan must still exist after both complete_task calls"
    persisted_task = next(t for t in persisted.tasks if t.task_id == task_id)
    assert persisted_task.completed_at == first_completed_at, (
        "Persisted plan completed_at must match the first completion's timestamp"
    )


# ---------------------------------------------------------------------------
# Property 11: Overdue task detection covers all tenants
#
# For any employer_id and any OnboardingTask whose due date
# (hire_date + due_offset_days) is strictly before the current date and whose
# completed_at is None, get_overdue_tasks SHALL include that task in its
# results.
#
# Feature: engineering-lifecycle-platform, Property 11: Overdue task detection covers all tenants
# Validates: Requirements 4.4
# ---------------------------------------------------------------------------

from datetime import date as _date


@given(
    days_overdue=st.integers(min_value=1, max_value=365),
    due_offset_days=st.integers(min_value=0, max_value=100),
)
@settings(max_examples=200)
def test_overdue_task_detection_completeness(
    days_overdue: int,
    due_offset_days: int,
) -> None:
    """Property 11: get_overdue_tasks covers all overdue tasks for every tenant.

    Given an OnboardingTask whose due date (hire_date + due_offset_days) is
    strictly before today and whose completed_at is None, get_overdue_tasks
    must include that task in its output.

    Validates: Requirements 4.4
    """
    # --- Setup: clear the store before each example ---
    _memory_store.clear()

    today = _date.today()

    # hire_date is chosen so that:
    #   hire_date + due_offset_days = today - days_overdue  (strictly < today)
    hire_date = today - __import__("datetime").timedelta(days=days_overdue + due_offset_days)
    hire_date_str = hire_date.isoformat()

    employer_id = str(uuid.uuid4())
    engineer_id = str(uuid.uuid4())

    # Build a template with exactly one task that will be overdue
    task = OnboardingTask(
        task_id=str(uuid.uuid4()),
        title="Overdue onboarding task",
        description="This task should be detected as overdue",
        due_offset_days=due_offset_days,
        assigned_role="engineer",
        completed_at=None,  # incomplete — must be detected
    )
    template = OnboardingTemplate(
        template_id=str(uuid.uuid4()),
        employer_id=employer_id,
        name="Overdue Test Template",
        tasks=[task],
    )
    save_template(template)

    plan = create_plan_from_template(
        engineer_id=engineer_id,
        employer_id=employer_id,
        template_id=template.template_id,
        hire_date=hire_date_str,
    )

    # The plan's task inherits due_offset_days from the template; confirm it
    # is genuinely overdue before asserting.
    plan_task = plan.tasks[0]
    due_date = hire_date + __import__("datetime").timedelta(days=plan_task.due_offset_days)
    assert due_date < today, (
        f"Test setup error: due_date {due_date} is not strictly before today {today}"
    )

    # --- Exercise ---
    overdue_pairs = get_overdue_tasks(employer_id)

    # --- Assert: the overdue task must appear in the results ---
    overdue_task_ids = {t.task_id for _, t in overdue_pairs}
    assert plan_task.task_id in overdue_task_ids, (
        f"Expected task {plan_task.task_id} (due {due_date}) to be in overdue results "
        f"for employer {employer_id}, but got task ids: {overdue_task_ids}. "
        f"hire_date={hire_date_str}, due_offset_days={due_offset_days}, "
        f"days_overdue={days_overdue}, today={today}"
    )
