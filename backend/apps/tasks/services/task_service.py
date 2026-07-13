"""
task_service.py — domain logic for the Task app.

All functions accept model instances and plain Python primitives.
No DRF Request objects enter this module.
Raises ValueError for invalid domain operations.
"""
from apps.tasks.models import Task, TaskRemark


def complete_task(task: Task) -> Task:
    """
    Transition task to STATUS_COMPLETED.

    Delegates to the model method which stamps completed_on and saves the
    relevant update_fields. Separated here so callers go through one entry
    point and any future pre/post hooks live in one place.
    """
    task.mark_completed()
    return task


def reject_task(task: Task, by_user, reason: str = "") -> tuple[Task, TaskRemark | None]:
    """
    Transition task to STATUS_REJECTED and optionally record a rejection remark.

    Returns:
        (task, remark) — remark is None when reason is empty.
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
    """
    Reset a completed or rejected task back to STATUS_PENDING.

    Clears: completed_on, rejected_by, rejection_reason.
    AuditModel.save() will stamp modified_on / modified_by automatically
    when update_fields is not used — but we use update_fields here to be
    explicit and avoid any signal side-effects on unrelated fields.
    """
    task.status = Task.STATUS_PENDING
    task.completed_on = None
    task.rejected_by = None
    task.rejection_reason = ""
    task.save(update_fields=[
        "status",
        "completed_on",
        "rejected_by",
        "rejection_reason",
        "modified_on",
        "modified_by",
    ])
    return task


def append_remark(task: Task, text: str, created_by) -> TaskRemark:
    """
    Validate and append a remark to a task.

    Args:
        task: The Task instance to attach the remark to.
        text: Raw text from the caller (will be stripped).
        created_by: User creating the remark.

    Returns:
        The newly created TaskRemark instance.

    Raises:
        ValueError: When text is empty after stripping.
    """
    text = (text or "").strip()
    if not text:
        raise ValueError("Remark text is required.")
    return TaskRemark.objects.create(task=task, text=text, created_by=created_by)
