"""
Dashboard v3 payload builders. Contract: docs/09-module-implementation/dashboard.md §4.

Money comes only from `LicenseBalanceCalculator` (through its per-licence
component breakdown). This module classifies, sums and formats; it never
re-derives a CIF formula. Licence status is classified in Python from one
row per licence so each expiry predicate is written once and tested directly.

Every section is built in isolation: a failure becomes `{"error": ...}` for
that section and the others still load (see `_section`).
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.db.models import Count, DecimalField, Exists, F, IntegerField, OuterRef, Prefetch, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce, Greatest, TruncMonth
from django.utils import timezone

from apps.allotment.models import AllotmentItems, AllotmentModel
from apps.bill_of_entry.models import BillOfEntryModel, RowDetails
from apps.core.constants import DEC_0
from apps.core.models import CompanyModel
from apps.core.utils.decimal_utils import to_decimal
from apps.core.utils.exceptions import api_error
from apps.license.models import LicenseDetailsModel, LicenseExportItemModel
from apps.license.services.balance_calculator import LicenseBalanceCalculator, quantize_2dp
from apps.license.services.c969_link_review import c969_link_mismatches
from apps.trade.models import LicenseTrade, LicenseTradePayment

LICENCE_ROLES = ("LICENSE_MANAGER", "LICENSE_VIEWER", "REPORT_VIEWER")
ALLOTMENT_ROLES = ("ALLOTMENT_MANAGER", "ALLOTMENT_VIEWER", "REPORT_VIEWER")
BOE_ROLES = ("BOE_MANAGER", "BOE_VIEWER", "ACCOUNT_ACCESS", "REPORT_VIEWER")
INVOICE_ROLES = ("TRADE_MANAGER", "TRADE_VIEWER", "ACCOUNT_ACCESS", "REPORT_VIEWER")

# Legacy business rule kept for the expiring-licence drill-down and its alert:
# only licences whose live financial balance is at least $100 are "usable".
USABLE_BALANCE_THRESHOLD = Decimal("100.00")
# "Missing DGFT" = live balance below 200. This is the licence list's own `is_null` rule
# (`LicenseDetailsViewSet.apply_advanced_filters`), so the count and its link agree.
MISSING_DGFT_BALANCE = Decimal("200.00")
WITHIN_DAYS = (7, 15, 30, 60)
EXPIRING_WINDOW_DAYS = 30
EXPIRING_LIST_LIMIT = 25
EXCEPTION_LIST_LIMIT = 25
LIST_LIMIT = 10
LICENCE_LIST_LIMIT = 5
TREND_MONTHS = 6

SALE_DIRECTIONS = (LicenseTrade.DIR_SALE, LicenseTrade.DIR_COMMISSION_SALE)
PURCHASE_DIRECTIONS = (LicenseTrade.DIR_PURCHASE, LicenseTrade.DIR_COMMISSION_PURCHASE)

NOT_MONITORED = [
    {
        "key": "invoice_states",
        "reason": "Draft, pending, confirmed and posted invoice states are not part of this system's "
                  "invoice model. Invoice status here is Paid, Partially paid or Unpaid.",
    },
    {"key": "reconciliation_issues", "reason": "Not computed on the dashboard. Use the Reconciliation page."},
    {"key": "duplicate_debit_findings", "reason": "No duplicate-debit detector feeds the dashboard yet."},
    {"key": "invalid_licence_mappings", "reason": "No mapping validator feeds the dashboard yet."},
    {"key": "incomplete_allotments", "reason": "No completeness rule is defined for allotments yet."},
]


def money(value) -> str:
    """Decimal string with 2 dp. Money crosses the API as text, never as a float."""
    return f"{quantize_2dp(to_decimal(value, DEC_0)):.2f}"


def _iso(value):
    return value.isoformat() if value is not None else None


@dataclass(frozen=True)
class DashboardScope:
    """Company and activity-date scope for one request. `as_of` is the business date."""

    as_of: date
    company: CompanyModel | None = None
    date_from: date | None = None
    date_to: date | None = None

    @property
    def cache_token(self) -> str:
        company = self.company.pk if self.company else "all"
        return f"{company}:{self.date_from or 'all'}:{self.date_to or 'all'}"

    def bounded(self, queryset, lookup: str):
        """Apply the activity date range. `lookup` is a date field, or `<datetime>__date` for a datetime."""
        if self.date_from:
            queryset = queryset.filter(**{f"{lookup}__gte": self.date_from})
        if self.date_to:
            queryset = queryset.filter(**{f"{lookup}__lte": self.date_to})
        return queryset

    def licences(self):
        queryset = LicenseDetailsModel.objects.all()
        return queryset.filter(exporter_id=self.company.pk) if self.company else queryset

    def allotments(self):
        queryset = AllotmentModel.objects.all()
        return queryset.filter(company_id=self.company.pk) if self.company else queryset

    def boes(self):
        queryset = BillOfEntryModel.objects.all()
        return queryset.filter(company_id=self.company.pk) if self.company else queryset

    def trades(self):
        queryset = LicenseTrade.objects.exclude(invoice_number="")
        if self.company:
            queryset = queryset.filter(Q(from_company_id=self.company.pk) | Q(to_company_id=self.company.pk))
        return queryset


def _section(name: str, build):
    """Run one section. A failure is logged and returned as `{"error": ...}` for that section only."""
    try:
        return build()
    except Exception as exc:  # isolate: one failing section must not hide the rest of the dashboard
        return api_error(f"Dashboard section '{name}' could not be loaded", exc, __name__)


# ---------------------------------------------------------------- licences

def expiry_band(*, expiry: date | None, days: int | None, expired: bool, active: bool) -> str:
    """Non-overlapping band. Expired wins over inactive; every licence lands in exactly one band."""
    if expired:
        return "expired"
    if not active:
        return "inactive"
    if expiry is None:
        return "no_expiry"
    if days <= 7:
        return "d0_7"
    if days <= 15:
        return "d8_15"
    if days <= 30:
        return "d16_30"
    if days <= 60:
        return "d31_60"
    return "over_60"


BAND_KEYS = ("expired", "d0_7", "d8_15", "d16_30", "d31_60", "over_60", "inactive", "no_expiry")


def _licence_snapshot(scope: DashboardScope) -> dict:
    """One licence pass. Returns the portfolio, the financial bridge and the expiring drill-down."""
    as_of = scope.as_of
    rows = list(scope.licences().values_list(
        "id", "license_number", "license_expiry_date", "flags__is_active", "flags__is_expired",
    ))
    ids = [row[0] for row in rows]
    numbers = {row[0]: row[1] for row in rows}
    components = LicenseBalanceCalculator.calculate_financial_components_for_licenses(ids)

    bands = Counter({key: 0 for key in BAND_KEYS})
    within = {days: 0 for days in WITHIN_DAYS}
    counts = Counter()
    expired_ids: list[int] = []
    stale_ids: list[int] = []
    expiring_usable: list[tuple] = []
    expiring_usable_7d = 0

    # Each predicate below is the same one its dashboard link applies in the licence list.
    for lid, _number, expiry, flag_active, flag_expired in rows:
        active_flag = True if flag_active is None else bool(flag_active)
        date_expired = expiry is not None and expiry < as_of
        days = (expiry - as_of).days if expiry is not None else None
        active = active_flag and not date_expired

        bands[expiry_band(expiry=expiry, days=days, expired=date_expired, active=active_flag)] += 1
        if components[lid]["available"] < MISSING_DGFT_BALANCE:
            counts["missing_dgft"] += 1
        if flag_expired is not None and bool(flag_expired) != date_expired:
            stale_ids.append(lid)
        if date_expired:
            counts["expired"] += 1
            expired_ids.append(lid)
        if active:
            counts["active"] += 1
            for window in WITHIN_DAYS:
                if days is not None and 0 <= days <= window:
                    within[window] += 1
            if days is not None and 0 <= days <= EXPIRING_WINDOW_DAYS:
                if components[lid]["available"] >= USABLE_BALANCE_THRESHOLD:
                    expiring_usable.append((expiry, lid, days))
                    if days <= 7:
                        expiring_usable_7d += 1

    expired_with_balance_ids = [lid for lid in expired_ids if components[lid]["available"] > DEC_0]
    over_utilised_ids = [lid for lid in ids if components[lid]["raw"] < DEC_0]
    portfolio = {
        "total": len(rows),
        "active": counts["active"],
        "expired": counts["expired"],
        "missing_dgft": counts["missing_dgft"],
        "expiring_usable_30d": len(expiring_usable),
        "stale_expiry_flags": len(stale_ids),
        "bands": [{"key": key, "count": bands[key]} for key in BAND_KEYS],
        "within": {str(days): within[days] for days in WITHIN_DAYS},
    }

    financial = _financial_bridge(components, expired_ids)
    expiring = _expiring_drilldown(sorted(expiring_usable), components)

    return {
        "portfolio": portfolio,
        "financial": financial,
        "expiring_licences": expiring,
        "exceptions": {
            "over_utilised": _licence_refs(over_utilised_ids, numbers),
            "expired_with_balance": _licence_refs(expired_with_balance_ids, numbers),
            "stale_expiry_flags": _licence_refs(stale_ids, numbers),
        },
        "metrics": {
            "expired_with_balance": len(expired_with_balance_ids),
            "expiring_7d_usable": expiring_usable_7d,
            "missing_dgft": counts["missing_dgft"],
            "over_utilised": financial["over_utilised_licences"],
            "stale_expiry_flags": len(stale_ids),
        },
    }


def _licence_refs(ids: list[int], numbers: dict) -> list[dict]:
    """Licences behind an exception, for links. Capped; the count in `attention` is not."""
    ordered = sorted(ids, key=lambda lid: numbers[lid])[:EXCEPTION_LIST_LIMIT]
    return [{"id": lid, "license_number": numbers[lid]} for lid in ordered]


def _financial_bridge(components: dict, expired_ids: list[int]) -> dict:
    """Sums the engine's per-licence components. The bridge identities are exact by construction."""
    total = {
        key: sum((row[key] for row in components.values()), DEC_0)
        for key in ("credit", "opening", "purchase", "sale", "boe", "allotment", "raw", "available")
    }
    previous_owner = sum((row["credit"] - row["opening"] for row in components.values()), DEC_0)

    authorized = total["credit"]
    reserved = total["allotment"]
    utilized = total["boe"] + total["sale"]
    unrounded_raw = authorized - previous_owner + total["purchase"] - total["sale"] - total["boe"] - reserved
    # Each licence's raw balance is quantized before the floor. `rounding` absorbs
    # that difference so the bridge closes exactly.
    rounding = total["raw"] - unrounded_raw
    over_utilisation_floor = total["available"] - total["raw"]
    committed_pct = None
    if authorized > DEC_0:
        committed_pct = round(float((utilized + reserved) / authorized * 100), 2)

    return {
        "engine": "financial_available_balance",
        "authorized_cif": money(authorized),
        "utilized_cif": money(utilized),
        "reserved_cif": money(reserved),
        "available_cif": money(total["available"]),
        "expired_available_cif": money(sum((components[lid]["available"] for lid in expired_ids), DEC_0)),
        "committed_pct": committed_pct,
        "licences_in_scope": len(components),
        "over_utilised_licences": sum(1 for row in components.values() if row["raw"] < DEC_0),
        "bridge": {
            "authorized": money(authorized),
            "previous_owner_utilisation": money(previous_owner),
            "purchased_cif": money(total["purchase"]),
            "sale_utilisation": money(total["sale"]),
            "boe_utilisation": money(total["boe"]),
            "reserved": money(reserved),
            "rounding": money(rounding),
            "raw_available": money(total["raw"]),
            "over_utilisation_floor": money(over_utilisation_floor),
            "available": money(total["available"]),
        },
    }


