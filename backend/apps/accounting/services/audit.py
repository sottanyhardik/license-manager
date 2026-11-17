from __future__ import annotations

from apps.accounting.models import AccountingAuditEvent


def record(action: str, obj, *, actor=None, entity=None, **detail) -> None:
    """Append an audit event in the caller's transaction."""
    AccountingAuditEvent.objects.create(
        entity=entity if entity is not None else getattr(obj, "entity", None),
        action=action,
        object_type=type(obj).__name__,
        object_id=getattr(obj, "pk", None),
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        detail={k: (str(v) if v is not None and not isinstance(v, (int, bool, list, dict)) else v) for k, v in detail.items()},
    )
