"""Unit tests for backend/app/onboarding_store.py — Task 4.1.

Tests cover:
- OnboardingTemplate save/get/list
- OnboardingPlan save/get/list
- create_plan_from_template
- complete_task (including idempotence)
- get_overdue_tasks
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest

from app.onboarding_store import (
    OnboardingTask,
    OnboardingTemplate,
    OnboardingPlan,
    _memory_store,
    complete_task,
    create_plan_from_template,
    get_overdue_tasks,
    get_plan,
    get_template,
    list_employer_plans,
    list_employer_templates,
    save_plan,
    save_template,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_task(due_offset_days: int = 5, completed_at: str | None = None) -> OnboardingTask:
    return OnboardingTask(
        task_id=str(uuid.uuid4()),
        title="Setup laptop",
        description="Unbox and configure the laptop",
        due_offset_days=due_offset_days,
        assigned_role="engineer",
        completed_at=completed_at,
    )


def _make_template(employer_id: str | None = None, tasks: list | None = None) -> OnboardingTemplate:
    if employer_id is None:
        employer_id = str(uuid.uuid4())
    if tasks is None:
        tasks = [_make_task()]
    return OnboardingTemplate(
        template_id=str(uuid.uuid4()),
        employer_id=employer_id,
        name="Standard Engineer Onboarding",
        tasks=tasks,
    )


@pytest.fixture(autouse=True)
def clear_memory_store():
    """Wipe the in-memory store before each test for isolation."""
    _memory_store.clear()
    yield
    _memory_store.clear()


# ---------------------------------------------------------------------------
# Template CRUD
# ---------------------------------------------------------------------------

class TestTemplateCRUD:
    def test_save_and_get_template(self):
        tmpl = _make_template()
        save_template(tmpl)
        loaded = get_template(tmpl.template_id)
        assert loaded is not None
        assert loaded.template_id == tmpl.template_id
        assert loaded.name == tmpl.name
        assert len(loaded.tasks) == len(tmpl.tasks)

    def test_get_template_missing_returns_none(self):
        assert get_template("nonexistent-id") is None

    def test_list_employer_templates_returns_saved(self):
        employer_id = str(uuid.uuid4())
        t1 = _make_template(employer_id=employer_id)
        t2 = _make_template(employer_id=employer_id)
        save_template(t1)
        save_template(t2)
        result = list_employer_templates(employer_id)
        ids = {t.template_id for t in result}
        assert t1.template_id in ids
        assert t2.template_id in ids

    def test_list_employer_templates_empty(self):
        assert list_employer_templates("unknown-employer") == []

    def test_save_template_preserves_tasks(self):
        tasks = [
            _make_task(due_offset_days=1),
            _make_task(due_offset_days=7),
        ]
        tmpl = _make_template(tasks=tasks)
        save_template(tmpl)
        loaded = get_template(tmpl.template_id)
        assert len(loaded.tasks) == 2
        offsets = {t.due_offset_days for t in loaded.tasks}
        assert offsets == {1, 7}

    def test_save_template_updates_existing(self):
        tmpl = _make_template()
        save_template(tmpl)
        tmpl.name = "Updated Name"
        tmpl.version = 2
        save_template(tmpl)
        loaded = get_template(tmpl.template_id)
        assert loaded.name == "Updated Name"
        assert loaded.version == 2


# ---------------------------------------------------------------------------
# Plan CRUD
# ---------------------------------------------------------------------------

class TestPlanCRUD:
    def test_save_and_get_plan(self):
        plan = OnboardingPlan(
            plan_id=str(uuid.uuid4()),
            engineer_id=str(uuid.uuid4()),
            employer_id=str(uuid.uuid4()),
            template_id=str(uuid.uuid4()),
            hire_date="2024-01-15",
            tasks=[_make_task()],
        )
        save_plan(plan)
        loaded = get_plan(plan.plan_id)
        assert loaded is not None
        assert loaded.plan_id == plan.plan_id
        assert loaded.engineer_id == plan.engineer_id

    def test_get_plan_missing_returns_none(self):
        assert get_plan("nonexistent") is None

    def test_list_employer_plans_returns_saved(self):
        employer_id = str(uuid.uuid4())
        p1 = OnboardingPlan(
            plan_id=str(uuid.uuid4()),
            engineer_id=str(uuid.uuid4()),
            employer_id=employer_id,
            template_id=str(uuid.uuid4()),
            hire_date="2024-01-01",
            tasks=[],
        )
        p2 = OnboardingPlan(
            plan_id=str(uuid.uuid4()),
            engineer_id=str(uuid.uuid4()),
            employer_id=employer_id,
            template_id=str(uuid.uuid4()),
            hire_date="2024-02-01",
            tasks=[],
        )
        save_plan(p1)
        save_plan(p2)
        result = list_employer_plans(employer_id)
        ids = {p.plan_id for p in result}
        assert p1.plan_id in ids
        assert p2.plan_id in ids

    def test_list_employer_plans_empty(self):
        assert list_employer_plans("unknown-employer") == []


# ---------------------------------------------------------------------------
# create_plan_from_template
# ---------------------------------------------------------------------------

class TestCreatePlanFromTemplate:
    def test_creates_plan_with_copied_tasks(self):
        template = _make_template(tasks=[_make_task(1), _make_task(3)])
        save_template(template)

        plan = create_plan_from_template(
            engineer_id="eng-1",
            employer_id=template.employer_id,
            template_id=template.template_id,
            hire_date="2024-06-01",
        )

        assert plan.engineer_id == "eng-1"
        assert plan.employer_id == template.employer_id
        assert plan.template_id == template.template_id
        assert plan.hire_date == "2024-06-01"
        assert len(plan.tasks) == 2

    def test_plan_tasks_have_fresh_ids(self):
        template = _make_template(tasks=[_make_task()])
        original_task_id = template.tasks[0].task_id
        save_template(template)

        plan = create_plan_from_template(
            engineer_id="eng-1",
            employer_id=template.employer_id,
            template_id=template.template_id,
            hire_date="2024-06-01",
        )

        assert plan.tasks[0].task_id != original_task_id

    def test_plan_tasks_start_uncompleted(self):
        task = _make_task()
        task.completed_at = "2024-01-01T00:00:00+00:00"  # artificially completed
        template = _make_template(tasks=[task])
        save_template(template)

        plan = create_plan_from_template(
            engineer_id="eng-1",
            employer_id=template.employer_id,
            template_id=template.template_id,
            hire_date="2024-06-01",
        )

        assert plan.tasks[0].completed_at is None

    def test_plan_is_persisted(self):
        template = _make_template()
        save_template(template)
        plan = create_plan_from_template(
            engineer_id="eng-2",
            employer_id=template.employer_id,
            template_id=template.template_id,
            hire_date="2024-07-01",
        )
        loaded = get_plan(plan.plan_id)
        assert loaded is not None
        assert loaded.plan_id == plan.plan_id

    def test_raises_for_missing_template(self):
        with pytest.raises(ValueError, match="Template not found"):
            create_plan_from_template(
                engineer_id="eng-1",
                employer_id="emp-1",
                template_id="does-not-exist",
                hire_date="2024-01-01",
            )

    def test_plan_registered_under_employer(self):
        employer_id = str(uuid.uuid4())
        template = _make_template(employer_id=employer_id)
        save_template(template)
        plan = create_plan_from_template(
            engineer_id="eng-3",
            employer_id=employer_id,
            template_id=template.template_id,
            hire_date="2024-08-01",
        )
        plans = list_employer_plans(employer_id)
        assert any(p.plan_id == plan.plan_id for p in plans)


# ---------------------------------------------------------------------------
# complete_task
# ---------------------------------------------------------------------------

class TestCompleteTask:
    def test_marks_task_completed(self):
        template = _make_template(tasks=[_make_task()])
        save_template(template)
        plan = create_plan_from_template(
            engineer_id="eng-1",
            employer_id=template.employer_id,
            template_id=template.template_id,
            hire_date="2024-01-01",
        )
        task_id = plan.tasks[0].task_id
        updated = complete_task(plan.plan_id, task_id)
        assert updated.tasks[0].completed_at is not None

    def test_completion_is_persisted(self):
        template = _make_template(tasks=[_make_task()])
        save_template(template)
        plan = create_plan_from_template(
            engineer_id="eng-1",
            employer_id=template.employer_id,
            template_id=template.template_id,
            hire_date="2024-01-01",
        )
        task_id = plan.tasks[0].task_id
        complete_task(plan.plan_id, task_id)
        reloaded = get_plan(plan.plan_id)
        assert reloaded.tasks[0].completed_at is not None

    def test_idempotent_complete_preserves_first_timestamp(self):
        """Calling complete_task twice must not change the completed_at value."""
        template = _make_template(tasks=[_make_task()])
        save_template(template)
        plan = create_plan_from_template(
            engineer_id="eng-1",
            employer_id=template.employer_id,
            template_id=template.template_id,
            hire_date="2024-01-01",
        )
        task_id = plan.tasks[0].task_id

        first = complete_task(plan.plan_id, task_id)
        first_ts = first.tasks[0].completed_at

        second = complete_task(plan.plan_id, task_id)
        second_ts = second.tasks[0].completed_at

        assert first_ts == second_ts

    def test_raises_for_missing_plan(self):
        with pytest.raises(ValueError, match="Plan not found"):
            complete_task("nonexistent-plan", "some-task")

    def test_raises_for_missing_task(self):
        template = _make_template(tasks=[_make_task()])
        save_template(template)
        plan = create_plan_from_template(
            engineer_id="eng-1",
            employer_id=template.employer_id,
            template_id=template.template_id,
            hire_date="2024-01-01",
        )
        with pytest.raises(ValueError, match="Task not found"):
            complete_task(plan.plan_id, "bad-task-id")

    def test_other_tasks_unaffected(self):
        """Completing one task should not touch sibling tasks."""
        tasks = [_make_task(due_offset_days=1), _make_task(due_offset_days=2)]
        template = _make_template(tasks=tasks)
        save_template(template)
        plan = create_plan_from_template(
            engineer_id="eng-1",
            employer_id=template.employer_id,
            template_id=template.template_id,
            hire_date="2024-01-01",
        )
        task_id_0 = plan.tasks[0].task_id
        updated = complete_task(plan.plan_id, task_id_0)
        assert updated.tasks[0].completed_at is not None
        assert updated.tasks[1].completed_at is None


# ---------------------------------------------------------------------------
# get_overdue_tasks
# ---------------------------------------------------------------------------

class TestGetOverdueTasks:
    def _hire_date_days_ago(self, n: int) -> str:
        return (date.today() - timedelta(days=n)).isoformat()

    def test_returns_overdue_task(self):
        employer_id = str(uuid.uuid4())
        # Task with offset 1 day, hired 10 days ago → due 9 days ago (overdue)
        task = _make_task(due_offset_days=1)
        template = _make_template(employer_id=employer_id, tasks=[task])
        save_template(template)
        plan = create_plan_from_template(
            engineer_id="eng-1",
            employer_id=employer_id,
            template_id=template.template_id,
            hire_date=self._hire_date_days_ago(10),
        )
        overdue = get_overdue_tasks(employer_id)
        assert len(overdue) == 1
        overdue_plan, overdue_task = overdue[0]
        assert overdue_plan.plan_id == plan.plan_id
        assert overdue_task.due_offset_days == 1

    def test_completed_task_not_overdue(self):
        employer_id = str(uuid.uuid4())
        task = _make_task(due_offset_days=1)
        template = _make_template(employer_id=employer_id, tasks=[task])
        save_template(template)
        plan = create_plan_from_template(
            engineer_id="eng-1",
            employer_id=employer_id,
            template_id=template.template_id,
            hire_date=self._hire_date_days_ago(10),
        )
        complete_task(plan.plan_id, plan.tasks[0].task_id)
        overdue = get_overdue_tasks(employer_id)
        assert overdue == []

    def test_future_due_date_not_overdue(self):
        employer_id = str(uuid.uuid4())
        # offset 30 days, hired today → due in 30 days (not overdue)
        task = _make_task(due_offset_days=30)
        template = _make_template(employer_id=employer_id, tasks=[task])
        save_template(template)
        create_plan_from_template(
            engineer_id="eng-1",
            employer_id=employer_id,
            template_id=template.template_id,
            hire_date=date.today().isoformat(),
        )
        overdue = get_overdue_tasks(employer_id)
        assert overdue == []

    def test_due_today_not_overdue(self):
        """A task due exactly today (not strictly before today) should NOT be overdue."""
        employer_id = str(uuid.uuid4())
        # hired 5 days ago, offset 5 → due exactly today
        task = _make_task(due_offset_days=5)
        template = _make_template(employer_id=employer_id, tasks=[task])
        save_template(template)
        create_plan_from_template(
            engineer_id="eng-1",
            employer_id=employer_id,
            template_id=template.template_id,
            hire_date=self._hire_date_days_ago(5),
        )
        overdue = get_overdue_tasks(employer_id)
        assert overdue == []

    def test_multiple_overdue_tasks_across_plans(self):
        employer_id = str(uuid.uuid4())
        for i in range(3):
            task = _make_task(due_offset_days=1)
            template = _make_template(employer_id=employer_id, tasks=[task])
            save_template(template)
            create_plan_from_template(
                engineer_id=f"eng-{i}",
                employer_id=employer_id,
                template_id=template.template_id,
                hire_date=self._hire_date_days_ago(10),
            )
        overdue = get_overdue_tasks(employer_id)
        assert len(overdue) == 3

    def test_tenant_isolation(self):
        """Overdue tasks from another employer must not appear."""
        emp_a = str(uuid.uuid4())
        emp_b = str(uuid.uuid4())

        for emp in (emp_a, emp_b):
            task = _make_task(due_offset_days=1)
            template = _make_template(employer_id=emp, tasks=[task])
            save_template(template)
            create_plan_from_template(
                engineer_id="eng-x",
                employer_id=emp,
                template_id=template.template_id,
                hire_date=self._hire_date_days_ago(10),
            )

        overdue_a = get_overdue_tasks(emp_a)
        assert len(overdue_a) == 1
        assert overdue_a[0][0].employer_id == emp_a

    def test_no_plans_returns_empty(self):
        assert get_overdue_tasks("unknown-employer") == []
