"""Product-wise Item Report, built on the canonical Item Pivot engine (owner decision 2026-11-20).

There is NO second aggregation here. For every selected norm the report is ``ItemPivotReportView().generate_report`` (the
canonical ``ItemPivotService`` projection, incl. owner decisions D1-D3 apportionment); the selected licence rows are then
projected with ``project_item_summary`` — the same function that produces the Item Pivot Item Summary / Total Summary — and
this module only renames and formats its fields.

Filter mapping (see ``docs/decisions/2026-11-20-item-pivot-attribution-owner-decisions-d1-d4.md``):

=====================================  =====================================================================================
``license_status`` / ``expiry_date_*`` /  passed to the pivot selection (``select_pivot_licenses``) unchanged
``company_ids`` / ``exclude_company_ids``
/ ``purchase_status`` / ``min_balance``
``norms``                              one pivot report per norm (``sion_norm``); default = every norm with a licence
``notification_numbers``               licence ROWS are filtered before projecting (the pivot has no such parameter)
``license_numbers``                    licence ROWS are filtered before projecting (exact match)
``item_names`` / ``hsn_code`` /        identity filters: a whole product (Item Name x SION) is kept or dropped; its figures are
``planning_status``                    never recomputed, so nothing is filtered after summing
=====================================  =====================================================================================

A licence that carries several selected norms is projected once (first norm, alphabetical) so it is never double counted.
"""
from collections import OrderedDict
from datetime import date
from decimal import Decimal

from apps.license.services.item_pivot_item_summary import (
    NO_ITEM_NAME_CATEGORY,
    _identity_pieces,
    identity_key_text,
    piece_identity_key,
    project_item_summary,
)

PLANNING_STATUSES = ("all", "planned", "unplanned")
ZERO_QTY, ZERO_CIF = Decimal("0.000"), Decimal("0.00")
QTY_Q, CIF_Q = Decimal("0.001"), Decimal("0.01")

# product field -> (pivot item-summary row field, kind). Order = the JSON / Excel column order of the metric block.
METRICS = (
    ("total_qty", "total_qty", "qty"), ("total_cif", "item_total_cif", "cif"),
    ("allotted_qty", "allotted_qty", "qty"), ("allotted_cif", "allotted_cif", "cif"),
    ("debited_qty", "boe_used_qty", "qty"), ("debited_cif", "boe_used_cif", "cif"),
    ("invoice_qty", "billed_qty", "qty"), ("invoice_cif", "billed_cif", "cif"),
    ("balance_qty", "available_qty", "qty"), ("balance_cif", "capacity_balance_cif", "cif"),
    ("planned_qty", "planned_qty", "qty"), ("planned_cif", "planned_cif", "cif"),
)
METRIC_FIELDS = tuple(name for name, _, _ in METRICS)
PRODUCT_FIELDS = ("key", "canonical_item_id", "item_name", "sion", "product_category", "hsn_codes", "license_count", "units",
                  "mixed_units", "is_planned") + METRIC_FIELDS


class FilterError(ValueError):
    """A request filter that cannot be applied (rendered as HTTP 400 by the view)."""

    def __init__(self, field, message):
        super().__init__(message)
        self.field = field


def _csv(value):
    return [part.strip() for part in (value or "").split(",") if part.strip()]


def _ids(field, value):
    try:
        return [int(part) for part in _csv(value)]
    except ValueError:
        raise FilterError(field, "Must be a comma-separated list of integer ids.")


def _iso(field, value):
    if value:
        try:
            date.fromisoformat(value)
        except ValueError:
            raise FilterError(field, "Must be YYYY-MM-DD.")
    return value or None


