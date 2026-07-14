# allotment/services/allotment_service.py
"""
Service layer for Allotment create / update / delete.

All database mutations run inside transaction.atomic().
After commit, the Celery recompute_license_balance_task is dispatched lazily
via transaction.on_commit() to avoid circular imports and to ensure the task
only fires after the transaction is durable.
"""
import logging

from django.db import transaction

from apps.allotment.models import AllotmentItems, AllotmentModel

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helper — lazy task dispatch inside on_commit
# ---------------------------------------------------------------------------

def _dispatch(item_ids):
    """
    Return an on_commit callback that fires recompute_license_balance_task
    for every affected item ID.

    The import is intentionally deferred to runtime to avoid circular imports.
    ImportError is logged at WARNING (task module genuinely absent).
    Any other exception is logged at ERROR so broker/connectivity failures
    are never silently swallowed.
    """
    def _task():
        try:
            from apps.license.tasks import recompute_license_balance_task
            for iid in item_ids:
                recompute_license_balance_task.delay(iid)
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
# Public service functions
# ---------------------------------------------------------------------------

def create_allotment(data: dict, user) -> AllotmentModel:
    """
    Create an AllotmentModel header plus its AllotmentItems in one transaction.

    Expected keys in `data`:
      - All AllotmentModel scalar/FK fields (company, type, required_quantity, …)
      - "items": list of dicts with keys: item (int ID), qty, cif_fc, cif_inr, is_boe

    After commit: dispatch recompute_license_balance_task for each item.item_id.
    """
    items_data = data.pop("items", [])

    with transaction.atomic():
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

    Collect affected item IDs before the delete, then dispatch recompute
    task after commit so balances are refreshed in the license module.
    """
    with transaction.atomic():
        # Collect item IDs before the rows are gone
        item_ids = list(
            AllotmentItems.objects
            .filter(allotment_id=allotment_id)
            .exclude(item_id__isnull=True)
            .values_list("item_id", flat=True)
        )

        AllotmentModel.objects.filter(pk=allotment_id).delete()

        transaction.on_commit(_dispatch(item_ids))
