"""Authorised, append-only sale-classification review workflow."""
from __future__ import annotations

import csv
from io import StringIO

from django.db import transaction
from django.utils import timezone

from apps.trade.models import LicenseTrade, LicenseTradeLine, SaleClassificationDecision


VALID_DECISIONS = {LicenseTrade.FINAL_PARTY_FINAL, LicenseTrade.FINAL_PARTY_INTERMEDIATE,
                   LicenseTrade.FINAL_PARTY_NOT_APPLICABLE}


def licence_ids_for_sale(trade):
    return sorted(set(LicenseTradeLine.objects.filter(trade=trade).values_list("sr_number__license_id", flat=True)))


def review_rows(queryset=None):
    sales = (queryset or LicenseTrade.objects).filter(direction=LicenseTrade.DIR_SALE,
        final_party_status=LicenseTrade.FINAL_PARTY_UNKNOWN).select_related("from_company", "to_company", "linked_trade", "counterpart", "copied_from")
    for sale in sales.order_by("pk"):
        licences = list(sale.lines.values_list("sr_number__license_id", "sr_number__license__license_number").distinct())
        yield {
            "sale_id": sale.pk, "licence_id": ";".join(str(x[0]) for x in licences),
            "licence_number": ";".join(str(x[1]) for x in licences), "invoice_number": sale.invoice_number,
            "seller": getattr(sale.from_company, "name", ""), "buyer": getattr(sale.to_company, "name", ""),
            "relationship_summary": "linked=%s counterpart=%s copied_from=%s" % (sale.linked_trade_id or "", sale.counterpart_id or "", sale.copied_from_id or ""),
            "decision": "", "reason": "", "finalized_status": getattr(sale, "status", ""),
        }


def apply_decision(*, sale_id, decision, reason, provenance, user):
    if decision not in VALID_DECISIONS or not reason.strip() or not provenance.strip():
        raise ValueError("decision, reason and provenance are required.")
    with transaction.atomic():
        trade = LicenseTrade.objects.select_for_update().get(pk=sale_id, direction=LicenseTrade.DIR_SALE)
        final_party_id = trade.to_company_id if decision == LicenseTrade.FINAL_PARTY_FINAL else None
        if decision == LicenseTrade.FINAL_PARTY_FINAL and not final_party_id:
            raise ValueError("A FINAL_PARTY sale requires its canonical invoice buyer.")
        scope = licence_ids_for_sale(trade)
        SaleClassificationDecision.objects.create(trade=trade, decision=decision, reason=reason.strip(),
            provenance=provenance.strip(), licence_ids=scope, decided_by=user)
        trade.final_party_status, trade.final_party_id = decision, final_party_id
        trade.final_party_resolution_note = reason.strip()
        trade.final_party_classification_provenance = "AUTHORISED_REVIEW:%s" % provenance.strip()[:44]
        trade.full_clean()
        trade.save(update_fields=["final_party_status", "final_party", "final_party_resolution_note", "final_party_classification_provenance", "modified_on"])
        # Requeue only affected items that were blocked by source validation.
        from apps.license.models import LicenseLedgerPackageItem
        affected = list(LicenseLedgerPackageItem.objects.select_for_update().filter(license_id__in=scope, status="failed", error__contains="FINAL_PARTY_CLASSIFICATION_REQUIRED").values_list("pk", flat=True))
        if affected:
            LicenseLedgerPackageItem.objects.filter(pk__in=affected).update(status="queued", error="", started_at=None, completed_at=None)
            from apps.license.tasks import enqueue_license_ledger_package_job
            job_ids = LicenseLedgerPackageItem.objects.filter(pk__in=affected).values_list("job_id", flat=True).distinct()
            for job_id in job_ids:
                transaction.on_commit(lambda job_id=job_id: enqueue_license_ledger_package_job.delay(job_id, affected))
    # New persistent requests keep data blockers as blocked_* rather than a
    # generic failure. Re-evaluate those exact items after every authorised
    # decision so the same request resumes without resubmission.
    from apps.license.services.ledger_package_recovery import requeue_ready_package_items
    requeue_ready_package_items(trade)
    return trade, scope


def import_rows(fileobj, user):
    rows = list(csv.DictReader(StringIO(fileobj.read().decode() if hasattr(fileobj.read, "__call__") else str(fileobj))))
    parsed = []
    for n, row in enumerate(rows, 2):
        try: sale_id = int(row.get("sale_id", ""))
        except ValueError: raise ValueError("Row %s: invalid sale_id" % n)
        decision, reason, provenance = row.get("decision", "").strip(), row.get("reason", "").strip(), row.get("provenance", "CSV_IMPORT").strip()
        if decision not in VALID_DECISIONS or not reason or not provenance: raise ValueError("Row %s: decision, reason and provenance are required" % n)
        parsed.append((sale_id, decision, reason, provenance))
    ids = [x[0] for x in parsed]
    if len(ids) != len(set(ids)) or LicenseTrade.objects.filter(pk__in=ids, direction=LicenseTrade.DIR_SALE).count() != len(ids):
        raise ValueError("CSV contains duplicate or non-sale IDs")
    for sale_id, decision, reason, provenance in parsed:
        apply_decision(sale_id=sale_id, decision=decision, reason=reason, provenance=provenance, user=user)
    return len(parsed)