def _expiring_drilldown(usable_sorted: list[tuple], components: dict) -> list[dict]:
    """Soonest-expiring usable licences, with SION norms prefetched for the rows shown."""
    top = usable_sorted[:EXPIRING_LIST_LIMIT]
    if not top:
        return []
    by_id = {
        licence.pk: licence
        for licence in LicenseDetailsModel.objects.filter(pk__in=[lid for _, lid, _ in top]).prefetch_related(
            Prefetch(
                "export_license",
                queryset=LicenseExportItemModel.objects.filter(norm_class__isnull=False).select_related("norm_class"),
            ),
        )
    }
    result = []
    for expiry, lid, days in top:
        licence = by_id[lid]
        norms = list(dict.fromkeys(
            item.norm_class.norm_class
            for item in licence.export_license.all()
            if item.norm_class is not None
        ))
        result.append({
            "id": lid,
            "license_number": licence.license_number,
            "license_expiry_date": _iso(expiry),
            "days_to_expiry": days,
            "balance_cif": money(components[lid]["available"]),
            "sion_norms": norms,
        })
    return result


# ---------------------------------------------------------------- allotments

def _allotment_status(allotted: Decimal, allocated: Decimal, consumed: Decimal, boe_count: int) -> str:
    """
    Status from the engine's own figures. "Consumed" means every item's CIF is matched by a BOE
    allocation. It does not mean the reserved figure is zero: the engine reports zero reservation
    for any BOE-linked allotment (ISS-008), so reservation cannot tell a full draw from a partial one.
    """
    if allocated > DEC_0 and consumed >= allotted:
        return "consumed"
    if allocated > DEC_0:
        return "partly_consumed"
    if boe_count > 0:
        return "boe_linked"
    return "open"


