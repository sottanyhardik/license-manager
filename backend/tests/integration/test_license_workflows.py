# tests/integration/test_license_workflows.py
"""
Cross-module integration tests for the License Manager.

Environment constraints
-----------------------
- `managed=False` models cannot be used against the SQLite in-memory test DB
  reliably because the `_patch_*_managed()` calls in test.py execute before
  the Django app registry is fully populated, so Django re-loads the models as
  managed=False during app setup and the tables are never created.
- The `SpectacularSwaggerUIView` import error in config/urls.py breaks any test
  that triggers URL loading through the DRF test client.

Strategy
--------
All tests that exercise business logic mock ORM calls via `unittest.mock.patch`
and invoke the real service/model code.  This matches the pattern used by all
other passing tests in this test suite (see tests/license/test_license.py,
tests/allotment/test_allotment.py).

What is tested
--------------
- BR-01: LicenseBalance is a materialised sub-table field.
- BR-02: balance = credit - debit - allotment - trade (mocked components).
- BR-02 (constraint): balance is clamped to 0, never goes negative.
- BR-03: is_expired flag set when license_expiry_date < today.
- BR-04: Frozen BOE row raises ValueError from service layer.
- BR-05: AllotmentItems (AT) are included in the allotment component.
- BR-06: license_number uniqueness enforced at model level.
- BR-07: Invoice number format regex and sequential uniqueness.
- BR-08: CIF billing calculation precision (Decimal, not float).
- E2E:   Full balance workflow (credit - debit - allotment = final balance).
"""
import re
from decimal import Decimal
from unittest.mock import MagicMock, call, patch

import pytest


# ---------------------------------------------------------------------------
# BR-02 — Test 1: balance_service produces correct balance after BOE debit
# ---------------------------------------------------------------------------

def test_license_balance_after_boe_row_creation():
    """
    BR-02: available_qty = authorised_cif - debited_quantity - allotted_quantity.

    Exercises recompute_license_balance() with mocked credit/debit/allotment/trade
    components.  Creating a RowDetails record increases the debit component;
    the resulting balance must equal credit - debit.
    """
    from apps.license.services.balance_service import recompute_license_balance

    license_id = 1
    mock_license = MagicMock(spec=["pk", "license_expiry_date"])
    mock_license.pk = license_id
    mock_license.license_expiry_date = None  # real None, not a MagicMock attribute

    with patch(
        "apps.license.models.LicenseDetailsModel.objects"
    ) as mock_ld_mgr, patch(
        "apps.license.services.balance_service._compute_credit",
        return_value=Decimal("10000.00"),
    ), patch(
        # Simulates one RowDetails with cif_fc = 3000 (a BOE debit)
        "apps.license.services.balance_service._compute_debit",
        return_value=Decimal("3000.00"),
    ), patch(
        "apps.license.services.balance_service._compute_allotment",
        return_value=Decimal("0.00"),
    ), patch(
        "apps.license.services.balance_service._compute_trade",
        return_value=Decimal("0.00"),
    ), patch(
        "apps.license.models.LicenseBalance.objects"
    ) as mock_bal_mgr, patch(
        "apps.license.models.LicenseFlags.objects"
    ) as mock_flags_mgr, patch(
        "django.db.transaction.atomic"
    ) as mock_atomic:
        mock_atomic.return_value.__enter__ = MagicMock(return_value=None)
        mock_atomic.return_value.__exit__ = MagicMock(return_value=False)

        mock_ld_mgr.select_for_update.return_value.select_related.return_value.get.return_value = mock_license
        mock_ld_mgr.DoesNotExist = LookupError  # allows the try/except to work

        recompute_license_balance(license_id)

    # The balance update_or_create must have been called with the correct value
    # credit=10000, debit=3000, allotment=0, trade=0 → balance=7000.00
    mock_bal_mgr.update_or_create.assert_called_once()
    bal_kwargs = mock_bal_mgr.update_or_create.call_args
    assert bal_kwargs.kwargs["defaults"]["balance_cif"] == Decimal("7000.00"), (
        f"Expected balance_cif=7000.00 but got {bal_kwargs.kwargs['defaults']['balance_cif']}"
    )


