# serializers.py (safe _sync_nested + example update integration)
from django.db import transaction
from rest_framework import serializers

# Import your models as appropriate:
# from ..models import SionNormClassModel, SIONExportModel, SIONImportModel

def _sync_nested(
    instance,
    model,
    incoming_list,
    fk_field="norm_class",
    *,
    treat_empty_list_as_delete=False,
):
    """
    Safe full-sync helper for nested relations.

    Args:
      - instance: parent model instance
      - model: nested model class (e.g. SIONExportModel)
      - incoming_list: list of dicts (may include 'id') OR None
      - fk_field: FK field name on nested model pointing to parent
      - treat_empty_list_as_delete: boolean (default False).
          If False: incoming_list == [] will NOT delete existing rows (non-destructive).
          If True: incoming_list == [] will delete all existing rows (full replacement).

    Behavior:
      - If incoming_list is None -> do nothing (safe)
      - If incoming_list contains dicts with ids -> update those, create new ones for items without id
      - If incoming_list contains at least one id or treat_empty_list_as_delete is True -> delete existing rows not present in incoming ids
      - If incoming_list contains no ids and treat_empty_list_as_delete is False -> do NOT delete existing rows (only create new ones)
    Returns:
      - dict summary: {"created": n, "updated": n, "deleted": n}
    """
    summary = {"created": 0, "updated": 0, "deleted": 0}

    # If incoming_list is None => caller didn't provide nested data => do nothing
    if incoming_list is None:
        return summary

    # Normalize items to dicts
    incoming_items = [it if isinstance(it, dict) else {} for it in incoming_list]

    # Determine incoming ids (integers)
    incoming_ids = set()
    for item in incoming_items:
        rid = item.get("id") or item.get("pk")
        if rid in (None, ""):
            continue
        try:
            incoming_ids.add(int(rid))
        except (ValueError, TypeError):
            continue

    # Fetch existing related objects for this parent
    existing_qs = model.objects.filter(**{fk_field: instance})
    existing_map = {obj.id: obj for obj in existing_qs}

    with transaction.atomic():
        # Decide delete behavior:
        # - If we have incoming_ids (client included ids), delete existing not included
        # - Else if treat_empty_list_as_delete is True, delete all existing (because client asked explicit full replacement)
        # - Else (no incoming ids and not treat_empty_list_as_delete): DO NOT delete existing rows (safe default)
        if incoming_ids:
            deleted_qs = model.objects.filter(**{fk_field: instance}).exclude(id__in=incoming_ids)
            deleted_count = deleted_qs.count()
            if deleted_count:
                deleted_qs.delete()
                summary["deleted"] = deleted_count
        elif treat_empty_list_as_delete:
            deleted_qs = model.objects.filter(**{fk_field: instance})
            deleted_count = deleted_qs.count()
            if deleted_count:
                deleted_qs.delete()
                summary["deleted"] = deleted_count
        else:
            # safe default: keep existing rows
            summary["deleted"] = 0

        # Upsert loop
        for item in incoming_items:
            raw_id = item.get("id") or item.get("pk")
            try:
                item_id = int(raw_id) if raw_id not in (None, "") else None
            except (ValueError, TypeError):
                item_id = None

            if item_id and item_id in existing_map:
                obj = existing_map[item_id]
                # Update only fields present in payload (skip id/pk)
                changed = False
                for k, v in item.items():
                    if k in ("id", "pk"):
                        continue
                    if hasattr(obj, k):
                        setattr(obj, k, v)
                        changed = True
                if changed:
                    obj.save()
                    summary["updated"] += 1
            else:
                # Create new object
                create_data = {k: v for k, v in item.items() if k not in ("id", "pk")}
                create_kwargs = {fk_field: instance}
                create_kwargs.update(create_data)
                model.objects.create(**create_kwargs)
                summary["created"] += 1
    return summary
