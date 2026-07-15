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
_THREE_PLACES = Decimal("0.001")
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

    from apps.allotment.models import AllotmentItems, AllotmentModel
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
                allotment__type=AllotmentModel.TYPE_AT,
            )
            .values("item_id")
            .annotate(
                qty_sum=Coalesce(Sum("qty"), _DEC_0),
                val_sum=Coalesce(Sum("cif_fc"), _DEC_0),
            )
        )
    }

    # ── Compute and collect changed items ─────────────────────────────────────
    to_update = []
    for item in items:
        deb_qty, deb_val = debit_map.get(item.pk, (_DEC_0, _DEC_0))
        allt_qty, allt_val = allot_map.get(item.pk, (_DEC_0, _DEC_0))

        total_qty = item.quantity or _DEC_0
        avail_qty = (total_qty - deb_qty - allt_qty).quantize(_THREE_PLACES, rounding=ROUND_DOWN)
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


def _handle_negative_balance_notification(license_id: int, balance: Decimal) -> None:
    """
    Create or update LicenseBalanceNotification for negative balance (BD-003).

    Rules:
    - If balance < 0 and no ACTIVE notification: create one.
    - If balance < 0 and ACTIVE notification exists: update balance_cif.
    - If balance >= 0: do NOT touch existing notifications
      (resolution is a deliberate business action, not automatic).

    Called inside transaction.atomic() — safe to write here.
    """
    if balance >= _DEC_0:
        return  # Balance is healthy — notifications managed by business process

    try:
        from apps.notifications.models import LicenseBalanceNotification
    except ImportError:
        logger.warning("notifications app not available — skipping notification")
        return

    existing = LicenseBalanceNotification.objects.filter(
        license_id=license_id,
        status=LicenseBalanceNotification.STATUS_ACTIVE,
    ).first()

    if existing:
        # Update the existing active notification with the latest balance
        existing.balance_cif = balance
        existing.save(update_fields=["balance_cif", "updated_at"])
        logger.info(
            "Updated negative balance notification for license %s: balance=%s",
            license_id, balance,
        )
    else:
        # Create new notification
        LicenseBalanceNotification.objects.create(
            license_id=license_id,
            status=LicenseBalanceNotification.STATUS_ACTIVE,
            balance_cif=balance,
        )
        logger.warning(
            "NEGATIVE BALANCE: License %s has balance=%s — notification created",
            license_id, balance,
        )


def group_import_items_by_name(license_id: int) -> list[dict]:
    """
    Group LicenseImportItemsModel rows by ItemNameModel for analytical views.

    BD-002: Raw rows are NEVER merged. This returns a computed view only.
    Used for: Planning, Reports, Dashboard analytics.
    NOT used for: Allotment, BOE, Ledger, Audit (those use raw SR rows).

    Grouping key: ItemNameModel.id (canonical, unique=True in the system).
    Fallback: item.description (free text, only when no ItemNameModel linked).

    Returns list of dicts sorted by item name:
    [{
        'item_name_id': int | str,    # ItemNameModel.id or 'desc:{description}'
        'item_name': str,             # display name
        'total_quantity': Decimal,    # SUM of quantity across all SR rows
        'available_quantity': Decimal, # SUM of available_quantity
        'debited_quantity': Decimal,  # SUM of debited_quantity
        'allotted_quantity': Decimal, # SUM of allotted_quantity
        'sr_numbers': list[int],      # original SR numbers (traceability)
        'row_ids': list[int],         # original row PKs
    }]
    """
    from collections import defaultdict

    from apps.license.models import LicenseImportItemsModel

    items = (
        LicenseImportItemsModel.objects
        .filter(license_id=license_id)
        .prefetch_related("items")  # ItemNameModel M2M
    )

    groups: dict = defaultdict(lambda: {
        "total_quantity": _DEC_0,
        "available_quantity": _DEC_0,
        "debited_quantity": _DEC_0,
        "allotted_quantity": _DEC_0,
        "sr_numbers": [],
        "row_ids": [],
    })

    for item in items:
        item_names = list(item.items.all())
        if item_names:
            # Use the first linked ItemNameModel as grouping key
            canonical = item_names[0]
            key_id: int | str = canonical.id
            key_name = canonical.name
        else:
            # No ItemNameModel linked — group by description as fallback
            key_id = f"desc:{item.description or item.serial_number}"
            key_name = item.description or f"SR-{item.serial_number}"

        g = groups[(key_id, key_name)]
        g["total_quantity"] += item.quantity or _DEC_0
        g["available_quantity"] += item.available_quantity or _DEC_0
        g["debited_quantity"] += item.debited_quantity or _DEC_0
        g["allotted_quantity"] += item.allotted_quantity or _DEC_0
        g["sr_numbers"].append(int(item.serial_number))
        g["row_ids"].append(item.pk)

    return [
        {"item_name_id": k[0], "item_name": k[1], **v}
        for k, v in sorted(groups.items(), key=lambda x: str(x[0][1]).lower())
    ]


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
        balance: Decimal = raw_balance.quantize(_TWO_PLACES, rounding=ROUND_DOWN)

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
        # BD-003: is_null only covers the [0, threshold) range; negative handled by notifications
        is_null = _DEC_0 <= balance < _NULL_THRESHOLD  # only meaningful when >= 0
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

        # BD-003: Handle negative balance notification
        _handle_negative_balance_notification(license_id, balance)

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