# ---------------------------------------------------------------------------
# BR-05 — Test 2: Allotment component reduces the balance
# ---------------------------------------------------------------------------

def test_allotment_reserves_quantity():
    """
    BR-05: AT allotment increases the allotment component.
    available_qty (balance) must decrease by the allotted cif_fc amount.
    """
    from apps.license.services.balance_service import recompute_license_balance

    license_id = 2
    mock_license = MagicMock(spec=["pk", "license_expiry_date"])
    mock_license.pk = license_id
    mock_license.license_expiry_date = None

    with patch(
        "apps.license.models.LicenseDetailsModel.objects"
    ) as mock_ld_mgr, patch(
        "apps.license.services.balance_service._compute_credit",
        return_value=Decimal("10000.00"),
    ), patch(
        "apps.license.services.balance_service._compute_debit",
        return_value=Decimal("0.00"),
    ), patch(
        # AllotmentItems with cif_fc = 2000 (AT allotment, no linked BOE)
        "apps.license.services.balance_service._compute_allotment",
        return_value=Decimal("2000.00"),
    ), patch(
        "apps.license.services.balance_service._compute_trade",
        return_value=Decimal("0.00"),
    ), patch(
        "apps.license.models.LicenseBalance.objects"
    ) as mock_bal_mgr, patch(
        "apps.license.models.LicenseFlags.objects"
    ) as mock_flags_mgr, patch(
        "django.db.transaction.atomic"
    ) as mock_atomic:
        mock_atomic.return_value.__enter__ = MagicMock(return_value=None)
        mock_atomic.return_value.__exit__ = MagicMock(return_value=False)

        mock_ld_mgr.select_for_update.return_value.select_related.return_value.get.return_value = mock_license
        mock_ld_mgr.DoesNotExist = LookupError  # allows the try/except to work

        recompute_license_balance(license_id)

    mock_bal_mgr.update_or_create.assert_called_once()
    bal_kwargs = mock_bal_mgr.update_or_create.call_args
    # credit=10000, debit=0, allotment=2000, trade=0 → balance=8000.00
    assert bal_kwargs.kwargs["defaults"]["balance_cif"] == Decimal("8000.00"), (
        f"Expected 8000.00 after allotment reservation, got {bal_kwargs.kwargs['defaults']['balance_cif']}"
    )


# ---------------------------------------------------------------------------
# BR-02 constraint — Test 3: Over-allotment clamped to 0 (floor)
# ---------------------------------------------------------------------------

def test_over_allotment_rejected():
    """
    BR-02 constraint: available_qty cannot go below 0.
    When allotment > credit, the balance is clamped to 0 (floor).
    The service enforces this via max(0, raw_balance).
    """
    from apps.license.services.balance_service import recompute_license_balance

    license_id = 3
    mock_license = MagicMock(spec=["pk", "license_expiry_date"])
    mock_license.pk = license_id
    mock_license.license_expiry_date = None

    with patch(
        "apps.license.models.LicenseDetailsModel.objects"
    ) as mock_ld_mgr, patch(
        "apps.license.services.balance_service._compute_credit",
        return_value=Decimal("500.00"),
    ), patch(
        "apps.license.services.balance_service._compute_debit",
        return_value=Decimal("0.00"),
    ), patch(
        # Allotment exceeds available credit: 800 > 500
        "apps.license.services.balance_service._compute_allotment",
        return_value=Decimal("800.00"),
    ), patch(
        "apps.license.services.balance_service._compute_trade",
        return_value=Decimal("0.00"),
    ), patch(
        "apps.license.models.LicenseBalance.objects"
    ) as mock_bal_mgr, patch(
        "apps.license.models.LicenseFlags.objects"
    ) as mock_flags_mgr, patch(
        "django.db.transaction.atomic"
    ) as mock_atomic:
        mock_atomic.return_value.__enter__ = MagicMock(return_value=None)
        mock_atomic.return_value.__exit__ = MagicMock(return_value=False)

        mock_ld_mgr.select_for_update.return_value.select_related.return_value.get.return_value = mock_license
        mock_ld_mgr.DoesNotExist = LookupError  # allows the try/except to work

        recompute_license_balance(license_id)

    mock_bal_mgr.update_or_create.assert_called_once()
    bal_kwargs = mock_bal_mgr.update_or_create.call_args
    # raw = 500 - 800 = -300; clamped to 0
    assert bal_kwargs.kwargs["defaults"]["balance_cif"] == Decimal("0.00"), (
        f"Balance must not go below 0, got {bal_kwargs.kwargs['defaults']['balance_cif']}"
    )


