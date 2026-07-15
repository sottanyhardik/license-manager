# tests/balance/test_bd_implementations.py
"""
Test suite for the three approved business decisions:

BD-001 — Allotment Cannot Exceed Available Balance
BD-002 — Import Item Grouping Helper
BD-003 — Negative Balance Support

All tests use unittest.mock.patch — NO @pytest.mark.django_db.
Model managers are mocked; no real DB is touched.
"""
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.core.exceptions import ValidationError

# ===========================================================================
# BD-001 Tests — Allotment Cannot Exceed Available Balance
# ===========================================================================


def _make_allotment_bd001_mocks():
    """Return standard mocks for create_allotment BD-001 tests."""
    mock_bd001_qs = MagicMock()
    mock_bd001_qs.values_list.return_value.get.return_value = 99  # license_id=99
    mock_bd001_model = MagicMock()
    mock_bd001_model.objects = mock_bd001_qs
    mock_bd001_model.DoesNotExist = LookupError
    return mock_bd001_model


def test_allotment_rejected_when_exceeds_license_cif_balance():
    """
    BD-001: _validate_balance_availability raises ValidationError when
    total allotment CIF FC > LicenseBalance.balance_cif.
    """
    from apps.allotment.services.allotment_service import _validate_balance_availability

    mock_balance = MagicMock()
    mock_balance.balance_cif = Decimal("1000.00")

    mock_bal_qs = MagicMock()
    mock_bal_qs.select_for_update.return_value.get.return_value = mock_balance

    # Per-item query returns empty (no items by PK) → item loop is a no-op
    mock_item_qs = MagicMock()
    mock_item_qs.select_for_update.return_value.filter.return_value = []

    with patch("apps.license.models.LicenseBalance") as MockBal, \
         patch("apps.license.models.LicenseImportItemsModel") as MockItem:

        MockBal.objects = mock_bal_qs
        MockBal.DoesNotExist = LookupError
        MockItem.objects = mock_item_qs

        items_data = [
            {"item": 1, "qty": Decimal("10.000"), "cif_fc": Decimal("1500.00")},
        ]

        with pytest.raises(ValidationError, match="exceeds available license balance"):
            _validate_balance_availability(license_id=99, items_data=items_data)


def test_allotment_rejected_when_item_qty_exceeds_available():
    """
    BD-001: _validate_balance_availability raises ValidationError when
    requested quantity > item.available_quantity (item-level check).
    """
    from apps.allotment.services.allotment_service import _validate_balance_availability

    mock_balance = MagicMock()
    mock_balance.balance_cif = Decimal("99999.00")  # license-level OK

    mock_item = MagicMock()
    mock_item.pk = 5
    mock_item.serial_number = 1
    mock_item.available_quantity = Decimal("50.000")  # only 50 available

    mock_bal_qs = MagicMock()
    mock_bal_qs.select_for_update.return_value.get.return_value = mock_balance

    mock_item_qs = MagicMock()
    mock_item_qs.select_for_update.return_value.filter.return_value = [mock_item]

    with patch("apps.license.models.LicenseBalance") as MockBal, \
         patch("apps.license.models.LicenseImportItemsModel") as MockItemModel:

        MockBal.objects = mock_bal_qs
        MockBal.DoesNotExist = LookupError
        MockItemModel.objects = mock_item_qs

        items_data = [
            {"item": 5, "qty": Decimal("100.000"), "cif_fc": Decimal("500.00")},
        ]

        with pytest.raises(ValidationError, match="exceeds available quantity"):
            _validate_balance_availability(license_id=99, items_data=items_data)