def build_allotment_activity(scope: DashboardScope) -> dict:
    """
    Allotment activity, one row per allotment in scope.

    Every CIF and quantity figure is an engine annotation summed over the allotment's items
    (`LicenseBalanceCalculator.get_allotment_rows_for_allotments`). This module adds no CIF formula.
    The one derived figure, `not_reserved_cif`, is `allotted - consumed - reserved`. It is the
    amount the engine neither reserves nor counts as consumed. It is zero for a non-BOE-linked
    allotment and is the ISS-008 gap for a BOE-linked one.

    Fixed quantities of four kinds stay separate: the original quantity (`required_quantity`),
    the quantity placed on licence items, the matched (consumed) quantity, and the remaining
    reserved quantity. A BOE-linked allotment is counted once however many BOEs are linked.
    """
    allotments = scope.bounded(scope.allotments(), "created_on__date")
    rows = list(allotments.order_by("-created_on", "-id").values(
        "id", "item_name", "company__name", "created_on", "required_quantity",
    ))
    ids = [row["id"] for row in rows]
    boe_counts = {}
    figures = {}
    if ids:
        boe_counts = dict(
            AllotmentModel.objects.filter(pk__in=ids)
            .annotate(boe_count=Count("bill_of_entry", distinct=True))
            .values_list("pk", "boe_count")
        )
        grouped = (
            LicenseBalanceCalculator.get_allotment_rows_for_allotments(ids)
            .values("allotment_id")
            .annotate(
                allotted=Coalesce(Sum("cif_fc"), DEC_0, output_field=DecimalField()),
                allocated=Coalesce(Sum("allocated"), DEC_0, output_field=DecimalField()),
                consumed=Coalesce(Sum("matched"), DEC_0, output_field=DecimalField()),
                reserved=Coalesce(Sum("contributed"), DEC_0, output_field=DecimalField()),
                remaining_qty=Coalesce(Sum("contributed_qty"), DEC_0, output_field=DecimalField()),
                item_qty=Coalesce(Sum("qty"), DEC_0, output_field=DecimalField()),
            )
        )
        figures = {row["allotment_id"]: row for row in grouped}

    def figures_for(allotment_id: int) -> dict:
        row = figures.get(allotment_id, {})
        allotted = row.get("allotted", DEC_0)
        consumed = row.get("consumed", DEC_0)
        reserved = row.get("reserved", DEC_0)
        return {
            "allotted": allotted,
            "allocated": row.get("allocated", DEC_0),
            "consumed": consumed,
            "reserved": reserved,
            "not_reserved": allotted - consumed - reserved,
            "remaining_qty": row.get("remaining_qty", DEC_0),
            "item_qty": row.get("item_qty", DEC_0),
            "status": _allotment_status(allotted, row.get("allocated", DEC_0), consumed, boe_counts.get(allotment_id, 0)),
        }

    counts = {"open": 0, "partly_consumed": 0, "consumed": 0, "boe_linked": 0}
    totals = {"allotted": DEC_0, "consumed": DEC_0, "reserved": DEC_0, "not_reserved": DEC_0}
    per_row = {}
    for row in rows:
        figs = figures_for(row["id"])
        per_row[row["id"]] = figs
        counts[figs["status"]] += 1
        for key in totals:
            totals[key] += figs[key]

    recent_rows = rows[:LIST_LIMIT]
    recent_ids = [row["id"] for row in recent_rows]
    licences_by_allotment: dict[int, list[dict]] = {}
    if recent_ids:
        seen = set()
        for allotment_id, licence_id, number in (
            AllotmentItems.objects.filter(allotment_id__in=recent_ids, item__license__isnull=False)
            .order_by("allotment_id", "item__license__license_number")
            .values_list("allotment_id", "item__license_id", "item__license__license_number")
        ):
            if (allotment_id, licence_id) in seen:
                continue
            seen.add((allotment_id, licence_id))
            licences_by_allotment.setdefault(allotment_id, []).append({"id": licence_id, "license_number": number})

    recent = []
    for row in recent_rows:
        figs = per_row[row["id"]]
        licences = licences_by_allotment.get(row["id"], [])
        recent.append({
            "id": row["id"],
            "reference": f"#{row['id']}",
            "item_name": row["item_name"],
            "company_name": row["company__name"],
            "created_on": _iso(row["created_on"]),
            "licences": licences[:LICENCE_LIST_LIMIT],
            "licence_count": len(licences),
            "original_quantity": money(row["required_quantity"]),
            "allocated_quantity": money(figs["item_qty"]),
            # Same definition as AllotmentModel.balanced_quantity: requested minus placed on items, never negative.
            "unplaced_quantity": money(max(to_decimal(row["required_quantity"], DEC_0) - figs["item_qty"], DEC_0)),
            "allotted_cif": money(figs["allotted"]),
            "consumed_cif": money(figs["consumed"]),
            "reserved_cif": money(figs["reserved"]),
            "not_reserved_cif": money(figs["not_reserved"]),
            "remaining_quantity": money(figs["remaining_qty"]),
            "boe_count": boe_counts.get(row["id"], 0),
            "status": figs["status"],
        })

    return {
        "total": len(rows),
        "counts": counts,
        "totals": {
            "allotted_cif": money(totals["allotted"]),
            "consumed_cif": money(totals["consumed"]),
            "reserved_cif": money(totals["reserved"]),
            "not_reserved_cif": money(totals["not_reserved"]),
        },
        "recent": recent,
    }