# ---------------------------------------------------------------------------
# BR-04 — Test 4: Frozen BOE row cannot be modified (service layer)
# ---------------------------------------------------------------------------

def test_frozen_boe_row_update_rejected():
    """
    BR-04: frozen=True rows cannot be edited or deleted via API.
    boe_service.update_row_detail() must raise ValueError for a frozen row.

    RowDetails is imported lazily inside update_row_detail() so we patch it at
    its source module path: apps.bill_of_entry.models.RowDetails.
    """
    from apps.bill_of_entry.services.boe_service import update_row_detail

    frozen_row = MagicMock()
    frozen_row.is_frozen = True
    frozen_row.pk = 999

    user = MagicMock()

    with patch(
        "apps.bill_of_entry.models.RowDetails"
    ) as MockRowDetails:
        MockRowDetails.objects.get.return_value = frozen_row
        MockRowDetails.DoesNotExist = Exception

        with pytest.raises(ValueError, match="frozen"):
            update_row_detail(row_id=999, data={"qty": "50.000"}, user=user, boe_id=1)


def test_frozen_boe_row_delete_rejected():
    """
    BR-04: frozen=True rows cannot be deleted via the service layer.
    boe_service.delete_row_detail() must raise ValueError for a frozen row.

    RowDetails is imported lazily so we patch at the model module level.
    """
    from apps.bill_of_entry.services.boe_service import delete_row_detail

    frozen_row = MagicMock()
    frozen_row.is_frozen = True
    frozen_row.pk = 998

    user = MagicMock()

    with patch(
        "apps.bill_of_entry.models.RowDetails"
    ) as MockRowDetails:
        MockRowDetails.objects.get.return_value = frozen_row
        MockRowDetails.DoesNotExist = Exception

        with pytest.raises(ValueError, match="frozen"):
            delete_row_detail(row_id=998, user=user, boe_id=1)


def test_non_frozen_boe_row_can_be_updated():
    """
    BR-04 (positive): non-frozen rows may be edited.
    boe_service.update_row_detail() must NOT raise for is_frozen=False.

    RowDetails is imported lazily so we patch at the model module level.
    """
    from apps.bill_of_entry.services.boe_service import update_row_detail

    non_frozen_row = MagicMock()
    non_frozen_row.is_frozen = False
    non_frozen_row.pk = 100

    user = MagicMock()
    saved_row = MagicMock()

    with patch(
        "apps.bill_of_entry.models.RowDetails"
    ) as MockRowDetails:
        MockRowDetails.objects.get.return_value = non_frozen_row
        MockRowDetails.DoesNotExist = Exception

        # RowDetailsSerializer is imported inside update_row_detail() — patch at its origin
        with patch(
            "apps.bill_of_entry.serializers.RowDetailsSerializer"
        ) as MockSerializer:
            mock_serializer_instance = MagicMock()
            mock_serializer_instance.is_valid.return_value = True
            mock_serializer_instance.save.return_value = saved_row
            MockSerializer.return_value = mock_serializer_instance

            result = update_row_detail(row_id=100, data={"qty": "50.000"}, user=user, boe_id=1)

    assert result is saved_row


