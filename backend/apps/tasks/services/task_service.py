"""
apps/tasks/services/task_service.py

Business-logic service layer for the Tasks app.
Views and other callers should use these functions rather than touching
model methods or ORM directly, so the logic stays testable in isolation.
"""
from apps.tasks.models import Task, TaskRemark


def create_task(data: dict, user) -> Task:
    """Create a task; sets created_by, defaults assigned_to=creator if not given."""
    from django.utils import timezone

    assigned_to = data.get("assigned_to") or user
    return Task.objects.create(
        title=data["title"],
        description=data.get("description", ""),
        status=Task.STATUS_PENDING,
        priority=data.get("priority", Task.PRIORITY_NORMAL),
        assigned_to=assigned_to,
        assigned_on=timezone.now(),
        due_date=data.get("due_date"),
        created_by=user,
        modified_by=user,
    )


def complete_task(task: Task) -> Task:
    """Mark a task as completed."""
    task.mark_completed()
    return task


def reject_task(task: Task, by_user, reason: str = "") -> tuple:
    """
    Mark a task as rejected.

    Returns (task, remark|None).  A TaskRemark is created only when a
    non-empty reason is supplied.
    """
    reason = (reason or "").strip()
    task.mark_rejected(by_user=by_user, reason=reason)
    remark = None
    if reason:
        remark = TaskRemark.objects.create(
            task=task,
            text=f"[Rejected] {reason}",
            created_by=by_user,
        )
    return task, remark


def reopen_task(task: Task) -> Task:
    """Reset a completed/rejected task back to pending."""
    task.status = Task.STATUS_PENDING
    task.completed_on = None
    task.rejected_by = None
    task.rejection_reason = ""
    task.save(
        update_fields=[
            "status",
            "completed_on",
            "rejected_by",
            "rejection_reason",
            "modified_on",
        ]
    )
    return task


def add_remark(task_id: int, text: str, user) -> TaskRemark:
    """Attach a plain-text remark to an existing task."""
    text = (text or "").strip()
    if not text:
        raise ValueError("Remark text is required.")
    task = Task.objects.get(pk=task_id)
    return TaskRemark.objects.create(task=task, text=text, created_by=user)
