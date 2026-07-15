# license/services/balance_service.py
"""
Balance recomputation service.

The canonical formula (replicated from legacy balance_calculator.py):

    balance = max(0, credit - debit - allotment - trade)

Where:
  credit     = SUM(LicenseExportItemModel.cif_fc)
  debit      = SUM(RowDetails.cif_fc WHERE transaction_type='D' AND bill_of_entry.license_trades IS NULL)
  allotment  = SUM(AllotmentItems.cif_fc WHERE allotment.bill_of_entry IS NULL)
  trade      = SUM(LicenseTradeLine.cif_fc WHERE trade.direction='SALE')

Result is quantized to 2 decimal places.

Cross-app models (RowDetails, AllotmentItems, LicenseTradeLine) are imported
lazily inside each _compute_* function to avoid circular imports at module
load time.  All three apps are required to be installed in production.
"""
import logging
from decimal import ROUND_DOWN, Decimal

from django.db import transaction
from django.utils import timezone

from apps.license.models import LicenseBalance, LicenseDetailsModel, LicenseFlags

logger = logging.getLogger(__name__)

_TWO_PLACES = Decimal("0.01")
_DEC_0 = Decimal("0")
_NULL_THRESHOLD = Decimal("500")


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
      - transaction_type = 'D'
      - bill_of_entry.license_trades IS NULL  (i.e. not tied to a trade)

    Path: RowDetails → sr_number (LicenseImportItemsModel) → license_id
    """
    from apps.bill_of_entry.models import TRANSACTION_TYPE_DEBIT, RowDetails

    result = (
        RowDetails.objects.filter(
            sr_number__license_id=license_id,
            transaction_type=TRANSACTION_TYPE_DEBIT,
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
    from apps.allotment.models import AllotmentItems

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
    from apps.trade.models import LicenseTradeLine

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


def _update_item_level_balances(license_id: int) -> None:
    """
    Update per-item balance fields for every LicenseImportItemsModel row
    belonging to *license_id*.

    Fields updated (mirrors legacy calculate_balance.update_balance_values):
      debited_quantity  — SUM(RowDetails.qty WHERE transaction_type='D')
      debited_value     — SUM(RowDetails.cif_fc WHERE transaction_type='D')
      allotted_quantity — SUM(AllotmentItems.qty  WHERE allotment has no BOE AND type=AT)
      allotted_value    — SUM(AllotmentItems.cif_fc WHERE same)
      available_quantity— max(0, quantity − debited_quantity − allotted_quantity)

    Must be called inside an existing transaction.atomic() block.
    Uses select_for_update() on items to prevent concurrent write races.
    Uses bulk_update() — one UPDATE per changed item, not N UPDATEs.
    """
    from django.db.models import Sum
    from django.db.models.functions import Coalesce

    from apps.allotment.models import AllotmentItems
    from apps.bill_of_entry.models import TRANSACTION_TYPE_DEBIT, RowDetails
    from apps.license.models import LicenseImportItemsModel

    items = list(
        LicenseImportItemsModel.objects
        .select_for_update()
        .filter(license_id=license_id)
    )
    if not items:
        return

    item_ids = [item.pk for item in items]

    # ── Debit aggregation ────────────────────────────────────────────────────
    debit_map: dict[int, tuple] = {
        row["sr_number_id"]: (row["qty_sum"], row["val_sum"])
        for row in (
            RowDetails.objects
            .filter(sr_number_id__in=item_ids, transaction_type=TRANSACTION_TYPE_DEBIT)
            .values("sr_number_id")
            .annotate(
                qty_sum=Coalesce(Sum("qty"), _DEC_0),
                val_sum=Coalesce(Sum("cif_fc"), _DEC_0),
            )
        )
    }

    # ── Allotment aggregation (pending only — no BOE linked, type=AT) ────────
    allot_map: dict[int, tuple] = {
        row["item_id"]: (row["qty_sum"], row["val_sum"])
        for row in (
            AllotmentItems.objects
            .filter(
                item_id__in=item_ids,
                allotment__bill_of_entry__isnull=True,
                allotment__type="AT",
            )
            .values("item_id")
            .annotate(
                qty_sum=Coalesce(Sum("qty"), _DEC_0),
                val_sum=Coalesce(Sum("cif_fc"), _DEC_0),
            )
        )
    }

    # ── Compute and collect changed items ─────────────────────────────────────
    _THREE_PLACES = Decimal("0.001")
    to_update = []
    for item in items:
        deb_qty, deb_val = debit_map.get(item.pk, (_DEC_0, _DEC_0))
        allt_qty, allt_val = allot_map.get(item.pk, (_DEC_0, _DEC_0))

        total_qty = item.quantity or _DEC_0
        avail_qty = max(_DEC_0, total_qty - deb_qty - allt_qty).quantize(
            _THREE_PLACES, rounding=ROUND_DOWN
        )
        deb_qty = deb_qty.quantize(_THREE_PLACES, rounding=ROUND_DOWN)
        allt_qty = allt_qty.quantize(_THREE_PLACES, rounding=ROUND_DOWN)
        deb_val = deb_val.quantize(_TWO_PLACES, rounding=ROUND_DOWN)
        allt_val = allt_val.quantize(_TWO_PLACES, rounding=ROUND_DOWN)

        if (
            item.debited_quantity != deb_qty
            or item.debited_value != deb_val
            or item.allotted_quantity != allt_qty
            or item.allotted_value != allt_val
            or item.available_quantity != avail_qty
        ):
            item.debited_quantity = deb_qty
            item.debited_value = deb_val
            item.allotted_quantity = allt_qty
            item.allotted_value = allt_val
            item.available_quantity = avail_qty
            to_update.append(item)

    if to_update:
        LicenseImportItemsModel.objects.bulk_update(
            to_update,
            [
                "debited_quantity",
                "debited_value",
                "allotted_quantity",
                "allotted_value",
                "available_quantity",
            ],
        )
        logger.info(
            "Item-level balances updated for license %s: %d item(s) changed",
            license_id,
            len(to_update),
        )


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

        # Update per-item balance fields (available_quantity, debited_quantity, etc.)
        # inside the same atomic transaction so item and license values are always consistent.
        _update_item_level_balances(license_id)