# ---------------------------------------------------------------- BOEs

def _boe_row(boe) -> dict:
    return {
        "id": boe.id,
        "bill_of_entry_number": boe.bill_of_entry_number,
        "bill_of_entry_date": _iso(boe.bill_of_entry_date),
        "company_name": boe.company.name if boe.company_id else None,
        "invoice_no": boe.invoice_no or None,
        "modified_on": _iso(boe.modified_on),
        "allotment_links": boe.allotment_links,
        "licence_items": boe.licence_items,
        "mapping_status": "pending_licence_mapping" if boe.licence_items == 0 else "mapped",
    }


def build_boe_activity(scope: DashboardScope) -> dict:
    """Counts follow the activity date range. The monthly trend follows only the company."""
    link_count = Subquery(
        BillOfEntryModel.allotment.through.objects.filter(billofentrymodel_id=OuterRef("pk"))
        .order_by().values("billofentrymodel_id").annotate(c=Count("id")).values("c")[:1],
        output_field=IntegerField(),
    )
    item_count = Subquery(
        RowDetails.objects.filter(bill_of_entry_id=OuterRef("pk"))
        .order_by().values("bill_of_entry_id").annotate(c=Count("id")).values("c")[:1],
        output_field=IntegerField(),
    )
    boes = scope.bounded(scope.boes(), "bill_of_entry_date")
    linked_q = Exists(BillOfEntryModel.allotment.through.objects.filter(billofentrymodel_id=OuterRef("pk")))
    unmapped_q = ~Exists(RowDetails.objects.filter(bill_of_entry_id=OuterRef("pk")))
    annotated = boes.select_related("company").annotate(
        allotment_links=Coalesce(link_count, 0),
        licence_items=Coalesce(item_count, 0),
    )
    total = boes.count()
    linked = boes.filter(linked_q).count()
    recent = annotated.order_by(F("bill_of_entry_date").desc(nulls_last=True), "-id")[:LIST_LIMIT]
    recently_modified = annotated.order_by("-modified_on", "-id")[:LIST_LIMIT]
    pending_mapping = annotated.filter(unmapped_q).order_by(F("bill_of_entry_date").desc(nulls_last=True), "-id")[:LIST_LIMIT]

    trend_start = scope.as_of - relativedelta(months=TREND_MONTHS - 1)
    monthly = (
        scope.boes().filter(bill_of_entry_date__gte=trend_start.replace(day=1), bill_of_entry_date__isnull=False)
        .annotate(month_start=TruncMonth("bill_of_entry_date"))
        .values("month_start").annotate(count=Count("id")).order_by("month_start")
    )
    by_month = {row["month_start"].strftime("%Y-%m"): row["count"] for row in monthly}
    trend = []
    for offset in range(TREND_MONTHS):
        month = trend_start + relativedelta(months=offset)
        trend.append({"month": month.strftime("%b %Y"), "count": by_month.get(month.strftime("%Y-%m"), 0)})

    return {
        "total": total,
        "linked_to_allotment": linked,
        "direct": total - linked,
        "pending_licence_mapping": boes.filter(unmapped_q).count(),
        "without_invoice_no": boes.filter(Q(invoice_no__isnull=True) | Q(invoice_no="")).count(),
        "recent": [_boe_row(boe) for boe in recent],
        "recently_modified": [_boe_row(boe) for boe in recently_modified],
        "pending_mapping": [_boe_row(boe) for boe in pending_mapping],
        "monthly_trend": trend,
    }


