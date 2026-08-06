"""
License Purchase & Profit Report — service layer.

A single, acquisition-focused table — License Summary — driven entirely by
the trade ledger:

- **Purchase Amount** / **Purchase From** / **License Selection** —
  `LicenseTrade` (via `LicenseTradeLine.sr_number__license_id`),
  `direction=PURCHASE`, `linked_trade__isnull=True`. A trade's
  `linked_trade` FK is set on BOTH sides of an auto-created paired
  counterpart (see `apps.trade.serializers`'s `auto_create_paired` flow) —
  an internal transfer between two of the business's own companies, not a
  genuine external market purchase. Excluding `linked_trade__isnull=False`
  on either side keeps both an internal PURCHASE leg and its mirrored SALE
  leg out of "Purchase Amount"/"first purchase date"/"Purchase From".
  `LicensePurchase` (the simple supplier-invoice model) is NOT used
  anywhere in this report — it remains available elsewhere for invoice
  management/audit only.
- **License Selection** — a license qualifies only when its EARLIEST
  qualifying (external, non-internal) PURCHASE trade's `invoice_date`
  falls within `[from_date, to_date]`. Once a license qualifies, its
  Purchase Amount is its FULL lifecycle total (not date-filtered) — buying
  a license is a one-time acquisition event.
- **Purchase $** — `LicenseTradeLine.cif_fc` (the line's foreign-currency/
  USD CIF value, entered alongside `exc_rate`/`cif_inr` regardless of the
  line's billing `mode` — see `LicenseTradeLine`/`purchase_invoice_pdf.py`),
  summed across the SAME qualifying external purchase trades as Purchase
  Amount. This is the purchased dollar value, NOT
  `LicenseImportItemsModel.cif_fc` (the license's original allocated CIF)
  — that field is no longer shown in this report.
- **Purchase From** — `LicenseTrade.from_company.name` of the EARLIEST
  qualifying external purchase trade (the same row that determines
  first-purchase-date/License Selection) — the supplier the license was
  originally acquired from. Sourced as a side-effect of the single ordered
  pass described below, never a second query.
- **Trade Balance ($)** — `Purchase $ − Sale $` (Original/acquired CIF $
  minus Debited/utilized CIF $), computed directly from this report's OWN
  `purchase_usd`/`sale_usd` figures — NOT delegated to
  `LicenseBalanceCalculator.calculate_financial_balance_for_licenses`
  (`apps.license.services.balance_calculator`). That calculator computes
  the license-wide "Balance CIF" shown in Item Pivot Report and elsewhere —
  a different, broader concept that also factors in Bill-of-Entry debits,
  allotments, and an opening-balance anchor, none of which this report
  tracks or displays anywhere else. This report's figure is deliberately
  named and scoped differently (`trade_balance_usd`, not `balance_cif`) so
  it is never mistaken for that license-wide balance: using the calculator
  here would silently diverge from this report's own Purchase $/Sale $
  columns (e.g. `Purchase $ − Sale $` on screen would NOT equal a
  "Balance CIF" column next to it). Trade Balance ($) here is deliberately
  this report's own, narrower, self-consistent figure: the same `sale_usd`
  (SALE-direction trade-ledger debit) already computed for the Sale $
  column, subtracted from the same `purchase_usd` already computed for the
  Purchase $ column — both raw (unquantized) Decimals, subtracted once,
  quantized once, matching this file's usual double-rounding-avoidance
  rule.
- **Exporter** — `LicenseDetailsModel.exporter.name`, the same company
  shown throughout the License module.
- **Norm(s)** — every distinct `LicenseExportItemModel.norm_class.norm_class`
  attached to the license (its RAW SION code, not bucketed into a
  CONVERSION_NORMS/"Others" pair the way the `norm` filter parameter is) —
  sorted numerically by the digits following the "E" prefix (E1, E5, E76,
  E98, E126, E132 — the order a business user expects, not a plain string
  sort, which would misorder different-length codes) and deduplicated.

There is no per-item, per-norm, or grand-total breakdown in this report —
`norm` remains a FILTER parameter only (narrows which licenses qualify via
`_base_license_queryset`), never an output grouping. The `summary` block
IS a grand total across the returned `licenses` rows (total_licenses/
purchase_amount/purchase_usd/trade_balance_usd/total_sale_usd/total_sale_amount/
total_profit_loss) — computed by summing the same Decimal maps used to
build each row, quantized once at the end, so it never compounds per-row
float rounding across many licenses.

Purchase Amount/Purchase $/first-purchase-date/Purchase From all come from
ONE ordered, non-aggregated bulk query over `LicenseTradeLine` (see
`build_purchase_profit_report`) — a single Python pass over rows ordered by
`(license_id, invoice_date, trade_id)` accumulates running sums and grabs
the first row seen per license, replacing what used to be three separate
`Min`/`Sum`/`Sum` `.annotate()` aggregates. This is still one query total
(no per-license DB hit), and it naturally solves "supplier from the
earliest purchase" without a second query or a window function.

- **Sale Amount** / **Sale $** / **Profit / Loss** — the disposal-side
  counterpart of Purchase Amount/Purchase $: `LicenseTradeLine.amount_inr`/
  `cif_fc` summed across the SAME `direction=SALE`,
  `linked_trade__isnull=True` qualifying trades the Item Utilization
  Matrix's debit lines are also drawn from (see `sale_agg` below), and
  `profit_loss = sale_amount - purchase_amount`. **Deliberately computed
  via its OWN plain `.values("sr_number__license_id").annotate(Sum(...))`
  aggregate, grouped by license only — never by summing across the
  item-matrix's `debit_qty`/`debit_cif`/`debit_bill` dicts.** Those dicts
  intentionally duplicate a SALE line's full amount across EVERY
  `ItemNameModel` its Import Item maps to (see "Multi-name attribution"
  below) — a correct DISPLAY convention for that pivot table, but adding
  those per-header numbers back up would double- (or triple-, etc.) count
  any license with a multi-item-name Import Item, silently overstating
  Sale Amount/Sale $ and therefore Profit/Loss for exactly those licenses.
  Sale Amount/Sale $ are real, undivided financial figures that feed
  directly into Profit/Loss, so they're sourced straight from the ledger,
  summed once per trade line, independent of how many item names any
  Import Item happens to have. This does mean SALE-direction
  `LicenseTradeLine` rows are queried twice in this function (once here,
  once again for `debit_lines` below) — an accepted, deliberate tradeoff:
  one query answers "per-license total," the other "per-license-per-item
  breakdown," and merging them risks reintroducing the double-counting bug
  this separation avoids. The grand `total_profit_loss` in `summary`
  follows the same rule as every other grand total in this file: computed
  from the raw running `total_sale_amount`/`total_purchase_amount` Decimal
  sums and quantized once, never by summing the individual rows'
  already-rounded `profit_loss` floats.

Dynamic Import Item Utilization Matrix (`item_matrix`)
-------------------------------------------------------
A second, pivot-style section: for each qualifying license, how much of
each purchased Import Item has been DEBITED (qty/CIF $/Bill ₹), with one
dynamic column per Import Item name.

- **Headers** — sourced ENTIRELY from `apps.core.models.ItemNameModel`
  names attached (via `LicenseImportItemsModel.items`, M2M
  `related_name="license_import_item"`) to any qualifying license's Import
  Items — NOT from the trade data used to populate the cells. Sorted
  case-insensitively (`sorted(names, key=str.upper)`) and deduplicated.
  A license with an Import Item but zero debit still gets a column entry
  for that item's name, zero-filled.
- **Cell values (qty/cif/bill)** — sourced from `LicenseTradeLine` rows
  with `trade__direction=LicenseTrade.DIR_SALE` and
  `trade__linked_trade__isnull=True`: the DEBIT-side counterpart of this
  same report's Purchase Amount/Purchase $ (which reads
  `direction=PURCHASE`), excluding internal/mirror SALE trades for the
  identical reason internal PURCHASE trades are excluded there — an
  internal transfer between the business's own companies is not a genuine
  utilization event. This is a DIFFERENT concept from
  `LicenseImportItemsModel.debited_quantity`/`debited_value`
  (Bill-of-Entry/customs physical-import utilization, used by
  `ItemPivotReportView`) — never conflate the two or reuse that view's
  fields here.
- **Multi-name attribution** — an Import Item with 2+ `ItemNameModel`s
  attached contributes its FULL debit (qty/cif/bill) to EVERY one of its
  header columns, never split — matching `item_pivot_report.py`'s existing
  multi-name attribution convention.
- **Totals** — `item_matrix["totals"][header]` is Decimal-summed across
  all rows for that header and quantized ONCE at the end, the same
  double-rounding-avoidance approach the top-level `summary` totals use.
  These per-header totals deliberately do NOT feed the top-level
  `summary` block (see "Sale Amount / Sale $ / Profit / Loss" above) —
  summing them would double-count whenever a multi-item-name Import Item
  exists. `summary.total_sale_usd`/`total_sale_amount` are a SEPARATE,
  correctly-computed figure from the independent `sale_agg` query, not a
  rollup of these per-header totals.
- Built from exactly 3 bulk queries (headers, Import-Item→name map, SALE
  debit lines) — no per-license DB hit, consistent with this file's
  existing "never loop-and-query per license" rule.
- **Dynamic Column Optimization** — after the Grand Total for every header
  is known, any header whose Grand Total Qty/CIF $/Bill are ALL zero is
  dropped entirely from `headers`, from every row's `items`, and from
  `totals` — never based on any single license's row, only the Grand Total.
  Decided once here; Web/API/Excel/PDF all render whatever `headers` this
  function returns and never re-decide visibility themselves.
"""
from __future__ import annotations