def parse_filters(query):
    """Validated filter dict from a QueryDict (``request.GET``)."""
    try:
        min_balance = int(query.get("min_balance") or 200)
    except ValueError:
        raise FilterError("min_balance", "Must be an integer.")
    planning_status = (query.get("planning_status") or "all").strip().lower()
    if planning_status not in PLANNING_STATUSES:
        raise FilterError("planning_status", f"Must be one of: {', '.join(PLANNING_STATUSES)}.")
    _ids("company_ids", query.get("company_ids"))
    _ids("exclude_company_ids", query.get("exclude_company_ids"))
    return {
        "license_status": query.get("license_status") or "active",
        "expiry_date_from": _iso("expiry_date_from", query.get("expiry_date_from")),
        "expiry_date_to": _iso("expiry_date_to", query.get("expiry_date_to")),
        "company_ids": query.get("company_ids") or None,
        "exclude_company_ids": query.get("exclude_company_ids") or None,
        "purchase_status": query.get("purchase_status") or None,
        "notification_numbers": _csv(query.get("notification_numbers")),
        "min_balance": min_balance,
        "norms": _csv(query.get("norms")),
        "item_names": _ids("item_names", query.get("item_names")),
        "hsn_code": (query.get("hsn_code") or "").strip(),
        "license_numbers": _csv(query.get("license_numbers")),
        "planning_status": planning_status,
    }


def _text_or_none(value):
    return None if value is None else str(value)


def _selected_norms(filters):
    if filters["norms"]:
        return sorted(dict.fromkeys(filters["norms"]))
    from apps.license.models import LicenseExportItemModel

    return sorted(set(LicenseExportItemModel.objects.filter(norm_class__isnull=False).values_list("norm_class__norm_class", flat=True)))


def select_licence_rows(filters, trace_rows=False):
    """The pivot's licence rows for this scope (one canonical report per norm) plus the pivot's own item-summary rows.

    Returns ``(norms, licence_rows, pivot_rows)``. ``pivot_rows`` are the pivot's Total Summary rows (``grand_total``) when the
    projected licences are exactly the pivot's licences, else a projection of the same kept rows — the comparator the
    reconciliation block checks the product totals against.
    """
    from apps.license.views.item_pivot_report import ItemPivotReportView

    norms = _selected_norms(filters)
    notifications = set(filters["notification_numbers"])
    license_numbers = set(filters["license_numbers"])
    seen, kept, pivot_rows, pivot_licence_count, used_norms = set(), [], [], 0, []
    for norm in norms:
        report = ItemPivotReportView().generate_report(
            days=30, sion_norm=norm, company_ids=filters["company_ids"], exclude_company_ids=filters["exclude_company_ids"],
            min_balance=filters["min_balance"], license_status=filters["license_status"], expiry_date_from=filters["expiry_date_from"],
            expiry_date_to=filters["expiry_date_to"], purchase_status=filters["purchase_status"], trace_rows=trace_rows)
        norm_rows = 0
        for group in report["notification_groups"]:
            for licence in group["licenses"]:
                norm_rows += 1
                if licence["license_id"] in seen:
                    continue
                if notifications and group["notification_number"] not in notifications:
                    continue
                if license_numbers and licence["license_number"] not in license_numbers:
                    continue
                seen.add(licence["license_id"])
                kept.append(licence)
        if norm_rows:
            used_norms.append(norm)
            pivot_licence_count += norm_rows
            pivot_rows.extend(report["grand_total"]["item_summary"])
    if len(kept) != pivot_licence_count:
        pivot_rows = project_item_summary(kept)["item_summary"]
    return used_norms, kept, pivot_rows


def _identity_filter(filters):
    ids, hsn = set(filters["item_names"]), filters["hsn_code"].lower()

    def keep(row):
        if ids and row["canonical_item_id"] not in ids:
            return False
        return not hsn or any(hsn in str(code).lower() for code in row.get("hsn_codes") or [])

    return keep


def _quantize(value, kind):
    return str(Decimal(str(value)).quantize(QTY_Q if kind == "qty" else CIF_Q))


def _product(row):
    product = {
        "key": row["identity_key"], "canonical_item_id": row["canonical_item_id"], "item_name": row["item_name"], "sion": row["sion"],
        "product_category": row["product_category"], "hsn_codes": row["hsn_codes"], "license_count": row["license_count"],
        "units": row["units"], "mixed_units": row["mixed_units"], "is_planned": row["is_planned"],
    }
    for name, source, _kind in METRICS:
        product[name] = row.get(source)  # None stays None: missing, not 0
    return product


def _sum_metrics(rows, field_of):
    """{metric: str | None} - Decimal sums of already quantized rows; None when no row carries the figure."""
    totals = {}
    for name, _source, kind in METRICS:
        present = [Decimal(str(value)) for value in (field_of(row, name) for row in rows) if value is not None]
        totals[name] = _quantize(sum(present, Decimal("0")), kind) if present else None
    return totals


