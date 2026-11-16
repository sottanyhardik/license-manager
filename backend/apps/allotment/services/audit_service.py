"""Audit writers for allotment mutations."""
from apps.allotment.models import AuditEvent


def record_allotment_deleted(allotment, actor=None):
    """Persist one AuditEvent snapshot of ``allotment``.

    Call inside the caller's atomic block, before the delete. The FK to
    AllotmentItems is left null (PROTECT, and the rows are about to be
    cascade-deleted); identifiers live in ``details`` so the deleted allotment
    can be reconstructed. No schema change.
    """
    actor = actor if actor is not None and getattr(actor, "is_authenticated", False) else None
    items = [
        {
            "item_id": row.item_id,
            "qty": str(row.qty),
            "cif_fc": str(row.cif_fc),
            "cif_inr": str(row.cif_inr),
        }
        for row in allotment.allotment_details.order_by("pk")
    ]
    return AuditEvent.objects.create(
        action=AuditEvent.RELEASE,
        actor=actor,
        created_by=actor,
        company_before=allotment.company,
        quantity_before=allotment.required_quantity,
        cif_before=allotment.cif_fc,
        reason="ALLOTMENT_DELETED",
        details={
            "event": "allotment_deleted",
            "allotment_id": allotment.pk,
            "company_id": allotment.company_id,
            "type": allotment.type,
            "required_quantity": str(allotment.required_quantity),
            "cif_fc": str(allotment.cif_fc),
            "cif_inr": str(allotment.cif_inr),
            "items": items,
        },
    )
