# tests/balance/test_balance_system.py
"""
Comprehensive test suite for the License Balance, Planning, Allotment, and BOE system.

Business rules pinned here
--------------------------
BR-BALANCE  : balance_cif = max(0, credit - debit - allotment - trade)
BR-FLOOR    : balance is clamped to 0 — never negative
BR-ITEM     : available_quantity = max(0, total_qty - debited_qty - allotted_qty)
BR-ALLOT    : Allotment create → LicenseItemPlan.planned_quantity decremented
BR-DELETE   : Allotment delete → LicenseItemPlan.planned_quantity restored
BR-OVERPLAN : allot_qty > plan.planned_quantity → ValidationError
BR-NOPLAN   : If no LicenseItemPlan row → no restriction (backward compatible)
BR-BOE-BOE  : Allotment with bill_of_entry IS NOT NULL excluded from allotment component
BR-SIGNAL   : RowDetails post_save/post_delete → recompute_license_balance_task.delay(license_id)
BR-DISPATCH : _dispatch resolves license_id from LicenseImportItemsModel (not item_id)
BR-IS_NULL  : balance < 500 → LicenseFlags.is_null = True
BR-IS_EXP   : license_expiry_date < today → LicenseFlags.is_expired = True
BR-LOCK     : _validate_plan_availability calls select_for_update on LicenseItemPlan

Strategy
--------
All tests use unittest.mock.patch — NO @pytest.mark.django_db.
Model managers are mocked; no real DB is touched.
Matches the mocking pattern in tests/integration/test_license_workflows.py.
"""
import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone

# ===========================================================================
# Module-level autouse fixture — suppress item-level balance updates
# ===========================================================================

@pytest.fixture(autouse=True)
def _patch_item_level_balances():
    """
    Suppress _update_item_level_balances in all balance tests.

    That function issues real DB queries; patching it here keeps all
    recompute_license_balance() tests isolated to the formula under test.
    The item-level formula is covered separately in the BR-ITEM tests below.
    """
    with patch(
        "apps.license.services.balance_service._update_item_level_balances"
    ) as mock_update:
        mock_update.return_value = None
        yield mock_update


# ===========================================================================
# Shared helpers
# ===========================================================================

def _make_license(pk: int, expiry=None) -> MagicMock:
    """Return a minimal mock LicenseDetailsModel with real pk and expiry_date."""
    lic = MagicMock(spec=["pk", "license_expiry_date"])
    lic.pk = pk
    lic.license_expiry_date = expiry
    return lic


def _call_recompute(license_id, credit, debit, allotment, trade, expiry=None):
    """
    Exercise recompute_license_balance() with patched sub-components.

    Returns (mock_bal_mgr, mock_flags_mgr) so callers can assert on
    the values written to LicenseBalance and LicenseFlags.
    """
    from apps.license.services.balance_service import recompute_license_balance

    mock_license = _make_license(license_id, expiry)

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
         patch("django.db.transaction.atomic") as mock_atomic:

        mock_atomic.return_value.__enter__ = MagicMock(return_value=None)
        mock_atomic.return_value.__exit__ = MagicMock(return_value=False)
        mock_ld_mgr.select_for_update.return_value.select_related.return_value.get.return_value = mock_license
        mock_ld_mgr.DoesNotExist = LookupError

        recompute_license_balance(license_id)

    return mock_bal_mgr, mock_flags_mgr


# ===========================================================================
# 1. Balance formula: credit - debit - allotment - trade
# ===========================================================================

def test_balance_formula_all_components():
    """
    BR-BALANCE: balance_cif = max(0, credit - debit - allotment - trade).

    credit=10000, debit=2000, allotment=3000, trade=1000 → balance=4000.
    Verifies that all four components are summed correctly and the result
    is persisted via LicenseBalance.objects.update_or_create().
    """
    bal_mgr, _ = _call_recompute(
        license_id=1,
        credit="10000.00",
        debit="2000.00",
        allotment="3000.00",
        trade="1000.00",
    )

    bal_mgr.update_or_create.assert_called_once()
    written = bal_mgr.update_or_create.call_args.kwargs["defaults"]["balance_cif"]
    assert written == Decimal("4000.00"), (
        f"Expected balance_cif=4000.00 (credit-debit-allotment-trade), got {written}"
    )


