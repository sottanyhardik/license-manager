"""Single lifecycle gateway and canonical SION resolver for plan lines."""

from dataclasses import dataclass
from typing import Literal

from django.core.exceptions import ValidationError
from django.db import transaction


ACTIVE_PLAN = "ACTIVE_PLAN"
NO_ACTIVE_PLAN = "NO_ACTIVE_PLAN"
AMBIGUOUS_ACTIVE_PLAN = "AMBIGUOUS_ACTIVE_PLAN"


@dataclass(frozen=True)
class PlanSionResolution:
    status: Literal["RESOLVED", "UNRESOLVED", "AMBIGUOUS"]
    sion_id: int | None
    sion_code: str | None
    source: str
    candidate_ids: tuple[int, ...]
    message: str | None


def resolve_plan_sion(plan) -> PlanSionResolution:
    """Resolve a plan's applicable SION without silently picking a first row.

    LicenseItemPlan has no direct SION foreign key.  The persisted canonical
    source is the plan's import item licence export-norm relationship.  It is
    usable only when one norm applies; multi-norm licences remain ambiguous
    until a more-specific persisted planning mapping exists.
    """
    if not plan.import_item_id or not plan.license_id or not plan.item_name_id:
        return PlanSionResolution("UNRESOLVED", None, None, "MISSING_PLAN_IDENTITY", (), "Plan identity is incomplete.")
    from apps.core.models import SionNormClassModel
    candidates = list(SionNormClassModel.objects.filter(
        export_item__license_id=plan.license_id,
    ).order_by("id").values_list("id", "norm_class"))
    if not candidates:
        return PlanSionResolution("UNRESOLVED", None, None, "LICENSE_NORM", (), "No SION is linked to this licence.")
    if len(candidates) != 1:
        return PlanSionResolution("AMBIGUOUS", None, None, "LICENSE_NORM", tuple(candidate[0] for candidate in candidates), "More than one SION applies to this plan.")
    sion_id, sion_code = candidates[0]
    return PlanSionResolution("RESOLVED", sion_id, sion_code, "LICENSE_NORM", (sion_id,), None)


def get_current_allocation_plan(*, license, license_item, sion, planning_target_item):
    """Select exactly one eligible plan line, never an arbitrary first row.

    Plan-line versions are not a globally versioned identity in this schema.
    Therefore one active record for the complete licence/import-item/SION/
    target identity is current; more than one is explicitly ambiguous.
    """
    from apps.license.models import LicenseItemPlan

    if not all((license, license_item, sion, planning_target_item)):
        return NO_ACTIVE_PLAN, None
    candidates = LicenseItemPlan.objects.filter(
        license=license,
        import_item=license_item,
        item_name=planning_target_item,
        is_active=True,
        is_deleted=False,
        is_cancelled=False,
        import_item__license__export_license__norm_class__norm_class=sion,
    ).order_by("id")
    count = candidates.count()
    if count == 0:
        return NO_ACTIVE_PLAN, None
    if count != 1:
        return AMBIGUOUS_ACTIVE_PLAN, None
    return ACTIVE_PLAN, candidates.get()


class PlanLifecycleService:
    """Apply explicit, auditable state transitions without deleting history."""

    @staticmethod
    @transaction.atomic
    def transition(plan, action: str):
        plan = type(plan).objects.select_for_update().get(pk=plan.pk)
        if action == "activate":
            if plan.is_deleted or plan.is_cancelled:
                raise ValidationError("Deleted or cancelled plan lines cannot be reactivated.")
            plan.is_active = True
        elif action == "deactivate":
            plan.is_active = False
        elif action == "cancel":
            plan.is_active = False
            plan.is_cancelled = True
        elif action == "delete":
            plan.is_active = False
            plan.is_deleted = True
        elif action == "supersede":
            plan.is_active = False
        else:
            raise ValidationError(f"Unsupported plan lifecycle transition: {action}.")
        plan.full_clean()
        plan.save(update_fields=["is_active", "is_deleted", "is_cancelled", "modified_on"])
        return plan