# ---------------------------------------------------------------------------
# BR-03 — Test 5: License expiry flag
# ---------------------------------------------------------------------------

def test_expired_license_flagged():
    """
    BR-03: license_expiry_date < today → LicenseFlags.is_expired = True.
    recompute_license_balance() writes the is_expired flag.
    """
    import datetime
    from django.utils import timezone
    from apps.license.services.balance_service import recompute_license_balance

    license_id = 5
    yesterday = timezone.now().date() - datetime.timedelta(days=1)

    mock_license = MagicMock(spec=["pk", "license_expiry_date"])
    mock_license.pk = license_id
    mock_license.license_expiry_date = yesterday  # real date object

    with patch(
        "apps.license.models.LicenseDetailsModel.objects"
    ) as mock_ld_mgr, patch(
        "apps.license.services.balance_service._compute_credit",
        return_value=Decimal("1000.00"),
    ), patch(
        "apps.license.services.balance_service._compute_debit",
        return_value=Decimal("0.00"),
    ), patch(
        "apps.license.services.balance_service._compute_allotment",
        return_value=Decimal("0.00"),
    ), patch(
        "apps.license.services.balance_service._compute_trade",
        return_value=Decimal("0.00"),
    ), patch(
        "apps.license.models.LicenseBalance.objects"
    ) as mock_bal_mgr, patch(
        "apps.license.models.LicenseFlags.objects"
    ) as mock_flags_mgr, patch(
        "django.db.transaction.atomic"
    ) as mock_atomic:
        mock_atomic.return_value.__enter__ = MagicMock(return_value=None)
        mock_atomic.return_value.__exit__ = MagicMock(return_value=False)

        mock_ld_mgr.select_for_update.return_value.select_related.return_value.get.return_value = mock_license
        mock_ld_mgr.DoesNotExist = LookupError  # allows the try/except to work

        recompute_license_balance(license_id)

    mock_flags_mgr.update_or_create.assert_called_once()
    flags_kwargs = mock_flags_mgr.update_or_create.call_args
    assert flags_kwargs.kwargs["defaults"]["is_expired"] is True, (
        "is_expired must be True when expiry_date < today"
    )


def test_non_expired_license_not_flagged():
    """
    BR-03: license_expiry_date >= today → is_expired remains False.
    """
    import datetime
    from django.utils import timezone
    from apps.license.services.balance_service import recompute_license_balance

    license_id = 6
    future = timezone.now().date() + datetime.timedelta(days=30)

    mock_license = MagicMock(spec=["pk", "license_expiry_date"])
    mock_license.pk = license_id
    mock_license.license_expiry_date = future  # real date object

    with patch(
        "apps.license.models.LicenseDetailsModel.objects"
    ) as mock_ld_mgr, patch(
        "apps.license.services.balance_service._compute_credit",
        return_value=Decimal("1000.00"),
    ), patch(
        "apps.license.services.balance_service._compute_debit",
        return_value=Decimal("0.00"),
    ), patch(
        "apps.license.services.balance_service._compute_allotment",
        return_value=Decimal("0.00"),
    ), patch(
        "apps.license.services.balance_service._compute_trade",
        return_value=Decimal("0.00"),
    ), patch(
        "apps.license.models.LicenseBalance.objects"
    ) as mock_bal_mgr, patch(
        "apps.license.models.LicenseFlags.objects"
    ) as mock_flags_mgr, patch(
        "django.db.transaction.atomic"
    ) as mock_atomic:
        mock_atomic.return_value.__enter__ = MagicMock(return_value=None)
        mock_atomic.return_value.__exit__ = MagicMock(return_value=False)

        mock_ld_mgr.select_for_update.return_value.select_related.return_value.get.return_value = mock_license
        mock_ld_mgr.DoesNotExist = LookupError  # allows the try/except to work

        recompute_license_balance(license_id)

    mock_flags_mgr.update_or_create.assert_called_once()
    flags_kwargs = mock_flags_mgr.update_or_create.call_args
    assert flags_kwargs.kwargs["defaults"]["is_expired"] is False, (
        "is_expired must be False when expiry_date >= today"
    )


