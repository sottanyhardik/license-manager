from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import AuditModel


class Task(AuditModel):
    STATUS_PENDING = "pending"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_COMPLETED = "completed"
    STATUS_REJECTED = "rejected"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_IN_PROGRESS, "In Progress"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_REJECTED, "Rejected"),
    ]

    PRIORITY_LOW = "low"
    PRIORITY_NORMAL = "normal"
    PRIORITY_HIGH = "high"

    PRIORITY_CHOICES = [
        (PRIORITY_LOW, "Low"),
        (PRIORITY_NORMAL, "Normal"),
        (PRIORITY_HIGH, "High"),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default=PRIORITY_NORMAL)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tasks_assigned",
    )
    assigned_on = models.DateTimeField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    completed_on = models.DateTimeField(null=True, blank=True)
    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tasks_rejected",
    )
    rejection_reason = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_on"]
        indexes = [
            models.Index(fields=["status", "-created_on"]),
            models.Index(fields=["assigned_to", "status"]),
            models.Index(fields=["created_by", "status"]),
        ]

    def __str__(self):
        return self.title

    def mark_completed(self):
        self.status = self.STATUS_COMPLETED
        self.completed_on = timezone.now()
        self.save(update_fields=["status", "completed_on", "modified_on", "modified_by"])

    def mark_rejected(self, by_user=None, reason=""):
        self.status = self.STATUS_REJECTED
        if by_user is not None:
            self.rejected_by = by_user
        self.rejection_reason = reason or ""
        self.save(update_fields=[
            "status", "rejected_by", "rejection_reason", "modified_on", "modified_by",
        ])


class TaskRemark(models.Model):
    """Append-only remark/comment on a task — preserves audit trail."""

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="remarks")
    text = models.TextField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="task_remarks_created",
    )
    created_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_on"]

    def __str__(self):
        return f"Remark on {self.task_id} by {self.created_by_id}"
