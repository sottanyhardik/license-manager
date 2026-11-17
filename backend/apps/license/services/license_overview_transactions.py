"""
License Overview — grouped BOE / Allotment transactions
(`GET licenses/<id>/overview-transactions/`).

Spec: `docs/modernization/frontend-audit/06_UNIFIED_LICENCE_WORKSPACE.md` §7.4.
Owner decisions (`docs/modernization/DECISION_REGISTER.md`):

* OD-BA-a — supplier = the transaction's own ``company`` FK, for BOEs
  (``BillOfEntryModel.company``) and allotments (``AllotmentModel.company``).
  ``related_company`` is not used.
* OD-BA-b — group strictly by ``company_id``. No name-based merging. A null
  company is its own explicit "No supplier recorded" group.
* OD-BA-c — product key (L2) = the licence import item (SR) the line is drawn
  against. Canonical names (``LicenseImportItemsModel.items``) are display
  only and are fetched separately, never joined into an aggregate (F5), so an
  SR with several canonical names is counted once. An SR with no canonical
  name keeps its own SR key and is labelled "Unmapped product" (F4).
* D4 — never merge suppliers, keep every record, and never add quantities of
  different units (per-unit subtotals; unit = exact string of the SR's unit).

Line grain (each source line classified exactly once):

* BOE line = ``RowDetails`` grouped by (``bill_of_entry_id``, ``sr_number_id``,
  ``transaction_type``). ``transaction_type`` is part of the key so a BOE that
  carries both CREDIT and DEBIT rows on one SR (F9) never mixes them; without
  such rows this is exactly the (BOE, SR) grain. (The DB unique constraint on
  those three columns means each line is in practice one ``RowDetails`` row;
  the grouping is kept so the grain does not depend on that constraint.) Base queryset and filters are
  the ones ``license_overview_boes.list_boe_rows`` uses: licence-scoped via
  ``sr_number__license``, previous-owner hidden BOEs excluded with the same
  ``annotate_and_exclude_hidden`` helper, rows without a BOE dropped.
* Allotment line = one ``AllotmentItems`` row (``item__license`` filter and
  "linked to BOE" = the real ``BillOfEntryModel.allotment`` M2M, both as in
  ``license_overview_allotments.list_allotment_rows``). Several rows for one
  (allotment, SR) stay separate (F12), each with its ``allocation_basis``.

Summaries are computed in SQL (``GROUPING SETS`` over the line subquery) and
are PARTITIONED — never combined across buckets:

* BOE buckets per ``transaction_type``;
* allotment buckets per (``allotment_type``, ``allocation_basis``,
  ``is_linked_to_boe``);
* each bucket: ``record_count`` (distinct records), ``line_count``, ``cif_fc``
  and ``qty_by_unit``.

Headline CIF figures are documented per response in ``cif_basis`` (see
``CIF_BASIS``). They are display aggregates scoped by the request filters and
are NOT balance figures; none is taken from or reconciled to the balance
engine. No available/balance quantity or any derived quantity is produced:
quantity semantics are not approved.

Status strings mirror ``license_overview_boes._boe_status`` (evaluated per
BOE line) and ``license_overview_allotments._allotment_status`` as SQL
``CASE`` expressions, so the ``status`` filter and the summaries stay in SQL.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from django.contrib.postgres.aggregates import BoolOr
from django.contrib.postgres.expressions import ArraySubquery
from django.db import connections
from django.db.models import (
    Case, CharField, Count, DecimalField, Exists, F, Min, OuterRef, Q,
    Subquery, Sum, Value, When,
)
from django.db.models.functions import Cast, Coalesce, Concat, Greatest

from apps.allotment.models import AllotmentItems
from apps.bill_of_entry.models import BillOfEntryModel, RowDetails, annotate_and_exclude_hidden
from apps.core.constants import DEBIT, DEC_0, DEC_000
from apps.core.models import CompanyModel
from apps.license.models import LicenseImportItemsModel

RECORD_TYPE_BOE = "BOE"
RECORD_TYPE_ALLOTMENT = "ALLOTMENT"
RECORD_TYPES = (RECORD_TYPE_BOE, RECORD_TYPE_ALLOTMENT)

NO_SUPPLIER_LABEL = "No supplier recorded"
UNMAPPED_PRODUCT_LABEL = "Unmapped product"
SUPPLIER_SOURCE = "company"
NULL_SUPPLIER_PARAM = "null"

CIF_BASIS = {
    "boe_debit_cif": (
        "Raw cif_fc of non-hidden DEBIT RowDetails lines (same basis as the customs "
        "LicenseBalanceCalculator.calculate_boe_debit_total). NOT the financial calculate_debit "
        "used by get_balance_cif: invoice/SALE allocations are not netted."
    ),
    "unlinked_allotment_cif": (
        "Raw cif_fc of AllotmentItems lines whose allotment has no BillOfEntry M2M link. NOT "
        "allocation-netted: active BOEAllotmentAllocation amounts (partial or cross-SR) are not "
        "subtracted, so it can exceed the engine's calculate_allotment."
    ),
    "linked_allotment_cif": (
        "Raw cif_fc of AllotmentItems lines whose allotment has at least one BillOfEntry M2M link. "
        "Shown separately; part of neither figure above."
    ),
    "exclusions": [
        "Previous-owner hidden BOEs (same rule as overview-boes/).",
        "RowDetails without a bill of entry.",
        "AllotmentItems with a null allotment (the engine's calculate_allotment still counts them).",
    ],
    "scope": "All figures are scoped by the request filters (search, record_type, status, dates) "
             "and are display aggregates, not balance figures.",
}

PAGE_SIZE_DEFAULT = 25
PAGE_SIZE_MAX = 200

# Public ordering name -> column of the unified record subquery.
ORDERING_FIELDS = {
    "date": "date",
    "record_number": "record_number",
    "record_type": "record_type",
    "cif_fc": "cif_fc",
    "qty": "qty",
    "status": "status",
}
DEFAULT_ORDERING = "-date"

_ALLOC_FIELD = DecimalField(max_digits=20, decimal_places=3)
_SUM_FIELD = DecimalField(max_digits=20, decimal_places=3)


class TransactionQueryError(ValueError):
    """Invalid query parameter; ``field`` names the offending parameter."""

    def __init__(self, field: str, message: str):
        super().__init__(message)
        self.field = field
        self.message = message


@dataclass(frozen=True)
class TransactionFilters:
    search: str = ""
    record_type: Optional[str] = None
    status: Optional[str] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None


# ---------------------------------------------------------------------------
# Line querysets
# ---------------------------------------------------------------------------

def _canonical_name_hit(sr_ref: str, search: str):
    """Exists() on the SR's canonical names — never a JOIN (F5 fan-out)."""
    through = LicenseImportItemsModel.items.through
    return Exists(
        through.objects.filter(
            licenseimportitemsmodel_id=OuterRef(sr_ref),
            itemnamemodel__name__icontains=search,
        )
    )


