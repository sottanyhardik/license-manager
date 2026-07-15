# allotment/services/allotment_service.py
"""
Service layer for Allotment create / update / delete.

All database mutations run inside transaction.atomic().
After commit, the Celery recompute_license_balance_task is dispatched lazily
via transaction.on_commit() to avoid circular imports and to ensure the task
only fires after the transaction is durable.
"""
import logging
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models, transaction

from apps.allotment.models import AllotmentItems, AllotmentModel

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helper — lazy task dispatch inside on_commit
# ---------------------------------------------------------------------------

def _dispatch(item_ids: list):
    """
    Return an on_commit callback dispatching recompute_license_balance_task
    for all *unique license IDs* derived from the given import-item IDs.

    LicenseImportItemsModel rows survive allotment deletes, so the lookup
    is always safe inside on_commit.

    The import is intentionally deferred to runtime to avoid circular imports.
    ImportError is logged at WARNING (task module genuinely absent).
    Any other exception is logged at ERROR so broker/connectivity failures
    are never silently swallowed.
    """
    def _task():
        try:
            from apps.license.models import LicenseImportItemsModel
            from apps.license.tasks import recompute_license_balance_task

            license_ids = set(
                LicenseImportItemsModel.objects
                .filter(pk__in=item_ids)
                .exclude(license_id__isnull=True)
                .values_list("license_id", flat=True)
            )
            for lid in license_ids:
                recompute_license_balance_task.delay(lid)

        except ImportError:
            logger.warning(
                "recompute_license_balance_task not available — skipping dispatch"
            )
        except Exception as exc:
            logger.error(
                "Failed to dispatch balance recompute for item_ids=%s: %s",
                item_ids,
                exc,
                exc_info=True,
            )

    return _task


# ---------------------------------------------------------------------------
# Internal helpers — LicenseItemPlan management
# ---------------------------------------------------------------------------

def _validate_plan_availability(import_item_id: int, qty_requested: Decimal, cif_fc_requested: Decimal) -> None:
    """
    Raise ValidationError if the requested allotment exceeds available plan.

    If no LicenseItemPlan exists for the item, no restriction is applied
    (planning is optional — backward compatible with legacy data).

    select_for_update() prevents concurrent over-allotment races.
    Must be called inside a transaction.atomic() block.
    """
    from apps.license.models import LicenseItemPlan

    plan = LicenseItemPlan.objects.select_for_update().filter(import_item_id=import_item_id).first()

    if plan is None:
        return  # No plan — no restriction

    if qty_requested > plan.planned_quantity:
        raise ValidationError(
            f"Requested quantity {qty_requested} exceeds available plan "
            f"{plan.planned_quantity} for import item {import_item_id}."
        )

    if cif_fc_requested > plan.planned_cif_fc:
        raise ValidationError(
            f"Requested CIF {cif_fc_requested} exceeds available planned CIF "
            f"{plan.planned_cif_fc} for import item {import_item_id}."
        )


def _adjust_plan(import_item_id: int, qty_delta: Decimal, cif_fc_delta: Decimal, cif_inr_delta: Decimal) -> None:
    """
    Adjust LicenseItemPlan for the given import item by the deltas.

    qty_delta, cif_fc_delta, cif_inr_delta are ADDED to the plan values.
    Pass negative values to decrease (allotment creation), positive to increase
    (allotment deletion / undo).

    If no LicenseItemPlan exists for the import item, this is a no-op:
    planning is optional — items without a plan have no restriction.

    Must be called inside a transaction.atomic() block; select_for_update()
    prevents concurrent update races.
    """
    from apps.license.models import LicenseItemPlan

    plan_qs = LicenseItemPlan.objects.select_for_update().filter(import_item_id=import_item_id)

    if not plan_qs.exists():
        return  # No plan exists — planning not enforced for this item

    plan_qs.update(
        planned_quantity=models.F("planned_quantity") + qty_delta,
        planned_cif_fc=models.F("planned_cif_fc") + cif_fc_delta,
        planned_cif_inr=models.F("planned_cif_inr") + cif_inr_delta,
    )


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------

