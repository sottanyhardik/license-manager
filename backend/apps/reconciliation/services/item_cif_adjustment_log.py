"""
Persist DEC-50 item CIF adjustments as an append-only audit trail
(`ItemCifAdjustmentRecord`). The live figures always come from
`apps.license.services.item_cif_adjustment.compute_item_cif_adjustments`;
this module only records each change of the computed set per licence.

`refresh_item_cif_adjustment_log(license_ids, dry_run=True)` compares the live
set with the licence's latest recorded batch and, when they differ (and not a
dry run), writes a new batch: one row per transfer, or a single marker row
(no items, amount 0) when the set became empty. Nothing is ever updated or
deleted. Running it against a real database is a data write that needs owner
approval (SAT gate §4).
"""
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Iterable

from django.db import transaction

from apps.license.services.item_cif_adjustment import compute_item_cif_adjustments
from apps.reconciliation.models import ItemCifAdjustmentRecord

REASON = "DEC-50 D: realised item CIF over-use covered by same-licence unused CIF (C-3 A, G1)"


def _key(source_id, destination_id, amount) -> tuple:
    return (source_id, destination_id, Decimal(amount).quantize(Decimal("0.01")))


def latest_recorded_set(license_id: int) -> set[tuple]:
    latest = (
        ItemCifAdjustmentRecord.objects.filter(license_id=license_id)
        .order_by("-created_on", "-id").values_list("batch_id", flat=True).first()
    )
    if latest is None:
        return set()
    return {
        _key(r.source_item_id, r.destination_item_id, r.amount_cif_fc)
        for r in ItemCifAdjustmentRecord.objects.filter(batch_id=latest, license_id=license_id)
        if r.source_item_id is not None
    }


def refresh_item_cif_adjustment_log(license_ids: Iterable[int], *, dry_run: bool = True, user=None) -> dict:
    ids = sorted({i for i in license_ids if i is not None})
    live = compute_item_cif_adjustments(ids)
    live_by_licence: dict[int, set[tuple]] = {}
    for t in live.transfers:
        live_by_licence.setdefault(t.license_id, set()).add(_key(t.source_item_id, t.destination_item_id, t.amount))
    changed = {}
    for lid in ids:
        current = live_by_licence.get(lid, set())
        recorded = latest_recorded_set(lid)
        has_history = ItemCifAdjustmentRecord.objects.filter(license_id=lid).exists()
        if current != recorded and (current or has_history):
            changed[lid] = current
    batch_id = None
    if changed and not dry_run:
        batch_id = str(uuid.uuid4())
        with transaction.atomic():
            for lid, transfers in changed.items():
                rows = [
                    ItemCifAdjustmentRecord(
                        batch_id=batch_id, license_id=lid, source_item_id=s, destination_item_id=d,
                        amount_cif_fc=a, reason=REASON, user=user,
                    )
                    for s, d, a in sorted(transfers)
                ] or [ItemCifAdjustmentRecord(batch_id=batch_id, license_id=lid, reason=REASON + " — none", user=user)]
                ItemCifAdjustmentRecord.objects.bulk_create(rows)
    return {
        "dry_run": dry_run,
        "batch_id": batch_id,
        "licences_changed": sorted(changed),
        "transfers": sum(len(v) for v in changed.values()),
    }