def _linked_to_boe(allotment_ref: str):
    through = BillOfEntryModel.allotment.through
    return Exists(through.objects.filter(allotmentmodel_id=OuterRef(allotment_ref)))


def boe_lines(license_obj, filters: TransactionFilters, *, supplier=None, product_key=None,
              with_details: bool = False):
    """BOE line queryset (``.values()`` rows, one per BOE x SR x type)."""
    from apps.reconciliation.models import BOEAllotmentAllocation

    rows = annotate_and_exclude_hidden(
        RowDetails.objects.filter(sr_number__license=license_obj, bill_of_entry__isnull=False),
        boe_field="bill_of_entry",
    )
    if filters.date_from:
        rows = rows.filter(bill_of_entry__bill_of_entry_date__gte=filters.date_from)
    if filters.date_to:
        rows = rows.filter(bill_of_entry__bill_of_entry_date__lte=filters.date_to)
    if filters.search:
        s = filters.search
        rows = rows.annotate(_name_hit=_canonical_name_hit("sr_number_id", s)).filter(
            Q(bill_of_entry__bill_of_entry_number__icontains=s)
            | Q(bill_of_entry__company__name__icontains=s)
            | Q(bill_of_entry__invoice_no__icontains=s)
            | Q(sr_number__description__icontains=s)
            | Q(_name_hit=True)
        )
    if supplier is not None:
        rows = rows.filter(**_supplier_lookup("bill_of_entry__company_id", supplier))
    if product_key is not None:
        rows = rows.filter(sr_number_id=product_key)

    # Same per-row allotment-side remaining-CIF formula as list_boe_rows.
    allocated_subquery = (
        BOEAllotmentAllocation.objects.filter(
            row_details_id=OuterRef("pk"),
            status=BOEAllotmentAllocation.STATUS_ACTIVE,
            is_current=True,
        )
        .order_by()
        .values("row_details_id")
        .annotate(total=Sum("allocated_cif_fc"))
        .values("total")
    )
    rows = rows.annotate(
        _allocated=Coalesce(
            Subquery(allocated_subquery, output_field=_ALLOC_FIELD), Value(DEC_0), output_field=_ALLOC_FIELD,
        )
    ).annotate(
        _remaining_row=Greatest(F("cif_fc") - F("_allocated"), Value(DEC_0), output_field=_ALLOC_FIELD)
    )

    keys = {
        "l_record_id": F("bill_of_entry_id"),
        "l_product_key": F("sr_number_id"),
        "l_tt": F("transaction_type"),
        "l_company_id": F("bill_of_entry__company_id"),
        "l_unit": F("sr_number__unit"),
    }
    if with_details:
        keys.update({
            "l_number": F("bill_of_entry__bill_of_entry_number"),
            "l_date": F("bill_of_entry__bill_of_entry_date"),
            "l_company_name": F("bill_of_entry__company__name"),
            "l_port": F("bill_of_entry__port__name"),
            "l_invoice_no": F("bill_of_entry__invoice_no"),
            "l_invoice_date": F("bill_of_entry__invoice_date"),
        })
    lines = (
        rows.order_by()
        .values(**keys)
        .annotate(
            l_line_id=Min("id"),
            l_source_rows=Count("id"),
            l_cif=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=_SUM_FIELD),
            l_qty=Coalesce(Sum("qty"), Value(DEC_000), output_field=_SUM_FIELD),
            l_remaining=Coalesce(Sum("_remaining_row"), Value(DEC_0), output_field=_SUM_FIELD),
            l_any_frozen=BoolOr("is_frozen"),
            l_any_dispute=BoolOr("is_dispute"),
        )
        .annotate(
            # Mirrors license_overview_boes._boe_status (Dispute > Frozen >
            # remaining-CIF-driven), evaluated at line grain.
            l_status=Case(
                When(l_any_dispute=True, then=Value("Dispute")),
                When(l_any_frozen=True, then=Value("Frozen")),
                When(l_remaining__lte=DEC_0, then=Value("Reconciled")),
                default=Value("Pending"),
                output_field=CharField(),
            )
        )
    )
    if filters.status:
        lines = lines.filter(l_status=filters.status)
    return lines


