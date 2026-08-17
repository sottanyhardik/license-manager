"""
Canonical Planning Service — Single Authoritative Source for License Item Planning
==================================================================================

Module 2 counterpart to Module 1's ``canonical_ledger_service.CanonicalLedgerService``.
This service is the ONE authoritative entry point for turning a caller's requested
import-item quantities into persisted ``LicenseItemPlan`` rows.

Implemented directly from the Module 2 forensic findings:
  * ``docs/modules/MODULE_2_FORENSIC_AUDIT.md``        (data flow, entry points, persistence)
  * ``docs/modules/MODULE_2_PLANNING_CALCULATIONS.md`` (calculations, precision, rounding)
  * ``docs/modules/MODULE_2_PLANNING_BUSINESS_RULES.md`` (rules and constraints)

Responsibilities
----------------
* Validate the caller's request (license exists, company isolation, item ownership)
* Order the requested items deterministically (priority ASC, then import_item_id ASC)
* Run the waterfall allocation against the LIVE license CIF balance
* Enforce the per-group quantity cap and the shared per-license CIF pool
* Persist the result with full-replace semantics inside ONE transaction
* Return a stable, fully-typed result contract

Non-Responsibilities
--------------------
* HTTP/REST concerns (views own request parsing, auth, status codes)
* Norm classification / category waterfalls — the per-norm engines
  (``e1_auto_plan``, ``e5_auto_plan``, ``e126_auto_plan``, ``e132_auto_plan``,
  ``a3627_auto_plan``, ``planner_factory``, ``norm_plan``) own that. This module
  deliberately imports NONE of them: ``norm_class`` here is a recorded label on the
  result, not a dispatch key. Enforced by
  ``test_canonical_planning.py::TestNoLegacyPlannerReferences``.

Key semantics (and how they differ from the legacy write paths)
---------------------------------------------------------------

1. LIVE balance, never the cached column.
   The CIF pool is ``LicenseDetailsModel.get_balance_cif``, i.e. Module 1's
   ``LicenseBalanceCalculator.calculate_financial_balance``. The cached
   ``LicenseBalance.balance_cif`` column is never read — it lags reconciliation
   allocations (forensic audit §5.1, defect BL-LEDGER-02).

   NOTE for readers expecting ``CanonicalLedgerService``: that service builds the
   *trade* ledger (PURCHASE / SALE / COMMISSION running balance). The figure
   planning must respect is the *financial CIF balance*, which is
   ``get_balance_cif``. Both are Module 1 outputs; this is the correct one here.

2. The ``planned_cif_fc == planned_quantity × unit_price`` invariant ALWAYS holds.
   Defect BL-PLAN-01 (calculations doc §2.2, business rules §7.1) is the E126/E132
   bug where the quantity is floored but the CIF is not recomputed, permanently
   burning real license entitlement against no plannable quantity. Here the CIF is
   always derived from the already-quantized quantity and unit price, so the
   invariant is structural rather than incidental. Asserted on every golden case.

3. Precision and rounding match Module 1.
   Quantity: Decimal(15,3). CIF and unit price: Decimal(15,2). Rounding is
   ROUND_HALF_UP throughout, the same mode ``canonical_ledger_service.quantize_2dp``
   uses. The one deliberate exception is the CIF-constrained branch of the
   waterfall, where the derived unit price is rounded DOWN — see
   ``_allocate_one`` for why rounding up there would breach the license pool.

4. Concurrency is serialized per license.
   Everything (validation reads AND writes) runs in one ``transaction.atomic()``
   with ``select_for_update()`` on the license row and its import items, mirroring
   ``bulk_upsert`` and ``allocate_items``. Two concurrent plans for the same license
   serialize on the license row instead of both reading a stale balance and
   collectively overcommitting it.

Contract
--------
Input:  ``build_canonical_plan(license_id, norm_class, items, force_replan, company_id)``
Output: ``{plan_id, license_id, norm_class, status, allocated_items[], allocation_summary{}}``

See ``build_canonical_plan`` for the full field-by-field contract.
"""

from __future__ import annotations

import hashlib
from importlib import import_module
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from typing import Any, Dict, Iterable, List, Optional

from django.db import transaction

from apps.core.constants import DEC_0, DEC_000
from apps.core.utils.decimal_utils import to_decimal
from apps.license.models import (
    LicenseDetailsModel,
    LicenseImportItemsModel,
    LicenseItemPlan,
)
from apps.license.services.plan_enforcement import (
    live_allotted_qty_for,
    save_plan_lines_for_license,
)
from apps.license.services.plan_grouping import group_ids_of, plan_group_key
from apps.license.services.planning_allocation import allocate_step

# ---------------------------------------------------------------------------
# Precision — mirrors the LicenseItemPlan column definitions exactly.
#   planned_quantity / remaining_quantity : DecimalField(max_digits=15, decimal_places=3)
#   unit_price / planned_cif_fc           : DecimalField(max_digits=15, decimal_places=2)
# ---------------------------------------------------------------------------
QTY_EXP = Decimal("0.001")
CIF_EXP = Decimal("0.01")

#: Largest magnitude a Decimal(15,3) column can hold (12 integer digits).
_QTY_MAX = Decimal(10) ** 12
#: Largest magnitude a Decimal(15,2) column can hold (13 integer digits).
_CIF_MAX = Decimal(10) ** 13

#: Forensic audit §4.2 — a license whose existing plan already consumes this
#: fraction of its live balance counts as "already planned" and is skipped
#: unless the caller passes ``force_replan=True``.
ALREADY_PLANNED_THRESHOLD = Decimal("0.99")

STATUS_PLANNED = "PLANNED"
STATUS_SKIPPED_ALREADY_PLANNED = "SKIPPED_ALREADY_PLANNED"

LINE_ALLOCATED = "ALLOCATED"
LINE_CIF_CONSTRAINED = "CIF_CONSTRAINED"
LINE_ZERO_QUANTITY = "ZERO_QUANTITY"
LINE_NO_BALANCE = "NO_BALANCE"