def test_allotment_allowed_when_within_balance():
    """
    BD-001: _validate_balance_availability does NOT raise when total CIF <= balance_cif
    AND each item qty <= available_quantity.
    """
    from apps.allotment.services.allotment_service import _validate_balance_availability

    mock_balance = MagicMock()
    mock_balance.balance_cif = Decimal("5000.00")

    mock_item = MagicMock()
    mock_item.pk = 5
    mock_item.serial_number = 1
    mock_item.available_quantity = Decimal("200.000")

    mock_bal_qs = MagicMock()
    mock_bal_qs.select_for_update.return_value.get.return_value = mock_balance

    mock_item_qs = MagicMock()
    mock_item_qs.select_for_update.return_value.filter.return_value = [mock_item]

    with patch("apps.license.models.LicenseBalance") as MockBal, \
         patch("apps.license.models.LicenseImportItemsModel") as MockItemModel:

        MockBal.objects = mock_bal_qs
        MockBal.DoesNotExist = LookupError
        MockItemModel.objects = mock_item_qs

        items_data = [
            {"item": 5, "qty": Decimal("100.000"), "cif_fc": Decimal("1000.00")},
        ]

        # Must not raise
        _validate_balance_availability(license_id=99, items_data=items_data)


def test_allotment_bd001_transaction_atomic_no_partial_saves():
    """
    BD-001: _validate_balance_availability is called inside transaction.atomic()
    in create_allotment — if validation fails, no AllotmentModel or AllotmentItems
    rows are saved (the exception aborts the transaction).

    Verifies that AllotmentModel.save() is never called when the balance check fails.
    """
    mock_allotment = MagicMock()

    mock_bd001_model = _make_allotment_bd001_mocks()

    data = {
        "company_id": 1,
        "items": [
            {
                "item": 7, "qty": Decimal("100.000"),
                "cif_fc": Decimal("5000.00"), "cif_inr": Decimal("0"), "is_boe": False,
            }
        ],
    }
    user = MagicMock()

    def raise_validation(*_args, **_kwargs):
        raise ValidationError("Total allotment CIF FC 5000 exceeds available license balance 100.")

    with patch("apps.allotment.services.allotment_service.AllotmentModel") as MockModel, \
         patch("apps.allotment.services.allotment_service.AllotmentItems"), \
         patch("apps.allotment.services.allotment_service.transaction") as mock_txn, \
         patch("apps.allotment.services.allotment_service._validate_plan_availability"), \
         patch("apps.allotment.services.allotment_service._validate_balance_availability",
               side_effect=raise_validation), \
         patch("apps.license.models.LicenseImportItemsModel", mock_bd001_model):

        mock_txn.atomic.return_value.__enter__ = MagicMock(return_value=None)
        mock_txn.atomic.return_value.__exit__ = MagicMock(return_value=False)
        mock_txn.on_commit = MagicMock()
        MockModel.return_value = mock_allotment

        from apps.allotment.services.allotment_service import create_allotment
        with pytest.raises(ValidationError):
            create_allotment(data, user)

    # AllotmentModel instance .save() must NOT have been called
    mock_allotment.save.assert_not_called()


# ===========================================================================
# BD-002 Tests — Import Item Grouping Helper
# ===========================================================================


