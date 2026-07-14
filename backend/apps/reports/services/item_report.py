# reports/services/item_report.py
"""
Item utilisation report service.

Queries LicenseImportItemsModel with optional filters and returns a plain
dict describing per-item utilisation across matching licenses.

Models are imported inside the function to prevent circular import errors
during app startup.
"""
import logging
from datetime import UTC, datetime
from decimal import Decimal

logger = logging.getLogger(__name__)

_DEC_0 = Decimal("0")


def generate_item_report(
    item_name_ids: list | None = None,
    company_ids: list | None = None,
    min_balance: Decimal | None = None,
    license_status: str = "active",
    expiry_date_from: str | None = None,
    expiry_date_to: str | None = None,
) -> dict:
    """
    Build item utilisation report.

    Filters:
      item_name_ids    : list of ItemNameModel PKs
      company_ids      : list of CompanyModel PKs (exporter FK on license)
      min_balance      : minimum available_value threshold (Decimal, default 200)
      license_status   : 'active' -> filter LicenseFlags.is_active=True, 'all' -> no filter
      expiry_date_from : ISO date string, filter license.license_expiry_date >= value
      expiry_date_to   : ISO date string, filter license.license_expiry_date <= value

    Returns dict with key 'items'.
    """
    from apps.license.models import LicenseImportItemsModel

    if min_balance is None:
        min_balance = Decimal("200")

    logger.info(
        "Generating item report: license_status=%s, min_balance=%s",
        license_status,
        min_balance,
    )

    # Start from import items; join back to license for additional filters
    qs = LicenseImportItemsModel.objects.select_related(
        "license", "license__exporter", "license__flags", "hs_code"
    ).prefetch_related("items")

    # Filter by available value threshold
    qs = qs.filter(available_value__gte=min_balance)

    # Filter by license active status
    if license_status == "active":
        qs = qs.filter(license__flags__is_active=True)

    # Filter by company
    if company_ids:
        qs = qs.filter(license__exporter_id__in=company_ids)

    # Filter by item names (M2M)
    if item_name_ids:
        qs = qs.filter(items__in=item_name_ids).distinct()

    # Filter by expiry date range
    if expiry_date_from:
        qs = qs.filter(license__license_expiry_date__gte=expiry_date_from)
    if expiry_date_to:
        qs = qs.filter(license__license_expiry_date__lte=expiry_date_to)

    items = []
    for imp in qs:
        lic = imp.license
        hs = imp.hs_code

        # Items detail: M2M names
        items_detail = list(imp.items.values_list("name", flat=True))

        items.append(
            {
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
        )

    return {
        "items": items,
        "generated_at": datetime.now(tz=UTC).isoformat(),
    }