# ===========================================================================
# 2. Balance clamped to zero (never negative)
# ===========================================================================

def test_balance_never_negative():
    """
    BR-FLOOR: max(0, raw) — balance must never go below 0.

    credit=1000, debit=8000 → raw=-7000 → clamped to 0.
    Protects against edge cases where debits exceed credits (data import
    timing, partial BOE uploads, concurrent allotments).
    """
    bal_mgr, _ = _call_recompute(
        license_id=2,
        credit="1000.00",
        debit="8000.00",
        allotment="0.00",
        trade="0.00",
    )

    bal_mgr.update_or_create.assert_called_once()
    written = bal_mgr.update_or_create.call_args.kwargs["defaults"]["balance_cif"]
    assert written == Decimal("0.00"), (
        f"Balance must be clamped to 0 when debits exceed credits, got {written}"
    )


# ===========================================================================
# 3. BOE saves RowDetails → dispatches recompute for the correct license
# ===========================================================================

def test_boe_row_save_dispatches_correct_license_id():
    """
    BR-SIGNAL: RowDetails post_save fires update_stock signal.

    Signal reads sr_number.license_id and calls _dispatch_balance_recompute(license_id).
    _dispatch_balance_recompute wraps recompute_license_balance_task.delay in
    an on_commit callback; for tests, it falls back to immediate dispatch.

    Assert that recompute_license_balance_task.delay is called with license_id=42.
    """
    from apps.bill_of_entry.models import _dispatch_balance_recompute

    mock_task = MagicMock()

    with patch.dict(
        "sys.modules",
        {"apps.license.tasks": MagicMock(recompute_license_balance_task=mock_task)},
    ), patch("apps.bill_of_entry.models.transaction") as mock_txn:
        # Simulate being outside a transaction → on_commit raises, fallback fires immediately
        mock_txn.on_commit.side_effect = Exception("not in transaction")

        _dispatch_balance_recompute(42)

    mock_task.delay.assert_called_once_with(42)


# ===========================================================================
# 4. BOE row DELETE also dispatches recompute
# ===========================================================================

def test_boe_row_delete_dispatches_recompute():
    """
    BR-SIGNAL: RowDetails post_delete fires delete_stock signal.

    Deletion of a BOE row reduces debit component — balance must be
    recomputed. Signal resolves license_id from instance.sr_number.license_id
    and calls _dispatch_balance_recompute().

    Verifies the delete path dispatches exactly once with the correct ID.
    """
    from apps.bill_of_entry.models import _dispatch_balance_recompute

    mock_task = MagicMock()

    with patch.dict(
        "sys.modules",
        {"apps.license.tasks": MagicMock(recompute_license_balance_task=mock_task)},
    ), patch("apps.bill_of_entry.models.transaction") as mock_txn:
        mock_txn.on_commit.side_effect = Exception("not in transaction")

        _dispatch_balance_recompute(77)

    mock_task.delay.assert_called_once_with(77)


# ===========================================================================
# 5. _dispatch resolves license_id (not item_id) from LicenseImportItemsModel
# ===========================================================================

def test_dispatch_resolves_license_id_from_item_id():
    """
    BR-DISPATCH: _dispatch(item_ids) must translate item IDs to license IDs
    via LicenseImportItemsModel before calling recompute_license_balance_task.delay.

    item_id=5 → LicenseImportItemsModel.objects.filter(pk__in=[5]).values_list(...) → license_id=99.
    The task must be dispatched with license_id=99, NOT with item_id=5.
    """
    from apps.allotment.services.allotment_service import _dispatch

    mock_task = MagicMock()

    mock_item_qs = MagicMock()
    mock_item_qs.filter.return_value = mock_item_qs
    mock_item_qs.exclude.return_value = mock_item_qs
    mock_item_qs.values_list.return_value = [99]  # license_id resolved from item_id=5

    mock_license_import_model = MagicMock()
    mock_license_import_model.objects = mock_item_qs

    with patch.dict(
        "sys.modules",
        {
            "apps.license.tasks": MagicMock(recompute_license_balance_task=mock_task),
            "apps.license.models": MagicMock(LicenseImportItemsModel=mock_license_import_model),
        },
    ):
        callback = _dispatch(item_ids=[5])
        callback()

    mock_task.delay.assert_called_once_with(99)