def build_products(filters):
    """The JSON contract of ``GET reports/item-report/products/``."""
    norms, licence_rows, pivot_rows = select_licence_rows(filters)
    return _assemble(filters, norms, licence_rows, pivot_rows)


def _assemble(filters, norms, licence_rows, pivot_rows):
    keep = _identity_filter(filters)
    projected = [row for row in project_item_summary(licence_rows)["item_summary"] if keep(row)]
    planned = sum(1 for row in projected if row["is_planned"])
    planning_counts = {"all": len(projected), "planned": planned, "unplanned": len(projected) - planned}
    status = filters["planning_status"]
    rows = [row for row in projected if status == "all" or row["is_planned"] == (status == "planned")]
    products = [_product(row) for row in rows]
    totals = _sum_metrics(products, lambda product, name: product[name])
    comparator = [row for row in pivot_rows if keep(row) and (status == "all" or row["is_planned"] == (status == "planned"))]
    pivot_totals = _sum_metrics(comparator, lambda row, name: row.get(dict((n, s) for n, s, _ in METRICS)[name]))
    metrics, reconciled = OrderedDict(), True
    for name in METRIC_FIELDS:
        report_value, pivot_value = totals[name], pivot_totals[name]
        difference = None if report_value is None and pivot_value is None else str(Decimal(report_value or "0") - Decimal(pivot_value or "0"))
        reconciled = reconciled and (difference is None or Decimal(difference) == 0)
        metrics[name] = {"item_report": report_value, "item_pivot": pivot_value, "difference": difference}
    return {
        "report_date": date.today().isoformat(),
        "scope": {"norms": norms, "licence_count": len(licence_rows), "filters": {
            key: value for key, value in filters.items()}},
        "products": products, "totals": totals, "planning_counts": planning_counts,
        "reconciliation": {"reconciled": reconciled, "metrics": metrics},
    }


# --- drill-down ------------------------------------------------------------------------------------------------------------

def _row(entry, kind):
    base = {"row_id": entry["row_id"], "qty": entry["qty"], "cif": entry["cif"]}
    if entry.get("share") is not None:
        base["share"] = entry["share"]
    if kind == "BOE":
        return {"boe_id": entry["record_id"], "bill_of_entry_number": entry.get("reference") or "", "date": entry.get("date"), **base}
    if kind == "ALLOTMENT":
        return {"allotment_id": entry["record_id"], "reference": entry.get("reference") or "", **base, "outstanding": True}
    return {"invoice_id": entry["record_id"], "invoice_number": entry.get("reference") or "", "date": entry.get("date"),
            "line_id": base.pop("row_id"), **base}


def _piece_usage_rows(piece):
    """Transaction rows of one identity piece: the engine's traced rows, or the NOT ATTRIBUTED records."""
    if piece.get("unattributed"):
        return [{"kind": rec["kind"], "row_id": rec["row_id"], "record_id": rec["record_id"], "reference": rec.get("reference") or "",
                 "date": rec.get("date"), "qty": rec["qty"], "cif": rec["cif_fc"], "share": None} for rec in piece.get("unattributed_records", [])
                if rec["kind"] in ("BOE", "ALLOTMENT", "BILLED")]
    return list(piece.get("usage_rows") or [])


def _piece_import_items(piece, norm):
    if piece.get("unattributed"):
        return [{"import_item_id": rec["import_item_id"], "serial_number": rec.get("serial_number"), "description": rec.get("description"),
                 "hs_code": rec.get("hsn_code"), "norm": norm, "unit": rec.get("unit"), "total_qty": None, "total_cif": None}
                for rec in piece.get("unattributed_records", [])]
    return [{"import_item_id": src.get("import_item_id"), "serial_number": src.get("serial_number"), "description": src.get("description"),
             "hs_code": src.get("hsn_code"), "norm": norm, "unit": src.get("unit"),
             "total_qty": src.get("quantity"), "total_cif": src.get("cif_fc")}
            for src in (piece.get("identity_sources") or piece.get("source_items") or [])]