import re
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.db.models import DecimalField, Sum, Value
from django.db.models.functions import Coalesce

from apps.core.constants import DEC_0
from apps.core.models import ItemNameModel
from apps.core.reports.envelope import validate_envelope
from apps.license.models import LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel
from apps.trade.models import LicenseTrade, LicenseTradeLine

# Mirrors the frontend's `NormCardGrid.tsx:22` convention — the four DFIA
# conversion norms recognized by the `norm` FILTER parameter; anything else
# with a norm_class is "Others". Licenses with NO norm_class at all
# (Incentive-scheme licenses) are out of scope for this report entirely.
# The "Norm(s)" DISPLAY column (see `_norms_by_license`) shows every raw
# norm_class code instead — it is never bucketed into "Others".
CONVERSION_NORMS = {"E1", "E5", "E126", "E132"}
OTHERS = "Others"

TWO_PLACES = Decimal("0.01")


def _q2(value) -> Decimal:
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _norm_sort_key(norm_class: str) -> tuple:
    """Numeric sort by the digits following the 'E' prefix (E1 < E5 < E76 <
    E98 < E126 < E132) rather than a plain string sort, which would put
    "E126" before "E5" purely on shorter-prefix ordering."""
    m = re.match(r"^[A-Za-z]*(\d+)$", norm_class or "")
    return (int(m.group(1)), norm_class) if m else (float("inf"), norm_class)


