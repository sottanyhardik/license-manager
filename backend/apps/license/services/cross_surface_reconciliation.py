"""Cross-surface reconciliation (read-only audit).

Calls the *real* backend function behind every screen for the same licences and diffs each metric against the
canonical balance engine (``.claude/rules/business-rules.md``). Nothing here computes a new business figure: every
number is taken from the function the screen itself uses, so a difference found here is a difference a user sees.

Surfaces (function → screen):
    canonical   ``balance_snapshot.get_snapshot_bulk`` + ``LicenseBalanceCalculator`` bulk methods (engine)
    overview    ``license_overview_summary.get_overview_counts``     → Licence Detail → Overview cards
    items_tab   ``license_overview_items.compute_item_ledger_rows`` → Licence Detail → Import Items table
    pivot       ``ItemPivotService.build``                           → Item Pivot Report (classic licence rows/cells)
    item_report ``ItemReportView.generate_report``                   → Item Report (+ its Excel export)

Read-only: the caller (management command) wraps the run in a transaction that is always rolled back.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional

CIF_TOL = Decimal("0.01")
QTY_TOL = Decimal("0.001")
ZERO = Decimal("0")


def D(value) -> Decimal:
    """Decimal from Decimal/str/int/float/None (floats via ``str`` so no binary noise is introduced)."""
    if value is None or value == "":
        return ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


@dataclass
class Discrepancy:
    license_id: int
    license_number: str
    metric: str
    source: str            # surface treated as the reference for this check
    source_value: Decimal
    report: str            # surface compared against it
    report_value: Decimal
    root_cause: str        # code key into ROOT_CAUSES
    item_id: Optional[int] = None
    item_name: str = ""
    hsn: str = ""
    sion: str = ""

    @property
    def difference(self) -> Decimal:
        return self.report_value - self.source_value

    def as_dict(self) -> Dict[str, Any]:
        return {
            "license_id": self.license_id, "license_number": self.license_number, "item_id": self.item_id,
            "item_name": self.item_name, "hsn": self.hsn, "sion": self.sion, "metric": self.metric,
            "source": self.source, "source_value": str(self.source_value), "report": self.report,
            "report_value": str(self.report_value), "difference": str(self.difference), "root_cause": self.root_cause,
        }


# Root-cause catalogue — every check below is tagged with the code-level reason the two surfaces differ.
ROOT_CAUSES = {
    "RC1_OVERVIEW_RAW_BOE_DEBIT": "Overview 'Debited CIF' card = calculate_boe_debit_total (raw BOE rows); canonical/pivot "
                                  "debit = calculate_debit (allocation-aware, excludes BOEs already represented by invoices).",
    "RC2_OVERVIEW_BILLED_NOT_SHOWN": "Overview balance is the financial balance (runs from the opening balance for licences "
                                     "bought from a previous owner, whose BOEs are hidden; also includes billed-without-BOE) "
                                     "but the cards show neither adjustment, so Total − Debited − Allotted ≠ Balance on screen.",
    "RC3_ITEMS_TAB_STORED_COLUMNS": "Import Items tab reads stored per-item debited_value/allotted_value/available_quantity "
                                    "(refreshed by the balance task) instead of the live engine — stale or differently derived.",
    "RC4_ITEM_REPORT_STORED_AVAILABLE_VALUE": "Item Report 'Available Balance' and its min_balance filter use the stored "
                                              "available_value column, not the live engine value.",
    "RC5_AVAILABLE_QTY_FORMULAS": "Available quantity has different formulas: snapshot = qty−debit−outstanding (floored 0); "
                                  "ItemBalanceCalculator (Item Report) = qty−debit−outstanding−direct_sale (signed). They "
                                  "differ only with direct sales or over-debited items. (Item Report vs live is a wiring check.)",
    "RC6_PLAN_ATTRIBUTION": "Planned qty/CIF attributed per plan.import_item_id (Item Report) vs licence aggregate "
                            "(Overview) vs pivot cell attribution (source_item_ids / D1 proportional).",
    "RC7_FILTER_SCOPE": "Filter scope differs between surfaces: pivot min_balance uses the live licence financial balance, "
                        "Item Report uses stored per-item available_value; the pivot also drops licences whose "
                        "purchase_status is NULL (purchase_status__code__in) while Licence Detail and Item Report show them.",
    "RC8_ENGINE_IDENTITY": "Canonical identity check: financial balance vs credit − debit − allotment − billed; residual = "
                           "opening balance / purchase credit / hidden-BOE adjustments (documented licence-level adjustments).",
    "RC9_PIVOT_ITEM_ATTRIBUTION": "Pivot licence row (canonical engine) vs Σ pivot item cells (raw transaction rows): BOE "
                                  "allocation netting and invoice representation are licence-level only.",
    "RC10_SURFACE_MISSING": "Same metric, same definition, different value (or licence missing from a surface).",
    "RC11_LICENCE_LEVEL_CIF": "Original CIF is Σ export-item cif_fc; these licences' import items carry cif_fc = 0 (shared "
                              "licence-level ceiling), so the Import Items 'Total CIF' footer shows 0 vs the Overview total.",
    "RC12_IMPORT_VS_EXPORT_CIF": "Σ import-item cif_fc is non-zero but differs from Σ export-item cif_fc (Original CIF).",
}


@dataclass
class ReconciliationResult:
    licences_checked: int = 0
    import_items_checked: int = 0
    product_combinations: int = 0
    discrepancies: List[Discrepancy] = field(default_factory=list)
    surface_values: Dict[int, Dict[str, Dict[str, Decimal]]] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

    def by_cause(self) -> Dict[str, Dict[str, Any]]:
        out: Dict[str, Dict[str, Any]] = {}
        for d in self.discrepancies:
            row = out.setdefault(d.root_cause, {"count": 0, "licences": set(), "abs_cif": ZERO, "abs_qty": ZERO})
            row["count"] += 1
            row["licences"].add(d.license_id)
            if d.metric == "presence":  # a missing-surface flag carries no amount
                continue
            if "qty" in d.metric:
                row["abs_qty"] += abs(d.difference)
            else:
                row["abs_cif"] += abs(d.difference)
        for row in out.values():
            row["licences"] = len(row["licences"])
        return dict(sorted(out.items(), key=lambda kv: (-kv[1]["abs_cif"], -kv[1]["abs_qty"])))


def _close(a: Decimal, b: Decimal, tol: Decimal) -> bool:
    return abs(a - b) < tol


def _walk_pivot_licence_rows(node) -> Iterable[dict]:
    """Yield every classic-pivot licence row (dicts carrying license_id + items + total_cif), at any nesting depth."""
    if isinstance(node, dict):
        if "license_id" in node and "items" in node and "total_cif" in node:
            yield node
            return
        for value in node.values():
            yield from _walk_pivot_licence_rows(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk_pivot_licence_rows(value)


def collect_surfaces(license_ids: List[int], *, chunk: int = 150, include_pivot: bool = True,
                     include_item_report: bool = True) -> ReconciliationResult:
    from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel, LicenseItemPlan
    from apps.license.services import balance_snapshot
    from apps.license.services.balance_calculator import ItemBalanceCalculator, LicenseBalanceCalculator
    from apps.license.services.license_overview_items import compute_item_ledger_rows
    from apps.license.services.license_overview_summary import get_overview_counts

    res = ReconciliationResult()
    values: Dict[int, Dict[str, Dict[str, Decimal]]] = defaultdict(lambda: defaultdict(dict))
    numbers: Dict[int, str] = {}
    live_item_value: Dict[int, Decimal] = {}

    pivot_licences = []
    if include_pivot:
        from apps.core.models import PurchaseStatus
        from apps.license.services.item_pivot_selection import select_pivot_licenses
        all_codes = ",".join(PurchaseStatus.objects.values_list("code", flat=True))
        wanted = set(license_ids)
        pivot_licences = [lic for lic in select_pivot_licenses(min_balance=-10 ** 15, license_status="all",
                                                              purchase_status=all_codes, include_norm_links=True)
                          if lic.id in wanted]

    for start in range(0, len(license_ids), chunk):
        ids = license_ids[start:start + chunk]
        snap = balance_snapshot.get_snapshot_bulk(ids)
        debit_alloc = LicenseBalanceCalculator.calculate_debit_for_licenses(ids)
        billed = LicenseBalanceCalculator.calculate_trade_for_licenses(ids)
        items = list(LicenseImportItemsModel.objects.filter(license_id__in=ids))
        live_qty = ItemBalanceCalculator.calculate_available_quantity_for_items(items)
        debit_qty = ItemBalanceCalculator.calculate_debited_quantity_for_items([i.id for i in items])
        outstanding = LicenseBalanceCalculator.get_outstanding_allotment_totals_for_items(ids)
        res.import_items_checked += len(items)
        items_by_lic = defaultdict(list)
        for it in items:
            items_by_lic[it.license_id].append(it)

        plan_tot = defaultdict(lambda: [ZERO, ZERO])
        for p in LicenseItemPlan.objects.filter(license_id__in=ids, is_active=True, is_deleted=False,
                                                is_cancelled=False).values("license_id", "planned_quantity", "planned_cif_fc"):
            plan_tot[p["license_id"]][0] += D(p["planned_quantity"])
            plan_tot[p["license_id"]][1] += D(p["planned_cif_fc"])

        lic_qs = LicenseDetailsModel.objects.filter(id__in=ids).select_related("exporter", "purchase_status", "port")
        for lic in lic_qs:
            lid = lic.id
            numbers[lid] = lic.license_number
            s = snap.get(lid, {})
            its = items_by_lic.get(lid, [])
            for iid, iv in (s.get("items") or {}).items():
                live_item_value[iid] = D(iv.get("available_value"))
            c = values[lid]["canonical"]
            c.update({
                "total_cif": D(s.get("total_licence_cif")), "boe_raw_cif": D(s.get("debited_cif")),
                "debited_cif": D(debit_alloc.get(lid)), "allotted_cif": D(s.get("outstanding_allotted_cif")),
                "billed_cif": D(billed.get(lid)), "balance_cif": D(s.get("financial_balance")),
                "customs_balance_cif": D(s.get("customs_balance")), "opening_balance": D(s.get("opening_balance")),
                "hidden_boe_cif": D(s.get("hidden_boe_total")),
                "planned_qty": plan_tot[lid][0], "planned_cif": plan_tot[lid][1],
                "total_qty": sum((D(i.quantity) for i in its), ZERO),
                "debited_qty": sum((D(debit_qty.get(i.id)) for i in its), ZERO),
                "allotted_qty": sum((D(outstanding.get(i.id, (ZERO, ZERO))[0]) for i in its), ZERO),
                "balance_qty_live": sum((D(live_qty.get(i.id)) for i in its), ZERO),
                "balance_qty_snapshot": sum((D(v.get("available_quantity")) for v in (s.get("items") or {}).values()), ZERO),
            })
            ov = get_overview_counts(lic)["summary"]
            values[lid]["overview"].update({
                "total_cif": D(ov["total_cif"]), "debited_cif": D(ov["total_debited_cif"]),
                "allotted_cif": D(ov["total_allotted_cif"]), "balance_cif": D(ov["total_balance_cif"]),
                "planned_cif": D(ov["total_planned_cif"]),
            })
            # Exactly what the Import Items tab renders: include_canonical=1 rows + footer_totals.
            tab_data = compute_item_ledger_rows(lic, include_canonical=True)
            rows = tab_data["rows"]
            t = values[lid]["items_tab"]
            for key in ("total_cif", "debited_cif", "allotted_cif", "total_qty", "debited_qty", "allotted_qty",
                        "balance_qty"):
                t[key] = sum((D(r[key]) for r in rows), ZERO)
            t["balance_cif"] = D(tab_data["footer_totals"]["actual_effective_balance_cif"])
            t["legacy_row_balance_cif"] = D(tab_data["footer_totals"]["balance_cif"])

        if include_pivot:
            from apps.license.services.item_pivot_service import ItemPivotService
            chunk_ids = set(ids)
            report = ItemPivotService.build([lic for lic in pivot_licences if lic.id in chunk_ids])
            seen = defaultdict(int)
            for row in _walk_pivot_licence_rows(report.get("groups", [])):
                lid = row["license_id"]
                seen[lid] += 1
                if seen[lid] > 1:
                    continue
                pv = values[lid]["pivot"]
                for key in ("total_cif", "debited_cif", "allotted_cif", "billed_cif", "balance_cif", "planned_cif"):
                    pv[key] = D(row.get(key))
                cells = list((row.get("items") or {}).values())
                res.product_combinations += len(cells)
                for key, cell_key in (("cells_total_qty", "total_qty"), ("cells_debited_qty", "debited_qty"),
                                      ("cells_allotted_qty", "allotted_qty"), ("cells_balance_qty", "balance_qty"),
                                      ("cells_planned_qty", "plan_qty"), ("cells_planned_cif", "planned_cif"),
                                      ("cells_debited_cif", "boe_used_cif"), ("cells_allotted_cif", "allotted_cif"),
                                      ("cells_billed_cif", "billed_cif")):
                    pv[key] = sum((D(cell.get(cell_key)) for cell in cells), ZERO)
            dup = [lid for lid, n in seen.items() if n > 1]
            if dup:
                res.notes.append(f"pivot: {len(dup)} licences appear in more than one group (first row used): {dup[:10]}")

    if include_item_report:
        from apps.license.api.views.item_report import ItemReportView
        report = ItemReportView().generate_report(license_status="all", min_balance=-10 ** 15)
        wanted = set(license_ids)
        for row in report["items"]:
            lid = row["license_id"]
            if lid not in wanted:
                continue
            ir = values[lid]["item_report"]
            for key, src in (("total_qty", "quantity"), ("balance_qty", "available_quantity"),
                             ("available_value", "available_balance"), ("planned_qty", "planned_quantity"),
                             ("planned_cif", "planned_cif")):
                ir[key] = ir.get(key, ZERO) + D(row.get(src))
            ir["balance_cif"] = D(row.get("balance_cif"))  # licence-level, repeated per row
            ir["rows"] = ir.get("rows", ZERO) + 1
            live = live_item_value.get(row["id"])
            stored = D(row.get("available_balance"))
            if live is not None and not _close(live, stored, CIF_TOL):
                d = Discrepancy(lid, row.get("license_number") or "?", "item_available_value", "canonical:live_item",
                                live, "item_report:stored", stored, "RC4_ITEM_REPORT_STORED_AVAILABLE_VALUE",
                                item_id=row["id"], item_name=", ".join(n["name"] for n in row.get("item_names") or []),
                                hsn=row.get("hs_code") or "")
                res.discrepancies.append(d)

    res.licences_checked = len(numbers)
    res.surface_values = {lid: {s: dict(m) for s, m in surfaces.items()} for lid, surfaces in values.items()}
    no_ps = frozenset(LicenseDetailsModel.objects.filter(id__in=license_ids, purchase_status__isnull=True)
                      .values_list("id", flat=True))
    _compare(res, numbers, include_pivot=include_pivot, include_item_report=include_item_report, no_purchase_status=no_ps)
    return res


def _compare(res: ReconciliationResult, numbers: Dict[int, str], *, include_pivot: bool, include_item_report: bool,
             no_purchase_status: frozenset = frozenset()) -> None:
    def add(lid, metric, src, sv, rep, rv, cause, tol):
        if not _close(sv, rv, tol):
            res.discrepancies.append(Discrepancy(lid, numbers.get(lid, "?"), metric, src, sv, rep, rv, cause))

    for lid, s in res.surface_values.items():
        c, ov, tab = s.get("canonical", {}), s.get("overview", {}), s.get("items_tab", {})
        pv, ir = s.get("pivot"), s.get("item_report")
        if not c:
            continue
        # 0. Canonical identity — the engine against the stated rule.
        identity = c["total_cif"] - c["debited_cif"] - c["allotted_cif"] - c["billed_cif"]
        add(lid, "balance_cif(identity)", "rule:credit−debit−allot−billed", identity, "canonical", c["balance_cif"],
            "RC8_ENGINE_IDENTITY", CIF_TOL)
        # 1. Overview cards vs canonical.
        add(lid, "total_cif", "canonical", c["total_cif"], "overview", ov["total_cif"], "RC10_SURFACE_MISSING", CIF_TOL)
        add(lid, "debited_cif", "canonical", c["debited_cif"], "overview", ov["debited_cif"], "RC1_OVERVIEW_RAW_BOE_DEBIT", CIF_TOL)
        add(lid, "allotted_cif", "canonical", c["allotted_cif"], "overview", ov["allotted_cif"], "RC10_SURFACE_MISSING", CIF_TOL)
        add(lid, "balance_cif", "canonical", c["balance_cif"], "overview", ov["balance_cif"], "RC10_SURFACE_MISSING", CIF_TOL)
        add(lid, "planned_cif", "canonical", c["planned_cif"], "overview", ov["planned_cif"], "RC6_PLAN_ATTRIBUTION", CIF_TOL)
        add(lid, "balance_cif(cards)", "overview:total−debited−allotted", ov["total_cif"] - ov["debited_cif"] - ov["allotted_cif"],
            "overview", ov["balance_cif"], "RC2_OVERVIEW_BILLED_NOT_SHOWN", CIF_TOL)
        # 2. Import Items tab totals vs canonical.
        # Original CIF lives on export items; import items may carry 0 (shared licence-level ceiling) → RC11.
        add(lid, "total_cif", "canonical", c["total_cif"], "items_tab", tab.get("total_cif", ZERO),
            "RC11_LICENCE_LEVEL_CIF" if tab.get("total_cif", ZERO) == ZERO else "RC12_IMPORT_VS_EXPORT_CIF", CIF_TOL)
        add(lid, "debited_cif", "canonical:raw_boe", c["boe_raw_cif"], "items_tab", tab.get("debited_cif", ZERO),
            "RC3_ITEMS_TAB_STORED_COLUMNS", CIF_TOL)
        add(lid, "allotted_cif", "canonical", c["allotted_cif"], "items_tab", tab.get("allotted_cif", ZERO),
            "RC3_ITEMS_TAB_STORED_COLUMNS", CIF_TOL)
        add(lid, "balance_cif", "canonical", c["balance_cif"], "items_tab", tab.get("balance_cif", ZERO),
            "RC3_ITEMS_TAB_STORED_COLUMNS", CIF_TOL)
        add(lid, "total_qty", "canonical", c["total_qty"], "items_tab", tab.get("total_qty", ZERO), "RC10_SURFACE_MISSING", QTY_TOL)
        add(lid, "debited_qty", "canonical", c["debited_qty"], "items_tab", tab.get("debited_qty", ZERO), "RC3_ITEMS_TAB_STORED_COLUMNS", QTY_TOL)
        add(lid, "allotted_qty", "canonical", c["allotted_qty"], "items_tab", tab.get("allotted_qty", ZERO), "RC3_ITEMS_TAB_STORED_COLUMNS", QTY_TOL)
        add(lid, "balance_qty", "canonical:live", c["balance_qty_live"], "items_tab", tab.get("balance_qty", ZERO), "RC3_ITEMS_TAB_STORED_COLUMNS", QTY_TOL)
        add(lid, "balance_qty", "canonical:live", c["balance_qty_live"], "canonical:snapshot", c["balance_qty_snapshot"], "RC5_AVAILABLE_QTY_FORMULAS", QTY_TOL)
        # 3. Pivot licence row vs canonical, and pivot row vs its own cells.
        if include_pivot:
            if not pv:
                # select_pivot_licenses filters purchase_status__code__in, so a NULL purchase status never reaches the pivot.
                cause = "RC7_FILTER_SCOPE" if lid in no_purchase_status else "RC10_SURFACE_MISSING"
                res.discrepancies.append(Discrepancy(lid, numbers.get(lid, "?"), "presence", "canonical", Decimal(1), "pivot", ZERO, cause))
            else:
                for m in ("total_cif", "debited_cif", "allotted_cif", "billed_cif", "balance_cif", "planned_cif"):
                    add(lid, m, "canonical", c[m], "pivot", pv[m], "RC10_SURFACE_MISSING", CIF_TOL)
                for m, cm in (("debited_cif", "cells_debited_cif"), ("allotted_cif", "cells_allotted_cif"),
                              ("billed_cif", "cells_billed_cif"), ("planned_cif", "cells_planned_cif")):
                    add(lid, m, "pivot:licence_row", pv[m], "pivot:Σcells", pv[cm], "RC9_PIVOT_ITEM_ATTRIBUTION", CIF_TOL)
                add(lid, "planned_qty", "canonical", c["planned_qty"], "pivot:Σcells", pv["cells_planned_qty"], "RC6_PLAN_ATTRIBUTION", QTY_TOL)
        # 4. Item Report vs canonical.
        if include_item_report:
            if not ir:
                res.discrepancies.append(Discrepancy(lid, numbers.get(lid, "?"), "presence", "canonical", Decimal(1), "item_report", ZERO, "RC10_SURFACE_MISSING"))
            else:
                add(lid, "balance_cif", "canonical", c["balance_cif"], "item_report", ir["balance_cif"], "RC10_SURFACE_MISSING", CIF_TOL)
                add(lid, "total_qty", "canonical", c["total_qty"], "item_report", ir["total_qty"], "RC10_SURFACE_MISSING", QTY_TOL)
                add(lid, "balance_qty", "canonical:live", c["balance_qty_live"], "item_report", ir["balance_qty"], "RC5_AVAILABLE_QTY_FORMULAS", QTY_TOL)
                add(lid, "planned_qty", "canonical", c["planned_qty"], "item_report", ir["planned_qty"], "RC6_PLAN_ATTRIBUTION", QTY_TOL)
                add(lid, "planned_cif", "canonical", c["planned_cif"], "item_report", ir["planned_cif"], "RC6_PLAN_ATTRIBUTION", CIF_TOL)
