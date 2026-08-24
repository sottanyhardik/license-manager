"""Canonical selection of the CIF balance source for a licence import row.

The legacy branch intentionally delegates to its caller's already-established
calculation.  Keeping it as a selector (rather than recreating that formula)
guarantees that NULL and False cannot drift from legacy behaviour.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable


LEGACY = "LICENSE"
INDIVIDUAL_ITEM = "INDIVIDUAL_ITEM"


def resolve_effective_cif_mode(licence) -> str:
    """Return INDIVIDUAL_ITEM only for an explicit boolean True override."""
    if getattr(licence, "individual_item_cif_override", None) is True:
        return INDIVIDUAL_ITEM
    return LEGACY


def _decimal(value: Any) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value or 0))


@dataclass(frozen=True)
class EffectiveCifProjection:
    """Auditable item CIF projection shared by read and mutation consumers.

    ``legacy_row_balance`` remains available for audit, while the false/null
    branch displays the licence-wide CIF balance.
    """

    raw_override: bool | None
    effective_mode: str
    legacy_row_balance: Decimal
    individual_item_balance: Decimal
    license_balance_cif: Decimal
    effective_row_balance: Decimal
    balance_source: str
    footer_totals: dict[str, Decimal]
    diagnostics: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "raw_override": self.raw_override,
            "effective_mode": self.effective_mode,
            "legacy_row_balance": self.legacy_row_balance,
            "individual_item_balance": self.individual_item_balance,
            "license_balance_cif": self.license_balance_cif,
            "effective_row_balance": self.effective_row_balance,
            "balance_source": self.balance_source,
            "footer_totals": self.footer_totals,
            "diagnostics": self.diagnostics,
        }


def project_effective_item_cif(*, licence, item, legacy_row_balance: Decimal | Any | Callable[[], Any]) -> EffectiveCifProjection:
    """Project an item's effective CIF balance without duplicating formulas.

    A callable may be passed for ``legacy_row_balance``; it is invoked only on
    the legacy branch, which makes the selector safe for costly legacy paths.
    """
    mode = resolve_effective_cif_mode(licence)
    raw_override = getattr(licence, "individual_item_cif_override", None)
    # `balance_cif_fc` is the legacy/display availability alias and may be a
    # licence-wide shared pool.  Individual mode must instead use the live
    # debit/credit ledger for this *persisted import-row primary key*.
    # Never derive this from HSN, product/SION labels, serials, or UI order.
    if getattr(item, "pk", None) is not None:
        from apps.license.services.balance_calculator import ItemBalanceCalculator
        individual = _decimal(ItemBalanceCalculator.calculate_item_balance(item))
    else:
        # Lightweight projections/tests may not be persisted models. They
        # carry an already supplied source-row balance; real request paths
        # always take the PK-backed live ledger branch above.
        individual = _decimal(getattr(item, "balance_cif_fc", 0))

    # Resolve the licence balance once for diagnostics and shared-pool output.
    cached = getattr(licence, "_effective_cif_license_balance", None)
    if cached is None:
        cached = _decimal(licence.get_balance_cif)
        setattr(licence, "_effective_cif_license_balance", cached)

    if mode == INDIVIDUAL_ITEM:
        effective = individual
        # A raw balance remains visible for audit/display.  Mutation callers
        # cap executable availability separately with max(value, 0).
        legacy = _decimal(legacy_row_balance() if callable(legacy_row_balance) else legacy_row_balance)
        source = "IMPORT_ITEM_CIF"
    else:
        # False/null uses the licence-wide balance CIF.  The item-level value
        # is only shown when the explicit individual-item override is enabled.
        legacy = _decimal(legacy_row_balance() if callable(legacy_row_balance) else legacy_row_balance)
        effective = _decimal(cached)
        source = "LICENSE"

    return EffectiveCifProjection(
        raw_override=raw_override,
        effective_mode=mode,
        legacy_row_balance=legacy,
        individual_item_balance=individual,
        license_balance_cif=_decimal(cached),
        effective_row_balance=effective,
        balance_source=source,
        footer_totals={"effective_balance_cif": effective},
        diagnostics={"executable_available_cif": max(effective, Decimal("0"))},
    )


def effective_source_row_cif_available(*, licence, item, legacy_available: Decimal | Any | Callable[[], Any]) -> Decimal:
    """Return the executable CIF ceiling for one persisted import source row.

    This is the mutation/candidate entry point.  Callers provide their existing
    legacy availability expression, which is evaluated unchanged for NULL and
    False.  Only a literal True reads the item's ledger balance, keyed by the
    persisted import-row primary key.  It deliberately has no HSN/product/SION
    arguments, making accidental label/group based attribution impossible.
    """
    projection = project_effective_item_cif(
        licence=licence,
        item=item,
        legacy_row_balance=legacy_available,
    )
    return max(projection.effective_row_balance, Decimal("0"))
