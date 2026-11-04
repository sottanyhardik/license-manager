"""Summary-card metrics for the License Ledger collection.

Three sources, kept strictly apart (never added to one another):

* Ledger money (USD for DFIA, INR for incentive) comes from the canonical
  ledger dataset ``summary`` blocks and is reported by the collection summary.
* Sold status comes from the canonical sold-status records:
  ``IncentiveLicense.sold_status`` (stored, derived from SALE lines by
  ``derive_sold_status``).  DFIA licences have no stored sold record, so the
  same rule is applied to the canonical DFIA ledger (sales vs. ledger balance,
  both USD).  No second sold rule exists.
* CIF utilisation, availability and over-utilisation come from the canonical
  licence-balance engine (``build_licence_balance_reports``).  DFIA only, USD.
  ``utilised = original − available`` (available = original − utilised).

Nothing here performs an accounting calculation of its own.
"""
from datetime import date, datetime
from decimal import Decimal

from django.utils import timezone
from django.utils.dateparse import parse_date

from apps.license.models import IncentiveLicense
from apps.license.models.core import derive_sold_status
from apps.license.services.canonical_ledger_service import quantize_2dp
from apps.license.services.licence_balance_report import (
    OVER_ALLOCATED,
    OVER_UTILISED,
    REVIEW_REQUIRED,
    UNMAPPED_ITEM,
    build_licence_balance_reports,
)

# Every engine status that needs review but is NOT a confirmed CIF over-utilisation.
NEEDS_REVIEW_STATUSES = frozenset({REVIEW_REQUIRED, OVER_ALLOCATED, UNMAPPED_ITEM})

ZERO = Decimal("0")
SOLD_YES = "YES"
SOLD_PARTIAL = "PARTIAL"
SOLD_NO = "NO"


def _as_date(value):
    # datetime is a subclass of date: normalise it before comparing with a date.
    if isinstance(value, datetime):
        return value.date()
    if value is None or isinstance(value, date):
        return value
    return parse_date(str(value))


def _dfia_sold_status(dataset) -> str:
    summary = dataset["summary"]
    return derive_sold_status(summary["total_sale"], summary["current_balance"])


def build_ledger_metrics(datasets, *, today: date | None = None) -> dict:
    """Return the summary-card metrics for a filtered canonical collection.

    ``datasets`` is the full filtered collection (never a page of it), so the
    cards describe the whole result set the user is filtering.
    """
    today = today or timezone.localdate()
    dfia_rows = [row for row in datasets if row["license_type"] == "DFIA"]
    incentive_rows = [row for row in datasets if row["license_type"] != "DFIA"]

    # ── Sold status (canonical sold-status records) ─────────────────────────
    incentive_ids = [row["license_id"] for row in incentive_rows]
    stored_sold = dict(
        IncentiveLicense.objects.filter(id__in=incentive_ids).values_list("id", "sold_status")
    ) if incentive_ids else {}
    sold_yes = sold_partial = 0
    for row in dfia_rows:
        status = _dfia_sold_status(row)
        sold_yes += status == SOLD_YES
        sold_partial += status == SOLD_PARTIAL
    for row in incentive_rows:
        status = stored_sold.get(row["license_id"], SOLD_NO)
        sold_yes += status == SOLD_YES
        sold_partial += status == SOLD_PARTIAL

    # ── CIF utilisation and status (DFIA only: the CIF engine is the authority) ──
    # Confirmed over-utilisation is the engine's OVER_UTILISED status. REVIEW_REQUIRED
    # is a separate state and is never counted as confirmed over-utilisation.
    cif_reports = (
        build_licence_balance_reports([row["license_id"] for row in dfia_rows], include_legacy=False)
        if dfia_rows else {}
    )
    cif_original = cif_utilised = cif_available = ZERO
    cif_licence_count = cif_unavailable = cif_over_utilised = review_required = 0
    for row in dfia_rows:
        report = cif_reports.get(row["license_id"])
        cif = report.summary_cif if report is not None else {}
        if report is not None and report.status in NEEDS_REVIEW_STATUSES:
            review_required += 1
        if report is not None and report.status == OVER_UTILISED:
            cif_over_utilised += 1
        if cif.get("original") is None or cif.get("available") is None:
            # Items without a CIF figure: stated as unavailable, never guessed.
            cif_unavailable += 1
            continue
        original = Decimal(cif["original"])
        available = Decimal(cif["available"])
        cif_licence_count += 1
        cif_original += original
        cif_available += available
        cif_utilised += original - available

    # ── Incentive ledger balance (INR). Not CIF: a negative INR ledger balance
    # is an over-sold position on the incentive ledger, reported separately.
    incentive_negative_balance = sum(
        1 for row in incentive_rows if Decimal(str(row["summary"]["current_balance"])) < ZERO
    )

    expired = 0
    for row in datasets:
        expiry = _as_date(row.get("expiry_date"))
        if expiry is not None and expiry < today:
            expired += 1

    return {
        "as_of": today.isoformat(),
        "total_licences": len(datasets),
        "sold_licences": sold_yes,
        "partially_sold_licences": sold_partial,
        "expired_licences": expired,
        # Confirmed CIF over-utilisation (DFIA, canonical engine status OVER_UTILISED).
        "cif_over_utilised_licences": cif_over_utilised,
        # Any engine exception other than confirmed over-utilisation (REVIEW_REQUIRED,
        # OVER_ALLOCATED, UNMAPPED_ITEM). Needs review; never counted as confirmed.
        "review_required_licences": review_required,
        # Incentive licences whose INR ledger balance is negative (not a CIF figure).
        "incentive_negative_balance_licences": incentive_negative_balance,
        "cif": {
            "currency": "USD",
            "source": "licence_balance_engine",
            "licence_count": cif_licence_count,
            "unavailable_count": cif_unavailable,
            "original": str(quantize_2dp(cif_original)),
            "utilised": str(quantize_2dp(cif_utilised)),
            "available": str(quantize_2dp(cif_available)),
        },
    }
