# tests/allotment/test_allotment.py
"""
Unit tests for the allotment module.

All tests mock the ORM and use no real database (no @pytest.mark.django_db).
This makes the suite fast and independent of migrations/fixtures.
"""
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# 1. create_allotment dispatches balance task
# ---------------------------------------------------------------------------

def test_create_allotment_dispatches_balance_task():
    """
    create_allotment() must call recompute_license_balance_task.delay(license_id)
    once for each unique license derived from the allotment items, after commit.

    _dispatch() now resolves license IDs from import-item IDs via
    LicenseImportItemsModel, so we mock that lookup to return license_id=7.
    """
    mock_allotment = MagicMock()
    mock_allotment.pk = 1

    # Capture the on_commit callback so we can invoke it synchronously
    captured_callbacks = []

    def fake_on_commit(fn):
        captured_callbacks.append(fn)

    data = {
        "company_id": 1,
        "item_name": "Test Item",
        "items": [
            {
                "item": 42,
                "qty": Decimal("10.000"),
                "cif_fc": Decimal("100.00"),
                "cif_inr": Decimal("8000.00"),
                "is_boe": False,
            }
        ],
    }
    user = MagicMock()

    # Build a mock LicenseImportItemsModel for the BD-001 license_id lookup
    mock_bd001_qs = MagicMock()
    mock_bd001_qs.values_list.return_value.get.return_value = 7  # license_id=7
    mock_bd001_model = MagicMock()
    mock_bd001_model.objects = mock_bd001_qs
    mock_bd001_model.DoesNotExist = LookupError

    with patch("apps.allotment.services.allotment_service.AllotmentModel") as MockAllotmentModel, \
         patch("apps.allotment.services.allotment_service.AllotmentItems") as MockAllotmentItems, \
         patch("apps.allotment.services.allotment_service.transaction") as mock_txn, \
         patch("apps.allotment.services.allotment_service._validate_plan_availability"), \
         patch("apps.allotment.services.allotment_service._validate_balance_availability"), \
         patch("apps.allotment.services.allotment_service._adjust_plan"), \
         patch("apps.license.models.LicenseImportItemsModel", mock_bd001_model):

        # Set up atomic as a context manager
        mock_txn.atomic.return_value.__enter__ = MagicMock(return_value=None)
        mock_txn.atomic.return_value.__exit__ = MagicMock(return_value=False)
        mock_txn.on_commit.side_effect = fake_on_commit

        # AllotmentModel() constructor and .save()
        MockAllotmentModel.return_value = mock_allotment

        # AllotmentItems() constructor and .save()
        mock_ai = MagicMock()
        mock_ai.item_id = 42
        mock_ai.qty = Decimal("10.000")
        mock_ai.cif_fc = Decimal("100.00")
        mock_ai.cif_inr = Decimal("8000.00")
        MockAllotmentItems.return_value = mock_ai

        from apps.allotment.services.allotment_service import create_allotment
        create_allotment(data, user)

        # on_commit must have been registered
        assert len(captured_callbacks) == 1

    # Now fire the callback — mock both LicenseImportItemsModel and tasks
    mock_recompute = MagicMock()

    # Build a mock LicenseImportItemsModel queryset that returns license_id=7
    mock_item_qs = MagicMock()
    mock_item_qs.filter.return_value = mock_item_qs
    mock_item_qs.exclude.return_value = mock_item_qs
    mock_item_qs.values_list.return_value = [7]  # license_id resolved from item_id=42

    mock_license_import_model = MagicMock()
    mock_license_import_model.objects = mock_item_qs

    with patch.dict(
        "sys.modules",
        {
            "apps.license.tasks": MagicMock(recompute_license_balance_task=mock_recompute),
            "apps.license.models": MagicMock(LicenseImportItemsModel=mock_license_import_model),
        },
    ):
        captured_callbacks[0]()
        mock_recompute.delay.assert_called_once_with(7)


# ---------------------------------------------------------------------------
# 2. delete_allotment dispatches balance task
# ---------------------------------------------------------------------------

