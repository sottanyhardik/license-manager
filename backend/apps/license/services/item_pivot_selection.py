"""Licence selection shared by the Item Pivot report and its intelligence views.

Moved verbatim from ``ItemPivotGenerateMixin.generate_report`` so both read
exactly the same filtered, prefetched licence population.
"""
import re
from decimal import Decimal

from django.db.models import Q, Prefetch

from apps.core.constants import CO, GE, MI
from apps.core.models import ItemNameModel
from apps.license.models import (
    LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel, LicenseTransferModel,
)

MITC_CODE = "MI"  # PurchaseStatus.code of MITC (the legacy ``MI`` constant is "NP")

# License Numbers filter: pasted lists are split on commas (and newlines / semicolons / tabs, which is what a
# spreadsheet column paste produces). A token longer than the model field can never match and is reported invalid.
LICENSE_NUMBER_SEPARATORS = re.compile(r"[,;\n\r\t]+")
LICENSE_NUMBER_MAX_LENGTH = 50  # LicenseDetailsModel.license_number max_length
MAX_LICENSE_NUMBERS = 5000


def parse_license_numbers(raw) -> list[str]:
    """Split, trim, drop empties and de-duplicate (first occurrence order kept). Exact values — no case folding."""
    if not raw:
        return []
    seen: dict[str, None] = {}
    for token in LICENSE_NUMBER_SEPARATORS.split(str(raw)):
        token = token.strip()
        if token:
            seen.setdefault(token, None)
    return list(seen)


def license_number_filter_summary(requested: list[str], selected_licenses: list) -> dict:
    """Additive report metadata: which requested numbers matched, which exist but fall outside the other filters
    (with their SION norms, since the report is built per norm tab), and which match no licence at all."""
    matched_set = {lic.license_number for lic in selected_licenses}
    candidates = [n for n in requested if len(n) <= LICENSE_NUMBER_MAX_LENGTH]
    norms_by_number: dict[str, set] = {}
    for number, norm in LicenseDetailsModel.objects.filter(license_number__in=candidates).values_list(
            "license_number", "export_license__norm_class__norm_class"):
        norms_by_number.setdefault(number, set())
        if norm:
            norms_by_number[number].add(norm)
    return {
        "requested": requested,
        "requested_count": len(requested),
        "matched": [n for n in requested if n in matched_set],
        "excluded_by_filters": [
            {"license_number": n, "sion_norms": sorted(norms_by_number[n])}
            for n in requested if n not in matched_set and n in norms_by_number
        ],
        "not_found": [n for n in requested if n not in matched_set and n not in norms_by_number],
    }


