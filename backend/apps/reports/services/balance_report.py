# reports/services/balance_report.py
"""
Balance report service.

Assembles per-license balance summary data from LicenseDetailsModel and
LicenseBalance.  Returns a plain dict that is JSON-serialisable (all
Decimal values are preserved as Decimal; the task layer uses default=str
when serialising to file).

Models are imported inside the function to prevent circular import errors
during app startup.
"""
import logging
from datetime import datetime, timezone
from decimal import Decimal

logger = logging.getLogger(__name__)

_DEC_0 = Decimal("0")


def generate_balance_report(license_ids: list, output_format: str) -> dict:
    """
    Assemble balance report data for the given license IDs.

    Returns a plain dict (JSON-serialisable via default=str).

    output_format: 'json' | 'pdf' | 'excel'
    Currently only JSON data is returned; the caller (task) handles file
    serialisation.
    """
    from apps.license.models import LicenseBalance, LicenseDetailsModel

    logger.info(
        "Generating balance report for %d licenses, format=%s",
        len(license_ids),
        output_format,
    )

    licenses_qs = (
        LicenseDetailsModel.objects.filter(pk__in=license_ids)
        .select_related("exporter", "balance", "flags")
    )

    licenses = []
    for lic in licenses_qs:
        balance_obj = getattr(lic, "balance", None)
        flags_obj = getattr(lic, "flags", None)

        balance_cif = balance_obj.balance_cif if balance_obj else _DEC_0

        # Compute total_authorised from export items (credit side)
        try:
            from django.db.models import Sum
            from apps.license.models import LicenseExportItemModel

            total_authorised = (
                LicenseExportItemModel.objects.filter(license_id=lic.pk)
                .aggregate(total=Sum("cif_fc"))["total"]
            ) or _DEC_0
        except Exception:
            total_authorised = _DEC_0

        # Compute total_debited from import items
        try:
            from apps.license.models import LicenseImportItemsModel

            total_debited = (
                LicenseImportItemsModel.objects.filter(license_id=lic.pk)
                .aggregate(total=Sum("debited_value"))["total"]
            ) or _DEC_0

            total_allotted = (
                LicenseImportItemsModel.objects.filter(license_id=lic.pk)
                .aggregate(total=Sum("allotted_value"))["total"]
            ) or _DEC_0
        except Exception:
            total_debited = _DEC_0
            total_allotted = _DEC_0

        # company_label: use archived name or exporter FK
        company_label = ""
        if lic.exporter_id and lic.exporter:
            company_label = str(lic.exporter)
        elif lic.archived_exporter_name:
            company_label = lic.archived_exporter_name

        # license_type: derive from scheme_code if available
        license_type = ""
        if lic.scheme_code_id:
            try:
                license_type = str(lic.scheme_code)
            except Exception:
                pass

        licenses.append(
            {
                "license_number": lic.license_number,
                "license_type": license_type,
                "company_label": company_label,
                "balance_cif": balance_cif,
                "total_authorised": total_authorised,
                "total_debited": total_debited,
                "total_allotted": total_allotted,
                "license_expiry_date": (
                    lic.license_expiry_date.isoformat()
                    if lic.license_expiry_date
                    else None
                ),
                "is_active": flags_obj.is_active if flags_obj else None,
            }
        )

    return {
        "licenses": licenses,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "output_format": output_format,
    }