# ---------------------------------------------------------------- invoices

def _trade_status(due: Decimal, paid: Decimal) -> str:
    if due <= DEC_0:
        return "paid"
    if paid > DEC_0:
        return "partially_paid"
    return "unpaid"


def build_invoice_activity(scope: DashboardScope) -> dict:
    """Invoice engine = `LicenseTrade` with a non-blank invoice number. Status uses the trade's own settlement rule."""
    paid_sum = Coalesce(
        Subquery(
            LicenseTradePayment.objects.filter(trade_id=OuterRef("pk"))
            .order_by().values("trade_id").annotate(s=Sum("amount")).values("s")[:1],
            output_field=DecimalField(max_digits=20, decimal_places=2),
        ),
        DEC_0,
        output_field=DecimalField(max_digits=20, decimal_places=2),
    )
    trades = scope.bounded(scope.trades(), "invoice_date").annotate(paid_sum=paid_sum)
    trades = trades.annotate(
        due=F("total_amount") - F("paid_sum"),
        outstanding=Greatest(F("total_amount") - F("paid_sum"), Value(DEC_0), output_field=DecimalField(max_digits=20, decimal_places=2)),
    )
    money_field = DecimalField(max_digits=20, decimal_places=2)
    # One aggregate query: the per-direction split is a filtered sum over the same rows.
    totals = trades.aggregate(
        total=Count("id"),
        paid=Count("id", filter=Q(due__lte=0)),
        partially_paid=Count("id", filter=Q(due__gt=0, paid_sum__gt=0)),
        unpaid=Count("id", filter=Q(due__gt=0, paid_sum__lte=0)),
        total_amount=Coalesce(Sum("total_amount"), DEC_0, output_field=money_field),
        paid_amount=Coalesce(Sum("paid_sum"), DEC_0, output_field=money_field),
        outstanding_amount=Coalesce(Sum("outstanding"), DEC_0, output_field=money_field),
        sale_total=Count("id", filter=Q(direction__in=SALE_DIRECTIONS)),
        sale_outstanding=Coalesce(Sum("outstanding", filter=Q(direction__in=SALE_DIRECTIONS)), DEC_0, output_field=money_field),
        purchase_total=Count("id", filter=Q(direction__in=PURCHASE_DIRECTIONS)),
        purchase_outstanding=Coalesce(Sum("outstanding", filter=Q(direction__in=PURCHASE_DIRECTIONS)), DEC_0, output_field=money_field),
    )
    by_direction = {
        "sale": {"total": totals["sale_total"], "outstanding_inr": money(totals["sale_outstanding"])},
        "purchase": {"total": totals["purchase_total"], "outstanding_inr": money(totals["purchase_outstanding"])},
    }

    recent = []
    for trade in trades.select_related("from_company", "to_company").order_by(
        F("invoice_date").desc(nulls_last=True), "-id",
    )[:LIST_LIMIT]:
        is_sale = trade.direction in SALE_DIRECTIONS
        party = trade.to_company if is_sale else trade.from_company
        recent.append({
            "id": trade.id,
            "invoice_number": trade.invoice_number,
            "invoice_date": _iso(trade.invoice_date),
            "direction": "sale" if is_sale else "purchase",
            "party_name": party.name if party else None,
            "total_amount_inr": money(trade.total_amount),
            "outstanding_inr": money(trade.outstanding),
            "status": _trade_status(trade.due, trade.paid_sum),
        })

    return {
        "total": totals["total"],
        "paid": totals["paid"],
        "partially_paid": totals["partially_paid"],
        "unpaid": totals["unpaid"],
        "open": totals["partially_paid"] + totals["unpaid"],
        "total_amount_inr": money(totals["total_amount"]),
        "paid_inr": money(totals["paid_amount"]),
        "outstanding_inr": money(totals["outstanding_amount"]),
        "by_direction": by_direction,
        "not_tracked": ["draft", "pending", "confirmed", "posted"],
        "recent": recent,
    }