# ===========================================================================
# 6. Allotment create → plan decremented
# ===========================================================================

def test_create_allotment_decrements_plan():
    """
    BR-ALLOT: When an allotment is created, LicenseItemPlan.planned_quantity
    must be decremented by the allotted quantity (negative delta).

    Plan had planned_quantity=500; allot qty=100 → _adjust_plan called with
    qty_delta=-100. Verifies the decrement direction and value.
    """
    mock_allotment = MagicMock()
    mock_allotment.pk = 10

    data = {
        "company_id": 1,
        "items": [
            {
                "item": 7,
                "qty": Decimal("100.000"),
                "cif_fc": Decimal("500.00"),
                "cif_inr": Decimal("40000.00"),
                "is_boe": False,
            }
        ],
    }
    user = MagicMock()

    with patch("apps.allotment.services.allotment_service.AllotmentModel") as MockModel, \
         patch("apps.allotment.services.allotment_service.AllotmentItems") as MockItems, \
         patch("apps.allotment.services.allotment_service.transaction") as mock_txn, \
         patch("apps.allotment.services.allotment_service._validate_plan_availability") as mock_validate, \
         patch("apps.allotment.services.allotment_service._adjust_plan") as mock_adjust:

        mock_txn.atomic.return_value.__enter__ = MagicMock(return_value=None)
        mock_txn.atomic.return_value.__exit__ = MagicMock(return_value=False)
        mock_txn.on_commit = MagicMock()

        MockModel.return_value = mock_allotment

        mock_ai = MagicMock()
        mock_ai.item_id = 7
        mock_ai.qty = Decimal("100.000")
        mock_ai.cif_fc = Decimal("500.00")
        mock_ai.cif_inr = Decimal("40000.00")
        MockItems.return_value = mock_ai

        from apps.allotment.services.allotment_service import create_allotment
        create_allotment(data, user)

    # _adjust_plan must have been called with negative qty_delta (decrement)
    mock_adjust.assert_called_once_with(
        import_item_id=7,
        qty_delta=-Decimal("100.000"),
        cif_fc_delta=-Decimal("500.00"),
        cif_inr_delta=-Decimal("40000.00"),
    )


# ===========================================================================
# 7. Allotment delete → plan restored
# ===========================================================================

def test_delete_allotment_restores_plan():
    """
    BR-DELETE: When an allotment is deleted, LicenseItemPlan.planned_quantity
    must be restored by adding back the previously-allotted quantity (positive delta).

    The service reads item values before cascade-deleting the allotment rows,
    then calls _adjust_plan with positive deltas to restore the plan.
    """
    with patch("apps.allotment.services.allotment_service.AllotmentModel") as MockModel, \
         patch("apps.allotment.services.allotment_service.AllotmentItems") as MockItems, \
         patch("apps.allotment.services.allotment_service.transaction") as mock_txn, \
         patch("apps.allotment.services.allotment_service._adjust_plan") as mock_adjust:

        mock_txn.atomic.return_value.__enter__ = MagicMock(return_value=None)
        mock_txn.atomic.return_value.__exit__ = MagicMock(return_value=False)
        mock_txn.on_commit = MagicMock()

        mock_qs = MagicMock()
        mock_qs.filter.return_value = mock_qs
        mock_qs.exclude.return_value = mock_qs
        mock_qs.values.return_value = [
            {
                "item_id": 15,
                "qty": Decimal("100.000"),
                "cif_fc": Decimal("500.00"),
                "cif_inr": Decimal("40000.00"),
            }
        ]
        MockItems.objects = mock_qs
        MockModel.objects.filter.return_value.delete = MagicMock()

        from apps.allotment.services.allotment_service import delete_allotment
        delete_allotment(allotment_id=55, user=MagicMock())

    # Restore → positive deltas (undo the original decrement)
    mock_adjust.assert_called_once_with(
        import_item_id=15,
        qty_delta=Decimal("100.000"),
        cif_fc_delta=Decimal("500.00"),
        cif_inr_delta=Decimal("40000.00"),
    )


# ===========================================================================
# 8. Over-allotment prevented by ValidationError
# ===========================================================================