def _empty_report() -> Dict[str, Any]:
    return {
        "summary": {
            "total_licenses": 0,
            "purchase_amount": 0.0,
            "purchase_usd": 0.0,
            "trade_balance_usd": 0.0,
            "total_sale_usd": 0.0,
            "total_sale_amount": 0.0,
            "total_profit_loss": 0.0,
        },
        "licenses": [],
        "item_matrix": {"headers": [], "rows": [], "totals": {}},
    }


def _as_list(value) -> Optional[List]:
    """
    Normalize a filter value that may arrive as a single scalar (existing
    single-select call sites) or a list/tuple/set (multi-select call sites)
    into `Optional[List]` — `None`/`""` stays `None` (no filter), a bare
    scalar becomes a one-item list, a collection passes through unchanged
    (falsy entries stripped).
    """
    if value is None or value == "":
        return None
    if isinstance(value, (list, tuple, set)):
        cleaned = [v for v in value if v not in (None, "")]
        return cleaned or None
    return [value]


def _normalize_norm_selection(norm) -> tuple:
    """
    Returns `(is_all, norm_buckets)`. `is_all=True` means no norm
    restriction at all (norm was falsy/"All"/absent, or the multi-select
    included "All"), matching the historical single-value "All" behaviour.
    Otherwise `norm_buckets` is the set of selected bucket names, each
    either a `CONVERSION_NORMS` code or `OTHERS`.
    """
    values = _as_list(norm) or []
    if not values or "All" in values:
        return True, set()
    return False, set(values)


