"""
Tests for bill_of_entry service layer and API endpoints.

Models use managed=False (no real DB tables), so service-layer tests mock
the DB models with MagicMock. API-level tests that need DB access use
@pytest.mark.django_db with mocked model calls.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Service layer tests (no DB required — models mocked with MagicMock)
# ---------------------------------------------------------------------------

class TestFrozenRowUpdateRejected:
    """update_row_detail raises ValueError for frozen rows."""

    def test_frozen_row_update_rejected(self):
        from apps.bill_of_entry.services.boe_service import update_row_detail

        frozen_row = MagicMock()
        frozen_row.is_frozen = True

        # RowDetails is imported lazily inside update_row_detail; patch at model level
        with patch("apps.bill_of_entry.models.RowDetails") as MockRowDetails:
            # Also patch the import in boe_service since it does its own local import
            with patch(
                "apps.bill_of_entry.services.boe_service.RowDetails",
                MockRowDetails,
                create=True,
            ):
                MockRowDetails.objects.get.return_value = frozen_row

                with pytest.raises(ValueError, match="frozen"):
                    update_row_detail(
                        row_id=1, data={"cif_inr": "100.000"}, user=MagicMock(), boe_id=1
                    )


class TestFrozenRowDeleteRejected:
    """delete_row_detail raises ValueError for frozen rows."""

    def test_frozen_row_delete_rejected(self):
        from apps.bill_of_entry.services.boe_service import delete_row_detail

        frozen_row = MagicMock()
        frozen_row.is_frozen = True

        with patch("apps.bill_of_entry.models.RowDetails") as MockRowDetails:
            with patch(
                "apps.bill_of_entry.services.boe_service.RowDetails",
                MockRowDetails,
                create=True,
            ):
                MockRowDetails.objects.get.return_value = frozen_row

                with pytest.raises(ValueError, match="frozen"):
                    delete_row_detail(row_id=1, user=MagicMock(), boe_id=1)


class TestDisputeRowResolve:
    """resolve_dispute_row clears is_dispute and links the correct license item."""

    def test_dispute_row_resolve_clears_is_dispute(self):
        from apps.bill_of_entry.services.boe_service import resolve_dispute_row

        dispute_row = MagicMock()
        dispute_row.pk = 5
        dispute_row.is_dispute = True

        mock_license_item_model = MagicMock()
        mock_license_item_model.DoesNotExist = Exception  # make try/except work

        with patch("apps.bill_of_entry.models.RowDetails") as MockRowDetails:
            with patch(
                "apps.bill_of_entry.services.boe_service.RowDetails",
                MockRowDetails,
                create=True,
            ):
                with patch(
                    "apps.license.models.LicenseImportItemsModel",
                    mock_license_item_model,
                ):
                    MockRowDetails.objects.get.return_value = dispute_row
                    MockRowDetails.objects.filter.return_value.update.return_value = 1
                    dispute_row.refresh_from_db.return_value = None

                    result = resolve_dispute_row(
                        row_id=5, license_item_id=42, user=MagicMock(), boe_id=1
                    )

        # Verify update() was called with the correct arguments
        MockRowDetails.objects.filter.assert_called_once_with(pk=5)
        MockRowDetails.objects.filter.return_value.update.assert_called_once_with(
            sr_number_id=42, is_dispute=False
        )
        dispute_row.refresh_from_db.assert_called_once()


class TestCreateBoeDispatchesBalanceTask:
    """After a BOE row is saved, balance update is triggered via on_commit."""

    def test_create_boe_dispatches_balance_task(self):
        """Verify that the post_save signal handler calls transaction.on_commit."""
        from apps.bill_of_entry import models as boe_models

        mock_item = MagicMock()
        mock_item.id = 99

        mock_instance = MagicMock(spec=boe_models.RowDetails)
        mock_instance.sr_number = mock_item
        mock_instance.bill_of_entry_id = 1

        with patch("apps.bill_of_entry.models.transaction") as mock_txn:
            boe_models.update_stock(
                sender=boe_models.RowDetails,
                instance=mock_instance,
            )

        mock_txn.on_commit.assert_called_once()
        callback = mock_txn.on_commit.call_args[0][0]
        assert callable(callback)


class TestUploadLedgerReturnsTaskId:
    """POST /api/v1/bill-of-entries/upload-ledger/ returns task_id and 202."""

    def test_upload_ledger_returns_task_id(self):
        """Test LedgerUploadView directly via APIRequestFactory (no DB needed)."""
        from apps.bill_of_entry.views.ledger import LedgerUploadView
        from django.core.files.uploadedfile import SimpleUploadedFile
        from rest_framework.test import APIRequestFactory

        test_file = SimpleUploadedFile(
            "test_ledger.xlsx",
            b"fake-excel-content",
            content_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        )

        factory = APIRequestFactory()
        request = factory.post(
            "/bill-of-entries/upload-ledger/",
            {"file": test_file},
            format="multipart",
        )
        mock_user = MagicMock()
        mock_user.is_authenticated = True
        request.user = mock_user

        with patch(
            "apps.accounts.permissions.LedgerUploadPermission.has_permission",
            return_value=True,
        ):
            view = LedgerUploadView.as_view()
            response = view(request)

        assert response.status_code == 202
        # response.data holds the dict directly on DRF Response objects
        data = response.data
        assert "task_id" in data
        assert data["status"] == "pending"
        assert data["task_id"]  # non-empty task identifier

    def test_upload_ledger_no_file_returns_400(self):
        """Missing file returns 400."""
        from apps.bill_of_entry.views.ledger import LedgerUploadView
        from rest_framework.test import APIRequestFactory

        factory = APIRequestFactory()
        request = factory.post(
            "/bill-of-entries/upload-ledger/", {}, format="multipart"
        )
        mock_user = MagicMock()
        mock_user.is_authenticated = True
        request.user = mock_user

        with patch(
            "apps.accounts.permissions.LedgerUploadPermission.has_permission",
            return_value=True,
        ):
            view = LedgerUploadView.as_view()
            response = view(request)

        assert response.status_code == 400
        data = response.data
        assert data["detail"] == "No file provided."