def allotment_lines(license_obj, filters: TransactionFilters, *, supplier=None, product_key=None,
                    with_details: bool = False):
    """Allotment line queryset (``.values()`` rows, one per AllotmentItems row)."""
    rows = AllotmentItems.objects.filter(item__license=license_obj, allotment__isnull=False)
    if filters.date_from:
        rows = rows.filter(allotment__estimated_arrival_date__gte=filters.date_from)
    if filters.date_to:
        rows = rows.filter(allotment__estimated_arrival_date__lte=filters.date_to)
    rows = rows.annotate(
        _number=Concat(Value("ALT-"), Cast("allotment_id", CharField()), output_field=CharField()),
        _is_linked=_linked_to_boe("allotment_id"),
    )
    if filters.search:
        s = filters.search
        rows = rows.annotate(_name_hit=_canonical_name_hit("item_id", s)).filter(
            Q(_number__icontains=s)
            | Q(allotment__company__name__icontains=s)
            | Q(allotment__invoice__icontains=s)
            | Q(allotment__item_name__icontains=s)
            | Q(item__description__icontains=s)
            | Q(_name_hit=True)
        )
    if supplier is not None:
        rows = rows.filter(**_supplier_lookup("allotment__company_id", supplier))
    if product_key is not None:
        rows = rows.filter(item_id=product_key)
    rows = rows.annotate(
        # Mirrors license_overview_allotments._allotment_status.
        _status=Case(
            When(_is_linked=True, then=Value("Linked to BOE")),
            When(allotment__is_approved=True, then=Value("Approved")),
            When(allotment__is_allotted=True, then=Value("Allotted")),
            default=Value("Pending"),
            output_field=CharField(),
        )
    )
    if filters.status:
        rows = rows.filter(_status=filters.status)

    cols = {
        "l_line_id": F("id"),
        "l_record_id": F("allotment_id"),
        "l_product_key": F("item_id"),
        "l_company_id": F("allotment__company_id"),
        "l_unit": F("item__unit"),
        "l_allotment_type": F("allotment__type"),
        "l_basis": F("allocation_basis"),
        "l_is_linked": F("_is_linked"),
        "l_cif": Coalesce(F("cif_fc"), Value(DEC_0), output_field=_SUM_FIELD),
        "l_qty": Coalesce(F("qty"), Value(DEC_000), output_field=_SUM_FIELD),
        "l_status": F("_status"),
    }
    if with_details:
        boe_numbers = (
            BillOfEntryModel.allotment.through.objects.filter(allotmentmodel_id=OuterRef("allotment_id"))
            .order_by("billofentrymodel__bill_of_entry_number")
            .values("billofentrymodel__bill_of_entry_number")
            .distinct()
        )
        cols.update({
            "l_number": F("_number"),
            "l_date": F("allotment__estimated_arrival_date"),
            "l_company_name": F("allotment__company__name"),
            "l_port": F("allotment__port__name"),
            "l_invoice_no": F("allotment__invoice"),
            "l_item_name": F("allotment__item_name"),
            "l_linked_boes": ArraySubquery(boe_numbers),
        })
    return rows.order_by().values(**cols)