def test_delete_allotment_dispatches_balance_task():
    """
    delete_allotment() must collect item IDs before deleting and dispatch
    recompute_license_balance_task.delay() for each unique license after commit.

    _dispatch() now resolves license IDs from import-item IDs via
    LicenseImportItemsModel. Item IDs 10 and 20 both map to license_id=5.
    """
    captured_callbacks = []

    def fake_on_commit(fn):
        captured_callbacks.append(fn)

    with patch("apps.allotment.services.allotment_service.AllotmentModel") as MockAllotmentModel, \
         patch("apps.allotment.services.allotment_service.AllotmentItems") as MockAllotmentItems, \
         patch("apps.allotment.services.allotment_service.transaction") as mock_txn, \
         patch("apps.allotment.services.allotment_service._adjust_plan"):

        mock_txn.atomic.return_value.__enter__ = MagicMock(return_value=None)
        mock_txn.atomic.return_value.__exit__ = MagicMock(return_value=False)
        mock_txn.on_commit.side_effect = fake_on_commit

        # Simulate two items attached to the allotment (values() returns dicts)
        mock_qs = MagicMock()
        mock_qs.filter.return_value = mock_qs
        mock_qs.exclude.return_value = mock_qs
        mock_qs.values.return_value = [
            {"item_id": 10, "qty": Decimal("5.000"), "cif_fc": Decimal("50.00"), "cif_inr": Decimal("4000.00")},
            {"item_id": 20, "qty": Decimal("3.000"), "cif_fc": Decimal("30.00"), "cif_inr": Decimal("2400.00")},
        ]
        MockAllotmentItems.objects = mock_qs

        MockAllotmentModel.objects.filter.return_value.delete = MagicMock()

        from apps.allotment.services.allotment_service import delete_allotment
        delete_allotment(99, MagicMock())

        assert len(captured_callbacks) == 1

    mock_recompute = MagicMock()

    # Both item_ids 10 and 20 map to license_id=5 (same license, de-duplicated by set)
    mock_item_qs = MagicMock()
    mock_item_qs.filter.return_value = mock_item_qs
    mock_item_qs.exclude.return_value = mock_item_qs
    mock_item_qs.values_list.return_value = [5]  # one unique license_id

    mock_license_import_model = MagicMock()
    mock_license_import_model.objects = mock_item_qs

    with patch.dict(
        "sys.modules",
        {
            "apps.license.tasks": MagicMock(recompute_license_balance_task=mock_recompute),
            "apps.license.models": MagicMock(LicenseImportItemsModel=mock_license_import_model),
        },
    ):
        captured_callbacks[0]()
        mock_recompute.delay.assert_called_once_with(5)


# ---------------------------------------------------------------------------
# 3. ALLOTMENT_TYPE_CHOICES constant
# ---------------------------------------------------------------------------

def test_allotment_type_choices():
    """
    AllotmentModel.ALLOTMENT_TYPE_CHOICES must be exactly the two-item list
    defined in the task spec.
    """
    # Django app registry is already initialised by the test runner; no patching needed
    from apps.allotment.models import AllotmentModel
    assert AllotmentModel.ALLOTMENT_TYPE_CHOICES == [
        ("AT", "Allotment"),
        ("TR", "Transfer"),
    ]


# ---------------------------------------------------------------------------
# 4. List endpoint filtered by license_number returns 200
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_list_filter_by_license(db, django_user_model, settings):
    """
    GET /api/v1/allotments/?license_number=DFIA-001 must return HTTP 200.

    The queryset is mocked so no real DB is touched beyond user creation.
    """
    from unittest.mock import MagicMock, patch

    from django.contrib.auth.models import Group
    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import RefreshToken

    # Provide a minimal Django settings override so DRF can resolve URLs
    settings.ROOT_URLCONF = "config.urls"

    # Create a real user with the ALLOTMENT_MANAGER role so auth + permission
    # both pass without any patching of the auth layer.
    user = django_user_model.objects.create_user(
        username="allot_tester", password="pass123"
    )
    group, _ = Group.objects.get_or_create(name="ALLOTMENT_MANAGER")
    user.groups.add(group)

    refresh = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")

    mock_qs = MagicMock()
    mock_qs.filter.return_value = mock_qs
    mock_qs.exclude.return_value = mock_qs
    mock_qs.order_by.return_value = mock_qs
    mock_qs.select_related.return_value = mock_qs
    mock_qs.prefetch_related.return_value = mock_qs
    mock_qs.__iter__ = MagicMock(return_value=iter([]))
    mock_qs.count.return_value = 0
    # Make it usable as a queryset in DRF pagination
    mock_qs.__getitem__ = MagicMock(return_value=mock_qs)
    mock_qs.__len__ = MagicMock(return_value=0)

    with patch(
        "apps.allotment.views.AllotmentViewSet.get_queryset",
        return_value=mock_qs,
    ):
        response = client.get(
            "/api/v1/allotments/?license_number=DFIA-001",
            format="json",
        )

    assert response.status_code == 200