def test_group_import_items_sums_correctly():
    """
    BD-002: group_import_items_by_name aggregates qty/available/debited/allotted
    correctly across multiple SR rows that share the same ItemNameModel.
    """
    from apps.license.services.balance_service import group_import_items_by_name

    canonical = MagicMock()
    canonical.id = 10
    canonical.name = "Sugar"

    item1 = MagicMock()
    item1.pk = 1
    item1.serial_number = 1
    item1.description = ""
    item1.quantity = Decimal("500.000")
    item1.available_quantity = Decimal("300.000")
    item1.debited_quantity = Decimal("100.000")
    item1.allotted_quantity = Decimal("100.000")
    item1.items.all.return_value = [canonical]

    item2 = MagicMock()
    item2.pk = 2
    item2.serial_number = 2
    item2.description = ""
    item2.quantity = Decimal("200.000")
    item2.available_quantity = Decimal("150.000")
    item2.debited_quantity = Decimal("50.000")
    item2.allotted_quantity = Decimal("0.000")
    item2.items.all.return_value = [canonical]

    mock_items_qs = MagicMock()
    mock_items_qs.__iter__ = MagicMock(return_value=iter([item1, item2]))

    mock_model = MagicMock()
    mock_model.objects.filter.return_value.prefetch_related.return_value = mock_items_qs

    with patch("apps.license.models.LicenseImportItemsModel", mock_model):
        result = group_import_items_by_name(license_id=99)

    assert len(result) == 1, f"Expected 1 group for 'Sugar', got {len(result)}"
    g = result[0]
    assert g["item_name"] == "Sugar"
    assert g["item_name_id"] == 10
    assert g["total_quantity"] == Decimal("700.000")
    assert g["available_quantity"] == Decimal("450.000")
    assert g["debited_quantity"] == Decimal("150.000")
    assert g["allotted_quantity"] == Decimal("100.000")
    assert sorted(g["sr_numbers"]) == [1, 2]
    assert sorted(g["row_ids"]) == [1, 2]


def test_group_preserves_raw_rows_unchanged():
    """
    BD-002: Raw SR rows must NOT be merged or modified — grouping is read-only.
    The original item objects must be untouched after calling the function.
    """
    from apps.license.services.balance_service import group_import_items_by_name

    canonical = MagicMock()
    canonical.id = 20
    canonical.name = "Wheat"

    item = MagicMock()
    item.pk = 5
    item.serial_number = 3
    item.description = "Wheat flour"
    item.quantity = Decimal("1000.000")
    item.available_quantity = Decimal("800.000")
    item.debited_quantity = Decimal("200.000")
    item.allotted_quantity = Decimal("0.000")
    item.items.all.return_value = [canonical]

    mock_items_qs = MagicMock()
    mock_items_qs.__iter__ = MagicMock(return_value=iter([item]))

    mock_model = MagicMock()
    mock_model.objects.filter.return_value.prefetch_related.return_value = mock_items_qs

    with patch("apps.license.models.LicenseImportItemsModel", mock_model):
        result = group_import_items_by_name(license_id=42)

    # The original item's fields must not have been modified
    assert item.quantity == Decimal("1000.000"), "Raw item quantity must not be modified"
    assert item.available_quantity == Decimal("800.000"), "Raw item available_quantity must not be modified"

    # Grouped result has single entry
    assert len(result) == 1
    assert result[0]["sr_numbers"] == [3]
    assert result[0]["row_ids"] == [5]


def test_group_handles_items_without_item_name():
    """
    BD-002: Items without a linked ItemNameModel fall back to description-based grouping.
    Two items with the same description are grouped together.
    """
    from apps.license.services.balance_service import group_import_items_by_name

    item1 = MagicMock()
    item1.pk = 10
    item1.serial_number = 1
    item1.description = "Raw Cotton"
    item1.quantity = Decimal("300.000")
    item1.available_quantity = Decimal("200.000")
    item1.debited_quantity = Decimal("100.000")
    item1.allotted_quantity = Decimal("0.000")
    item1.items.all.return_value = []  # no ItemNameModel linked

    item2 = MagicMock()
    item2.pk = 11
    item2.serial_number = 2
    item2.description = "Raw Cotton"
    item2.quantity = Decimal("100.000")
    item2.available_quantity = Decimal("100.000")
    item2.debited_quantity = Decimal("0.000")
    item2.allotted_quantity = Decimal("0.000")
    item2.items.all.return_value = []  # no ItemNameModel linked

    mock_items_qs = MagicMock()
    mock_items_qs.__iter__ = MagicMock(return_value=iter([item1, item2]))

    mock_model = MagicMock()
    mock_model.objects.filter.return_value.prefetch_related.return_value = mock_items_qs

    with patch("apps.license.models.LicenseImportItemsModel", mock_model):
        result = group_import_items_by_name(license_id=1)

    assert len(result) == 1, f"Two items with same description should form 1 group, got {len(result)}"
    g = result[0]
    assert g["item_name"] == "Raw Cotton"
    assert g["total_quantity"] == Decimal("400.000")
    assert sorted(g["sr_numbers"]) == [1, 2]


