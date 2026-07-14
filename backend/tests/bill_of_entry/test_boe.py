"""
Tests for bill_of_entry service layer and API endpoints.

Models use managed=False (no real DB tables), so service-layer tests mock
the DB models with MagicMock. API-level tests that need DB access use
@pytest.mark.django_db with mocked model calls.
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch, PropertyMock


# ---------------------------------------------------------------------------
# Service layer tests (no DB required — models mocked with MagicMock)
# ---------------------------------------------------------------------------

class TestFrozenRowUpdateRejected:
    """update_row_detail raises ValueError for frozen rows."""

    def test_frozen_row_update_rejected(self):
        from apps.bill_of_entry.services.boe_service import update_row_detail

        frozen_row = MagicMock()
        frozen_row.is_frozen = True

        with patch(
            "apps.bill_of_entry.services.boe_service.RowDetails"
        ) as MockRowDetails:
            MockRowDetails.objects.get.return_value = frozen_row

            with pytest.raises(ValueError, match="frozen"):
                update_row_detail(row_id=1, data={"cif_inr": "100.000"}, user=MagicMock())


class TestFrozenRowDeleteRejected:
    """delete_row_detail raises ValueError for frozen rows."""

    def test_frozen_row_delete_rejected(self):
        from apps.bill_of_entry.services.boe_service import delete_row_detail

        frozen_row = MagicMock()
        frozen_row.is_frozen = True

        with patch(
            "apps.bill_of_entry.services.boe_service.RowDetails"
        ) as MockRowDetails:
            MockRowDetails.objects.get.return_value = frozen_row

            with pytest.raises(ValueError, match="frozen"):
                delete_row_detail(row_id=1, user=MagicMock())


class TestDisputeRowResolve:
    """resolve_dispute_row clears is_dispute and links the correct license item."""

    def test_dispute_row_resolve_clears_is_dispute(self):
        from apps.bill_of_entry.services.boe_service import resolve_dispute_row

        dispute_row = MagicMock()
        dispute_row.pk = 5
        dispute_row.is_dispute = True

        # After update() + refresh_from_db(), the row should reflect is_dispute=False
        updated_row = MagicMock()
        updated_row.pk = 5
        updated_row.is_dispute = False
        updated_row.sr_number_id = 42

        with patch(
            "apps.bill_of_entry.services.boe_service.RowDetails"
        ) as MockRowDetails:
            MockRowDetails.objects.get.return_value = dispute_row
            # update() call: returns 1 (rows affected)
            MockRowDetails.objects.filter.return_value.update.return_value = 1
            # After refresh_from_db() the mock still holds — simulate by returning updated_row
            dispute_row.refresh_from_db.return_value = None

            result = resolve_dispute_row(
                row_id=5, license_item_id=42, user=MagicMock()
            )

        # Verify update() was called with the correct arguments
        MockRowDetails.objects.filter.assert_called_once_with(pk=5)
        MockRowDetails.objects.filter.return_value.update.assert_called_once_with(
            sr_number_id=42, is_dispute=False
        )
        # refresh_from_db must be called to return the updated state
        dispute_row.refresh_from_db.assert_called_once()


class TestCreateBoeDispatchesBalanceTask:
    """After a BOE row is saved, balance update is triggered via on_commit."""

    def test_create_boe_dispatches_balance_task(self):
        """Verify that the post_save signal calls transaction.on_commit with _update_balance_sync."""
        from apps.bill_of_entry import models as boe_models

        mock_item = MagicMock()
        mock_item.id = 99

        mock_instance = MagicMock(spec=boe_models.RowDetails)
        mock_instance.sr_number = mock_item
        mock_instance.bill_of_entry_id = 1

        with patch("apps.bill_of_entry.models.transaction") as mock_txn:
            # Simulate the post_save signal handler directly
            boe_models.update_stock(
                sender=boe_models.RowDetails,
                instance=mock_instance,
            )

        # on_commit must be called with a callable
        mock_txn.on_commit.assert_called_once()
        callback = mock_txn.on_commit.call_args[0][0]
        assert callable(callback)


class TestUploadLedgerReturnsTaskId:
    """POST /api/v1/bill-of-entries/upload-ledger/ returns task_id and 202."""

    @pytest.mark.django_db
    def test_upload_ledger_returns_task_id(self, authenticated_client):
        from io import BytesIO
        from django.core.files.uploadedfile import SimpleUploadedFile

        test_file = SimpleUploadedFile(
            "test_ledger.xlsx",
            b"fake-excel-content",
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        with patch(
            "apps.accounts.permissions.BillOfEntryPermission.has_permission",
            return_value=True,
        ):
            response = authenticated_client.post(
                "/api/v1/bill-of-entries/upload-ledger/",
                {"file": test_file},
                format="multipart",
            )

        assert response.status_code == 202
        data = response.json()
        assert "task_id" in data
        assert data["status"] == "pending"
        assert "test_ledger.xlsx" in data["task_id"]

    def test_upload_ledger_no_file_returns_400(self):
        """Missing file returns 400 without needing DB access."""
        from rest_framework.test import APIRequestFactory
        from apps.bill_of_entry.views.ledger import LedgerUploadView

        factory = APIRequestFactory()
        request = factory.post("/upload-ledger/", {}, format="multipart")

        # Attach a mock user so permission check can proceed
        mock_user = MagicMock()
        mock_user.is_authenticated = True
        request.user = mock_user

        with patch(
            "apps.accounts.permissions.BillOfEntryPermission.has_permission",
            return_value=True,
        ):
            view = LedgerUploadView.as_view()
            response = view(request)

        assert response.status_code == 400
        assert response.data["detail"] == "No file provided."