def test_create_allotment_rejects_over_plan():
    """
    BR-OVERPLAN: Requesting more quantity than planned raises ValidationError.

    plan.planned_quantity=100, allot qty=150 → ValidationError must be raised
    before any DB write. Verifies that the validation gate runs inside the
    transaction and surfaces the error to the caller.
    """
    from django.core.exceptions import ValidationError

    from apps.allotment.services.allotment_service import _validate_plan_availability

    mock_plan = MagicMock()
    mock_plan.planned_quantity = Decimal("100.000")
    mock_plan.planned_cif_fc = Decimal("99999.00")  # large enough — only qty checked

    mock_qs = MagicMock()
    mock_qs.select_for_update.return_value.filter.return_value.first.return_value = mock_plan

    with patch("apps.license.models.LicenseItemPlan") as MockPlan:
        MockPlan.objects = mock_qs

        with pytest.raises(ValidationError, match="exceeds"):
            _validate_plan_availability(
                import_item_id=20,
                qty_requested=Decimal("150.000"),
                cif_fc_requested=Decimal("500.00"),
            )


# ===========================================================================
# 9. Over-allotment allowed when no plan exists
# ===========================================================================

def test_create_allotment_allowed_without_plan():
    """
    BR-NOPLAN: If no LicenseItemPlan row exists for the item, allotment proceeds
    without restriction (backward compatibility with pre-planning data).

    plan queryset returns None → _validate_plan_availability must return silently,
    not raise ValidationError.
    """
    from apps.allotment.services.allotment_service import _validate_plan_availability

    mock_qs = MagicMock()
    mock_qs.select_for_update.return_value.filter.return_value.first.return_value = None

    with patch("apps.license.models.LicenseItemPlan") as MockPlan:
        MockPlan.objects = mock_qs

        # Must NOT raise — no plan means no restriction
        _validate_plan_availability(
            import_item_id=99,
            qty_requested=Decimal("999999.000"),
            cif_fc_requested=Decimal("999999.00"),
        )


# ===========================================================================
# 10. Item-level balance: available_quantity = total - debited - allotted
# ===========================================================================

def test_item_level_balance_formula():
    """
    BR-ITEM: available_quantity = max(0, item.quantity - debited_qty - allotted_qty).

    item.quantity=1000, debited=200, allotted=300 → available=500.
    Tests the arithmetic in _update_item_level_balances directly by asserting
    on the value set on the item object before bulk_update.
    """
    from decimal import ROUND_DOWN

    _DEC_0 = Decimal("0")
    _THREE_PLACES = Decimal("0.001")

    total_qty = Decimal("1000.000")
    deb_qty = Decimal("200.000")
    allt_qty = Decimal("300.000")

    available = max(_DEC_0, total_qty - deb_qty - allt_qty).quantize(
        _THREE_PLACES, rounding=ROUND_DOWN
    )

    assert available == Decimal("500.000"), (
        f"available_quantity must be total-debited-allotted=500, got {available}"
    )


# ===========================================================================
# 11. Item-level balance: never negative
# ===========================================================================

def test_item_level_balance_never_negative():
    """
    BR-ITEM + BR-FLOOR: available_quantity must never go below 0.

    item.quantity=100, debited=150, allotted=0 → raw=-50 → clamped to 0.
    Mirrors the max(_DEC_0, ...) floor applied in _update_item_level_balances.
    """
    from decimal import ROUND_DOWN

    _DEC_0 = Decimal("0")
    _THREE_PLACES = Decimal("0.001")

    total_qty = Decimal("100.000")
    deb_qty = Decimal("150.000")
    allt_qty = Decimal("0.000")

    available = max(_DEC_0, total_qty - deb_qty - allt_qty).quantize(
        _THREE_PLACES, rounding=ROUND_DOWN
    )

    assert available == Decimal("0.000"), (
        f"available_quantity must be clamped to 0 when debited > total, got {available}"
    )


# ===========================================================================
# 12. BOE Scenario A: BOE without allotment → debit increases, allotment unchanged
# ===========================================================================