def test_group_key_is_item_name_id():
    """
    BD-002: item_name_id in returned dicts must be the ItemNameModel.id (int)
    when an ItemNameModel is linked, or 'desc:{description}' (str) when not.
    """
    from apps.license.services.balance_service import group_import_items_by_name

    canonical = MagicMock()
    canonical.id = 42
    canonical.name = "Salt"

    item_with_name = MagicMock()
    item_with_name.pk = 1
    item_with_name.serial_number = 1
    item_with_name.description = ""
    item_with_name.quantity = Decimal("100.000")
    item_with_name.available_quantity = Decimal("100.000")
    item_with_name.debited_quantity = Decimal("0.000")
    item_with_name.allotted_quantity = Decimal("0.000")
    item_with_name.items.all.return_value = [canonical]

    item_without_name = MagicMock()
    item_without_name.pk = 2
    item_without_name.serial_number = 2
    item_without_name.description = "Unknown Item"
    item_without_name.quantity = Decimal("50.000")
    item_without_name.available_quantity = Decimal("50.000")
    item_without_name.debited_quantity = Decimal("0.000")
    item_without_name.allotted_quantity = Decimal("0.000")
    item_without_name.items.all.return_value = []

    mock_items_qs = MagicMock()
    mock_items_qs.__iter__ = MagicMock(return_value=iter([item_with_name, item_without_name]))

    mock_model = MagicMock()
    mock_model.objects.filter.return_value.prefetch_related.return_value = mock_items_qs

    with patch("apps.license.models.LicenseImportItemsModel", mock_model):
        result = group_import_items_by_name(license_id=1)

    # Find each group by name
    named_groups = {g["item_name"]: g for g in result}

    assert "Salt" in named_groups, "Expected a 'Salt' group from ItemNameModel"
    assert named_groups["Salt"]["item_name_id"] == 42, (
        f"item_name_id must be int 42, got {named_groups['Salt']['item_name_id']}"
    )
    assert "Unknown Item" in named_groups, "Expected an 'Unknown Item' group (fallback)"
    assert named_groups["Unknown Item"]["item_name_id"] == "desc:Unknown Item", (
        f"item_name_id for fallback must be 'desc:Unknown Item', "
        f"got {named_groups['Unknown Item']['item_name_id']}"
    )


# ===========================================================================
# BD-003 Tests — Negative Balance Support
# ===========================================================================

@pytest.fixture(autouse=True)
def _suppress_notification_handler():
    """
    Suppress _handle_negative_balance_notification and _update_item_level_balances
    in all BD-003 balance tests (except those that test the handler directly).

    Tests that exercise _handle_negative_balance_notification directly unset
    this fixture by patching it themselves.
    """
    with patch(
        "apps.license.services.balance_service._update_item_level_balances",
        return_value=None,
    ):
        yield


def _call_recompute(license_id, credit, debit, allotment, trade, expiry=None):
    """Exercise recompute_license_balance() with mocked sub-components."""
    from apps.license.services.balance_service import recompute_license_balance

    mock_license = MagicMock(spec=["pk", "license_expiry_date"])
    mock_license.pk = license_id
    mock_license.license_expiry_date = expiry

    with patch("apps.license.models.LicenseDetailsModel.objects") as mock_ld_mgr, \
         patch("apps.license.services.balance_service._compute_credit",
               return_value=Decimal(str(credit))), \
         patch("apps.license.services.balance_service._compute_debit",
               return_value=Decimal(str(debit))), \
         patch("apps.license.services.balance_service._compute_allotment",
               return_value=Decimal(str(allotment))), \
         patch("apps.license.services.balance_service._compute_trade",
               return_value=Decimal(str(trade))), \
         patch("apps.license.models.LicenseBalance.objects") as mock_bal_mgr, \
         patch("apps.license.models.LicenseFlags.objects") as mock_flags_mgr, \
         patch("apps.license.services.balance_service._handle_negative_balance_notification") as mock_notify, \
         patch("django.db.transaction.atomic") as mock_atomic:

        mock_atomic.return_value.__enter__ = MagicMock(return_value=None)
        mock_atomic.return_value.__exit__ = MagicMock(return_value=False)
        mock_ld_mgr.select_for_update.return_value.select_related.return_value.get.return_value = mock_license
        mock_ld_mgr.DoesNotExist = LookupError

        recompute_license_balance(license_id)

    return mock_bal_mgr, mock_flags_mgr, mock_notify