# ---------------------------------------------------------------- attention

ATTENTION_RULES = (
    # key, section, severity
    ("expired_with_balance", "licence_portfolio", "high"),
    ("expiring_7d_usable", "licence_portfolio", "high"),
    ("missing_dgft", "licence_portfolio", "high"),
    ("over_utilised", "financial", "high"),
    ("stale_expiry_flags", "licence_portfolio", "medium"),
    ("c969_link_review", "c969_link_review", "medium"),
    ("boe_pending_licence_mapping", "boe_activity", "medium"),
    ("invoices_outstanding", "invoice_activity", "medium"),
    ("boe_without_invoice_no", "boe_activity", "low"),
)


def build_attention(sections: dict, metrics: dict | None) -> list[dict]:
    """A row appears only when its count is verified (> 0) and its section loaded without error."""
    def loaded(name):
        section = sections.get(name)
        return isinstance(section, dict) and "error" not in section

    counts = {}
    if metrics is not None:
        counts.update(metrics)
    if loaded("boe_activity"):
        counts["boe_pending_licence_mapping"] = sections["boe_activity"]["pending_licence_mapping"]
        counts["boe_without_invoice_no"] = sections["boe_activity"]["without_invoice_no"]
    if loaded("invoice_activity"):
        counts["invoices_outstanding"] = sections["invoice_activity"]["open"]
    if loaded("c969_link_review"):
        counts["c969_link_review"] = sections["c969_link_review"]["count"]

    items = []
    for key, section, severity in ATTENTION_RULES:
        if key in counts and loaded(section) and counts[key] > 0:
            items.append({"key": key, "count": counts[key], "severity": severity, "section": section})
    return items


