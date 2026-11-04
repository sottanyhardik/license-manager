"""Cross-licence batch loading for the canonical ledger engine.

The canonical engine (``CanonicalLedgerService.build_canonical_ledger_dataset``)
was written to build one licence at a time, so a collection of N licences ran
roughly eight queries per licence (about 666 queries for 80 licences).

``LedgerBatch`` loads the SAME rows, with the SAME filters and prefetches, for
every licence of one collection in a fixed number of queries, then hands each
licence exactly the rows its per-licence query would have returned. It contains
no accounting formula. The engine's calculations are unchanged; only the data
access moves from "one query per licence" to "one query per collection".

Equivalence is enforced by the golden-snapshot gate in
``apps/license/tests/test_canonical_ledger_batch_equivalence.py``. Any path
that is not batched falls back to the original per-licence query, so a
missing key can never produce a silently different result.
"""
from __future__ import annotations

import copy
from collections import defaultdict
from decimal import Decimal
from typing import Dict, Iterable, List, Optional, Tuple

from django.db.models import Prefetch, Sum

DEC_0 = Decimal("0.00")

# Licence-type families, mirroring _get_license_object() in the canonical engine.
DFIA = "DFIA"
INCENTIVE = "INCENTIVE"
INCENTIVE_TYPES = frozenset({"INCENTIVE", "RODTEP", "ROSTL", "MEIS"})


def _kind(license_type: str) -> Optional[str]:
    if license_type == DFIA:
        return DFIA
    if license_type in INCENTIVE_TYPES:
        return INCENTIVE
    return None