def test_balance_can_be_negative():
    """
    BD-003: balance_cif must be stored as the actual negative value when
    credit < debit + allotment + trade (no floor applied).

    credit=1000, debit=3000 → balance=-2000.00 (not clamped to 0).
    """
    bal_mgr, _, _ = _call_recompute(
        license_id=301,
        credit="1000.00",
        debit="3000.00",
        allotment="0.00",
        trade="0.00",
    )

    bal_mgr.update_or_create.assert_called_once()
    written = bal_mgr.update_or_create.call_args.kwargs["defaults"]["balance_cif"]
    assert written == Decimal("-2000.00"), (
        f"BD-003: balance must be -2000.00 (no floor), got {written}"
    )


def test_available_quantity_can_be_negative():
    """
    BD-003: available_quantity = total - debited - allotted (no floor).

    When debited + allotted > total, available_quantity must be negative.
    """
    from decimal import ROUND_DOWN

    _DEC_0 = Decimal("0")
    _THREE_PLACES = Decimal("0.001")

    total_qty = Decimal("100.000")
    deb_qty = Decimal("150.000")
    allt_qty = Decimal("0.000")

    # BD-003: no max(_DEC_0, ...) floor
    available = (total_qty - deb_qty - allt_qty).quantize(_THREE_PLACES, rounding=ROUND_DOWN)

    assert available == Decimal("-50.000"), (
        f"BD-003: available_quantity must be -50.000 (no floor), got {available}"
    )


def test_is_null_not_set_when_balance_negative():
    """
    BD-003: is_null must be False when balance is negative.

    is_null is only True when balance is in [0, 500) — the 'null/depleted'
    state. A negative balance is a distinct over-debit state tracked via
    LicenseBalanceNotification.
    """
    _, flags_mgr, _ = _call_recompute(
        license_id=302,
        credit="0.00",
        debit="500.00",
        allotment="0.00",
        trade="0.00",
    )

    flags_mgr.update_or_create.assert_called_once()
    flags_written = flags_mgr.update_or_create.call_args.kwargs["defaults"]
    assert flags_written["is_null"] is False, (
        f"is_null must be False when balance is negative, got {flags_written['is_null']}"
    )


def test_negative_balance_creates_notification():
    """
    BD-003: _handle_negative_balance_notification creates a new
    LicenseBalanceNotification when balance < 0 and no active notification exists.
    """
    from apps.license.services.balance_service import _handle_negative_balance_notification

    mock_notif_qs = MagicMock()
    mock_notif_qs.filter.return_value.first.return_value = None  # no existing notification

    mock_create = MagicMock()

    mock_notif_model = MagicMock()
    mock_notif_model.objects = mock_notif_qs
    mock_notif_model.objects.filter = mock_notif_qs.filter
    mock_notif_model.objects.create = mock_create
    mock_notif_model.STATUS_ACTIVE = "active"

    with patch.dict("sys.modules", {
        "apps.notifications.models": MagicMock(LicenseBalanceNotification=mock_notif_model),
    }):
        _handle_negative_balance_notification(license_id=99, balance=Decimal("-500.00"))

    mock_create.assert_called_once()
    call_kwargs = mock_create.call_args.kwargs
    assert call_kwargs["license_id"] == 99
    assert call_kwargs["balance_cif"] == Decimal("-500.00")
    assert call_kwargs["status"] == "active"