# ---------------------------------------------------------------- orchestration

# Sections a client may request on their own (`GET /api/dashboard/?section=`). Each entry pairs
# the role gate with its builder, so the full payload and a single-section request cannot
# disagree about who sees what. The licence sections share one snapshot and are not listed.
# Builders are looked up by name at call time, not captured here, so a patched builder is what runs.
RETRYABLE_SECTIONS = {
    "allotment_activity": (ALLOTMENT_ROLES, lambda scope: build_allotment_activity(scope)),
    "boe_activity": (BOE_ROLES, lambda scope: build_boe_activity(scope)),
    "invoice_activity": (INVOICE_ROLES, lambda scope: build_invoice_activity(scope)),
}


def user_can_see(user, role_codes) -> bool:
    return user.is_superuser or user.has_any_role(list(role_codes))


def build_section_on_its_own(name: str, scope: DashboardScope) -> dict:
    """One retryable section, failure-isolated like the full payload. The caller checks the role gate."""
    _roles, builder = RETRYABLE_SECTIONS[name]
    return {name: _section(name, lambda: builder(scope))}


def build_dashboard_payload(user, scope: DashboardScope) -> dict:
    """Role-gated payload. A section is absent when the role does not grant it; never zero-filled."""
    sections: dict = {}
    licence_metrics = None

    if user_can_see(user, LICENCE_ROLES):
        snapshot = _section("licence", lambda: _licence_snapshot(scope))
        if "error" in snapshot:
            for name in ("licence_portfolio", "financial", "expiring_licences", "licence_exceptions"):
                sections[name] = snapshot
        else:
            sections["licence_portfolio"] = snapshot["portfolio"]
            sections["financial"] = snapshot["financial"]
            sections["expiring_licences"] = snapshot["expiring_licences"]
            sections["licence_exceptions"] = snapshot["exceptions"]
            licence_metrics = snapshot["metrics"]
        sections["c969_link_review"] = _c969_section()

    for name, (roles, _builder) in RETRYABLE_SECTIONS.items():
        if user_can_see(user, roles):
            sections.update(build_section_on_its_own(name, scope))

    sections["attention"] = build_attention(sections, licence_metrics)
    sections["not_monitored"] = NOT_MONITORED
    return sections


def _c969_section() -> dict:
    """Keeps the v2 shape (`count`, `rows`) on failure, so the card can say why it is empty."""
    try:
        return c969_link_mismatches()
    except Exception as exc:  # the review is read-only; isolate its failure from the rest of the page
        return {"count": 0, "rows": [], **api_error("C969 link review could not run", exc, __name__)}


def build_meta(scope: DashboardScope, *, cached: bool, generated_at) -> dict:
    return {
        "generated_at": generated_at.isoformat(),
        "as_of": scope.as_of.isoformat(),
        "as_of_timezone": timezone.get_current_timezone_name(),
        "cached": cached,
        "scope": {
            "company_id": scope.company.pk if scope.company else None,
            "company_name": scope.company.name if scope.company else None,
            "date_from": _iso(scope.date_from),
            "date_to": _iso(scope.date_to),
        },
        "units": {"cif": "FC", "invoice": "INR"},
    }


def as_of_today() -> date:
    """The business date for expiry. `timezone.localdate()` follows settings.TIME_ZONE (UTC)."""
    return timezone.localdate()


def has_error(payload: dict) -> bool:
    """True when any section failed. Such a payload is served but not cached."""
    return any(isinstance(value, dict) and "error" in value for value in payload.values())