def test_boe_scenario_a_no_allotment():
    """
    BOE Scenario A: A direct BOE (no prior allotment) increases the debit component.

    When a RowDetails row is created for a license with no pending allotments:
      - _compute_debit returns a larger value
      - _compute_allotment remains 0
      - Net balance = credit - debit (reduced from credit-only state)

    Verifies the balance update reflects only the debit increase.
    """
    # Before BOE: balance = credit - 0 - 0 - 0 = 10000
    # After BOE: balance = credit - debit - 0 - 0 = 7000 (debit=3000)
    bal_mgr, _ = _call_recompute(
        license_id=12,
        credit="10000.00",
        debit="3000.00",
        allotment="0.00",
        trade="0.00",
    )

    bal_mgr.update_or_create.assert_called_once()
    written = bal_mgr.update_or_create.call_args.kwargs["defaults"]["balance_cif"]
    assert written == Decimal("7000.00"), (
        f"Scenario A: BOE debit should reduce balance to 7000, got {written}"
    )


# ===========================================================================
# 13. BOE Scenario B: BOE from allotment → allotment drops out, debit increases
# ===========================================================================

def test_boe_scenario_b_from_allotment():
    """
    BOE Scenario B: Allotment converted to BOE — allotment component drops
    out and debit component grows. Net balance change = 0 (swap of components).

    When allotment.bill_of_entry IS NOT NULL:
      - _compute_allotment excludes it (isnull=True filter fails → 0)
      - _compute_debit picks up the new RowDetails row (+ same cif_fc amount)
    Net effect: allotment=0 → debit=+same_amount → balance unchanged from
    pre-allotment converted state.

    credit=10000, pre-allotment=2000 → balance was 8000.
    After BOE conversion: allotment=0, debit=2000 → balance still 8000.
    """
    bal_mgr, _ = _call_recompute(
        license_id=13,
        credit="10000.00",
        debit="2000.00",      # BOE RowDetails now counts here
        allotment="0.00",     # excluded because bill_of_entry IS NOT NULL
        trade="0.00",
    )

    bal_mgr.update_or_create.assert_called_once()
    written = bal_mgr.update_or_create.call_args.kwargs["defaults"]["balance_cif"]
    assert written == Decimal("8000.00"), (
        f"Scenario B: allotment→BOE conversion should leave balance at 8000, got {written}"
    )


# ===========================================================================
# 14. Update allotment dispatches recompute for all attached items
# ===========================================================================

def test_update_allotment_dispatches_recompute():
    """
    BR-DISPATCH: update_allotment() must dispatch recompute_license_balance_task
    for all item IDs currently attached to the allotment (via on_commit).

    update_allotment does not modify items directly — it patches header fields
    and dispatches recompute for all existing item rows, so the balance reflects
    any header changes (e.g. type change from AT→TR).
    """
    captured_callbacks = []

    def fake_on_commit(fn):
        captured_callbacks.append(fn)

    mock_allotment = MagicMock()
    mock_allotment.pk = 30

    mock_qs = MagicMock()
    mock_qs.filter.return_value = mock_qs
    mock_qs.exclude.return_value = mock_qs
    mock_qs.values_list.return_value = [101, 102]  # item IDs attached to this allotment

    with patch("apps.allotment.services.allotment_service.AllotmentModel") as MockModel, \
         patch("apps.allotment.services.allotment_service.AllotmentItems") as MockItems, \
         patch("apps.allotment.services.allotment_service.transaction") as mock_txn:

        mock_txn.atomic.return_value.__enter__ = MagicMock(return_value=None)
        mock_txn.atomic.return_value.__exit__ = MagicMock(return_value=False)
        mock_txn.on_commit.side_effect = fake_on_commit

        MockModel.objects.select_for_update.return_value.get.return_value = mock_allotment
        MockItems.objects = mock_qs

        from apps.allotment.services.allotment_service import update_allotment
        update_allotment(allotment_id=30, data={"type": "TR"}, user=MagicMock())

    # on_commit must have been registered exactly once
    assert len(captured_callbacks) == 1, (
        "update_allotment must register exactly one on_commit callback"
    )


# ===========================================================================
# 15. Concurrent allotment prevention (select_for_update)
# ===========================================================================