def _base_license_queryset(
    norm,
    license_number,
    exporter_id,
    exclude_license_numbers=None,
):
    """
    `norm`, `license_number`, `exporter_id` each accept either a single
    scalar (original single-select contract, unchanged behaviour) or a
    list of scalars (multi-select contract). `exclude_license_numbers` is
    multi-select only — always an exact `__in` exclude, applied last so it
    wins over an overlapping `license_number` inclusion.
    """
    qs = LicenseDetailsModel.objects.all()

    exporter_ids = _as_list(exporter_id)
    if exporter_ids:
        qs = qs.filter(exporter_id__in=exporter_ids)

    license_numbers = _as_list(license_number)
    if license_numbers:
        if len(license_numbers) == 1:
            # Single value preserves the original "search box" contains
            # semantics; 2+ values is a multi-select of exact numbers.
            qs = qs.filter(license_number__icontains=license_numbers[0])
        else:
            qs = qs.filter(license_number__in=license_numbers)

    exclude_numbers = _as_list(exclude_license_numbers)
    if exclude_numbers:
        qs = qs.exclude(license_number__in=exclude_numbers)

    is_all, norm_buckets = _normalize_norm_selection(norm)
    if is_all:
        # "All" (default) and any unrecognized value collapse to "All"
        # semantics: still requires SOME norm class — licenses with no norm
        # class at all are out of scope for this report per the plan.
        qs = qs.filter(export_license__norm_class__isnull=False)
    else:
        conversion_selected = norm_buckets & CONVERSION_NORMS
        others_selected = OTHERS in norm_buckets
        # Each bucket's qualifying pk set is computed against its own
        # `.filter()`/`.exclude()` chain off `qs` (never combined into one
        # `Q` expression): "Others" specifically needs `.exclude()`'s
        # NOT-EXISTS semantics ("this license has NO conversion-norm export
        # item at all") which a `~Q(...)` join can't reproduce — `~Q` only
        # excludes the individual joined row, so a license with BOTH an E1
        # and an "Others" export item would wrongly re-qualify for
        # "Others" via its non-E1 row. Union the pk sets in Python instead.
        candidate_pks = set()
        if conversion_selected:
            candidate_pks |= set(
                qs.filter(export_license__norm_class__norm_class__in=conversion_selected)
                .values_list("pk", flat=True)
            )
        if others_selected:
            candidate_pks |= set(
                qs.filter(export_license__norm_class__isnull=False)
                .exclude(export_license__norm_class__norm_class__in=CONVERSION_NORMS)
                .values_list("pk", flat=True)
            )
        qs = qs.filter(pk__in=candidate_pks) if (conversion_selected or others_selected) else qs.none()

    # export_license is a reverse FK (one license -> many export items),
    # so the norm-class filters above can multiply-join; distinct() collapses back to one row per license.
    return qs.distinct()


def _norms_by_license(license_ids: List[int]) -> Dict[int, List[str]]:
    """Every distinct raw SION norm_class code attached to each license,
    sorted numerically and deduplicated (see `_norm_sort_key`)."""
    raw: Dict[int, set] = defaultdict(set)
    for row in (
        LicenseExportItemModel.objects.filter(license_id__in=license_ids, norm_class__isnull=False)
        .values("license_id", "norm_class__norm_class")
        .distinct()
    ):
        raw[row["license_id"]].add(row["norm_class__norm_class"])
    return {lid: sorted(codes, key=_norm_sort_key) for lid, codes in raw.items()}