def _supplier_lookup(field: str, supplier) -> Dict[str, Any]:
    if supplier == NULL_SUPPLIER_PARAM:
        return {f"{field}__isnull": True}
    return {field: supplier}


def _compile(qs) -> Tuple[str, Sequence[Any]]:
    return qs.query.get_compiler(using=qs.db).as_sql()


def _fetch(qs_db: str, sql: str, params: Sequence[Any]) -> List[Dict[str, Any]]:
    with connections[qs_db].cursor() as cursor:
        cursor.execute(sql, params)
        names = [c[0] for c in cursor.description]
        return [dict(zip(names, row)) for row in cursor.fetchall()]


# ---------------------------------------------------------------------------
# Summaries (SQL GROUPING SETS)
# ---------------------------------------------------------------------------

_SCOPES = (("l_company_id", "l_product_key"), ("l_company_id",), ())


def _grouped_summary(qs, buckets: Tuple[str, ...], extra: Tuple[Tuple[str, ...], ...] = ()):
    """
    One SQL statement per record type. For each scope (supplier x product,
    supplier, licence) it emits: scope+bucket (counts/CIF), scope+bucket+unit
    (qty per unit), scope alone (distinct records per type) and scope+extra
    (e.g. linked / not linked).
    """
    inner_sql, params = _compile(qs)
    dims = ("l_company_id", "l_product_key", "l_unit") + buckets
    sets: List[Tuple[str, ...]] = []
    for scope in _SCOPES:
        sets.append(scope + buckets)
        sets.append(scope + buckets + ("l_unit",))
        sets.append(scope)
        for e in extra:
            sets.append(scope + e)
    grouping_cols = ", ".join(f'GROUPING("{d}") AS "g_{d}"' for d in dims)
    dim_cols = ", ".join(f'"{d}"' for d in dims)
    sets_sql = ", ".join("(" + ", ".join(f'"{c}"' for c in s) + ")" for s in sets)
    sql = (
        f"SELECT {grouping_cols}, {dim_cols}, "
        f'COUNT(DISTINCT "l_record_id") AS record_count, COUNT(*) AS line_count, '
        f'COALESCE(SUM("l_cif"), 0) AS cif_fc, COALESCE(SUM("l_qty"), 0) AS qty '
        f"FROM ({inner_sql}) AS lines GROUP BY GROUPING SETS ({sets_sql})"
    )
    return _fetch(qs.db, sql, params)


def _new_summary() -> Dict[str, Any]:
    return {
        "record_count_by_type": {RECORD_TYPE_BOE: 0, RECORD_TYPE_ALLOTMENT: 0},
        "line_count_by_type": {RECORD_TYPE_BOE: 0, RECORD_TYPE_ALLOTMENT: 0},
        "boe_buckets": [],
        "allotment_buckets": [],
        "boe_debit_cif": DEC_0,
        "unlinked_allotment_cif": DEC_0,
        "linked_allotment_cif": DEC_0,
    }