class LedgerBatch:
    """Pre-loaded dependencies for one collection of licences.

    Construct with ``LedgerBatch.for_licences([(id, type), ...])``. Every lookup
    returns ``None``/absent for unknown keys, and callers fall back to the
    original per-licence query in that case.
    """

    def __init__(self, dfia_ids: Iterable[int], incentive_ids: Iterable[int]):
        self._dfia_ids: List[int] = sorted({int(i) for i in dfia_ids})
        self._incentive_ids: List[int] = sorted({int(i) for i in incentive_ids})
        self._objects: Dict[Tuple[str, int], object] = {}
        self._opening: Dict[int, Decimal] = {}
        self._trades: Dict[int, list] = defaultdict(list)
        self._incentive_trades: Dict[int, list] = defaultdict(list)
        self._boe_cif: Dict[int, Dict[int, Decimal]] = defaultdict(dict)
        self._company_names: Dict[int, str] = {}
        self._loaded_company_ids: set = set()
        # Keys this batch was asked to load. A key outside this set must never receive
        # batch data: the caller falls back to the original per-licence queries.
        self._covered = {(DFIA, int(i)) for i in self._dfia_ids} | {(INCENTIVE, int(i)) for i in self._incentive_ids}
        self._load()

    @classmethod
    def for_licences(cls, refs: Iterable[Tuple[int, str]]) -> "LedgerBatch":
        dfia, incentive = [], []
        for license_id, license_type in refs:
            kind = _kind(license_type)
            if kind == DFIA:
                dfia.append(license_id)
            elif kind == INCENTIVE:
                incentive.append(license_id)
        return cls(dfia, incentive)

    # ── loading (fixed number of queries, independent of licence count) ──────

    def _load(self) -> None:
        from apps.license.models import IncentiveLicense, LicenseDetailsModel
        from apps.license.services.balance_calculator import LicenseBalanceCalculator
        from apps.reconciliation.models import InvoiceBOEAllocation
        from apps.trade.models import LicenseTrade, LicenseTradeLine

        if self._dfia_ids:
            # Same select/prefetch as the per-licence _get_license_object() query.
            for obj in (
                LicenseDetailsModel.objects
                .select_related("exporter", "port")
                .prefetch_related("export_license__norm_class")
                .filter(id__in=self._dfia_ids)
            ):
                self._objects[(DFIA, obj.id)] = obj

            # Export CIF per licence: the batched sibling of calculate_credit(),
            # which is what the model's opening_balance property evaluates.
            self._opening = dict(LicenseBalanceCalculator.calculate_credit_for_licenses(self._dfia_ids))

            # Trades for ALL DFIA licences in one query, with every line for those
            # licences prefetched in one query. Lines are split per licence below,
            # using exactly the filter the per-licence query used.
            lines_qs = (
                LicenseTradeLine.objects
                .filter(sr_number__license_id__in=self._dfia_ids)
                .select_related("sr_number")
                .prefetch_related("sr_number__items__sion_norm_class")
            )
            trades_all = list(
                LicenseTrade.objects.filter(
                    license_type="DFIA",
                    lines__sr_number__license_id__in=self._dfia_ids,
                ).select_related("from_company", "to_company").prefetch_related(
                    Prefetch("lines", queryset=lines_qs, to_attr="license_lines_batch")
                ).distinct()
            )
            for trade in trades_all:
                by_licence: Dict[int, list] = defaultdict(list)
                for line in trade.license_lines_batch:
                    by_licence[line.sr_number.license_id].append(line)
                # Keep the trade's global order; give each licence its own shallow
                # copy so per-licence line lists never leak between licences.
                for licence_id, lines in by_licence.items():
                    clone = copy.copy(trade)
                    # Drop the collection-wide attribute so the clone cannot expose other licences' lines.
                    clone.__dict__.pop("license_lines_batch", None)
                    clone.license_lines = lines
                    self._trades[licence_id].append(clone)

            # BOE CIF per (licence, trade): active, current allocations only.
            boe_totals = (
                InvoiceBOEAllocation.objects
                .filter(
                    trade_line__sr_number__license_id__in=self._dfia_ids,
                    status=InvoiceBOEAllocation.STATUS_ACTIVE,
                    is_current=True,
                )
                .values("trade_line__sr_number__license_id", "trade_line__trade_id")
                .annotate(total=Sum("allocated_cif_inr"))
            )
            for row in boe_totals:
                self._boe_cif[row["trade_line__sr_number__license_id"]][row["trade_line__trade_id"]] = (
                    _quantize(row["total"])
                )

        if self._incentive_ids:
            from apps.trade.models import IncentiveTradeLine
            for obj in (
                IncentiveLicense.objects
                .select_related("exporter", "port_code")
                .filter(id__in=self._incentive_ids)
            ):
                self._objects[(INCENTIVE, obj.id)] = obj

            # Incentive trades for ALL incentive licences: one trade query and one line
            # query, split per licence by the line's incentive licence (same filter as
            # the per-licence query).
            incentive_lines_qs = IncentiveTradeLine.objects.filter(
                incentive_license_id__in=self._incentive_ids,
            )
            incentive_trades_all = list(
                LicenseTrade.objects.filter(
                    license_type="INCENTIVE",
                    incentive_lines__incentive_license_id__in=self._incentive_ids,
                ).select_related("from_company", "to_company").prefetch_related(
                    Prefetch("incentive_lines", queryset=incentive_lines_qs, to_attr="license_incentive_lines_batch")
                ).distinct()
            )
            for trade in incentive_trades_all:
                by_licence: Dict[int, list] = defaultdict(list)
                for line in trade.license_incentive_lines_batch:
                    by_licence[line.incentive_license_id].append(line)
                for licence_id, lines in by_licence.items():
                    clone = copy.copy(trade)
                    clone.__dict__.pop("license_incentive_lines_batch", None)
                    clone.license_incentive_lines = lines
                    self._incentive_trades[licence_id].append(clone)

    # ── lookups ──────────────────────────────────────────────────────────────

    def covers(self, license_id: int, license_type: str) -> bool:
        """True only for licences this batch was built for (never for an unknown key)."""
        kind = _kind(license_type)
        return kind is not None and (kind, int(license_id)) in self._covered

    def license_object(self, license_id: int, license_type: str):
        """The licence master object, or None when this batch does not hold it."""
        kind = _kind(license_type)
        if kind is None:
            return None
        return self._objects.get((kind, int(license_id)))

    def opening_balance(self, license_id: int, license_type: str) -> Optional[Decimal]:
        """Equivalent of ``getattr(license_obj, 'opening_balance', None)``.

        DFIA: the export-CIF total (zero when there are no export items).
        Incentive models have no such property, so None is returned, matching
        the original getattr default.
        """
        if _kind(license_type) != DFIA:
            return None
        return self._opening.get(int(license_id), DEC_0)

    def dfia_trades(self, license_id: int) -> list:
        """The trades of one DFIA licence, each with ``license_lines`` for that licence."""
        return list(self._trades.get(int(license_id), []))

    def incentive_trades(self, license_id: int) -> list:
        """The trades of one incentive licence, each with ``license_incentive_lines``."""
        return list(self._incentive_trades.get(int(license_id), []))

    def dfia_boe_cif_by_trade(self, license_id: int) -> Dict[int, Decimal]:
        return dict(self._boe_cif.get(int(license_id), {}))

    def company_names(self, company_ids: Iterable[int]) -> Dict[int, str]:
        """Resolve company names with at most one query per call for unseen ids."""
        wanted = {int(cid) for cid in company_ids if cid}
        missing = wanted - self._loaded_company_ids
        if missing:
            from apps.core.models import CompanyModel
            try:
                for row in CompanyModel.objects.filter(id__in=sorted(missing)).values("id", "name"):
                    self._company_names[row["id"]] = row["name"] or "Unknown"
            except Exception:
                return {cid: self._company_names[cid] for cid in wanted if cid in self._company_names}
            self._loaded_company_ids |= missing
        return {cid: self._company_names[cid] for cid in wanted if cid in self._company_names}


def _quantize(value) -> Decimal:
    from apps.license.services.canonical_ledger_service import quantize_2dp, to_decimal
    return quantize_2dp(to_decimal(value, DEC_0))