def build_purchase_profit_report(
    from_date,
    to_date,
    norm: str = "All",
    license_number: Optional[str] = None,
    exporter_id: Optional[int] = None,
    exclude_license_number=None,
) -> Dict[str, Any]:
    base_qs = _base_license_queryset(
        norm, license_number, exporter_id, exclude_license_numbers=exclude_license_number,
    )
    base_license_ids = list(base_qs.values_list("id", flat=True))
    if not base_license_ids:
        return _empty_report()

    # --- Purchase Amount (INR) + Purchase $ (USD/FC) + first qualifying
    # purchase date + Purchase From, from the trade ledger only, in ONE
    # ordered, non-aggregated bulk query + a single Python pass. Excludes
    # internal linked/auto-generated mirror entries
    # (`linked_trade__isnull=True` on both legs of a paired internal
    # transfer — see module docstring). Full lifecycle, never
    # date-filtered — buying a license is a one-time event. Ordering by
    # `(license_id, invoice_date, trade_id)` means the first row seen per
    # license IS its earliest qualifying purchase — that same row's
    # `from_company__name` is "Purchase From", with no second query. ------
    purchase_lines = (
        LicenseTradeLine.objects.filter(
            sr_number__license_id__in=base_license_ids,
            trade__direction=LicenseTrade.DIR_PURCHASE,
            trade__linked_trade__isnull=True,
        )
        .order_by("sr_number__license_id", "trade__invoice_date", "trade_id")
        .values(
            "sr_number__license_id",
            "trade_id",
            "trade__invoice_date",
            "trade__from_company__name",
            "amount_inr",
            "cif_fc",
        )
    )

    purchase_amount_by_license: Dict[int, Decimal] = {}
    purchase_usd_by_license: Dict[int, Decimal] = {}
    first_purchase_date_by_license: Dict[int, Any] = {}
    purchase_from_by_license: Dict[int, str] = {}
    for row in purchase_lines:
        lid = row["sr_number__license_id"]
        purchase_amount_by_license[lid] = (
            purchase_amount_by_license.get(lid, DEC_0) + (row["amount_inr"] or DEC_0)
        )
        purchase_usd_by_license[lid] = (
            purchase_usd_by_license.get(lid, DEC_0) + (row["cif_fc"] or DEC_0)
        )
        if lid not in first_purchase_date_by_license:
            # First row seen for this license_id, given the ordering above,
            # IS its earliest qualifying purchase trade.
            first_purchase_date_by_license[lid] = row["trade__invoice_date"]
            purchase_from_by_license[lid] = row["trade__from_company__name"] or ""

    qualifying_license_ids = [
        lid
        for lid, first_date in first_purchase_date_by_license.items()
        if first_date is not None and from_date <= first_date <= to_date
    ]
    if not qualifying_license_ids:
        return _empty_report()

    # --- Sale Amount (INR) + Sale $ (USD/FC): the disposal-side counterpart
    # of Purchase Amount/Purchase $ above, from a plain per-license
    # `.annotate(Sum())` aggregate over the SAME `direction=SALE`,
    # `linked_trade__isnull=True` qualifying trades the Item Utilization
    # Matrix's `debit_lines` below also reads. Deliberately NOT derived from
    # `debit_qty`/`debit_cif`/`debit_bill` (built later, per (license, item
    # name)) — those dicts intentionally duplicate a multi-item-name Import
    # Item's full debit across every header it maps to, which would
    # double-count Sale Amount/Sale $ for any such license. See module
    # docstring for the full rationale. --------------------------------
    sale_agg = (
        LicenseTradeLine.objects.filter(
            sr_number__license_id__in=qualifying_license_ids,
            trade__direction=LicenseTrade.DIR_SALE,
            trade__linked_trade__isnull=True,
        )
        .values("sr_number__license_id")
        .annotate(
            sale_amount=Coalesce(Sum("amount_inr"), Value(DEC_0), output_field=DecimalField()),
            sale_usd=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=DecimalField()),
        )
    )
    sale_amount_by_license = {r["sr_number__license_id"]: r["sale_amount"] for r in sale_agg}
    sale_usd_by_license = {r["sr_number__license_id"]: r["sale_usd"] for r in sale_agg}

    norms_by_license = _norms_by_license(qualifying_license_ids)

    license_lookup = {
        lic.id: lic
        for lic in LicenseDetailsModel.objects.filter(id__in=qualifying_license_ids)
        .select_related("exporter")
    }

    # --- License Summary: one flat row per qualifying license, plus a
    # `summary` grand total computed from the same Decimal maps (summed
    # before a single final quantize+float, so it never compounds
    # already-rounded-float error across many rows). ----------------------
    licenses: List[dict] = []
    license_id_by_number: Dict[str, int] = {}
    total_purchase_amount = DEC_0
    total_purchase_usd = DEC_0
    total_trade_balance_usd = DEC_0
    total_sale_amount = DEC_0
    total_sale_usd = DEC_0
    for license_id in qualifying_license_ids:
        lic = license_lookup.get(license_id)
        if lic is None:
            continue
        purchase_amount = purchase_amount_by_license.get(license_id, DEC_0)
        purchase_usd = purchase_usd_by_license.get(license_id, DEC_0)
        sale_amount = sale_amount_by_license.get(license_id, DEC_0)
        sale_usd = sale_usd_by_license.get(license_id, DEC_0)
        profit_loss = sale_amount - purchase_amount
        # Trade Balance ($) = Purchase $ − Sale $ (Original/acquired CIF $
        # minus Debited/utilized CIF $) — this report's OWN figures, never
        # the broader `LicenseBalanceCalculator` engine. See module
        # docstring for why.
        trade_balance_usd = purchase_usd - sale_usd
        total_purchase_amount += purchase_amount
        total_purchase_usd += purchase_usd
        total_trade_balance_usd += trade_balance_usd
        total_sale_amount += sale_amount
        total_sale_usd += sale_usd
        license_id_by_number[lic.license_number] = license_id
        licenses.append(
            {
                "license_number": lic.license_number,
                "license_date": lic.license_date.isoformat() if lic.license_date else None,
                "expiry_date": lic.license_expiry_date.isoformat() if lic.license_expiry_date else None,
                "exporter": (lic.exporter.name if lic.exporter_id else "") or "",
                "norms": norms_by_license.get(license_id, []),
                "purchase_from": purchase_from_by_license.get(license_id, ""),
                "purchase_amount": float(_q2(purchase_amount)),
                "purchase_usd": float(_q2(purchase_usd)),
                "sale_amount": float(_q2(sale_amount)),
                "sale_usd": float(_q2(sale_usd)),
                "profit_loss": float(_q2(profit_loss)),
                "trade_balance_usd": float(_q2(trade_balance_usd)),
            }
        )
    licenses.sort(key=lambda r: r["license_number"])

    # ----------------------------------------------------------------------
    # Dynamic Import Item Utilization Matrix — see module docstring for the
    # full rationale. Headers come from Import Items (independent of the
    # trade-sourced cell values below); cell values come from SALE-direction
    # trade-ledger debits, the debit-side counterpart of Purchase Amount/
    # Purchase $ above. 3 bulk queries total, no per-license DB hit.
    # ----------------------------------------------------------------------
    headers = sorted(
        ItemNameModel.objects.filter(
            license_import_item__license_id__in=qualifying_license_ids
        ).values_list("name", flat=True).distinct(),
        key=str.upper,
    )

    # Import Item -> its attached Item Name(s). An Import Item's `items` M2M
    # can carry multiple names; each contributes below to ALL of them.
    item_names_by_import_item: Dict[int, List[str]] = defaultdict(list)
    for row in (
        LicenseImportItemsModel.objects.filter(license_id__in=qualifying_license_ids)
        .values("id", "license_id", "items__name")
    ):
        name = row["items__name"]
        if name:
            item_names_by_import_item[row["id"]].append(name)

    # SALE-direction debit lines, excluding internal linked/mirror trades —
    # same exclusion rationale as the PURCHASE query above, mirrored for the
    # debit side. Ordered for consistency with the purchase-lines query
    # above; aggregation itself is order-independent.
    debit_lines = (
        LicenseTradeLine.objects.filter(
            sr_number__license_id__in=qualifying_license_ids,
            trade__direction=LicenseTrade.DIR_SALE,
            trade__linked_trade__isnull=True,
        )
        .order_by("sr_number__license_id", "trade__invoice_date", "trade_id")
        .values("sr_number_id", "sr_number__license_id", "qty_kg", "cif_fc", "amount_inr")
    )

    debit_qty: Dict[tuple, Decimal] = defaultdict(lambda: DEC_0)
    debit_cif: Dict[tuple, Decimal] = defaultdict(lambda: DEC_0)
    debit_bill: Dict[tuple, Decimal] = defaultdict(lambda: DEC_0)
    for row in debit_lines:
        item_names = item_names_by_import_item.get(row["sr_number_id"]) or []
        if not item_names:
            continue
        lid = row["sr_number__license_id"]
        qty = row["qty_kg"] or DEC_0
        cif = row["cif_fc"] or DEC_0
        bill = row["amount_inr"] or DEC_0
        # Full debit attributed to EVERY header the import item maps to —
        # never split — matching item_pivot_report.py's own convention.
        for name in item_names:
            key = (lid, name)
            debit_qty[key] += qty
            debit_cif[key] += cif
            debit_bill[key] += bill

    item_matrix_rows_all: List[dict] = []
    totals_qty: Dict[str, Decimal] = {h: DEC_0 for h in headers}
    totals_cif: Dict[str, Decimal] = {h: DEC_0 for h in headers}
    totals_bill: Dict[str, Decimal] = {h: DEC_0 for h in headers}
    for license_row in licenses:
        license_id = license_id_by_number.get(license_row["license_number"])
        items_cell: Dict[str, dict] = {}
        for header in headers:
            key = (license_id, header)
            qty = debit_qty.get(key, DEC_0)
            cif = debit_cif.get(key, DEC_0)
            bill = debit_bill.get(key, DEC_0)
            items_cell[header] = {
                "qty": float(qty),
                "cif": float(_q2(cif)),
                "bill": float(_q2(bill)),
            }
            totals_qty[header] += qty
            totals_cif[header] += cif
            totals_bill[header] += bill
        item_matrix_rows_all.append({**license_row, "items": items_cell})

    # Dynamic Column Optimization — an Import Item column group is dropped
    # entirely when its GRAND TOTAL (never an individual license's row) is
    # zero across all three sub-columns (Qty/CIF $/Bill). Decided once, here,
    # right after the Grand Total is known, so every renderer (Web/API/
    # Excel/PDF) receives the same already-pruned `headers`/`rows`/`totals`
    # — none of them run their own visibility logic.
    kept_headers = [
        h for h in headers
        if totals_qty[h] != DEC_0 or totals_cif[h] != DEC_0 or totals_bill[h] != DEC_0
    ]

    item_matrix_rows = [
        {**row, "items": {h: row["items"][h] for h in kept_headers}}
        for row in item_matrix_rows_all
    ]
    item_matrix_totals = {
        header: {
            "qty": float(totals_qty[header]),
            "cif": float(_q2(totals_cif[header])),
            "bill": float(_q2(totals_bill[header])),
        }
        for header in kept_headers
    }
    item_matrix = {
        "headers": kept_headers,
        "rows": item_matrix_rows,
        "totals": item_matrix_totals,
    }

    # Grand Profit/Loss from the raw (unquantized) running Decimal totals,
    # quantized ONCE here — never by summing the individual rows'
    # already-rounded `profit_loss` floats (same double-rounding-avoidance
    # approach as every other grand total in this file).
    total_profit_loss = total_sale_amount - total_purchase_amount

    summary = {
        "total_licenses": len(licenses),
        "purchase_amount": float(_q2(total_purchase_amount)),
        "purchase_usd": float(_q2(total_purchase_usd)),
        "trade_balance_usd": float(_q2(total_trade_balance_usd)),
        "total_sale_usd": float(_q2(total_sale_usd)),
        "total_sale_amount": float(_q2(total_sale_amount)),
        "total_profit_loss": float(_q2(total_profit_loss)),
    }
    report_data = {"summary": summary, "licenses": licenses, "item_matrix": item_matrix}
    if settings.DEBUG:
        # Debug/test-only shape guard — never raises for a real production
        # request. See apps/core/reports/envelope.py.
        validate_envelope(
            report_data, 'licenses',
            required_summary_keys={'total_licenses', 'purchase_usd', 'trade_balance_usd'},
        )
    return report_data