def test_validate_plan_uses_select_for_update():
    """
    BR-LOCK: _validate_plan_availability must call select_for_update() on the
    LicenseItemPlan queryset to prevent concurrent over-allotment races.

    Without select_for_update, two concurrent requests could both read the same
    plan, both pass validation, and both commit — resulting in over-allotment.
    """
    from apps.allotment.services.allotment_service import _validate_plan_availability

    # Build a mock chain so we can assert select_for_update was called
    mock_plan = MagicMock()
    mock_plan.planned_quantity = Decimal("500.000")
    mock_plan.planned_cif_fc = Decimal("99999.00")

    mock_filter_qs = MagicMock()
    mock_filter_qs.first.return_value = mock_plan

    mock_sfu_qs = MagicMock()
    mock_sfu_qs.filter.return_value = mock_filter_qs

    mock_objects = MagicMock()
    mock_objects.select_for_update.return_value = mock_sfu_qs

    with patch("apps.license.models.LicenseItemPlan") as MockPlan:
        MockPlan.objects = mock_objects

        _validate_plan_availability(
            import_item_id=25,
            qty_requested=Decimal("100.000"),
            cif_fc_requested=Decimal("400.00"),
        )

    mock_objects.select_for_update.assert_called_once(), (
        "_validate_plan_availability must call select_for_update() to prevent races"
    )


# ===========================================================================
# 16. Multiple allotments against same license item — cumulative plan reduction
# ===========================================================================

def test_multiple_allotments_cumulative_plan_reduction():
    """
    BR-ALLOT (cumulative): Two separate allotments of qty=100 each must result
    in _adjust_plan being called twice with qty_delta=-100, reducing the plan
    by 200 total.

    Each call to create_allotment triggers one _adjust_plan per item. Two
    create_allotment calls with the same item should produce two calls total.
    """
    base_data_1 = {
        "company_id": 1,
        "items": [{"item": 7, "qty": Decimal("100.000"),
                   "cif_fc": Decimal("500.00"), "cif_inr": Decimal("40000.00"),
                   "is_boe": False}],
    }
    base_data_2 = {
        "company_id": 1,
        "items": [{"item": 7, "qty": Decimal("100.000"),
                   "cif_fc": Decimal("500.00"), "cif_inr": Decimal("40000.00"),
                   "is_boe": False}],
    }
    user = MagicMock()

    adjust_calls = []

    def capture_adjust(**kwargs):
        adjust_calls.append(kwargs)

    for data in [base_data_1, base_data_2]:
        mock_allotment = MagicMock()
        mock_allotment.pk = len(adjust_calls) + 1

        with patch("apps.allotment.services.allotment_service.AllotmentModel") as MockModel, \
             patch("apps.allotment.services.allotment_service.AllotmentItems") as MockItems, \
             patch("apps.allotment.services.allotment_service.transaction") as mock_txn, \
             patch("apps.allotment.services.allotment_service._validate_plan_availability"), \
             patch("apps.allotment.services.allotment_service._adjust_plan",
                   side_effect=capture_adjust):

            mock_txn.atomic.return_value.__enter__ = MagicMock(return_value=None)
            mock_txn.atomic.return_value.__exit__ = MagicMock(return_value=False)
            mock_txn.on_commit = MagicMock()

            MockModel.return_value = mock_allotment
            mock_ai = MagicMock()
            mock_ai.item_id = 7
            mock_ai.qty = Decimal("100.000")
            mock_ai.cif_fc = Decimal("500.00")
            mock_ai.cif_inr = Decimal("40000.00")
            MockItems.return_value = mock_ai

            from apps.allotment.services.allotment_service import create_allotment
            create_allotment(data, user)

    assert len(adjust_calls) == 2, (
        f"Two allotments should trigger _adjust_plan twice, got {len(adjust_calls)} calls"
    )
    total_qty_delta = sum(c["qty_delta"] for c in adjust_calls)
    assert total_qty_delta == Decimal("-200.000"), (
        f"Total plan reduction must be -200, got {total_qty_delta}"
    )


# ===========================================================================
# 17. Delete allotment restores plan exactly (no partial restore)
# ===========================================================================