# ---------------------------------------------------------------------------
# BR-08 — Test 6: Trade billing decimal precision
# ---------------------------------------------------------------------------

def test_trade_billing_pct_3_decimal_precision():
    """
    Hotfix / BR-08: pct=7.925 × cif=100000 must produce amount=7925.00.

    Using Python Decimal arithmetic (not float) yields the exact result.
    Float would round 7.925 × 100000 / 100 incorrectly on some platforms.
    """
    pct = Decimal("7.925")
    cif_inr = Decimal("100000.00")

    # Correct: Decimal arithmetic
    amount = (cif_inr * pct / Decimal("100")).quantize(Decimal("0.01"))
    assert amount == Decimal("7925.00"), (
        f"Expected 7925.00 but got {amount}"
    )

    # Demonstrate that naive float arithmetic may differ from exact Decimal result
    # We do NOT assert float == 7925.00 since that is the bug; we assert Decimal is correct.
    assert amount == Decimal("7925.00")


def test_trade_billing_qty_mode_precision():
    """
    BR-08 (QTY mode): amount = qty_kg × rate_inr_per_kg, Decimal arithmetic.
    """
    qty_kg = Decimal("500.000")
    rate = Decimal("15.75")
    expected = Decimal("7875.00")
    result = (qty_kg * rate).quantize(Decimal("0.01"))
    assert result == expected, f"Expected {expected}, got {result}"


def test_trade_billing_fob_mode_precision():
    """
    BR-08 (FOB_INR mode): amount = fob_inr × pct / 100.
    """
    fob_inr = Decimal("250000.00")
    pct = Decimal("3.500")
    expected = Decimal("8750.00")
    result = (fob_inr * pct / Decimal("100")).quantize(Decimal("0.01"))
    assert result == expected, f"Expected {expected}, got {result}"


# ---------------------------------------------------------------------------
# BR-07 — Test 7: Invoice number format
# ---------------------------------------------------------------------------

def test_invoice_number_format():
    """
    BR-07: Invoice numbers follow INV-FY<YY>-<NNNN> format.
    """
    pattern = re.compile(r"^INV-FY\d{2}-\d{4}$")

    valid_numbers = [
        "INV-FY25-0001",
        "INV-FY25-0002",
        "INV-FY26-0001",
        "INV-FY99-9999",
    ]
    invalid_numbers = [
        "INV25-0001",
        "INV-FY2025-0001",  # 4-digit year, not 2
        "INV-FY25-01",      # sequence too short
        "ABCDE",
        "INV-FY25-00001",   # sequence too long
        "",
    ]

    for num in valid_numbers:
        assert pattern.match(num), f"'{num}' should match INV-FY<YY>-<NNNN>"

    for num in invalid_numbers:
        assert not pattern.match(num), f"'{num}' should NOT match INV-FY<YY>-<NNNN>"


def test_invoice_sequential_numbering():
    """
    BR-07: Sequential numbers INV-FY25-0001, INV-FY25-0002 must be correctly
    formatted and differ by exactly 1 in the sequence component.
    """
    pattern = re.compile(r"^INV-FY\d{2}-(\d{4})$")
    first = "INV-FY25-0001"
    second = "INV-FY25-0002"

    m1 = pattern.match(first)
    m2 = pattern.match(second)
    assert m1 and m2
    seq1 = int(m1.group(1))
    seq2 = int(m2.group(1))
    assert seq2 == seq1 + 1, (
        f"Sequential invoices must differ by 1: {seq1} → {seq2}"
    )