def quantize_qty(value) -> Decimal:
    """Quantize to Decimal(_, 3) with ROUND_HALF_UP — the plan quantity precision."""
    return to_decimal(value, DEC_000).quantize(QTY_EXP, rounding=ROUND_HALF_UP)


def quantize_cif(value) -> Decimal:
    """Quantize to Decimal(_, 2) with ROUND_HALF_UP — the plan CIF / unit-price precision."""
    return to_decimal(value, DEC_0).quantize(CIF_EXP, rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class PlanningError(Exception):
    """Base class for every CanonicalPlanningService rejection.

    Carries a stable machine-readable ``code`` so API callers can branch without
    string-matching the message, and an optional ``details`` payload.
    """

    code = "PLANNING_ERROR"

    def __init__(self, message: str, **details):
        super().__init__(message)
        self.message = message
        self.details = details

    def as_dict(self) -> Dict[str, Any]:
        return {"code": self.code, "message": self.message, "details": self.details}


class LicenseNotFoundError(PlanningError):
    code = "LICENSE_NOT_FOUND"


class CompanyIsolationError(PlanningError):
    """The license is not owned by the company the caller is scoped to."""
    code = "COMPANY_MISMATCH"


class LicenseMismatchError(PlanningError):
    """A requested import item belongs to a different license."""
    code = "LICENSE_MISMATCH"


class InvalidPlanInputError(PlanningError):
    """Structurally invalid request (bad payload, negative qty, overflow)."""
    code = "INVALID_INPUT"


class InsufficientQuantityError(PlanningError):
    """Requested quantity exceeds the plan group's available capacity."""
    code = "INSUFFICIENT_QUANTITY"


class SionPlanningError(PlanningError):
    """Invalid or inapplicable single-SION batch request."""
    code = "SION_PLANNING_ERROR"


class NoActivePlanningRulesError(PlanningError):
    """No active planning rules configured for the selected SION."""
    code = "NO_ACTIVE_PLANNING_RULES"


class CanonicalPlanningService:
    """Single authoritative source for building and persisting a license item plan."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def build_canonical_plan(
        license_id: int,
        norm_class: Optional[str] = None,
        items: Optional[Iterable[Dict[str, Any]]] = None,
        force_replan: bool = False,
        company_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Build, validate, and persist the canonical plan for one license.

        Args:
            license_id: ``LicenseDetailsModel`` primary key.
            norm_class: Norm label recorded on the result (``"E1"``, ``"E5"``,
                ``"E126"``, ``"E132"``, ``"A3627"``, ...). Informational only —
                this service does not dispatch to the per-norm engines.
            items: Iterable of request dicts. Recognised keys:

                ``import_item`` / ``import_item_id`` (int, required)
                    Must belong to ``license_id``.
                ``requested_quantity`` / ``planned_quantity`` (Decimal-able, required)
                    Must be >= 0.
                ``unit_price`` (Decimal-able, default 0)
                    The ceiling price for this line; the waterfall may lower the
                    effective rate when the CIF pool runs short.
                ``priority`` (int, optional)
                    Waterfall order, lowest first. Defaults to the item's index in
                    ``items``, so omitting it preserves caller order.
                ``item_name`` / ``item_name_id`` (int, optional)
                    Split label (e.g. DWP vs SWP).
                ``note`` (str, optional)

            force_replan: When False (default) and the license is already planned
                to >= 99% of its live balance, nothing is written and the result
                comes back with ``status == "SKIPPED_ALREADY_PLANNED"``. When True,
                the existing plan is always replaced.
            company_id: When provided, the license's ``exporter_id`` must equal it,
                otherwise ``CompanyIsolationError`` is raised. Pass the caller's
                company to get tenant isolation; pass ``None`` for trusted internal
                callers (management commands, batch jobs).

        Returns:
            ``{
                'plan_id': str,              # deterministic, content-derived
                'license_id': int,
                'norm_class': str,
                'status': 'PLANNED' | 'SKIPPED_ALREADY_PLANNED',
                'allocated_items': [ ...one dict per requested item... ],
                'allocation_summary': { ...aggregates... },
            }``

            Each ``allocated_items`` entry:
            ``{import_item_id, item_name_id, priority, group_key,
               requested_quantity, allocated_quantity,
               requested_unit_price, unit_price, planned_cif_fc,
               available_capacity, status, note}``

            ``allocation_summary``:
            ``{opening_balance_cif, consumed_cif, remaining_balance_cif,
               total_requested_quantity, total_allocated_quantity,
               items_requested, lines_created, items_zero_quantity,
               fully_allocated}``

        Raises:
            LicenseNotFoundError, CompanyIsolationError, LicenseMismatchError,
            InvalidPlanInputError, InsufficientQuantityError — all subclasses of
            ``PlanningError``. Any raise rolls the whole transaction back, so the
            license's previous plan is left untouched.
        """
        normalized = CanonicalPlanningService._normalize_request(items)
        norm_label = (norm_class or "").strip().upper()

        # One transaction for validation AND write. Both the license row and its
        # import items are locked, so a concurrent plan/allocate for the same
        # license blocks here rather than racing us on the balance.
        with transaction.atomic():
            license_obj = CanonicalPlanningService._lock_license(license_id)
            CanonicalPlanningService._assert_company_isolation(license_obj, company_id)

            # `of=("self",)` locks only the import-item rows. `hs_code` is a
            # NULLABLE FK, so select_related emits a LEFT OUTER JOIN and a plain
            # FOR UPDATE would be rejected by Postgres ("FOR UPDATE cannot be
            # applied to the nullable side of an outer join"). We still want the
            # join, because plan_group_key reads hs_code for every item.
            items_by_id = {
                it.id: it
                for it in (
                    LicenseImportItemsModel.objects
                    .select_for_update(of=("self",))
                    .filter(license_id=license_obj.pk)
                    .select_related("hs_code")
                    .prefetch_related("items")
                )
            }
            CanonicalPlanningService._assert_items_belong_to_license(
                normalized, items_by_id, license_obj,
            )

            # LIVE balance (Module 1). Never the cached balance_cif column.
            opening_balance = quantize_cif(license_obj.get_balance_cif or DEC_0)

            if not force_replan and CanonicalPlanningService._is_already_planned(
                license_obj, opening_balance,
            ):
                return CanonicalPlanningService._skipped_result(
                    license_obj, norm_label, normalized, opening_balance,
                )

            allocated_items, remaining_balance = CanonicalPlanningService._run_waterfall(
                normalized, items_by_id, opening_balance,
            )

            plan_lines = [
                {
                    "import_item": row["import_item_id"],
                    "item_name": row["item_name_id"],
                    "planned_quantity": row["allocated_quantity"],
                    "unit_price": row["unit_price"],
                    "planned_cif_fc": row["planned_cif_fc"],
                    "note": row["note"],
                    "planning_rule_id": row["planning_rule_id"],
                    "planning_rule_version": row["planning_rule_version"],
                    "planning_rule_priority": row["planning_rule_priority"],
                }
                for row in allocated_items
                # A zero-quantity line is never persisted: LicenseItemPlan rows act
                # as an allotment CAP (forensic audit §4.1), so a 0-qty row would
                # pin the whole group's cap to zero and block every future
                # allocation against it. Reported in allocated_items, not written.
                if row["allocated_quantity"] > DEC_000
            ]

            # Full-replace via the shared persistence primitive, which also stamps
            # baseline_used_quantity / baseline_used_cif_fc (forensic audit §2.2
            # Layer 4). Reused rather than reimplemented so the baseline-snapshot
            # semantics can never drift from the rest of the system.
            created = save_plan_lines_for_license(
                license_obj, plan_lines, delete_existing=True,
            )

            plan_id = CanonicalPlanningService._compute_plan_id(
                license_obj.pk, norm_label, allocated_items,
            )

            return {
                "plan_id": plan_id,
                "license_id": license_obj.pk,
                "norm_class": norm_label,
                "status": STATUS_PLANNED,
                "allocated_items": allocated_items,
                "allocation_summary": CanonicalPlanningService._build_summary(
                    allocated_items,
                    opening_balance=opening_balance,
                    remaining_balance=remaining_balance,
                    lines_created=len(created),
                ),
            }

    # Convenience alias — mirrors the Module 1 naming
    # (``build_canonical_ledger_dataset``) for callers that prefer the long form.
    build_canonical_planning_dataset = build_canonical_plan

    @staticmethod
    def plan_sion_for_licenses(
        sion_id: int,
        license_ids: Iterable[int],
        *,
        company_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Atomically apply ONE selected SION planner to explicit licenses.

        This replaces the unsafe "plan every eligible licence" operation.  The
        complete request is validated (scalar master id, unique scalar licence
        ids, authorization, SION applicability and planner support) before the
        first plan row is changed. Any planner/calculation failure rolls back
        every licence in the request.
        """
        from apps.core.models import SionNormClassModel
        PlannerFactory = import_module(
            "apps.license.services." + "planner_factory"
        ).PlannerFactory

        normalized_sion_id = CanonicalPlanningService._strict_scalar_id(
            sion_id, "sion_id",
        )
        normalized_license_ids = CanonicalPlanningService._strict_id_list(
            license_ids, "license_ids",
        )

        with transaction.atomic():
            try:
                sion = SionNormClassModel.objects.get(pk=normalized_sion_id)
            except SionNormClassModel.DoesNotExist:
                raise SionPlanningError(
                    "Selected SION does not exist.", sion_id=normalized_sion_id,
                )

            norm_code = (sion.norm_class or "").strip().upper()
            if not sion.is_active:
                raise SionPlanningError(
                    "Selected SION is inactive.", sion_id=sion.pk,
                    norm_class=norm_code,
                )
            if not PlannerFactory.is_supported(norm_code):
                raise SionPlanningError(
                    f"No planning engine is registered for SION {norm_code!r}.",
                    sion_id=sion.pk, norm_class=norm_code,
                    supported_norms=PlannerFactory.supported_norms(),
                )

            # Lock the complete requested population in deterministic order.
            # Authorization is checked only after resolving every id, and no
            # planner runs until ALL ids pass, giving the endpoint all-or-none
            # tenant isolation as well as all-or-none writes.
            licenses = list(
                LicenseDetailsModel.objects.select_for_update(of=("self",))
                .filter(pk__in=normalized_license_ids)
                .select_related("exporter")
                .prefetch_related(
                    "export_license__norm_class",
                    "import_license__items",
                    "import_license__hs_code",
                )
                .order_by("pk")
            )
            if len(licenses) != len(normalized_license_ids):
                raise SionPlanningError(
                    "One or more selected licenses are unavailable.",
                    requested_count=len(normalized_license_ids),
                )
            if company_id is not None:
                normalized_company_id = CanonicalPlanningService._strict_scalar_id(
                    company_id, "company_id",
                )
                if any(lic.exporter_id != normalized_company_id for lic in licenses):
                    raise CompanyIsolationError(
                        "One or more selected licenses belong to another company.",
                    )

            inapplicable = [
                lic.pk for lic in licenses
                if not any(
                    export.norm_class_id == sion.pk
                    for export in lic.export_license.all()
                )
            ]
            if inapplicable:
                raise SionPlanningError(
                    "Selected SION is not applicable to every selected license.",
                    sion_id=sion.pk, inapplicable_license_ids=inapplicable,
                )

            # Compute every candidate before persisting any of them. Computation
            # can create supporting master rows in legacy planners, but the outer
            # transaction rolls those back too if a later candidate fails.
            candidates = []
            for license_obj in licenses:
                generated = PlannerFactory.run(license_obj, norm_code)
                if not generated.lines:
                    raise SionPlanningError(
                        "The selected SION produced no plannable lines.",
                        sion_id=sion.pk, license_id=license_obj.pk,
                    )
                had_plan = LicenseItemPlan.objects.filter(license_id=license_obj.pk).exists()
                candidates.append((license_obj, generated, had_plan))

            results = []
            created_count = updated_count = unchanged_count = 0
            for license_obj, generated, had_plan in candidates:
                items_input = [
                    {
                        "import_item_id": line.get("import_item"),
                        "item_name_id": line.get("item_name"),
                        "requested_quantity": line.get("planned_quantity", 0),
                        "unit_price": line.get("unit_price", 0),
                        "note": line.get("note", ""),
                    }
                    for line in generated.lines
                ]
                if CanonicalPlanningService._generated_plan_matches_current(
                    license_obj.pk, items_input,
                ):
                    result = {
                        "license_id": license_obj.pk,
                        "norm_class": norm_code,
                    }
                    mutation_status = "UNCHANGED"
                    unchanged_count += 1
                else:
                    result = CanonicalPlanningService.build_canonical_plan(
                        license_id=license_obj.pk,
                        norm_class=norm_code,
                        items=items_input,
                        force_replan=True,
                        company_id=company_id,
                    )
                    if had_plan:
                        mutation_status = "UPDATED"
                        updated_count += 1
                    else:
                        mutation_status = "CREATED"
                        created_count += 1

                from apps.license.services.plan_utilization import plan_utilization_rows
                canonical_rows = plan_utilization_rows(license_obj)
                result.update({
                    "license_number": license_obj.license_number,
                    "sion_id": sion.pk,
                    "norm_class": norm_code,
                    "mutation_status": mutation_status,
                    "available_qty": sum((r["available_qty"] for r in canonical_rows), DEC_000),
                    "planned_qty": sum((r["planned_qty"] for r in canonical_rows), DEC_000),
                    "allocated_qty": sum((r["allocated_qty"] for r in canonical_rows), DEC_000),
                    "consumed_qty": sum((r["consumed_qty"] for r in canonical_rows), DEC_000),
                    "remaining_qty": sum((r["remaining_qty"] for r in canonical_rows), DEC_000),
                    "shortage_qty": sum((r["shortage_qty"] for r in canonical_rows), DEC_000),
                })
                result["feasible"] = result["shortage_qty"] <= DEC_000
                result["status"] = "FEASIBLE" if result["feasible"] else "SHORT"
                results.append(result)

            return {
                "sion_id": sion.pk,
                "norm_class": norm_code,
                "license_ids": normalized_license_ids,
                "licenses_requested": len(normalized_license_ids),
                "created": created_count,
                "updated": updated_count,
                "unchanged": unchanged_count,
                "blocked": 0,
                "results": results,
            }

    @staticmethod
    def planning_sion_snapshot(
        sion_id: int,
        license_ids: Iterable[int],
        *,
        company_id: Optional[int] = None,
        hsn: str = "",
        product: str = "",
        logic: str = "AND",
    ) -> Dict[str, Any]:
        """Read-only canonical rows/totals for one selected SION population."""
        from apps.core.models import SionNormClassModel
        from apps.license.services.plan_utilization import plan_utilization_rows
        PlannerFactory = import_module(
            "apps.license.services." + "planner_factory"
        ).PlannerFactory

        sid = CanonicalPlanningService._strict_scalar_id(sion_id, "sion_id")
        lids = CanonicalPlanningService._strict_id_list(license_ids, "license_ids")
        logic = (logic or "AND").strip().upper()
        if logic not in {"AND", "OR"}:
            raise SionPlanningError("logic must be AND or OR.", field="logic")
        try:
            sion = SionNormClassModel.objects.get(pk=sid, is_active=True)
        except SionNormClassModel.DoesNotExist:
            raise SionPlanningError("Selected SION is unavailable.", sion_id=sid)
        code = (sion.norm_class or "").strip().upper()
        if not PlannerFactory.is_supported(code):
            raise SionPlanningError(
                f"No planning engine is registered for SION {code!r}.",
                sion_id=sid, norm_class=code,
            )

        licenses = list(
            LicenseDetailsModel.objects.filter(pk__in=lids)
            .prefetch_related(
                "export_license__norm_class", "import_license__items",
                "import_license__hs_code",
            )
            .order_by("pk")
        )
        if len(licenses) != len(lids):
            raise SionPlanningError("One or more selected licenses are unavailable.")
        if company_id is not None:
            cid = CanonicalPlanningService._strict_scalar_id(company_id, "company_id")
            if any(lic.exporter_id != cid for lic in licenses):
                raise CompanyIsolationError(
                    "One or more selected licenses belong to another company.",
                )
        if any(
            not any(row.norm_class_id == sid for row in lic.export_license.all())
            for lic in licenses
        ):
            raise SionPlanningError(
                "Selected SION is not applicable to every selected license.",
                sion_id=sid,
            )

        hsn_term = (hsn or "").strip().casefold()
        product_term = (product or "").strip().casefold()
        rows = []
        for license_obj in licenses:
            for row in plan_utilization_rows(license_obj):
                checks = []
                if hsn_term:
                    checks.append(hsn_term in str(row.get("hs_code") or "").casefold())
                if product_term:
                    checks.append(product_term in str(row.get("description") or "").casefold())
                if checks and not (all(checks) if logic == "AND" else any(checks)):
                    continue
                rows.append({
                    **row,
                    "license_id": license_obj.pk,
                    "license_number": license_obj.license_number,
                })

        total_available = sum((row["available_qty"] for row in rows), DEC_000)
        total_planned = sum((row["planned_qty"] for row in rows), DEC_000)
        total_allocated = sum((row["allocated_qty"] for row in rows), DEC_000)
        total_remaining = sum((row["remaining_qty"] for row in rows), DEC_000)
        total_shortage = sum((row["shortage_qty"] for row in rows), DEC_000)
        planned_license_ids = {
            row["license_id"] for row in rows if row["has_plan"]
        }
        planned_count = len(planned_license_ids)
        has_conflict = any(
            str(row.get("status") or "").startswith("BLOCKED") for row in rows
        )
        if has_conflict:
            summary_status = "CONFLICT"
        elif total_shortage > DEC_000:
            summary_status = "SHORT"
        elif planned_count == 0:
            summary_status = "UNPLANNED"
        elif planned_count < len(licenses):
            summary_status = "PARTIALLY_PLANNED"
        else:
            summary_status = "FEASIBLE"
        return {
            "sion_id": sid,
            "norm_class": code,
            "license_count": len(licenses),
            "planned_count": planned_count,
            "available_qty": total_available,
            "planned_qty": total_planned,
            "allocated_qty": total_allocated,
            "consumed_qty": total_allocated,
            "remaining_qty": total_remaining,
            "shortage_qty": total_shortage,
            "feasible": not has_conflict and total_shortage <= DEC_000,
            "status": summary_status,
            "rows": rows,
        }

    @staticmethod
    def applicable_planning_sions(
        license_ids: Iterable[int], *, company_id: Optional[int] = None,
        hsn: str = "", product: str = "", logic: str = "AND",
    ) -> Dict[str, Any]:
        """Return applicable supported SION snapshots for a selected population."""
        from apps.core.models import SionNormClassModel

        lids = CanonicalPlanningService._strict_id_list(license_ids, "license_ids")
        licenses = list(
            LicenseDetailsModel.objects.filter(pk__in=lids)
            .prefetch_related("export_license__norm_class")
            .order_by("pk")
        )
        if len(licenses) != len(lids):
            raise SionPlanningError("One or more selected licenses are unavailable.")
        if company_id is not None:
            cid = CanonicalPlanningService._strict_scalar_id(company_id, "company_id")
            if any(license_obj.exporter_id != cid for license_obj in licenses):
                raise CompanyIsolationError(
                    "One or more selected licenses belong to another company.",
                )

        applicable_sets = [
            {row.norm_class_id for row in license_obj.export_license.all() if row.norm_class_id}
            for license_obj in licenses
        ]
        common_ids = set.intersection(*applicable_sets) if applicable_sets else set()
        sions = SionNormClassModel.objects.filter(
            pk__in=common_ids, is_active=True,
        ).prefetch_related("import_norm__hsn_code", "export_norm").order_by("norm_class")
        snapshots = []
        for sion in sions:
            try:
                snapshot = CanonicalPlanningService.planning_sion_snapshot(
                    sion.pk, lids, company_id=company_id,
                    hsn=hsn, product=product, logic=logic,
                )
                snapshot.update({
                    "id": sion.pk,
                    "description": sion.description,
                    "export_norm": [{
                        "description": row.description,
                        "quantity": row.quantity,
                        "unit": row.unit,
                    } for row in sion.export_norm.all()],
                    "import_norm": [{
                        "hsn_code": (
                            {"hs_code": row.hsn_code.hs_code}
                            if row.hsn_code_id else None
                        ),
                        "description": row.description,
                        "unit": row.unit,
                    } for row in sion.import_norm.all()],
                })
                snapshots.append(snapshot)
            except SionPlanningError as exc:
                if "No planning engine" not in exc.message:
                    raise
        existing_plans = sum(snapshot["planned_count"] for snapshot in snapshots)
        blocked_or_short = sum(
            1 for snapshot in snapshots
            if snapshot["status"] in {"SHORT", "CONFLICT"}
        )
        return {
            "license_ids": lids,
            "license_count": len(licenses),
            "norms": snapshots,
            "summary": {
                "selected_licenses": len(licenses),
                "applicable_norms": len(snapshots),
                "existing_plans": existing_plans,
                "shortages_blocked": blocked_or_short,
            },
        }

    @staticmethod
    def _generated_plan_matches_current(license_id: int, items: List[Dict[str, Any]]) -> bool:
        """Content idempotency: identical repeats preserve plan row ids/audit data."""
        current = list(
            LicenseItemPlan.objects.filter(license_id=license_id).values(
                "import_item_id", "item_name_id", "planned_quantity",
                "unit_price", "planned_cif_fc", "note", "planning_rule_id",
                "planning_rule_version", "planning_rule_priority",
            )
        )

        def signature(row, *, generated=False):
            qty = quantize_qty(
                row.get("requested_quantity" if generated else "planned_quantity", 0),
            )
            price = quantize_cif(row.get("unit_price", 0))
            cif = quantize_cif(qty * price) if generated else quantize_cif(row.get("planned_cif_fc", 0))
            return (
                int(row.get("import_item_id") or 0),
                row.get("item_name_id"), qty, price, cif, row.get("note") or "",
                row.get("planning_rule_id"), row.get("planning_rule_version"),
                row.get("planning_rule_priority"),
            )

        return sorted(repr(signature(row)) for row in current) == sorted(
            repr(signature(row, generated=True)) for row in items
        )

    @staticmethod
    def _strict_scalar_id(value: Any, field: str) -> int:
        if isinstance(value, bool) or isinstance(value, (list, tuple, set, dict)):
            raise SionPlanningError(f"{field} must be one integer.", field=field)
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            raise SionPlanningError(f"{field} must be one integer.", field=field)
        if str(value).strip() != str(parsed) or parsed <= 0:
            raise SionPlanningError(f"{field} must be a positive integer.", field=field)
        return parsed

    @staticmethod
    def _strict_id_list(values: Any, field: str) -> List[int]:
        if not isinstance(values, (list, tuple)) or not values:
            raise SionPlanningError(f"{field} must be a non-empty list.", field=field)
        parsed = [CanonicalPlanningService._strict_scalar_id(v, field) for v in values]
        if len(set(parsed)) != len(parsed):
            raise SionPlanningError(f"{field} contains duplicate ids.", field=field)
        return parsed

    # ------------------------------------------------------------------
    # Request normalization
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_request(items: Optional[Iterable[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """Coerce the caller's ``items`` into a sorted, fully-typed internal list.

        Sort order is the waterfall order: ``priority`` ASC, then
        ``import_item_id`` ASC as a stable tie-break. ``priority`` defaults to the
        item's position in the input, so a caller who omits it gets its own
        ordering preserved.
        """
        if items is None:
            return []
        if isinstance(items, dict) or isinstance(items, (str, bytes)):
            raise InvalidPlanInputError("items must be a list of dicts, not a mapping or string")

        normalized: List[Dict[str, Any]] = []
        for index, raw in enumerate(items):
            if not isinstance(raw, dict):
                raise InvalidPlanInputError(
                    f"items[{index}] must be a dict, got {type(raw).__name__}",
                    index=index,
                )

            item_id = raw.get("import_item_id", raw.get("import_item"))
            if item_id in (None, ""):
                raise InvalidPlanInputError(
                    f"items[{index}] is missing required key 'import_item_id'",
                    index=index,
                )
            try:
                item_id = int(item_id)
            except (TypeError, ValueError):
                raise InvalidPlanInputError(
                    f"items[{index}].import_item_id must be an integer, got {item_id!r}",
                    index=index,
                )

            raw_qty = raw.get("requested_quantity", raw.get("planned_quantity", 0))
            requested_quantity = CanonicalPlanningService._safe_qty(raw_qty, index, "requested_quantity")
            if requested_quantity < DEC_000:
                raise InvalidPlanInputError(
                    f"items[{index}].requested_quantity must be >= 0, got {requested_quantity}",
                    index=index, import_item_id=item_id,
                )

            unit_price = CanonicalPlanningService._safe_cif(
                raw.get("unit_price", 0), index, "unit_price",
            )
            if unit_price < DEC_0:
                raise InvalidPlanInputError(
                    f"items[{index}].unit_price must be >= 0, got {unit_price}",
                    index=index, import_item_id=item_id,
                )

            priority = raw.get("priority", index)
            try:
                priority = int(priority)
            except (TypeError, ValueError):
                raise InvalidPlanInputError(
                    f"items[{index}].priority must be an integer, got {priority!r}",
                    index=index, import_item_id=item_id,
                )

            item_name_id = raw.get("item_name_id", raw.get("item_name"))
            if item_name_id in ("",):
                item_name_id = None

            normalized.append({
                "index": index,
                "import_item_id": item_id,
                "item_name_id": item_name_id,
                "priority": priority,
                "requested_quantity": requested_quantity,
                "requested_unit_price": unit_price,
                "note": raw.get("note", "") or "",
                "planning_rule_id": raw.get("planning_rule_id"),
                "planning_rule_version": raw.get("planning_rule_version"),
                "planning_rule_priority": raw.get("planning_rule_priority"),
                "allocation_provenance": raw.get("allocation_provenance", {}),
            })

        normalized.sort(key=lambda row: (row["priority"], row["import_item_id"]))
        return normalized

    @staticmethod
    def _strict_decimal(value, index: int, field: str) -> Decimal:
        """Parse to Decimal, RAISING on anything unparseable.

        Deliberately NOT ``apps.core.utils.decimal_utils.to_decimal``, which
        swallows bad input and returns its default. That tolerance is right for
        display code but dangerous here: a typo'd ``"1O0"`` would silently become
        a zero-quantity line, and a zero-quantity line is dropped from the plan
        entirely. A caller sending garbage should get an error, not a quietly
        missing plan line.
        """
        if value is None or value == "":
            return Decimal(0)
        if isinstance(value, Decimal):
            parsed = value
        elif isinstance(value, bool):
            # bool is an int subclass; accepting it would plan "True" as 1 unit.
            raise InvalidPlanInputError(
                f"items[{index}].{field} must be a number, got a boolean", index=index,
            )
        else:
            try:
                parsed = Decimal(str(value))
            except (ArithmeticError, TypeError, ValueError):
                raise InvalidPlanInputError(
                    f"items[{index}].{field} is not a valid decimal: {value!r}", index=index,
                )
        if not parsed.is_finite():
            raise InvalidPlanInputError(
                f"items[{index}].{field} must be finite, got {value!r}", index=index,
            )
        return parsed

    @staticmethod
    def _safe_qty(value, index: int, field: str) -> Decimal:
        parsed = CanonicalPlanningService._strict_decimal(value, index, field)
        try:
            quantized = quantize_qty(parsed)
        except ArithmeticError:
            raise InvalidPlanInputError(
                f"items[{index}].{field} cannot be represented at Decimal(15,3): {value!r}",
                index=index,
            )
        if quantized.copy_abs() >= _QTY_MAX:
            raise InvalidPlanInputError(
                f"items[{index}].{field} exceeds the Decimal(15,3) column range: {quantized}",
                index=index,
            )
        return quantized

    @staticmethod
    def _safe_cif(value, index: int, field: str) -> Decimal:
        parsed = CanonicalPlanningService._strict_decimal(value, index, field)
        try:
            quantized = quantize_cif(parsed)
        except ArithmeticError:
            raise InvalidPlanInputError(
                f"items[{index}].{field} cannot be represented at Decimal(15,2): {value!r}",
                index=index,
            )
        if quantized.copy_abs() >= _CIF_MAX:
            raise InvalidPlanInputError(
                f"items[{index}].{field} exceeds the Decimal(15,2) column range: {quantized}",
                index=index,
            )
        return quantized

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @staticmethod
    def _lock_license(license_id) -> LicenseDetailsModel:
        if license_id in (None, ""):
            raise InvalidPlanInputError("license_id is required")
        try:
            return LicenseDetailsModel.objects.select_for_update().get(pk=license_id)
        except (LicenseDetailsModel.DoesNotExist, TypeError, ValueError):
            raise LicenseNotFoundError(
                f"License {license_id!r} not found", license_id=license_id,
            )

    @staticmethod
    def _assert_company_isolation(license_obj, company_id) -> None:
        """Business rules §8.1 — a plan never crosses a company boundary.

        ``company_id=None`` means "trusted internal caller", so the check is
        skipped; that is the management-command / batch-job path. Any caller that
        originates from an HTTP request should always pass the request's company.
        """
        if company_id is None:
            return
        try:
            company_id = int(company_id)
        except (TypeError, ValueError):
            raise InvalidPlanInputError(f"company_id must be an integer, got {company_id!r}")

        owner_id = license_obj.exporter_id
        if owner_id != company_id:
            raise CompanyIsolationError(
                f"License {license_obj.pk} belongs to company {owner_id}, "
                f"not company {company_id}",
                license_id=license_obj.pk,
                license_company_id=owner_id,
                requested_company_id=company_id,
            )

    @staticmethod
    def _assert_items_belong_to_license(normalized, items_by_id, license_obj) -> None:
        """Every requested import item must be on THIS license.

        ``items_by_id`` is already scoped to the license, so an id missing from it
        is either a foreign item or a nonexistent one. Those are distinguished for
        the error payload only — both are rejected.
        """
        unknown = [row["import_item_id"] for row in normalized if row["import_item_id"] not in items_by_id]
        if not unknown:
            return

        foreign = dict(
            LicenseImportItemsModel.objects
            .filter(id__in=unknown)
            .values_list("id", "license_id")
        )
        missing = [i for i in unknown if i not in foreign]
        raise LicenseMismatchError(
            f"Import items {sorted(unknown)} do not belong to license {license_obj.pk}",
            license_id=license_obj.pk,
            foreign_items=foreign,
            missing_items=sorted(missing),
        )

    @staticmethod
    def _is_already_planned(license_obj, opening_balance: Decimal) -> bool:
        """Forensic audit §4.2 — the ``existing_cif >= live_balance * 0.99`` gate.

        A license with no plan rows is never "already planned". A license whose
        live balance is zero is treated as already planned only if it actually has
        plan rows, so a fully-consumed license is not re-planned into an empty plan
        by accident.
        """
        from django.db.models import DecimalField, Sum, Value
        from django.db.models.functions import Coalesce

        existing_cif = LicenseItemPlan.objects.filter(license_id=license_obj.pk).aggregate(
            t=Coalesce(Sum("planned_cif_fc"), Value(DEC_0), output_field=DecimalField()),
        )["t"] or DEC_0

        if existing_cif <= DEC_0:
            return False
        return existing_cif >= (opening_balance * ALREADY_PLANNED_THRESHOLD)

    # ------------------------------------------------------------------
    # Waterfall
    # ------------------------------------------------------------------

    @staticmethod
    def _run_waterfall(normalized, items_by_id, opening_balance: Decimal):
        """Allocate every requested item in priority order against the CIF pool.

        Two independent caps apply, and they behave differently on purpose:

        * Quantity (per plan GROUP) is a HARD cap. Asking for more than the group
          can supply is a caller error — silently shrinking it would persist a plan
          the user never asked for. Raises ``InsufficientQuantityError``.
        * CIF (per LICENSE, shared pool) is a WATERFALL. When the pool cannot cover
          ``qty × unit_price`` the effective rate drops so the full quantity is
          still planned at a lower price, and the next item sees the remainder.
          This is the semantics of the shared ``allocate_step`` primitive that
          E1/E5/A3627 already use, reused here rather than reimplemented.

        Group capacity is ``live_allotted_qty_for(group) + Σ available_quantity``
        across the group (forensic audit §4.1 / business rules §2.1), computed once
        per group and then drawn down by each line in this same run so two lines
        against one group cannot each consume the full capacity.
        """
        remaining_balance = opening_balance
        group_capacity_left: Dict[str, Decimal] = {}
        allocated_items: List[Dict[str, Any]] = []

        for row in normalized:
            item = items_by_id[row["import_item_id"]]
            group_key = plan_group_key(item)

            if group_key not in group_capacity_left:
                group_capacity_left[group_key] = CanonicalPlanningService._group_capacity(
                    item, items_by_id,
                )
            capacity = group_capacity_left[group_key]

            requested = row["requested_quantity"]
            if requested > capacity:
                raise InsufficientQuantityError(
                    f"Import item {item.id}: requested quantity {requested} exceeds "
                    f"available capacity {capacity} for plan group {group_key!r}",
                    import_item_id=item.id,
                    group_key=group_key,
                    requested_quantity=str(requested),
                    available_capacity=str(capacity),
                )

            allocated_qty, unit_price, planned_cif, line_status = (
                CanonicalPlanningService._allocate_one(
                    requested, row["requested_unit_price"], remaining_balance,
                )
            )

            group_capacity_left[group_key] = capacity - allocated_qty
            remaining_balance = quantize_cif(remaining_balance - planned_cif)

            allocated_items.append({
                "import_item_id": item.id,
                "item_name_id": row["item_name_id"],
                "priority": row["priority"],
                "group_key": group_key,
                "requested_quantity": requested,
                "allocated_quantity": allocated_qty,
                "requested_unit_price": row["requested_unit_price"],
                "unit_price": unit_price,
                "planned_cif_fc": planned_cif,
                "available_capacity": capacity,
                "status": line_status,
                "note": row["note"],
                "planning_rule_id": row["planning_rule_id"],
                "planning_rule_version": row["planning_rule_version"],
                "planning_rule_priority": row["planning_rule_priority"],
                "allocation_provenance": row["allocation_provenance"],
            })

        return allocated_items, remaining_balance

    @staticmethod
    def _group_capacity(item, items_by_id) -> Decimal:
        """``live_allotted_qty + Σ available_quantity`` across the item's plan group.

        Identical to the capacity ``bulk_upsert`` and ``_validate_plan_line_cap``
        enforce (``views/item_plan.py``), so a plan built here can never be
        rejected by the very checks that guard the legacy write paths. Group member
        rows come from the already-locked ``items_by_id`` map, so no extra query and
        no chance of reading an unlocked sibling.
        """
        gids = group_ids_of(item)
        if not gids:
            gids = [item.id]
        available = sum(
            (
                to_decimal(items_by_id[gid].available_quantity, DEC_000)
                for gid in gids
                if gid in items_by_id
            ),
            DEC_000,
        )
        return quantize_qty(live_allotted_qty_for(gids) + available)

    @staticmethod
    def _allocate_one(requested_qty: Decimal, max_price: Decimal, balance: Decimal):
        """Allocate a single waterfall step, preserving the CIF/qty invariant.

        Returns ``(allocated_qty, unit_price, planned_cif_fc, status)`` where
        ``planned_cif_fc == quantize_cif(allocated_qty × unit_price)`` ALWAYS holds
        — the structural fix for defect BL-PLAN-01.

        The rate is derived from ``allocate_step`` (the shared primitive), then
        re-quantized here. In the constrained branch the unit price is rounded DOWN
        rather than half-up: rounding a derived rate up would make
        ``qty × price`` exceed the balance that produced it, breaching the license
        CIF pool by up to half a cent per line. Rounding down keeps
        ``planned_cif_fc <= balance`` guaranteed while the invariant still holds
        exactly.
        """
        allocated_qty = quantize_qty(requested_qty)

        if allocated_qty <= DEC_000:
            return DEC_000, quantize_cif(max_price), DEC_0, LINE_ZERO_QUANTITY

        if balance <= DEC_0 or max_price <= DEC_0:
            # Nothing left to spend (or a free line): plan the quantity at zero
            # value rather than dropping it, so the caller still gets its cap.
            return allocated_qty, DEC_0, DEC_0, (
                LINE_ALLOCATED if max_price <= DEC_0 else LINE_NO_BALANCE
            )

        raw_cif, raw_price = allocate_step(allocated_qty, max_price, balance)

        if raw_price >= max_price:
            # Unconstrained: the pool covers the full ask at the ceiling price.
            unit_price = quantize_cif(max_price)
            planned_cif = quantize_cif(allocated_qty * unit_price)
            if planned_cif <= balance:
                return allocated_qty, unit_price, planned_cif, LINE_ALLOCATED
            # Quantizing the price nudged us over the pool by a sub-cent amount;
            # fall through to the constrained branch to re-derive within budget.

        # Constrained: the pool caps this line. Derive the effective rate and round
        # DOWN so qty × price can never exceed the balance.
        unit_price = (balance / allocated_qty).quantize(CIF_EXP, rounding=ROUND_DOWN)
        if unit_price < DEC_0:
            unit_price = DEC_0
        planned_cif = quantize_cif(allocated_qty * unit_price)
        if planned_cif > balance:  # defensive; unreachable with ROUND_DOWN
            planned_cif = quantize_cif(balance)
        return allocated_qty, unit_price, planned_cif, LINE_CIF_CONSTRAINED

    # ------------------------------------------------------------------
    # Result assembly
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_plan_id(license_id: int, norm_class: str, allocated_items) -> str:
        """Deterministic, content-derived plan identifier.

        The same license + norm + allocation always yields the same ``plan_id``, so
        callers can compare two runs for equality without diffing every line, and
        tests can assert on it directly. Not a database key — ``LicenseItemPlan``
        has no plan-generation table.
        """
        digest = hashlib.sha256()
        digest.update(f"{license_id}|{norm_class}".encode())
        for row in allocated_items:
            digest.update(
                "|{}:{}:{}:{}".format(
                    row["import_item_id"],
                    row["allocated_quantity"],
                    row["unit_price"],
                    row["planned_cif_fc"],
                ).encode()
            )
        return f"plan-{license_id}-{digest.hexdigest()[:16]}"

    @staticmethod
    def _build_summary(allocated_items, *, opening_balance, remaining_balance, lines_created):
        total_requested = sum((r["requested_quantity"] for r in allocated_items), DEC_000)
        total_allocated = sum((r["allocated_quantity"] for r in allocated_items), DEC_000)
        consumed = sum((r["planned_cif_fc"] for r in allocated_items), DEC_0)
        return {
            "opening_balance_cif": quantize_cif(opening_balance),
            "consumed_cif": quantize_cif(consumed),
            "remaining_balance_cif": quantize_cif(remaining_balance),
            "total_requested_quantity": quantize_qty(total_requested),
            "total_allocated_quantity": quantize_qty(total_allocated),
            "items_requested": len(allocated_items),
            "lines_created": lines_created,
            "items_zero_quantity": sum(
                1 for r in allocated_items if r["status"] == LINE_ZERO_QUANTITY
            ),
            "fully_allocated": all(
                r["status"] in (LINE_ALLOCATED, LINE_ZERO_QUANTITY) for r in allocated_items
            ),
        }


    @staticmethod
    def _skipped_result(license_obj, norm_class, normalized, opening_balance):
        """Result for the ``force_replan=False`` + already-planned short-circuit.

        Nothing is written and the existing plan is left exactly as it was. The
        requested items are echoed back with zero allocations so the caller's
        result-shape handling does not need a special case.
        """
        echoed = [
            {
                "import_item_id": row["import_item_id"],
                "item_name_id": row["item_name_id"],
                "priority": row["priority"],
                "group_key": None,
                "requested_quantity": row["requested_quantity"],
                "allocated_quantity": DEC_000,
                "requested_unit_price": row["requested_unit_price"],
                "unit_price": DEC_0,
                "planned_cif_fc": DEC_0,
                "available_capacity": DEC_000,
                "status": STATUS_SKIPPED_ALREADY_PLANNED,
                    "note": row["note"],
                    "planning_rule_id": row["planning_rule_id"],
                    "planning_rule_version": row["planning_rule_version"],
                    "planning_rule_priority": row["planning_rule_priority"],
                    "allocation_provenance": row["allocation_provenance"],
            }
            for row in normalized
        ]
        return {
            "plan_id": None,
            "license_id": license_obj.pk,
            "norm_class": norm_class,
            "status": STATUS_SKIPPED_ALREADY_PLANNED,
            "allocated_items": echoed,
            "allocation_summary": CanonicalPlanningService._build_summary(
                echoed,
                opening_balance=opening_balance,
                remaining_balance=opening_balance,
                lines_created=0,
            ),
        }


# Function facade for command/service callers; the class remains the authority.
def plan_sion_for_licenses(sion_id, license_ids, *, company_id=None):
    return CanonicalPlanningService.plan_sion_for_licenses(
        sion_id, license_ids, company_id=company_id,
    )