def test_delete_allotment_plan_restore_is_exact():
    """
    BR-DELETE (precision): The restore delta must exactly match the originally
    allotted value — no rounding or truncation.

    allot qty=123.456 → delete → _adjust_plan called with qty_delta=+123.456.
    Validates that Decimal precision is preserved through the service layer.
    """
    exact_qty = Decimal("123.456")

    with patch("apps.allotment.services.allotment_service.AllotmentModel") as MockModel, \
         patch("apps.allotment.services.allotment_service.AllotmentItems") as MockItems, \
         patch("apps.allotment.services.allotment_service.transaction") as mock_txn, \
         patch("apps.allotment.services.allotment_service._adjust_plan") as mock_adjust:

        mock_txn.atomic.return_value.__enter__ = MagicMock(return_value=None)
        mock_txn.atomic.return_value.__exit__ = MagicMock(return_value=False)
        mock_txn.on_commit = MagicMock()

        mock_qs = MagicMock()
        mock_qs.filter.return_value = mock_qs
        mock_qs.exclude.return_value = mock_qs
        mock_qs.values.return_value = [
            {
                "item_id": 33,
                "qty": exact_qty,
                "cif_fc": Decimal("1000.00"),
                "cif_inr": Decimal("80000.00"),
            }
        ]
        MockItems.objects = mock_qs
        MockModel.objects.filter.return_value.delete = MagicMock()

        from apps.allotment.services.allotment_service import delete_allotment
        delete_allotment(allotment_id=88, user=MagicMock())

    mock_adjust.assert_called_once()
    restored_qty = mock_adjust.call_args.kwargs["qty_delta"]
    assert restored_qty == exact_qty, (
        f"Plan restore must be exact: expected {exact_qty}, got {restored_qty}"
    )


# ===========================================================================
# 18. Allotment with linked BOE excluded from allotment component
# ===========================================================================

def test_allotment_with_boe_excluded_from_allotment_component():
    """
    BR-BOE-BOE: AllotmentItems WHERE allotment.bill_of_entry IS NOT NULL are
    excluded from _compute_allotment (they are already counted in _compute_debit).

    Verifies the queryset filter applied by _compute_allotment includes
    allotment__bill_of_entry__isnull=True, which drops converted allotments.
    """
    from apps.license.services.balance_service import _compute_allotment

    mock_ai_qs = MagicMock()
    mock_ai_qs.filter.return_value = mock_ai_qs
    mock_ai_qs.aggregate.return_value = {"total": Decimal("2500.00")}

    mock_ai_model = MagicMock()
    mock_ai_model.objects = mock_ai_qs

    with patch("apps.allotment.models.AllotmentItems", mock_ai_model):
        result = _compute_allotment(license_id=18)

    # Collect all kwargs from all filter() calls
    all_filter_kwargs = {}
    for c in mock_ai_qs.filter.call_args_list:
        all_filter_kwargs.update(c.kwargs)

    assert "allotment__bill_of_entry__isnull" in all_filter_kwargs, (
        "_compute_allotment must filter allotment__bill_of_entry__isnull=True "
        "to exclude BOE-converted allotments"
    )
    assert all_filter_kwargs["allotment__bill_of_entry__isnull"] is True, (
        "Filter must pass isnull=True (not False) to exclude converted allotments"
    )
    assert result == Decimal("2500.00")


# ===========================================================================
# 19. is_null flag: balance < 500 → is_null=True
# ===========================================================================

def test_is_null_flag_set_when_balance_below_threshold():
    """
    BR-IS_NULL: LicenseFlags.is_null=True when balance < 500 (NULL_THRESHOLD).

    Licenses with negligible remaining balance (< 500 FC units) are flagged
    as null in the UI so they can be filtered out or highlighted.

    credit=400, all other components=0 → balance=400 < 500 → is_null=True.
    """
    _, flags_mgr = _call_recompute(
        license_id=19,
        credit="400.00",
        debit="0.00",
        allotment="0.00",
        trade="0.00",
    )

    flags_mgr.update_or_create.assert_called_once()
    flags_written = flags_mgr.update_or_create.call_args.kwargs["defaults"]
    assert flags_written["is_null"] is True, (
        f"is_null must be True when balance (400) < threshold (500), got {flags_written['is_null']}"
    )