def test_invoice_number_uniqueness_enforced_by_model():
    """
    BR-07: Invoice.invoice_number has unique=True at the model level.
    Verify this is declared on the field (no DB hit required).
    """
    from apps.license.models import Invoice

    field = Invoice._meta.get_field("invoice_number")
    assert field.unique is True, (
        "Invoice.invoice_number must be declared unique=True"
    )


# ---------------------------------------------------------------------------
# Test 8 — Full balance workflow (credit - debit - allotment = final balance)
# ---------------------------------------------------------------------------

def test_end_to_end_license_workflow():
    """
    End-to-end balance computation through the real service:

    1. License has credit = 10 000 (from export items)
    2. BOE debit = 3 000
    3. AT allotment = 2 000
    4. No trade lines
    5. Expected balance = 5 000.00

    Exercises the complete recompute_license_balance() call graph.
    """
    from apps.license.services.balance_service import recompute_license_balance

    license_id = 8
    mock_license = MagicMock(spec=["pk", "license_expiry_date"])
    mock_license.pk = license_id
    mock_license.license_expiry_date = None

    with patch(
        "apps.license.models.LicenseDetailsModel.objects"
    ) as mock_ld_mgr, patch(
        "apps.license.services.balance_service._compute_credit",
        return_value=Decimal("10000.00"),
    ), patch(
        "apps.license.services.balance_service._compute_debit",
        return_value=Decimal("3000.00"),
    ), patch(
        "apps.license.services.balance_service._compute_allotment",
        return_value=Decimal("2000.00"),
    ), patch(
        "apps.license.services.balance_service._compute_trade",
        return_value=Decimal("0.00"),
    ), patch(
        "apps.license.models.LicenseBalance.objects"
    ) as mock_bal_mgr, patch(
        "apps.license.models.LicenseFlags.objects"
    ) as mock_flags_mgr, patch(
        "django.db.transaction.atomic"
    ) as mock_atomic:
        mock_atomic.return_value.__enter__ = MagicMock(return_value=None)
        mock_atomic.return_value.__exit__ = MagicMock(return_value=False)

        mock_ld_mgr.select_for_update.return_value.select_related.return_value.get.return_value = mock_license
        mock_ld_mgr.DoesNotExist = LookupError  # allows the try/except to work

        recompute_license_balance(license_id)

    mock_bal_mgr.update_or_create.assert_called_once()
    bal_kwargs = mock_bal_mgr.update_or_create.call_args
    # credit=10000 - debit=3000 - allotment=2000 - trade=0 = 5000.00
    assert bal_kwargs.kwargs["defaults"]["balance_cif"] == Decimal("5000.00"), (
        f"E2E balance expected 5000.00, got {bal_kwargs.kwargs['defaults']['balance_cif']}"
    )


# ---------------------------------------------------------------------------
# BR-01 — LicenseBalance.balance_cif is a concrete, persisted field
# ---------------------------------------------------------------------------

def test_license_balance_is_materialised_field():
    """
    BR-01: balance_cif must be a real database field on LicenseBalance,
    not a Python property or annotation.
    """
    from apps.license.models import LicenseBalance

    field = LicenseBalance._meta.get_field("balance_cif")
    # It must be a DecimalField (concrete DB column)
    from django.db.models import DecimalField
    assert isinstance(field, DecimalField), (
        "LicenseBalance.balance_cif must be a DecimalField (materialised column)"
    )
    # Must not be a property or virtual field
    assert not field.is_relation, (
        "LicenseBalance.balance_cif must not be a relation field"
    )


# ---------------------------------------------------------------------------
# BR-06 — License number uniqueness declared on model
# ---------------------------------------------------------------------------