def build_trace(licence_rows):
    """{product key: [per-licence drill-down entry]} for every product of these (traced) licence rows."""
    entries = {}
    for licence in licence_rows:
        per_key = {}
        for whole_cell in (licence.get("items") or {}).values():
            for piece in _identity_pieces(whole_cell):
                key = identity_key_text(piece_identity_key(piece))
                bucket = per_key.setdefault(key, {"pieces": [], "rows": [], "import_items": OrderedDict()})
                bucket["pieces"].append(piece)
                bucket["rows"].extend(_piece_usage_rows(piece))
                for item in _piece_import_items(piece, piece.get("sion") or ""):
                    bucket["import_items"].setdefault(item["import_item_id"], item)
        for key, bucket in per_key.items():
            def total(field, kind, nullable=False, _pieces=bucket["pieces"]):
                present = [Decimal(str(piece.get(field))) for piece in _pieces if piece.get(field) is not None]
                if not present:
                    return None if nullable else _quantize(0, kind)
                return _quantize(sum(present, Decimal("0")), kind)

            boes = [_row(r, "BOE") for r in bucket["rows"] if r["kind"] == "BOE"]
            allotments = [_row(r, "ALLOTMENT") for r in bucket["rows"] if r["kind"] == "ALLOTMENT"]
            invoices = [_row(r, "BILLED") for r in bucket["rows"] if r["kind"] == "BILLED"]
            attributed = not bucket["pieces"][0].get("unattributed")
            entries.setdefault(key, []).append({
                "license_id": licence["license_id"], "license_number": licence["license_number"],
                "import_items": list(bucket["import_items"].values()), "boes": boes, "allotments": allotments, "invoices": invoices,
                "total_qty": total("adjusted_total_qty", "qty") if attributed else _quantize(0, "qty"),
                "total_cif": total("item_total_cif", "cif", nullable=True) if attributed else None,
                "debited_qty": total("debited_qty", "qty"), "debited_cif": total("boe_used_cif", "cif"),
                "allotted_qty": total("allotted_qty", "qty"), "allotted_cif": total("allotted_cif", "cif"),
                "invoice_qty": total("billed_qty", "qty"), "invoice_cif": total("billed_cif", "cif"),
                "balance_qty": total("available_qty", "qty") if attributed else _quantize(0, "qty"),
                "balance_cif": total("capacity_balance_cif", "cif", nullable=True) if attributed else None,
            })
    return entries


def build_drilldown(filters, key):
    """The JSON contract of ``GET reports/item-report/products/drilldown/?key=``; None when the product is not in scope."""
    norms, licence_rows, pivot_rows = select_licence_rows(filters, trace_rows=True)
    report = _assemble(filters, norms, licence_rows, pivot_rows)
    product = next((p for p in report["products"] if p["key"] == key), None)
    if product is None:
        return None
    return {"product": product, "licences": build_trace(licence_rows).get(key, [])}


def build_products_with_detail(filters):
    """Products JSON plus the drill-down of every product (Excel export: one traced build, nothing recomputed)."""
    norms, licence_rows, pivot_rows = select_licence_rows(filters, trace_rows=True)
    report = _assemble(filters, norms, licence_rows, pivot_rows)
    trace = build_trace(licence_rows)
    detail = [{"product": product, "licences": trace.get(product["key"], [])} for product in report["products"]]
    return report, detail


DETAIL_COLUMNS = ("Product Key", "Item Name", "SION", "Licence Number", "Record Type", "Reference", "Date", "Row ID", "Qty", "CIF", "Share")


def detail_rows(detail):
    """Flat Licence-detail rows (one per BOE / allotment / invoice row) shared by the Excel sheet and its test."""
    out = []
    for entry in detail:
        product = entry["product"]
        for licence in entry["licences"]:
            for row in licence["boes"]:
                out.append([product["key"], product["item_name"], product["sion"], licence["license_number"], "BOE",
                            row["bill_of_entry_number"], row["date"], row["row_id"], row["qty"], row["cif"], row.get("share")])
            for row in licence["allotments"]:
                out.append([product["key"], product["item_name"], product["sion"], licence["license_number"], "ALLOTMENT",
                            row["reference"], None, row["row_id"], row["qty"], row["cif"], row.get("share")])
            for row in licence["invoices"]:
                out.append([product["key"], product["item_name"], product["sion"], licence["license_number"], "INVOICE",
                            row["invoice_number"], row["date"], row["line_id"], row["qty"], row["cif"], row.get("share")])
    return out