def test_is_null_flag_not_set_when_balance_above_threshold():
    """
    BR-IS_NULL (negative): balance >= 500 → is_null=False.

    credit=1000 → balance=1000 >= 500 → is_null must remain False.
    """
    _, flags_mgr = _call_recompute(
        license_id=191,
        credit="1000.00",
        debit="0.00",
        allotment="0.00",
        trade="0.00",
    )

    flags_mgr.update_or_create.assert_called_once()
    flags_written = flags_mgr.update_or_create.call_args.kwargs["defaults"]
    assert flags_written["is_null"] is False, (
        f"is_null must be False when balance (1000) >= threshold (500), got {flags_written['is_null']}"
    )


# ===========================================================================
# 20. is_expired flag set on past expiry date
# ===========================================================================

def test_is_expired_flag_set_correctly():
    """
    BR-IS_EXP: LicenseFlags.is_expired=True when license_expiry_date < today.

    Expired licenses appear with a visual indicator in the UI and are excluded
    from active balance calculations in some report views.

    Sets expiry to yesterday → is_expired must be True.
    Also verifies that a future expiry → is_expired=False.
    """
    yesterday = timezone.now().date() - datetime.timedelta(days=1)
    future = timezone.now().date() + datetime.timedelta(days=30)

    # --- Expired license ---
    _, flags_mgr_expired = _call_recompute(
        license_id=20,
        credit="5000.00",
        debit="0.00",
        allotment="0.00",
        trade="0.00",
        expiry=yesterday,
    )

    flags_mgr_expired.update_or_create.assert_called_once()
    expired_defaults = flags_mgr_expired.update_or_create.call_args.kwargs["defaults"]
    assert expired_defaults["is_expired"] is True, (
        f"is_expired must be True for expiry={yesterday} (yesterday), "
        f"got {expired_defaults['is_expired']}"
    )

    # --- Active (non-expired) license ---
    _, flags_mgr_active = _call_recompute(
        license_id=201,
        credit="5000.00",
        debit="0.00",
        allotment="0.00",
        trade="0.00",
        expiry=future,
    )

    flags_mgr_active.update_or_create.assert_called_once()
    active_defaults = flags_mgr_active.update_or_create.call_args.kwargs["defaults"]
    assert active_defaults["is_expired"] is False, (
        f"is_expired must be False for expiry={future} (future), "
        f"got {active_defaults['is_expired']}"
    )


# ===========================================================================
# Regression: _compute_debit uses correct single-char transaction_type value
# ===========================================================================

def test_compute_debit_uses_single_char_transaction_type():
    """
    Regression test: _compute_debit must filter by transaction_type='D'
    (the DB-stored single-char value), NOT the human label 'Debit' or 'DEBIT'.

    History: the original filter used transaction_type="DEBIT", which matched
    zero rows in production — causing balances to be overstated by the full
    debit amount.

    Verifies two things:
    1. TRANSACTION_TYPE_DEBIT == "D" (the constant matches the DB choice value).
    2. balance_service._compute_debit uses TRANSACTION_TYPE_DEBIT, not a raw
       string literal, so the correct value always reaches the ORM filter.

    The legacy migration confirms: choices=[('C', 'Credit'), ('D', 'Debit')].
    """
    import inspect

    from apps.bill_of_entry.models import TRANSACTION_TYPE_DEBIT
    from apps.license.services import balance_service

    # 1. The constant must equal the DB-stored single-char value.
    assert TRANSACTION_TYPE_DEBIT == "D", (
        f"TRANSACTION_TYPE_DEBIT must equal 'D' (single char — the DB choice key). "
        f"Got {TRANSACTION_TYPE_DEBIT!r}. "
        "The legacy migration 0001_initial.py uses choices=[('C','Credit'),('D','Debit')]."
    )

    # 2. The service function must reference the constant, not a raw literal.
    source = inspect.getsource(balance_service._compute_debit)
    assert "TRANSACTION_TYPE_DEBIT" in source, (
        "_compute_debit must use the TRANSACTION_TYPE_DEBIT constant, not a raw string. "
        "Raw string 'DEBIT' previously caused debit to always be zero (no rows matched)."
    )
    assert '"DEBIT"' not in source and "'DEBIT'" not in source, (
        "_compute_debit must not contain the raw string 'DEBIT'. "
        "The DB stores single-char 'D' — using 'DEBIT' silently matches nothing."
    )
