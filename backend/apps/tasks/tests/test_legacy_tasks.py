from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.tasks.models import Task


class TaskModelTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="task-user", password="Pass12345!")

    def test_mark_completed_sets_status_and_timestamp(self):
        task = Task.objects.create(title="Follow up", assigned_to=self.user)

        task.mark_completed()

        task.refresh_from_db()
        self.assertEqual(task.status, Task.STATUS_COMPLETED)
        self.assertIsNotNone(task.completed_on)

    def test_mark_rejected_sets_user_and_reason(self):
        task = Task.objects.create(title="Review file", assigned_to=self.user)

        task.mark_rejected(by_user=self.user, reason="Duplicate")

        task.refresh_from_db()
        self.assertEqual(task.status, Task.STATUS_REJECTED)
        self.assertEqual(task.rejected_by, self.user)
        self.assertEqual(task.rejection_reason, "Duplicate")
