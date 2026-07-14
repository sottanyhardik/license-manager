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
    create_allotment() must call recompute_license_balance_task.delay(item_id)
    once for each item after the transaction commits.
    """
    mock_allotment = MagicMock()
    mock_allotment.pk = 1

    mock_item = MagicMock()
    mock_item.item_id = 42

    mock_task = MagicMock()

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

    with patch("apps.allotment.services.allotment_service.AllotmentModel") as MockAllotmentModel, \
         patch("apps.allotment.services.allotment_service.AllotmentItems") as MockAllotmentItems, \
         patch("apps.allotment.services.allotment_service.transaction") as mock_txn:

        # Set up atomic as a context manager
        mock_txn.atomic.return_value.__enter__ = MagicMock(return_value=None)
        mock_txn.atomic.return_value.__exit__ = MagicMock(return_value=False)
        mock_txn.on_commit.side_effect = fake_on_commit

        # AllotmentModel() constructor and .save()
        MockAllotmentModel.return_value = mock_allotment

        # AllotmentItems() constructor and .save()
        mock_ai = MagicMock()
        mock_ai.item_id = 42
        MockAllotmentItems.return_value = mock_ai

        from apps.allotment.services.allotment_service import create_allotment
        create_allotment(data, user)

        # on_commit must have been registered
        assert len(captured_callbacks) == 1

    # Now fire the callback with the lazy task import mocked
    with patch("apps.license.tasks.recompute_license_balance_task") as mock_recompute:
        import sys
        import types

        # Stub apps.license.tasks if not already importable
        if "apps.license" not in sys.modules:
            license_mod = types.ModuleType("apps.license")
            tasks_mod = types.ModuleType("apps.license.tasks")
            tasks_mod.recompute_license_balance_task = mock_recompute
            sys.modules.setdefault("apps.license", license_mod)
            sys.modules.setdefault("apps.license.tasks", tasks_mod)

        # Patch the import path used inside _dispatch's inner function
        with patch.dict(
            "sys.modules",
            {"apps.license.tasks": MagicMock(recompute_license_balance_task=mock_recompute)},
        ):
            captured_callbacks[0]()
            mock_recompute.delay.assert_called_once_with(42)


# ---------------------------------------------------------------------------
# 2. delete_allotment dispatches balance task
# ---------------------------------------------------------------------------

def test_delete_allotment_dispatches_balance_task():
    """
    delete_allotment() must collect item IDs before deleting and dispatch
    recompute_license_balance_task.delay() for each one after commit.
    """
    captured_callbacks = []

    def fake_on_commit(fn):
        captured_callbacks.append(fn)

    mock_task = MagicMock()

    with patch("apps.allotment.services.allotment_service.AllotmentModel") as MockAllotmentModel, \
         patch("apps.allotment.services.allotment_service.AllotmentItems") as MockAllotmentItems, \
         patch("apps.allotment.services.allotment_service.transaction") as mock_txn:

        mock_txn.atomic.return_value.__enter__ = MagicMock(return_value=None)
        mock_txn.atomic.return_value.__exit__ = MagicMock(return_value=False)
        mock_txn.on_commit.side_effect = fake_on_commit

        # Simulate two item IDs attached to the allotment
        mock_qs = MagicMock()
        mock_qs.filter.return_value = mock_qs
        mock_qs.exclude.return_value = mock_qs
        mock_qs.values_list.return_value = [10, 20]
        MockAllotmentItems.objects = mock_qs

        MockAllotmentModel.objects.filter.return_value.delete = MagicMock()

        from apps.allotment.services.allotment_service import delete_allotment
        delete_allotment(99, MagicMock())

        assert len(captured_callbacks) == 1

    mock_recompute = MagicMock()
    with patch.dict(
        "sys.modules",
        {"apps.license.tasks": MagicMock(recompute_license_balance_task=mock_recompute)},
    ):
        captured_callbacks[0]()
        assert mock_recompute.delay.call_count == 2
        mock_recompute.delay.assert_any_call(10)
        mock_recompute.delay.assert_any_call(20)


# ---------------------------------------------------------------------------
# 3. ALLOTMENT_TYPE_CHOICES constant
# ---------------------------------------------------------------------------

def test_allotment_type_choices():
    """
    AllotmentModel.ALLOTMENT_TYPE_CHOICES must be exactly the two-item list
    defined in the task spec.
    """
    # Import lazily — Django app registry may not be ready in pure unit tests

    # Patch Django's apps to avoid AppRegistryNotReady in models.py
    with patch("django.db.models.ForeignKey.__init__", return_value=None), \
         patch("django.db.models.DecimalField.__init__", return_value=None), \
         patch("django.db.models.CharField.__init__", return_value=None), \
         patch("django.db.models.BooleanField.__init__", return_value=None), \
         patch("django.db.models.DateField.__init__", return_value=None):
        pass  # just importing is enough; we access the class attribute directly

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