def create_allotment(data: dict, user) -> AllotmentModel:
    """
    Create an AllotmentModel header plus its AllotmentItems in one transaction.

    Expected keys in `data`:
      - All AllotmentModel scalar/FK fields (company, type, required_quantity, …)
      - "items": list of dicts with keys: item (int ID), qty, cif_fc, cif_inr, is_boe

    Raises ValidationError if any item exceeds its available LicenseItemPlan.
    After commit: dispatch recompute_license_balance_task for affected licenses.
    """
    items_data = data.pop("items", [])

    # Validate all items before entering the transaction so no partial writes occur.
    with transaction.atomic():
        for item_dict in items_data:
            import_item_id = item_dict.get("item")
            if import_item_id:
                _validate_plan_availability(
                    import_item_id=import_item_id,
                    qty_requested=Decimal(str(item_dict.get("qty") or 0)),
                    cif_fc_requested=Decimal(str(item_dict.get("cif_fc") or 0)),
                )

        allotment = AllotmentModel(**data)
        allotment.created_by = user
        allotment.modified_by = user
        allotment.save()

        item_ids = []
        for item_dict in items_data:
            ai = AllotmentItems(
                allotment=allotment,
                item_id=item_dict.get("item"),
                qty=item_dict.get("qty", 0),
                cif_fc=item_dict.get("cif_fc", 0),
                cif_inr=item_dict.get("cif_inr", 0),
                is_boe=item_dict.get("is_boe", False),
                created_by=user,
                modified_by=user,
            )
            ai.save()
            if ai.item_id:
                item_ids.append(ai.item_id)
                # Decrease the plan by the amount being allotted (negative deltas)
                _adjust_plan(
                    import_item_id=ai.item_id,
                    qty_delta=-Decimal(str(ai.qty or 0)),
                    cif_fc_delta=-Decimal(str(ai.cif_fc or 0)),
                    cif_inr_delta=-Decimal(str(ai.cif_inr or 0)),
                )

        transaction.on_commit(_dispatch(item_ids))

    return allotment


def update_allotment(allotment_id: int, data: dict, user) -> AllotmentModel:
    """
    Partial-update header fields only.

    Items are managed via the AllotmentItems endpoints directly — this
    function does not bulk-replace them. After commit: dispatch recompute
    task for all currently-attached item IDs.
    """
    # Pop items if accidentally passed; not handled here
    data.pop("items", None)

    with transaction.atomic():
        allotment = AllotmentModel.objects.select_for_update().get(pk=allotment_id)

        for field, value in data.items():
            setattr(allotment, field, value)

        allotment.modified_by = user
        allotment.save()

        # Collect item IDs for recompute dispatch
        item_ids = list(
            AllotmentItems.objects
            .filter(allotment_id=allotment_id)
            .exclude(item_id__isnull=True)
            .values_list("item_id", flat=True)
        )

        transaction.on_commit(_dispatch(item_ids))

    return allotment


def delete_allotment(allotment_id: int, user) -> None:
    """
    Delete the AllotmentModel header (DB cascade handles AllotmentItems).

    Collect affected item IDs and plan adjustment values before the delete,
    restore LicenseItemPlan for each item, then dispatch recompute task after
    commit so balances are refreshed in the license module.
    """
    with transaction.atomic():
        # Collect item values before the rows are gone
        plan_adjustments = list(
            AllotmentItems.objects
            .filter(allotment_id=allotment_id)
            .exclude(item_id__isnull=True)
            .values("item_id", "qty", "cif_fc", "cif_inr")
        )

        item_ids = [adj["item_id"] for adj in plan_adjustments]

        AllotmentModel.objects.filter(pk=allotment_id).delete()

        # Restore plan for each deleted item (positive deltas = undo allotment)
        for adj in plan_adjustments:
            _adjust_plan(
                import_item_id=adj["item_id"],
                qty_delta=Decimal(str(adj["qty"] or 0)),
                cif_fc_delta=Decimal(str(adj["cif_fc"] or 0)),
                cif_inr_delta=Decimal(str(adj["cif_inr"] or 0)),
            )

        transaction.on_commit(_dispatch(item_ids))
