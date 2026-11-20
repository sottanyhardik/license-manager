"""
Item CIF over-utilisation adjustment (owner DEC-50 D, eligibility C-3 A, gate
G1 — 2026-11-20, `docs/qa/SAT_USER_DECISION_REGISTER.md`).

Rule:
- Only items with an item-attributed CIF basis (`cif_fc > 0`,
  `ItemBalanceCalculator.has_item_attributed_cif`) take part; shared-ceiling
  items already use the licence balance.
- Receivers: items whose REALISED over-use (visible BOE debit CIF − own credit)
  is > 0. Outstanding allotments are not covered (G1: adjustments absorb
  realised over-use only; allotment caps are unchanged).
- Donors: ANY other attributed item on the SAME licence (C-3 A) with unused CIF
  = credit − visible debit − outstanding allotment, when > 0. Never across
  licences; total licence CIF is preserved and no entitlement is created
  (Σ given == Σ received per licence).
- CIF only — quantity is never transferred between different goods.
- Deterministic: receivers in ascending item id; donors by largest unused CIF,
  then ascending item id. Whatever cannot be covered stays as `uncovered`
  (flagged as over-utilisation, never hidden).

Pure computation over canonical data (no writes). The audit trail of the
computed transfers is persisted separately; statutory/DGFT entitlement records
(`LicenseImportItemsModel.cif_fc`) are never altered.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Iterable

from apps.core.constants import DEC_0


@dataclass(frozen=True)
class CifTransfer:
    license_id: int
    source_item_id: int
    destination_item_id: int
    amount: Decimal


@dataclass
class ItemAdjustment:
    received: Decimal = DEC_0
    given: Decimal = DEC_0
    uncovered: Decimal = DEC_0  # realised over-use left after adjustment

    @property
    def net(self) -> Decimal:
        return self.received - self.given


@dataclass
class AdjustmentResult:
    transfers: list[CifTransfer] = field(default_factory=list)
    by_item: dict[int, ItemAdjustment] = field(default_factory=dict)

    def for_item(self, item_id: int) -> ItemAdjustment:
        return self.by_item.get(item_id, ItemAdjustment())


def _licences_with_realised_over_use(license_ids: list[int]) -> list[int]:
    from django.db.models import DecimalField, F, OuterRef, Subquery, Sum

    from apps.bill_of_entry.models import RowDetails
    from apps.core.constants import DEBIT
    from apps.license.models import LicenseImportItemsModel
    from apps.license.services.balance_calculator import exclude_hidden

    visible_debit = (
        exclude_hidden(RowDetails.objects.filter(sr_number_id=OuterRef("pk"), transaction_type=DEBIT))
        .order_by()
        .values("sr_number_id")
        .annotate(t=Sum("cif_fc"))
        .values("t")
    )
    return sorted(set(
        LicenseImportItemsModel.objects.filter(license_id__in=license_ids, cif_fc__gt=0)
        .annotate(debit=Subquery(visible_debit, output_field=DecimalField(max_digits=20, decimal_places=3)))
        .filter(debit__gt=F("cif_fc"))
        .values_list("license_id", flat=True)
    ))


def compute_item_cif_adjustments(license_ids: Iterable[int]) -> AdjustmentResult:
    """Transfers for every attributed import item on the given licences."""
    from apps.license.models import LicenseImportItemsModel
    from apps.license.services.balance_calculator import (
        ItemBalanceCalculator as IBC,
        LicenseBalanceCalculator as LBC,
    )
    from apps.core.utils.decimal_utils import to_decimal

    ids = sorted({i for i in license_ids if i is not None})
    result = AdjustmentResult()
    if not ids:
        return result
    # Cheap guard (one query): only licences with at least one attributed item
    # whose visible BOE debit CIF exceeds its own credit can have transfers.
    ids = _licences_with_realised_over_use(ids)
    if not ids:
        return result
    items = list(
        LicenseImportItemsModel.objects.filter(license_id__in=ids, cif_fc__gt=0)
        .only("id", "license_id", "cif_fc")
        .order_by("license_id", "id")
    )
    if not items:
        return result
    debit_map = IBC.calculate_debited_cif_for_items([i.id for i in items])
    outstanding_map = LBC.get_outstanding_allotment_totals_for_items(ids)

    by_licence: dict[int, list] = {}
    for item in items:
        by_licence.setdefault(item.license_id, []).append(item)

    for license_id, licence_items in by_licence.items():
        over_use: dict[int, Decimal] = {}
        unused: dict[int, Decimal] = {}
        for item in licence_items:
            credit = to_decimal(item.cif_fc, DEC_0)
            debit = debit_map.get(item.id, DEC_0)
            outstanding = outstanding_map.get(item.id, (DEC_0, DEC_0))[1]
            realised = debit - credit
            if realised > DEC_0:
                over_use[item.id] = realised
            spare = credit - debit - outstanding
            if spare > DEC_0:
                unused[item.id] = spare
        if not over_use:
            continue
        for receiver_id in sorted(over_use):
            need = over_use[receiver_id]
            donors = sorted(
                (d for d in unused if d != receiver_id and unused[d] > DEC_0),
                key=lambda d: (-unused[d], d),
            )
            for donor_id in donors:
                if need <= DEC_0:
                    break
                amount = min(need, unused[donor_id])
                unused[donor_id] -= amount
                need -= amount
                result.transfers.append(CifTransfer(license_id, donor_id, receiver_id, amount))
                result.by_item.setdefault(donor_id, ItemAdjustment()).given += amount
                result.by_item.setdefault(receiver_id, ItemAdjustment()).received += amount
            if need > DEC_0:
                result.by_item.setdefault(receiver_id, ItemAdjustment()).uncovered = need
    return result
