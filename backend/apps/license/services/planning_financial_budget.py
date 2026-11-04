"""Authoritative planning CIF budget: one calculation for validation and execution.

Planning Original CIF is the export-manifest CIF per SION norm (``LicenseExportItemModel``
rows with that ``norm_class``). It is NOT the import-item CIF.

Utilisation comes from the canonical licence calculation and is split into three
mutually exclusive parts:

    BOE CIF              = debited + invoiced_boe_covered   (every BOE amount, once)
    ALLOTMENT CIF        = allotted                          (outstanding, not BOE-backed)
    BILLED WITHOUT BOE   = invoiced - invoiced_boe_covered   (sales not represented by BOE)
    Utilised CIF        = BOE CIF + ALLOTMENT CIF + BILLED WITHOUT BOE
                         = debited + allotted + invoiced

Attribution to a SION norm (conservative, fail-closed):

* BOE and allotment usage is attributed to a norm only when its planning target item is
  exported under exactly one norm on the same licence. That usage is ``attributed``.
* Everything else (unmapped or ambiguous BOE/allotment, and all billed-without-BOE sales)
  stays licence-level ``unattributed`` usage. It is never assigned to a norm.

Planning ceiling for norm N on licence L:

    licence_remaining = export_total(L) - utilised(L)
    norm_remaining    = export(L, N) - attributed(L, N)
    ceiling           = max(0, min(licence_remaining, norm_remaining))

Because every utilisation amount is subtracted once at licence level, no amount can be
counted twice across norms. Attribution only decides which norm may use the remainder
first; the licence-level cap always holds.

Missing canonical data, a missing export entitlement, or a negative remainder block the
affected norm explicitly. The legacy balance is never a fallback.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Mapping, Optional

ZERO = Decimal("0")

STATUS_OK = None
STATUS_NOT_COMPUTED = "BLOCKED_NOT_COMPUTED"
STATUS_NO_ENTITLEMENT = "BLOCKED_NO_ENTITLEMENT"
STATUS_OVER_UTILISED = "BLOCKED_OVER_UTILISED"
STATUS_NO_AVAILABLE = "BLOCKED_NO_AVAILABLE_CIF"

_REASONS = {
    STATUS_NOT_COMPUTED: "Canonical utilisation is not computed for this licence; planning is blocked. The legacy balance is not used.",
    STATUS_NO_ENTITLEMENT: "No export-manifest CIF entitlement exists for this licence and SION norm; planning is blocked as a data-quality error.",
    STATUS_OVER_UTILISED: "Licence CIF is over-utilised; no planning allocation is allowed.",
    STATUS_NO_AVAILABLE: "No planning CIF remains for this licence and SION norm; no further allocation is allowed.",
}


def _d(value) -> Decimal:
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


@dataclass(frozen=True)
class CanonicalUtilisation:
    """Canonical licence utilisation, already split into mutually exclusive parts."""

    debited: Decimal
    allotted: Decimal
    invoiced: Decimal
    invoiced_boe_covered: Decimal

    @property
    def boe_cif(self) -> Decimal:
        return self.debited + self.invoiced_boe_covered

    @property
    def allotment_cif(self) -> Decimal:
        return self.allotted

    @property
    def billed_without_boe_cif(self) -> Decimal:
        return self.invoiced - self.invoiced_boe_covered

    @property
    def utilised_cif(self) -> Decimal:
        return self.boe_cif + self.allotment_cif + self.billed_without_boe_cif

    @classmethod
    def from_summary(cls, summary: Mapping[str, object]) -> "CanonicalUtilisation":
        return cls(
            debited=_d(summary.get("debited")),
            allotted=_d(summary.get("allotted")),
            invoiced=_d(summary.get("invoiced")),
            invoiced_boe_covered=_d(summary.get("invoiced_boe_covered")),
        )


@dataclass(frozen=True)
class NormBudget:
    norm_id: int
    status: Optional[str]
    reason: str
    export_cif: Decimal
    attributed_cif: Decimal
    licence_remaining: Decimal
    norm_remaining: Decimal
    ceiling: Decimal
    over_utilised_cif: Decimal = ZERO
    unattributed_utilisation_cif: Decimal = ZERO
    trace: tuple = field(default_factory=tuple)

    @property
    def allowed(self) -> bool:
        return self.status is None


def compute_norm_budgets(
    *,
    export_cif_by_norm: Mapping[int, Decimal],
    attributed_cif_by_norm: Mapping[int, Decimal],
    utilisation: Optional[CanonicalUtilisation],
) -> dict[int, NormBudget]:
    """Return a budget for every norm of one licence.

    ``export_cif_by_norm`` maps norm id to the export-manifest CIF for this licence.
    ``attributed_cif_by_norm`` maps norm id to BOE + allotment usage attributed to it.
    ``utilisation`` is the canonical result; ``None`` means it was not computed.
    """
    export_total = sum((_d(v) for v in export_cif_by_norm.values()), ZERO)
    if utilisation is None:
        return {
            norm: NormBudget(norm, STATUS_NOT_COMPUTED, _REASONS[STATUS_NOT_COMPUTED],
                             _d(export_cif_by_norm.get(norm)), ZERO, ZERO, ZERO, ZERO)
            for norm in export_cif_by_norm
        }

    utilised = utilisation.utilised_cif
    licence_remaining = export_total - utilised
    attributed_total = sum((_d(v) for v in attributed_cif_by_norm.values()), ZERO)
    unattributed = utilised - attributed_total

    budgets: dict[int, NormBudget] = {}
    for norm, export_raw in export_cif_by_norm.items():
        export_cif = _d(export_raw)
        attributed = _d(attributed_cif_by_norm.get(norm))
        norm_remaining = export_cif - attributed
        trace = (
            ("export_manifest_cif", str(export_cif)),
            ("attributed_boe_and_allotment_cif", str(attributed)),
            ("licence_export_total", str(export_total)),
            ("utilised_cif", str(utilised)),
            ("unattributed_utilisation_cif", str(unattributed)),
        )
        if export_cif <= 0:
            budgets[norm] = NormBudget(norm, STATUS_NO_ENTITLEMENT, _REASONS[STATUS_NO_ENTITLEMENT],
                                       export_cif, attributed, licence_remaining, norm_remaining, ZERO,
                                       unattributed_utilisation_cif=unattributed, trace=trace)
            continue
        if licence_remaining < 0 or norm_remaining < 0:
            excess = max(-licence_remaining, -norm_remaining, ZERO)
            budgets[norm] = NormBudget(norm, STATUS_OVER_UTILISED, _REASONS[STATUS_OVER_UTILISED],
                                       export_cif, attributed, licence_remaining, norm_remaining, ZERO,
                                       over_utilised_cif=excess, unattributed_utilisation_cif=unattributed,
                                       trace=trace)
            continue
        ceiling = min(licence_remaining, norm_remaining)
        if ceiling == 0:
            budgets[norm] = NormBudget(norm, STATUS_NO_AVAILABLE, _REASONS[STATUS_NO_AVAILABLE],
                                       export_cif, attributed, licence_remaining, norm_remaining, ZERO,
                                       unattributed_utilisation_cif=unattributed, trace=trace)
            continue
        budgets[norm] = NormBudget(norm, STATUS_OK, "", export_cif, attributed, licence_remaining,
                                   norm_remaining, ceiling, unattributed_utilisation_cif=unattributed,
                                   trace=trace)
    return budgets


def planning_budget_for_licence_norm(license_id: int, norm_id: int) -> NormBudget:
    """Database adapter: the single authoritative planning budget for one licence and SION norm.

    * Export-manifest entitlement: export items of this licence whose ``norm_class`` is ``norm_id``.
    * Attributed usage: BOE and unlinked-allotment usage whose planning target item is exported
      under exactly this norm on this licence. A target exported under two norms is ambiguous and
      is left unattributed, so it only reduces the licence-level remainder.
    * Utilisation: the canonical licence calculation. ``None`` when it is not computed.
    """
    from apps.license.models import LicenseExportItemModel
    from apps.license.services.licence_balance_report import build_licence_balance_reports
    from apps.license.services.planning_usage_reconciliation import aggregate_license_usage

    export_rows = list(
        LicenseExportItemModel.objects.filter(license_id=license_id, norm_class__isnull=False)
        .values_list("norm_class_id", "item_id", "cif_fc")
    )
    export_by_norm: dict[int, Decimal] = {}
    norms_by_target: dict[int, set] = {}
    for norm, item_id, cif in export_rows:
        export_by_norm[norm] = export_by_norm.get(norm, ZERO) + _d(cif)
        if item_id is not None:
            norms_by_target.setdefault(item_id, set()).add(norm)

    if norm_id not in export_by_norm:
        export_by_norm[norm_id] = ZERO

    usage = aggregate_license_usage(license_id)
    attributed: dict[int, Decimal] = {norm: ZERO for norm in export_by_norm}
    for (_source_item, target_item), bucket in usage["mapped"].items():
        owners = norms_by_target.get(target_item, set())
        if len(owners) != 1:
            continue  # unexported or ambiguous target: stays licence-level
        norm = next(iter(owners))
        attributed[norm] = attributed.get(norm, ZERO) + _d(bucket["boe_used_cif"]) + _d(bucket["unlinked_allotment_cif"])

    report = build_licence_balance_reports([license_id], include_legacy=False).get(license_id)
    utilisation = CanonicalUtilisation.from_summary(report.summary_cif) if report is not None and report.summary_cif else None

    budgets = compute_norm_budgets(
        export_cif_by_norm=export_by_norm,
        attributed_cif_by_norm=attributed,
        utilisation=utilisation,
    )
    return budgets[norm_id]