PRODUCT_COLUMNS = (
    ("key", "Product Key"), ("canonical_item_id", "Item ID"), ("item_name", "Item Name"), ("sion", "SION"), ("product_category", "Category"),
    ("hsn_codes", "HSN Codes"), ("license_count", "Licences"), ("units", "Units"), ("mixed_units", "Mixed Units"), ("is_planned", "Planned"),
    ("total_qty", "Total Qty"), ("total_cif", "Total CIF"), ("allotted_qty", "Allotted Qty"), ("allotted_cif", "Allotted CIF"),
    ("debited_qty", "Debited Qty"), ("debited_cif", "Debited CIF"), ("invoice_qty", "Invoice Qty"), ("invoice_cif", "Invoice CIF"),
    ("balance_qty", "Balance Qty"), ("balance_cif", "Balance CIF"), ("planned_qty", "Planned Qty"), ("planned_cif", "Planned CIF"),
)


def build_excel(report, detail):
    """Workbook bytes: 'Products' (JSON columns, same order, SUM totals row) + 'Licence detail' (drill-down rows)."""
    from io import BytesIO

    import openpyxl
    from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
    from openpyxl.styles import Font

    from apps.core.exporters.excel.cell_formats import (
        INTEGER_FORMAT, QUANTITY_FORMAT, finalize_workbook, write_date, write_number, write_sum, write_text,
    )

    def safe(value):
        return ILLEGAL_CHARACTERS_RE.sub("", value) if isinstance(value, str) else value

    bold = Font(bold=True)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Products"
    for col, (_field, label) in enumerate(PRODUCT_COLUMNS, start=1):
        ws.cell(row=1, column=col, value=label).font = bold
    kinds = {name: kind for name, _, kind in METRICS}
    for r, product in enumerate(report["products"], start=2):
        for col, (field, _label) in enumerate(PRODUCT_COLUMNS, start=1):
            cell, value = ws.cell(row=r, column=col), product[field]
            if field in kinds:
                write_number(cell, value, QUANTITY_FORMAT if kinds[field] == "qty" else "#,##0.00")
            elif field in ("canonical_item_id", "license_count"):
                write_number(cell, value, INTEGER_FORMAT)
            elif field in ("hsn_codes", "units"):
                write_text(cell, ", ".join(value))
            elif field in ("mixed_units", "is_planned"):
                cell.value = bool(value)
            else:
                write_text(cell, safe(value))
    first, last = 2, 1 + len(report["products"])
    total_row = last + 1
    ws.cell(row=total_row, column=1, value="TOTAL").font = bold
    for col, (field, _label) in enumerate(PRODUCT_COLUMNS, start=1):
        if field in kinds:
            cell = ws.cell(row=total_row, column=col)
            if report["totals"][field] is None:
                write_number(cell, None)  # missing, not 0
            else:
                write_sum(cell, first, last, QUANTITY_FORMAT if kinds[field] == "qty" else "#,##0.00")
            cell.font = bold
    ws.freeze_panes = "A2"

    detail_ws = wb.create_sheet("Licence detail")
    for col, label in enumerate(DETAIL_COLUMNS, start=1):
        detail_ws.cell(row=1, column=col, value=label).font = bold
    for r, values in enumerate(detail_rows(detail), start=2):
        for col, (label, value) in enumerate(zip(DETAIL_COLUMNS, values), start=1):
            cell = detail_ws.cell(row=r, column=col)
            if label in ("Qty",):
                write_number(cell, value, QUANTITY_FORMAT)
            elif label == "CIF":
                write_number(cell, value)
            elif label == "Row ID":
                write_number(cell, value, INTEGER_FORMAT)
            elif label == "Share":
                write_number(cell, value, "0.000000")
            elif label == "Date":
                write_date(cell, value)
            else:
                write_text(cell, safe(value))
    detail_ws.freeze_panes = "A2"
    finalize_workbook(wb)
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


__all__ = ["FilterError", "NO_ITEM_NAME_CATEGORY", "PLANNING_STATUSES", "build_drilldown", "build_excel", "build_products",
           "build_products_with_detail", "detail_rows", "parse_filters"]