def _scope_key(row) -> Tuple[str, Any]:
    """('licence'|'supplier'|'product', key) from GROUPING flags."""
    if row["g_l_company_id"]:
        return ("licence", None)
    if row["g_l_product_key"]:
        return ("supplier", row["l_company_id"])
    return ("product", (row["l_company_id"], row["l_product_key"]))


def _absorb(summaries: Dict[Tuple[str, Any], Dict[str, Any]], rows, record_type: str,
            buckets: Tuple[str, ...], bucket_label: Dict[str, str]) -> set:
    """Place each SQL row into its scope summary. No arithmetic here."""
    bucket_map: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
    supplier_keys = set()
    list_name = "boe_buckets" if record_type == RECORD_TYPE_BOE else "allotment_buckets"
    unit_rows = []
    for row in rows:
        scope = _scope_key(row)
        if scope[0] == "licence" and row["line_count"] == 0:
            continue  # empty-input grand total row
        summary = summaries.setdefault(scope, _new_summary())
        if scope[0] == "supplier":
            supplier_keys.add(scope[1])
        all_buckets_grouped = all(row[f"g_{b}"] for b in buckets)
        no_bucket_grouped = not any(row[f"g_{b}"] for b in buckets)
        if all_buckets_grouped and row["g_l_unit"]:
            summary["record_count_by_type"][record_type] = row["record_count"]
            summary["line_count_by_type"][record_type] = row["line_count"]
            continue
        if no_bucket_grouped:
            key = (scope,) + tuple(row[b] for b in buckets)
            if row["g_l_unit"]:
                bucket = {bucket_label[b]: row[b] for b in buckets}
                bucket.update({
                    "record_count": row["record_count"], "line_count": row["line_count"],
                    "cif_fc": row["cif_fc"], "qty_by_unit": [],
                })
                bucket_map[key] = bucket
                summary[list_name].append(bucket)
                if record_type == RECORD_TYPE_BOE and row["l_tt"] == DEBIT:
                    summary["boe_debit_cif"] = row["cif_fc"]
            else:
                unit_rows.append((key, row))
            continue
        # Partial grouping: only the allotment "extra" set (scope + linked).
        if record_type == RECORD_TYPE_ALLOTMENT and not row["g_l_is_linked"] and row["g_l_unit"]:
            target = "linked_allotment_cif" if row["l_is_linked"] else "unlinked_allotment_cif"
            summary[target] = row["cif_fc"]
    for key, row in unit_rows:
        bucket_map[key]["qty_by_unit"].append(
            {"unit": row["l_unit"], "qty": row["qty"], "line_count": row["line_count"]}
        )
    for bucket in bucket_map.values():
        bucket["qty_by_unit"].sort(key=lambda u: (u["unit"] is None, u["unit"] or ""))
    return supplier_keys


def _sort_buckets(summary: Dict[str, Any]) -> None:
    summary["boe_buckets"].sort(key=lambda b: b["transaction_type"] or "")
    summary["allotment_buckets"].sort(
        key=lambda b: (b["allotment_type"] or "", b["allocation_basis"] or "", bool(b["is_linked_to_boe"]))
    )


_BOE_BUCKETS = ("l_tt",)
_ALLOT_BUCKETS = ("l_allotment_type", "l_basis", "l_is_linked")
_BOE_LABELS = {"l_tt": "transaction_type"}
_ALLOT_LABELS = {"l_allotment_type": "allotment_type", "l_basis": "allocation_basis",
                 "l_is_linked": "is_linked_to_boe"}


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def _supplier_payload(company_id, companies: Dict[int, Dict[str, Any]]) -> Dict[str, Any]:
    if company_id is None:
        return {
            "supplier_id": None, "supplier_name": None, "supplier_iec": None,
            "supplier_label": NO_SUPPLIER_LABEL, "supplier_source": SUPPLIER_SOURCE,
            "is_missing_supplier": True,
        }
    company = companies.get(company_id, {})
    return {
        "supplier_id": company_id,
        "supplier_name": company.get("name"),
        "supplier_iec": company.get("iec"),
        "supplier_label": company.get("name"),
        "supplier_source": SUPPLIER_SOURCE,
        "is_missing_supplier": False,
    }