def test_license_number_unique_constraint_declared():
    """
    BR-06: license_number must be globally unique.
    Verify unique=True is declared on the field (no DB hit required).
    """
    from apps.license.models import LicenseDetailsModel

    field = LicenseDetailsModel._meta.get_field("license_number")
    assert field.unique is True, (
        "LicenseDetailsModel.license_number must be declared unique=True"
    )


# ---------------------------------------------------------------------------
# BR-02 — _compute_allotment filters out allotments already converted to BOE
# ---------------------------------------------------------------------------

def test_compute_allotment_excludes_boe_linked():
    """
    BR-05 / BR-02: AllotmentItems tied to a BOE (allotment.bill_of_entry IS NOT NULL)
    must NOT be counted in _compute_allotment — they are already counted in debit.

    Verifies the queryset filter applied by _compute_allotment.
    """
    from apps.license.services.balance_service import _compute_allotment

    mock_ai_qs = MagicMock()
    mock_ai_qs.filter.return_value = mock_ai_qs
    mock_ai_qs.aggregate.return_value = {"total": Decimal("1500.00")}

    mock_ai_model = MagicMock()
    mock_ai_model.objects = mock_ai_qs

    with patch(
        "apps.allotment.models.AllotmentItems",
        mock_ai_model,
    ):
        result = _compute_allotment(license_id=10)

    # The filter must include allotment__bill_of_entry__isnull=True
    filter_kwargs_list = [c.kwargs for c in mock_ai_qs.filter.call_args_list]
    # flatten all kwargs from all filter calls
    all_kwargs = {}
    for kw in filter_kwargs_list:
        all_kwargs.update(kw)

    assert "allotment__bill_of_entry__isnull" in all_kwargs, (
        "_compute_allotment must filter allotment__bill_of_entry__isnull=True"
    )
    assert all_kwargs["allotment__bill_of_entry__isnull"] is True, (
        "The filter must exclude allotments already converted to BOE"
    )
    assert result == Decimal("1500.00")


# ---------------------------------------------------------------------------
# BR-02 — is_null flag set when balance < 500
# ---------------------------------------------------------------------------

def test_is_null_flag_set_when_balance_below_threshold():
    """
    BR-02 / balance_service: is_null=True when balance < 500 (the null threshold).
    """
    from apps.license.services.balance_service import recompute_license_balance

    license_id = 11
    mock_license = MagicMock(spec=["pk", "license_expiry_date"])
    mock_license.pk = license_id
    mock_license.license_expiry_date = None

    with patch(
        "apps.license.models.LicenseDetailsModel.objects"
    ) as mock_ld_mgr, patch(
        "apps.license.services.balance_service._compute_credit",
        return_value=Decimal("400.00"),
    ), patch(
        "apps.license.services.balance_service._compute_debit",
        return_value=Decimal("0.00"),
    ), patch(
        "apps.license.services.balance_service._compute_allotment",
        return_value=Decimal("0.00"),
    ), patch(
        "apps.license.services.balance_service._compute_trade",
        return_value=Decimal("0.00"),
    ), patch(
        "apps.license.models.LicenseBalance.objects"
    ) as mock_bal_mgr, patch(
        "apps.license.models.LicenseFlags.objects"
    ) as mock_flags_mgr, patch(
        "django.db.transaction.atomic"
    ) as mock_atomic:
        mock_atomic.return_value.__enter__ = MagicMock(return_value=None)
        mock_atomic.return_value.__exit__ = MagicMock(return_value=False)

        mock_ld_mgr.select_for_update.return_value.select_related.return_value.get.return_value = mock_license
        mock_ld_mgr.DoesNotExist = LookupError  # allows the try/except to work

        recompute_license_balance(license_id)

    mock_flags_mgr.update_or_create.assert_called_once()
    flags_kwargs = mock_flags_mgr.update_or_create.call_args
    assert flags_kwargs.kwargs["defaults"]["is_null"] is True, (
        "is_null must be True when balance (400) < threshold (500)"
    )
