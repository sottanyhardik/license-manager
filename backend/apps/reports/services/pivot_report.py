# reports/services/pivot_report.py
"""
Pivot report service: items grouped by SION norm class.

Queries LicenseImportItemsModel (via the export item's norm_class FK) and
groups results by SionNormClassModel.  Accepts the same filters as
item_report plus an optional sion_norm string filter.

Models are imported inside the function to prevent circular import errors
during app startup.
"""
import logging
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

logger = logging.getLogger(__name__)

_DEC_0 = Decimal("0")


def generate_pivot_report(
    item_name_ids: Optional[list] = None,
    company_ids: Optional[list] = None,
    min_balance: Optional[Decimal] = None,
    license_status: str = "active",
    expiry_date_from: Optional[str] = None,
    expiry_date_to: Optional[str] = None,
    sion_norm: Optional[str] = None,
) -> dict:
    """
    Build pivot report: import items grouped by SION norm class.

    The pivot is achieved by pulling LicenseExportItemModel (which carries
    norm_class) and cross-referencing with LicenseImportItemsModel on the
    same license.

    Returns dict with key 'norm_classes', each entry being:
      { norm_class: str, items: [ ... same shape as item_report ... ] }
    """
    from apps.license.models import (
        LicenseExportItemModel,
        LicenseImportItemsModel,
    )

    if min_balance is None:
        min_balance = Decimal("200")

    logger.info(
        "Generating pivot report: license_status=%s, min_balance=%s, sion_norm=%s",
        license_status,
        min_balance,
        sion_norm,
    )

    # Build the base import-item queryset (mirrors item_report logic)
    imp_qs = LicenseImportItemsModel.objects.select_related(
        "license", "license__exporter", "license__flags", "hs_code"
    ).prefetch_related("items").filter(available_value__gte=min_balance)

    if license_status == "active":
        imp_qs = imp_qs.filter(license__flags__is_active=True)

    if company_ids:
        imp_qs = imp_qs.filter(license__exporter_id__in=company_ids)

    if item_name_ids:
        imp_qs = imp_qs.filter(items__in=item_name_ids).distinct()

    if expiry_date_from:
        imp_qs = imp_qs.filter(license__license_expiry_date__gte=expiry_date_from)
    if expiry_date_to:
        imp_qs = imp_qs.filter(license__license_expiry_date__lte=expiry_date_to)

    # Collect license IDs from matched import items
    license_ids = list(imp_qs.values_list("license_id", flat=True).distinct())

    # Build a map: license_id -> norm_class label (from export items)
    exp_qs = LicenseExportItemModel.objects.filter(
        license_id__in=license_ids
    ).select_related("norm_class")

    if sion_norm:
        exp_qs = exp_qs.filter(norm_class__name__icontains=sion_norm)

    # Map license_id -> set of norm class labels
    license_norm_map: dict[int, set] = defaultdict(set)
    for exp in exp_qs:
        label = str(exp.norm_class) if exp.norm_class_id else "Uncategorised"
        license_norm_map[exp.license_id].add(label)

    # Group import items by norm class
    grouped: dict[str, list] = defaultdict(list)

    for imp in imp_qs:
        lic = imp.license
        hs = imp.hs_code
        items_detail = list(imp.items.values_list("name", flat=True))
        item_row = {
            "license_number": lic.license_number,
            "serial_number": imp.serial_number,
            "description": imp.description,
            "hs_code": hs.code if hs else "",
            "quantity": imp.quantity,
            "debited_quantity": imp.debited_quantity,
            "available_quantity": imp.available_quantity,
            "cif_fc": imp.cif_fc,
            "balance_cif_fc": imp.available_value,
            "items_detail": items_detail,
        }
        norms = license_norm_map.get(lic.pk, {"Uncategorised"})
        for norm in norms:
            grouped[norm].append(item_row)

    norm_classes = [
        {"norm_class": nc, "items": rows}
        for nc, rows in sorted(grouped.items())
    ]

    return {
        "norm_classes": norm_classes,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
    }
