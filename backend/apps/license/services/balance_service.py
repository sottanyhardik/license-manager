# license/services/balance_service.py
"""
Balance recomputation service.

The canonical formula (replicated from legacy balance_calculator.py):

    balance = max(0, credit - debit - allotment - trade)

Where:
  credit     = SUM(LicenseExportItemModel.cif_fc)
  debit      = SUM(RowDetails.cif_fc WHERE transaction_type=DEBIT AND bill_of_entry.license_trades IS NULL)
  allotment  = SUM(AllotmentItems.cif_fc WHERE allotment.bill_of_entry IS NULL)
  trade      = SUM(LicenseTradeLine.cif_fc WHERE trade.direction='SALE')

Result is quantized to 2 decimal places.

Cross-app models (RowDetails, AllotmentItems, LicenseTradeLine) are imported
lazily via django.apps.apps.get_model() so this module stays importable even
when those apps haven't been installed yet.
"""
import logging
from decimal import ROUND_DOWN, Decimal
from typing import Optional

from django.db import transaction
from django.utils import timezone

from apps.license.models import LicenseBalance, LicenseDetailsModel, LicenseFlags

logger = logging.getLogger(__name__)

_TWO_PLACES = Decimal("0.01")
_DEC_0 = Decimal("0")
_NULL_THRESHOLD = Decimal("500")


def _safe_get_model(app_label: str, model_name: str):
    """
    Return the Django model class or None if the app/model is not yet
    installed.  Avoids ImportError during Phase 3 when allotment/trade/boe
    apps are absent.
    """
    from django.apps import apps as django_apps

    try:
        return django_apps.get_model(app_label, model_name)
    except LookupError:
        logger.debug(
            "Model %s.%s not installed — skipping in balance calculation.",
            app_label,
            model_name,
        )
        return None


def _compute_credit(license_id: int) -> Decimal:
    """Sum of all export item CIF FC values."""
    from apps.license.models import LicenseExportItemModel

    result = (
        LicenseExportItemModel.objects.filter(license_id=license_id)
        .aggregate(total=_sum_decimal("cif_fc"))["total"]
    )
    return result or _DEC_0


def _compute_debit(license_id: int) -> Decimal:
    """
    Sum of RowDetails.cif_fc where:
      - transaction_type = 'DEBIT'
      - bill_of_entry.license_trades IS NULL  (i.e. not tied to a trade)

    Path: RowDetails → sr_number (LicenseImportItemsModel) → license_id
    """
    RowDetails = _safe_get_model("bill_of_entry", "RowDetails")
    if RowDetails is None:
        return _DEC_0

    result = (
        RowDetails.objects.filter(
            sr_number__license_id=license_id,
            transaction_type="DEBIT",
            bill_of_entry__license_trades__isnull=True,
        )
        .aggregate(total=_sum_decimal("cif_fc"))["total"]
    )
    return result or _DEC_0


def _compute_allotment(license_id: int) -> Decimal:
    """
    Sum of AllotmentItems.cif_fc where allotment.bill_of_entry IS NULL
    (pending allotments not yet converted to BOE).

    Path: AllotmentItems → item (LicenseImportItemsModel) → license_id
    """
    AllotmentItems = _safe_get_model("allotment", "AllotmentItems")
    if AllotmentItems is None:
        return _DEC_0

    result = (
        AllotmentItems.objects.filter(
            item__license_id=license_id,
            allotment__bill_of_entry__isnull=True,
        )
        .aggregate(total=_sum_decimal("cif_fc"))["total"]
    )
    return result or _DEC_0


def _compute_trade(license_id: int) -> Decimal:
    """
    Sum of LicenseTradeLine.cif_fc where trade.direction = 'SALE'.

    Path: LicenseTradeLine → sr_number (LicenseImportItemsModel) → license_id
    """
    LicenseTradeLine = _safe_get_model("trade", "LicenseTradeLine")
    if LicenseTradeLine is None:
        return _DEC_0

    result = (
        LicenseTradeLine.objects.filter(
            sr_number__license_id=license_id,
            trade__direction="SALE",
        )
        .aggregate(total=_sum_decimal("cif_fc"))["total"]
    )
    return result or _DEC_0


def _sum_decimal(field: str):
    """Helper — returns a Sum() expression using the given field name."""
    from django.db.models import Sum

    return Sum(field)


def recompute_license_balance(license_id: int) -> None:
    """
    Recompute and persist the CIF balance for *license_id*.

    Also updates:
      - LicenseFlags.is_null  (True when balance < 500)
      - LicenseFlags.is_expired  (True when expiry_date < today)

    Returns silently if the license no longer exists (deleted between task
    dispatch and execution).  Wrapped in a single atomic transaction.
    """
    with transaction.atomic():
        # H2: Lock the license row to prevent concurrent recomputes from racing.
        try:
            license_obj: LicenseDetailsModel = (
                LicenseDetailsModel.objects
                .select_for_update()
                .select_related("balance", "flags")
                .get(pk=license_id)
            )
        except LicenseDetailsModel.DoesNotExist:
            logger.warning(
                "License %s not found — skipping balance recompute (deleted between dispatch and execution).",
                license_id,
            )
            return

        credit = _compute_credit(license_id)
        debit = _compute_debit(license_id)
        allotment = _compute_allotment(license_id)
        trade = _compute_trade(license_id)

        raw_balance: Decimal = credit - debit - allotment - trade
        balance: Decimal = max(_DEC_0, raw_balance).quantize(_TWO_PLACES, rounding=ROUND_DOWN)

        # B4: use update_or_create so the row is created when it doesn't exist yet.
        LicenseBalance.objects.update_or_create(
            license_id=license_id,
            defaults={
                "balance_cif": balance,
                "ledger_date": timezone.now().date(),
            },
        )

        # B4: same for LicenseFlags — filter().update() is a no-op on a missing row.
        today = timezone.now().date()
        is_null = balance < _NULL_THRESHOLD
        is_expired = (
            license_obj.license_expiry_date is not None
            and license_obj.license_expiry_date < today
        )
        LicenseFlags.objects.update_or_create(
            license_id=license_id,
            defaults={
                "is_null": is_null,
                "is_expired": is_expired,
            },
        )

        logger.info(
            "Balance recomputed for license %s: credit=%s debit=%s allotment=%s trade=%s => %s",
            license_id,
            credit,
            debit,
            allotment,
            trade,
            balance,
        )
