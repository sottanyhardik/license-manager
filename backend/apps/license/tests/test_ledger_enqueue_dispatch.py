"""Regression: _enqueue_download_request used LicenseLedgerPackageJob without importing it,
so a NameError after .delay() meant root_task_id / dispatch_failed were never persisted."""
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.license.models import LicenseLedgerPackageJob
from apps.license.views.ledger import LicenseLedgerViewSet


class EnqueueDownloadRequestDispatchTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username="ledger-enqueue", password="Pass12345!")
        self.job = LicenseLedgerPackageJob.objects.create(
            key="enqueue-dispatch-key", requested_by=user,
            expires_at=timezone.now() + timedelta(days=1),
        )

    def test_successful_dispatch_saves_root_task_id(self):
        with patch("apps.license.tasks.enqueue_license_ledger_package_job.delay",
                   return_value=MagicMock(id="task-123")) as delay:
            LicenseLedgerViewSet._enqueue_download_request(self.job.pk)
        delay.assert_called_once_with(self.job.pk)
        self.job.refresh_from_db()
        self.assertEqual(self.job.root_task_id, "task-123")
        self.assertEqual(self.job.status, LicenseLedgerPackageJob.STATUS_QUEUED)

    def test_failing_dispatch_marks_dispatch_failed(self):
        with patch("apps.license.tasks.enqueue_license_ledger_package_job.delay",
                   side_effect=RuntimeError("broker down")):
            LicenseLedgerViewSet._enqueue_download_request(self.job.pk)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, "dispatch_failed")
        self.assertEqual(self.job.root_task_id, "")
