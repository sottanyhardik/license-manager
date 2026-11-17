"""Generic bulk actions for master viewsets built by ``MasterViewSet.create_viewset``.

``POST <list-url>bulk/`` with ``{"action": "activate" | "deactivate" | "delete", "keys": [...]}``.

Rules:
* Each record goes through the viewset's own ``perform_update`` / ``perform_destroy``,
  so validation, delete protection (``ProtectedError`` → refused) and the MDS
  write-through behave exactly as for a single edit or delete.
* Each record runs in its own transaction together with its audit row: one
  failure never rolls back or blocks the others, and a change is never
  committed without its audit entry.
* The response reports every key (``ok`` / ``error``). Nothing is skipped silently.
* Audit rows are written per record against the record's own URL, so they show
  in that record's history exactly like a single edit.
* Write permission is the viewset's (``MasterDataPermission``: superuser or
  USER_MANAGER). Enabled by default only for ``core`` masters; domain viewsets
  (licences, BOEs, trades, …) have their own delete guards and are excluded.
"""
from __future__ import annotations

from typing import Any

from django.db import DatabaseError, transaction
from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

MAX_BULK_KEYS = 200
STATUS_FIELD = "is_active"


def bulk_actions_for(viewset) -> list[str]:
    """Bulk actions a viewset supports (shown to the UI in list metadata)."""
    if not getattr(viewset, "bulk_enabled", False):
        return []
    actions = []
    serializer = viewset.get_serializer()
    field = serializer.fields.get(STATUS_FIELD)
    if field is not None and not field.read_only:
        actions += ["activate", "deactivate"]
    return actions + ["delete"]


def _first_error(detail: Any) -> str:
    if isinstance(detail, (list, tuple)):
        return next((_first_error(d) for d in detail if d), "")
    if isinstance(detail, dict):
        for key in ("detail", "non_field_errors"):
            if key in detail:
                return _first_error(detail[key])
        return next((f"{k}: {_first_error(v)}" for k, v in detail.items()), "")
    return str(detail)


def _audit(request: Request, base_path: str, key: str, action: str, status_code: int, instance=None) -> None:
    from apps.core.models import ActivityLog

    user = request.user if getattr(request.user, "is_authenticated", False) else None
    ActivityLog.objects.create(
        user=user,
        username=getattr(user, "username", "") or "",
        action=ActivityLog.ACTION_DELETE if action == "delete" else ActivityLog.ACTION_UPDATE,
        module="masters",
        resource_id=str(getattr(instance, "pk", "") or "")[:60],
        description=f"Bulk {action}"[:500],
        endpoint=f"{base_path}{key}/"[:500],
        method="POST",
        status_code=status_code,
        extra={"bulk": True},
    )


def run_bulk(viewset, request: Request) -> Response:
    if not getattr(viewset, "bulk_enabled", False):
        return Response({"detail": "Bulk actions are not available here."}, status=status.HTTP_404_NOT_FOUND)

    action = str(request.data.get("action", "")).strip().lower()
    keys = request.data.get("keys")
    allowed = bulk_actions_for(viewset)
    if action not in allowed:
        return Response({"action": [f"Choose one of: {', '.join(allowed)}."]}, status=status.HTTP_400_BAD_REQUEST)
    if not isinstance(keys, list) or not keys:
        return Response({"keys": ["Send a non-empty list of record keys."]}, status=status.HTTP_400_BAD_REQUEST)
    if len(keys) > MAX_BULK_KEYS:
        return Response({"keys": [f"At most {MAX_BULK_KEYS} records per request."]}, status=status.HTTP_400_BAD_REQUEST)

    lookup = viewset.lookup_field or "pk"
    base_path = request.path[: -len("bulk/")] if request.path.endswith("bulk/") else request.path
    queryset = viewset.get_queryset()
    results: list[dict[str, Any]] = []

    from apps.core.mds_write import MasterServiceUnavailable

    unique_keys = list(dict.fromkeys(str(k) for k in keys))  # de-duplicate, keep order
    for index, raw in enumerate(unique_keys):
        instance = queryset.filter(**{lookup: raw}).first()
        if instance is None:
            results.append({"key": raw, "ok": False, "error": "Not found."})
            continue
        try:
            with transaction.atomic():
                # Audit row first: if it cannot be written nothing is changed, and nothing
                # local can fail after an MDS write-through has already succeeded.
                if action == "delete":
                    _audit(request, base_path, raw, action, status.HTTP_204_NO_CONTENT, instance)
                    viewset.perform_destroy(instance)
                else:
                    serializer = viewset.get_serializer(instance, data={STATUS_FIELD: action == "activate"}, partial=True)
                    serializer.is_valid(raise_exception=True)
                    _audit(request, base_path, raw, action, status.HTTP_200_OK, instance)
                    viewset.perform_update(serializer)
        except MasterServiceUnavailable as exc:
            # MDS (the write authority) is down: stop instead of waiting out a timeout per record.
            reason = _first_error(exc.detail) or "Master data service unavailable."
            results.append({"key": raw, "ok": False, "error": reason})
            results.extend({"key": k, "ok": False, "error": f"Not attempted: {reason}"} for k in unique_keys[index + 1:])
            break
        except (ValidationError, APIException) as exc:
            results.append({"key": raw, "ok": False, "error": _first_error(exc.detail) or "Refused."})
            continue
        except DatabaseError:
            # This record's savepoint rolled back; report it and carry on with the rest.
            results.append({"key": raw, "ok": False, "error": "Database error; nothing was changed for this record."})
            continue
        results.append({"key": raw, "ok": True})

    succeeded = sum(1 for r in results if r["ok"])
    return Response({
        "action": action,
        "requested": len(results),
        "succeeded": succeeded,
        "failed": len(results) - succeeded,
        "results": results,
    })