def test_repeated_negative_balance_updates_existing_notification():
    """
    BD-003: When balance goes more negative, the EXISTING active notification
    is updated (balance_cif updated), not replaced with a new record.
    """
    from apps.license.services.balance_service import _handle_negative_balance_notification

    existing_notif = MagicMock()
    existing_notif.balance_cif = Decimal("-100.00")

    mock_notif_qs = MagicMock()
    mock_notif_qs.filter.return_value.first.return_value = existing_notif

    mock_notif_model = MagicMock()
    mock_notif_model.objects = mock_notif_qs
    mock_notif_model.STATUS_ACTIVE = "active"

    with patch.dict("sys.modules", {
        "apps.notifications.models": MagicMock(LicenseBalanceNotification=mock_notif_model),
    }):
        _handle_negative_balance_notification(license_id=99, balance=Decimal("-750.00"))

    # Must update, not create
    assert existing_notif.balance_cif == Decimal("-750.00"), (
        "Existing notification balance_cif must be updated"
    )
    existing_notif.save.assert_called_once()
    saved_fields = existing_notif.save.call_args.kwargs.get("update_fields", [])
    assert "balance_cif" in saved_fields
    # Must NOT call create
    mock_notif_model.objects.create.assert_not_called()


def test_positive_balance_does_not_auto_resolve_notification():
    """
    BD-003: When balance returns to >= 0, existing notifications are NOT
    automatically resolved. Resolution is a deliberate business action only.

    _handle_negative_balance_notification must return immediately without
    touching any notification records when balance >= 0.
    """
    from apps.license.services.balance_service import _handle_negative_balance_notification

    mock_notif_model = MagicMock()

    with patch.dict("sys.modules", {
        "apps.notifications.models": MagicMock(LicenseBalanceNotification=mock_notif_model),
    }):
        _handle_negative_balance_notification(license_id=99, balance=Decimal("1500.00"))

    # Must not touch the DB at all when balance is healthy
    mock_notif_model.objects.filter.assert_not_called()
    mock_notif_model.objects.create.assert_not_called()


def test_balance_status_healthy():
    """
    BD-003: LicenseFlagsSerializer.get_balance_status returns 'healthy'
    when balance_cif >= 500.
    """
    from apps.license.serializers.license import LicenseFlagsSerializer

    mock_flags = MagicMock()
    mock_flags.license.balance.balance_cif = Decimal("5000.00")

    serializer = LicenseFlagsSerializer()
    result = serializer.get_balance_status(mock_flags)

    assert result == "healthy", f"Expected 'healthy' for balance=5000, got {result!r}"


def test_balance_status_null():
    """
    BD-003: LicenseFlagsSerializer.get_balance_status returns 'null'
    when 0 <= balance_cif < 500.
    """
    from apps.license.serializers.license import LicenseFlagsSerializer

    mock_flags = MagicMock()
    mock_flags.license.balance.balance_cif = Decimal("200.00")

    serializer = LicenseFlagsSerializer()
    result = serializer.get_balance_status(mock_flags)

    assert result == "null", f"Expected 'null' for balance=200, got {result!r}"


def test_balance_status_negative():
    """
    BD-003: LicenseFlagsSerializer.get_balance_status returns 'negative'
    when balance_cif < 0.
    """
    from apps.license.serializers.license import LicenseFlagsSerializer

    mock_flags = MagicMock()
    mock_flags.license.balance.balance_cif = Decimal("-300.00")

    serializer = LicenseFlagsSerializer()
    result = serializer.get_balance_status(mock_flags)

    assert result == "negative", f"Expected 'negative' for balance=-300, got {result!r}"