def _products(product_ids: Iterable[int]) -> Dict[int, Dict[str, Any]]:
    from django.db.models import Prefetch
    from apps.core.models import ItemNameModel

    ids = list(product_ids)
    if not ids:
        return {}
    srs = (
        LicenseImportItemsModel.objects.filter(id__in=ids)
        .only("id", "serial_number", "description", "unit")
        .prefetch_related(Prefetch("items", queryset=ItemNameModel.objects.only("id", "name").order_by("name", "id")))
    )
    out: Dict[int, Dict[str, Any]] = {}
    for sr in srs:
        names = [{"id": n.id, "name": n.name} for n in sr.items.all()]
        out[sr.id] = {
            "product_key": sr.id,
            "serial_number": sr.serial_number,
            "description": sr.description,
            "unit": sr.unit,
            "product_names": names,
            "product_label": " / ".join(n["name"] for n in names) if names else UNMAPPED_PRODUCT_LABEL,
            "is_unmapped": not names,
        }
    return out


def _page_bounds(count: int, page: int, page_size: int) -> Tuple[int, int, int]:
    total_pages = max(1, -(-count // page_size))
    if page > total_pages:
        raise TransactionQueryError("page", "Invalid page.")
    start = (page - 1) * page_size
    return start, start + page_size, total_pages


def build_supplier_groups(license_obj, filters: TransactionFilters, *, page: int = 1,
                          page_size: int = PAGE_SIZE_DEFAULT) -> Dict[str, Any]:
    """Supplier groups (paged) with their product summaries and licence totals."""
    summaries: Dict[Tuple[str, Any], Dict[str, Any]] = {}
    supplier_keys: set = set()
    if filters.record_type in (None, RECORD_TYPE_BOE):
        rows = _grouped_summary(boe_lines(license_obj, filters), _BOE_BUCKETS)
        supplier_keys |= _absorb(summaries, rows, RECORD_TYPE_BOE, _BOE_BUCKETS, _BOE_LABELS)
    if filters.record_type in (None, RECORD_TYPE_ALLOTMENT):
        rows = _grouped_summary(
            allotment_lines(license_obj, filters), _ALLOT_BUCKETS, extra=(("l_is_linked",),),
        )
        supplier_keys |= _absorb(summaries, rows, RECORD_TYPE_ALLOTMENT, _ALLOT_BUCKETS, _ALLOT_LABELS)

    for summary in summaries.values():
        _sort_buckets(summary)

    company_ids = [k for k in supplier_keys if k is not None]
    companies = {
        c["id"]: c for c in CompanyModel.objects.filter(id__in=company_ids).values("id", "name", "iec")
    } if company_ids else {}

    # Stable order: supplier_name, supplier_id; the "No supplier recorded"
    # group last.
    ordered = sorted(
        supplier_keys,
        key=lambda k: (k is None, (companies.get(k, {}).get("name") or "") if k is not None else "", k or 0),
    )
    count = len(ordered)
    start, end, total_pages = _page_bounds(count, page, page_size)
    page_keys = ordered[start:end]
    page_key_set = set(page_keys)

    products_by_supplier: Dict[Any, List[Any]] = {}
    for scope, _summary in summaries.items():
        if scope[0] == "product" and scope[1][0] in page_key_set:
            products_by_supplier.setdefault(scope[1][0], []).append(scope[1][1])
    product_info = _products(pk for pks in products_by_supplier.values() for pk in pks)

    results = []
    for key in page_keys:
        group = _supplier_payload(key, companies)
        group["summary"] = summaries[("supplier", key)]
        products = []
        for pk in products_by_supplier.get(key, []):
            info = dict(product_info.get(pk) or {
                "product_key": pk, "serial_number": None, "description": None, "unit": None,
                "product_names": [], "product_label": UNMAPPED_PRODUCT_LABEL, "is_unmapped": True,
            })
            info["summary"] = summaries[("product", (key, pk))]
            products.append(info)
        products.sort(key=lambda p: (p["serial_number"] is None, p["serial_number"] or 0, p["product_key"]))
        group["products"] = products
        results.append(group)

    return {
        "license_id": license_obj.pk,
        "license_number": license_obj.license_number,
        "totals": summaries.get(("licence", None)) or _new_summary(),
        "cif_basis": CIF_BASIS,
        "count": count,
        "page_size": page_size,
        "total_pages": total_pages,
        "current_page": page,
        "results": results,
    }


_RECORD_COLUMNS = (
    "record_type", "line_id", "record_id", "record_number", "date", "supplier_id", "supplier_name",
    "product_key", "unit", "qty", "cif_fc", "status", "port", "invoice_no", "invoice_date",
    "transaction_type", "allotment_type", "allocation_basis", "is_linked_to_boe", "linked_boe_numbers",
    "allotment_item_name", "source_row_count",
)


def _boe_record_select(inner: str) -> str:
    return (
        "SELECT 'BOE'::varchar AS record_type, l_line_id AS line_id, l_record_id AS record_id, "
        "l_number::varchar AS record_number, l_date AS date, l_company_id AS supplier_id, "
        "l_company_name::varchar AS supplier_name, l_product_key AS product_key, l_unit::varchar AS unit, "
        "l_qty AS qty, l_cif AS cif_fc, l_status::varchar AS status, l_port::varchar AS port, "
        "l_invoice_no::varchar AS invoice_no, l_invoice_date AS invoice_date, "
        "l_tt::varchar AS transaction_type, NULL::varchar AS allotment_type, "
        "NULL::varchar AS allocation_basis, NULL::boolean AS is_linked_to_boe, "
        "NULL::varchar[] AS linked_boe_numbers, NULL::varchar AS allotment_item_name, "
        f"l_source_rows AS source_row_count FROM ({inner}) AS b"
    )


def _allotment_record_select(inner: str) -> str:
    return (
        "SELECT 'ALLOTMENT'::varchar AS record_type, l_line_id AS line_id, l_record_id AS record_id, "
        "l_number::varchar AS record_number, l_date AS date, l_company_id AS supplier_id, "
        "l_company_name::varchar AS supplier_name, l_product_key AS product_key, l_unit::varchar AS unit, "
        "l_qty AS qty, l_cif AS cif_fc, l_status::varchar AS status, l_port::varchar AS port, "
        "l_invoice_no::varchar AS invoice_no, NULL::date AS invoice_date, "
        "NULL::varchar AS transaction_type, l_allotment_type::varchar AS allotment_type, "
        "l_basis::varchar AS allocation_basis, l_is_linked AS is_linked_to_boe, "
        "l_linked_boes::varchar[] AS linked_boe_numbers, l_item_name::varchar AS allotment_item_name, "
        f"1 AS source_row_count FROM ({inner}) AS a"
    )


def list_product_records(license_obj, filters: TransactionFilters, *, supplier, product_key: int,
                         page: int = 1, page_size: int = PAGE_SIZE_DEFAULT,
                         ordering: str = DEFAULT_ORDERING) -> Dict[str, Any]:
    """Paged record lines for one (supplier, product) group."""
    parts: List[str] = []
    params: List[Any] = []
    db = RowDetails.objects.db
    if filters.record_type in (None, RECORD_TYPE_BOE):
        sql, p = _compile(boe_lines(license_obj, filters, supplier=supplier, product_key=product_key,
                                    with_details=True))
        parts.append(_boe_record_select(sql))
        params.extend(p)
    if filters.record_type in (None, RECORD_TYPE_ALLOTMENT):
        sql, p = _compile(allotment_lines(license_obj, filters, supplier=supplier, product_key=product_key,
                                          with_details=True))
        parts.append(_allotment_record_select(sql))
        params.extend(p)
    union = " UNION ALL ".join(f"({p})" for p in parts)

    count = _fetch(db, f"SELECT COUNT(*) AS n FROM ({union}) AS u", params)[0]["n"]
    start, _end, total_pages = _page_bounds(count, page, page_size)

    desc = ordering.startswith("-")
    column = ORDERING_FIELDS[ordering.lstrip("-")]  # validated by parse_params
    order_sql = (
        f'"{column}" {"DESC" if desc else "ASC"} NULLS LAST, record_type, record_id, line_id'
    )
    cols = ", ".join(_RECORD_COLUMNS)
    rows = _fetch(
        db,
        f"SELECT {cols} FROM ({union}) AS u ORDER BY {order_sql} LIMIT %s OFFSET %s",
        list(params) + [page_size, start],
    )
    product = _products([product_key]).get(product_key) or {
        "product_key": product_key, "serial_number": None, "description": None, "unit": None,
        "product_names": [], "product_label": UNMAPPED_PRODUCT_LABEL, "is_unmapped": True,
    }
    for row in rows:
        row["supplier_source"] = SUPPLIER_SOURCE
        row["supplier_label"] = NO_SUPPLIER_LABEL if row["supplier_id"] is None else row["supplier_name"]
        row["linked_boe_numbers"] = list(row["linked_boe_numbers"]) if row["linked_boe_numbers"] is not None \
            else None
        row["product_label"] = product["product_label"]
    return {
        "license_id": license_obj.pk,
        "license_number": license_obj.license_number,
        "supplier_id": None if supplier == NULL_SUPPLIER_PARAM else supplier,
        "product": product,
        "cif_basis": CIF_BASIS,
        "count": count,
        "page_size": page_size,
        "total_pages": total_pages,
        "current_page": page,
        "results": rows,
    }


# ---------------------------------------------------------------------------
# Query-param parsing (kept here so the view stays a thin wrapper)
# ---------------------------------------------------------------------------

def _parse_int(params, name: str, default: Optional[int] = None, minimum: int = 1) -> Optional[int]:
    raw = params.get(name)
    if raw in (None, ""):
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise TransactionQueryError(name, "A valid integer is required.")
    if value < minimum:
        raise TransactionQueryError(name, f"Ensure this value is greater than or equal to {minimum}.")
    return value


def _parse_date(params, *names: str) -> Optional[date]:
    for name in names:
        raw = params.get(name)
        if raw in (None, ""):
            continue
        try:
            return date.fromisoformat(str(raw))
        except ValueError:
            raise TransactionQueryError(name, "Date has wrong format. Use YYYY-MM-DD.")
    return None


def parse_params(params) -> Dict[str, Any]:
    record_type = (params.get("record_type") or "").strip().upper() or None
    if record_type and record_type not in RECORD_TYPES:
        raise TransactionQueryError("record_type", f"Must be one of: {', '.join(RECORD_TYPES)}.")
    ordering = (params.get("ordering") or DEFAULT_ORDERING).strip()
    if ordering.lstrip("-") not in ORDERING_FIELDS:
        raise TransactionQueryError("ordering", f"Must be one of: {', '.join(sorted(ORDERING_FIELDS))}.")
    filters = TransactionFilters(
        search=(params.get("search") or "").strip(),
        record_type=record_type,
        status=(params.get("status") or "").strip() or None,
        # `date_from`/`date_to`, or the `date__gte`/`date__lte` wire names
        # `lib/listContract.ts::toQuery` produces from them.
        date_from=_parse_date(params, "date_from", "date__gte"),
        date_to=_parse_date(params, "date_to", "date__lte"),
    )
    page = _parse_int(params, "page", default=1)
    page_size = min(_parse_int(params, "page_size", default=PAGE_SIZE_DEFAULT), PAGE_SIZE_MAX)

    raw_supplier = params.get("supplier_id")
    supplier = None
    if raw_supplier not in (None, ""):
        supplier = NULL_SUPPLIER_PARAM if str(raw_supplier).lower() == NULL_SUPPLIER_PARAM \
            else _parse_int(params, "supplier_id")
    product_key = _parse_int(params, "product_key")
    if (supplier is None) != (product_key is None):
        raise TransactionQueryError(
            "supplier_id" if supplier is None else "product_key",
            "supplier_id and product_key must be supplied together.",
        )
    return {
        "filters": filters, "page": page, "page_size": page_size, "ordering": ordering,
        "supplier": supplier, "product_key": product_key,
    }


def get_overview_transactions(license_obj, params) -> Dict[str, Any]:
    parsed = parse_params(params)
    if parsed["supplier"] is not None:
        return list_product_records(
            license_obj, parsed["filters"], supplier=parsed["supplier"], product_key=parsed["product_key"],
            page=parsed["page"], page_size=parsed["page_size"], ordering=parsed["ordering"],
        )
    return build_supplier_groups(
        license_obj, parsed["filters"], page=parsed["page"], page_size=parsed["page_size"],
    )