def select_pivot_licenses(days: int = 30, sion_norm: str = None,
                          company_ids: str = None, exclude_company_ids: str = None,
                          min_balance: int = 200, license_status: str = 'active',
                          expiry_date_from: str = None, expiry_date_to: str = None,
                          purchase_status: str = None, include_norm_links: bool = False,
                          license_numbers: list[str] | None = None) -> list:
    from datetime import date, timedelta
    today = date.today()

    # Base query - licenses with required purchase status.
    # The frontend sends the chosen codes as a comma-separated string;
    # when omitted, fall back to GE / MI / CO (Global Exim, MITC,
    # Conversion) which is the historical default for this report.
    if purchase_status:
        ps_codes = [c.strip() for c in purchase_status.split(',') if c.strip()]
    else:
        # MITC's purchase-status code is "MI"; the legacy ``MI`` constant is "NP", which matched no MITC licence, so the
        # default silently dropped every MITC licence (E1 025/2023 MITC, 2026-11-20). Both codes are accepted.
        ps_codes = [GE, MI, MITC_CODE, CO]
    licenses = LicenseDetailsModel.objects.filter(
        purchase_status__code__in=ps_codes
    )

    # License Numbers filter (AND-ed with every other filter; one ``IN`` query, applied before the live-balance
    # batch so only the requested licences are balanced). None/empty keeps the historical behaviour.
    if license_numbers:
        licenses = licenses.filter(license_number__in=list(license_numbers))

    # Apply license status filter
    if license_status == 'active':
        # Active: expiry date > today - 30 days (not expired more than 30 days ago)
        licenses = licenses.filter(
            flags__is_active=True,
            license_expiry_date__gt=today - timedelta(days=30)
        )
    elif license_status == 'expired':
        # Expired: expiry date < today (don't filter by is_active to include all expired licenses)
        licenses = licenses.filter(license_expiry_date__lt=today)
    elif license_status == 'expiring_soon':
        # Expiring soon: expiry within next 30 days
        licenses = licenses.filter(
            flags__is_active=True,
            license_expiry_date__gte=today,
            license_expiry_date__lte=today + timedelta(days=30)
        )
    # If 'all', no date or is_active filter applied - shows everything

    # Apply explicit expiry date range filter (overrides license_status date logic if provided)
    if expiry_date_from:
        from datetime import datetime as _dt
        licenses = licenses.filter(license_expiry_date__gte=_dt.strptime(expiry_date_from, '%Y-%m-%d').date())
    if expiry_date_to:
        from datetime import datetime as _dt
        licenses = licenses.filter(license_expiry_date__lte=_dt.strptime(expiry_date_to, '%Y-%m-%d').date())

    # Filter by SION norm if specified (optional)
    if sion_norm:
        licenses = licenses.filter(export_license__norm_class__norm_class=sion_norm).distinct()

    # Filter by company IDs if specified
    if company_ids:
        company_id_list = [int(cid.strip()) for cid in company_ids.split(',') if cid.strip()]
        licenses = licenses.filter(exporter_id__in=company_id_list)

    # Exclude company IDs if specified
    if exclude_company_ids:
        exclude_id_list = [int(cid.strip()) for cid in exclude_company_ids.split(',') if cid.strip()]
        licenses = licenses.exclude(exporter_id__in=exclude_id_list)

    # Filter by min_balance against the LIVE, batched-computed balance
    # instead of the cached `balance__balance_cif` column (BL-LEDGER-02:
    # the cache has no signal on reconciliation-allocation changes and
    # can go stale) -- same fix already applied to the License List /
    # Item Report / other report views. Still a fixed number of
    # queries regardless of how many candidate licenses there are.
    from apps.license.services.balance_calculator import LicenseBalanceCalculator
    candidate_ids = list(licenses.values_list('id', flat=True))
    live_balance_by_license = LicenseBalanceCalculator.calculate_financial_balance_for_licenses(candidate_ids)
    min_balance_dec = Decimal(str(min_balance))
    matching_ids = [
        i for i in candidate_ids
        if live_balance_by_license.get(i, Decimal('0')) >= min_balance_dec
    ]
    licenses = licenses.filter(id__in=matching_ids)

    # Build filtered prefetch querysets based on sion_norm
    import_items_qs = LicenseImportItemsModel.objects.select_related('hs_code')
    export_items_qs = LicenseExportItemModel.objects.select_related('norm_class')
    # NOTE: do NOT filter is_active here. Inactive item names are still needed
    # so a manually-planned-but-inactive item (e.g. WALNUT planned on an E132
    # DFIA) gets its quantities into item_quantities and renders. The column
    # set (all_items) still hides inactive items via its own is_active check,
    # except those that are explicitly planned (added back below).
    item_names_qs = ItemNameModel.objects.select_related('sion_norm_class')

    # If sion_norm specified, filter prefetch queries to only that norm.
    if sion_norm:
        if include_norm_links:
            # Intelligence views: a master is legitimate for the norm through its ``norms`` M2M (the authoritative,
            # multi-norm field) as well as the legacy single-norm FK — e.g. canonical "PP" (FK A3627, norms E1/E5/…).
            # The classic pivot keeps the legacy FK filter unchanged.
            item_names_qs = item_names_qs.filter(Q(sion_norm_class__norm_class=sion_norm) | Q(norms__norm_class=sion_norm)).distinct()
        else:
            item_names_qs = item_names_qs.filter(sion_norm_class__norm_class=sion_norm)
        export_items_qs = export_items_qs.filter(norm_class__norm_class=sion_norm)
    if include_norm_links:
        item_names_qs = item_names_qs.prefetch_related("norms")

    # Optimize with select_related and prefetch_related to reduce queries.
    # balance_cif / balance_report_notes / condition_sheet / current_owner now
    # live on OneToOne sub-tables (LicenseBalance / LicenseNotes / LicenseOwnership);
    # they're accessed via @property shims, so pull the sub-rows in one shot.
    licenses = licenses.select_related(
        'exporter',
        'port',
        'balance',
        'notes',
        'ownership__current_owner',
        'purchase_status',
        'notification_number',   # Fix #6: was lazy-loaded per licence (~2×N extra queries)
    ).prefetch_related(
        Prefetch('import_license',
                 queryset=import_items_qs.prefetch_related(
                     Prefetch('items', queryset=item_names_qs)
                 ).only('id', 'license_id', 'hs_code_id', 'quantity', 'allotted_quantity',
                        'debited_quantity', 'available_quantity', 'debited_value', 'cif_fc', 'description',
                        'condition_type', 'serial_number', 'unit')),
        Prefetch('export_license',
                 queryset=export_items_qs.only('id', 'license_id', 'norm_class_id', 'cif_fc')),
        'license_documents',
        # Fix #5: ordered Prefetch avoids re-querying with ORDER BY inside _build_license_row
        Prefetch('transfers',
                 queryset=LicenseTransferModel.objects.order_by('-transfer_date', '-id'),
                 to_attr='transfers_ordered'),
    ).order_by('license_expiry_date', 'license_date')

    valid_licenses = list(licenses)  # Licenses already filtered by LIVE balance above
    return valid_licenses
