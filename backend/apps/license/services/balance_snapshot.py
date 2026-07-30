"""
Balance Snapshot — the single shared, batched read-model for "Balance CIF"
(license-level AND per-item), composed entirely from EXISTING bulk building
blocks in `balance_calculator.py` / `condition_pool.py` / `plan_reporting.py`.
No arithmetic is re-derived here except `average_cif`'s divide-by-zero guard
(see `get_snapshot_bulk`'s docstring) — everything else is lookup/composition
of numbers those modules already compute and already agree on.

Goal: "exactly one implementation, every consumer calls the snapshot" for
Balance CIF. New/redirected consumers should call `get_snapshot_bulk` (many
licenses, e.g. list views/reports) or `get_snapshot` (one license, e.g. a
detail/overview endpoint) instead of re-composing these same bulk calls
themselves.

Deliberately does NOT cover `apps.license.services.license_overview_items.
compute_item_ledger_rows` — that module's own docstring documents its
`available_value`/`available_quantity` as intentionally DISTINCT from this
snapshot's, and explicitly must not call into `calculate_balance.py`. Do not
redirect it here.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict

from apps.core.constants import DEC_0
from apps.core.utils.decimal_utils import to_decimal


def _empty_snapshot() -> Dict[str, Any]:
    """Zero-value shape returned by `get_snapshot` for an id with no rows
    anywhere (no license found / no license-level components), mirroring
    the empty-dict fallback `plan_map_for_license`/`plan_map_for_import_items`
    return for an id with nothing to report (see `plan_reporting.py`)."""
    return {
        "balance_cif": DEC_0,
        "total_licence_cif": DEC_0,
        "debited_cif": DEC_0,
        "outstanding_allotted_cif": DEC_0,
        # Additive "two engines" fields (Financial Balance Engine) — see
        # `get_snapshot_bulk`'s docstring for the full field writeup.
        "original_licence_cif": DEC_0,
        "hidden_boe_total": DEC_0,
        "opening_balance": DEC_0,
        "remaining_tradable_licence": DEC_0,
        "financial_balance": DEC_0,
        "customs_balance": DEC_0,
        "balance_difference": DEC_0,
        # Exact-named fields per the "LicenseBalanceService.get_snapshot()"
        # spec — see `get_snapshot_bulk`'s docstring.
        "financial_available_balance": DEC_0,
        "customs_available_balance": DEC_0,
        "previous_owner_utilisation": DEC_0,
        "purchased_licence_cif": DEC_0,
        "sold_licence_cif": DEC_0,
        "pending_allotments": DEC_0,
        "difference": DEC_0,
        "items": {},
    }


def get_snapshot_bulk(license_ids) -> Dict[int, Dict[str, Any]]:
    """
    Batched Balance Snapshot for MANY licenses — a fixed small number of
    queries regardless of how many licenses/items are batched (never
    N-per-license), by composing:

      - License-level CIF (each called ONCE with the full `license_ids`
        list): `LicenseBalanceCalculator.calculate_balance_for_licenses`
        (`balance_cif`), `.calculate_credit_for_licenses`
        (`total_licence_cif`), `.calculate_boe_debit_total_for_licenses`
        (`debited_cif`), `.calculate_allotment_for_licenses`
        (`outstanding_allotted_cif`).
      - "Two engines" fields (Financial Balance Engine, additive — see
        `LicenseBalanceCalculator.calculate_financial_balance`'s and
        `.calculate_opening_balance`'s docstrings for the formulas/gate
        this composes verbatim, never re-derives): `.calculate_credit_
        for_licenses` again for `original_licence_cif` (alias of `total_
        licence_cif` — same map, same number, business-vocabulary name),
        `.calculate_hidden_boe_debit_total_for_licenses` (`hidden_boe_
        total`), `.calculate_opening_balance_for_licenses` (`opening_
        balance` / `remaining_tradable_licence` — same number, two names:
        the design doc's "Remaining Tradable Licence" is this value's
        display name whenever hidden BOEs exist), `.calculate_financial_
        balance_for_licenses` (`financial_balance`), `balance_cif` again
        as `customs_balance` (alias distinguishing the two engines), and
        `balance_difference = financial_balance - customs_balance` (the
        ONLY arithmetic this block performs itself, on top of lookups).
      - Per-item CIF: `apps.license.services.condition_pool.
        available_value_bulk_map` for `available_value`/`balance_cif_fc`
        (aliases of the same Decimal — see that function's docstring and
        `LicenseImportItemsModel.available_value_calculated`'s).
      - Per-item planning: `apps.license.services.plan_reporting.
        plan_map_for_import_items` for `planned_quantity`/`planned_cif_fc`.
      - Per-item quantity: `ItemBalanceCalculator.
        calculate_available_quantity_for_items` (`available_quantity`),
        `.calculate_debited_quantity_for_items` (`debited_quantity`), and
        `LicenseBalanceCalculator.get_outstanding_allotment_totals_for_items`
        (`outstanding_allotted_quantity`) — same Balance-Engine lineage as
        the Allotment Max-button path, not the legacy
        `apps.core.scripts.calculate_balance` stored-field lineage.

    `average_cif` (`available_value / available_quantity`, guarded to
    `Decimal('0')` when `available_quantity` is 0) is the ONLY arithmetic
    this module performs itself — every other field is a direct lookup from
    the maps above.

    Args:
        license_ids: iterable of license pks.

    Returns:
        `{license_id: {...}}` with an entry for EVERY id in `license_ids`
        (matching `calculate_balance_for_licenses`'s own "every id gets an
        entry, missing components contribute DEC_0" convention), shaped:
        ```
        {
            "balance_cif": Decimal,
            "total_licence_cif": Decimal,
            "debited_cif": Decimal,
            "outstanding_allotted_cif": Decimal,
            "original_licence_cif": Decimal,      # alias of total_licence_cif
            "hidden_boe_total": Decimal,
            "opening_balance": Decimal,            # alias: remaining_tradable_licence
            "remaining_tradable_licence": Decimal, # alias of opening_balance
            "financial_balance": Decimal,
            "customs_balance": Decimal,            # alias of balance_cif
            "balance_difference": Decimal,         # financial_balance - customs_balance
            "items": {
                item_id: {
                    "available_value": Decimal,
                    "balance_cif_fc": Decimal,       # alias of available_value
                    "planned_quantity": float | Decimal("0"),
                    "planned_cif_fc": float | 0,
                    "available_quantity": Decimal,
                    "debited_quantity": Decimal,
                    "outstanding_allotted_quantity": Decimal,
                    "average_cif": Decimal,
                },
                ...
            },
        }
        ```
    """
    ids = list(license_ids)
    if not ids:
        return {}

    from apps.license.models import LicenseImportItemsModel
    from apps.license.services.balance_calculator import ItemBalanceCalculator, LicenseBalanceCalculator
    from apps.license.services.condition_pool import available_value_bulk_map
    from apps.license.services.plan_reporting import plan_map_for_import_items

    # License-level CIF — 3 queries total (calculate_balance_for_licenses
    # itself composes credit/debit/allotment, so this is 3 queries, not 4;
    # see that method's docstring).
    balance_map = LicenseBalanceCalculator.calculate_balance_for_licenses(ids)
    credit_map = LicenseBalanceCalculator.calculate_credit_for_licenses(ids)
    debit_map = LicenseBalanceCalculator.calculate_boe_debit_total_for_licenses(ids)
    allotment_map = LicenseBalanceCalculator.calculate_allotment_for_licenses(ids)

    # "Two engines" fields (Financial Balance Engine, additive) — each
    # composes its own `_for_licenses` bulk sibling on `balance_calculator.
    # py` (never a per-license loop); see this function's docstring for the
    # full field-by-field writeup.
    hidden_map = LicenseBalanceCalculator.calculate_hidden_boe_debit_total_for_licenses(ids)
    opening_map = LicenseBalanceCalculator.calculate_opening_balance_for_licenses(ids)
    financial_map = LicenseBalanceCalculator.calculate_financial_balance_for_licenses(ids)
    purchase_credit_map = LicenseBalanceCalculator.calculate_purchase_credit_for_licenses(ids)
    sale_debit_map = LicenseBalanceCalculator.calculate_trade_for_licenses(ids)
    # The literal, hidden-inclusive Customs figure — the ONE that always
    # matches `build_customs_ledger`'s own running total exactly (see
    # `calculate_customs_balance`'s docstring). NOT `balance_map` above
    # (`calculate_balance_for_licenses`, excludes hidden rows) — that one
    # stays only as the `customs_balance`/back-compat alias key below.
    customs_available_map = LicenseBalanceCalculator.calculate_customs_balance_for_licenses(ids)

    # One query for every import item across all requested licenses.
    items = list(LicenseImportItemsModel.objects.filter(license_id__in=ids))
    item_ids = [item.id for item in items]

    value_map = available_value_bulk_map(items)
    plan_map = plan_map_for_import_items(item_ids)
    debited_qty_map = ItemBalanceCalculator.calculate_debited_quantity_for_items(item_ids)
    outstanding_map = LicenseBalanceCalculator.get_outstanding_allotment_totals_for_items(ids)

    items_by_license: Dict[int, Dict[int, Dict[str, Any]]] = {lid: {} for lid in ids}
    for item in items:
        available_value = value_map.get(item.id, DEC_0)
        debited_quantity = debited_qty_map.get(item.id, DEC_0)
        outstanding_qty, _outstanding_cif = outstanding_map.get(item.id, (DEC_0, DEC_0))
        # Same `quantity - debited - outstanding` formula as
        # `ItemBalanceCalculator.calculate_available_quantity_for_items` —
        # inlined here (reusing the `debited_qty_map`/`outstanding_map`
        # already fetched above for `debited_quantity`/
        # `outstanding_allotted_quantity`) rather than calling that helper,
        # which would redundantly re-fetch both maps. Keep in lock-step with
        # that method's docstring if this formula ever changes.
        total_quantity = to_decimal(item.quantity, DEC_0)
        available_quantity = total_quantity - debited_quantity - outstanding_qty
        available_quantity = available_quantity if available_quantity >= DEC_0 else DEC_0

        plan = plan_map.get(item.id)
        if plan:
            planned_quantity = plan["total_planned_quantity"]
            planned_cif_fc = plan["total_planned_cif"]
        else:
            planned_quantity = Decimal("0")
            planned_cif_fc = 0

        average_cif = (available_value / available_quantity) if available_quantity > 0 else Decimal("0")

        items_by_license[item.license_id][item.id] = {
            "available_value": available_value,
            "balance_cif_fc": available_value,
            "planned_quantity": planned_quantity,
            "planned_cif_fc": planned_cif_fc,
            "available_quantity": available_quantity,
            "debited_quantity": debited_quantity,
            "outstanding_allotted_quantity": outstanding_qty,
            "average_cif": average_cif,
        }

    result = {}
    for lid in ids:
        customs_balance = balance_map.get(lid, DEC_0)
        financial_balance = financial_map.get(lid, DEC_0)
        opening_balance = opening_map.get(lid, DEC_0)
        hidden_total = hidden_map.get(lid, DEC_0)
        customs_available_balance = customs_available_map.get(lid, DEC_0)
        result[lid] = {
            # `balance_cif` is THE business "Balance CIF" every consumer
            # reads — the Financial Ledger figure, matching
            # `LicenseDetailsModel.get_balance_cif`'s own definition (see
            # that property's docstring). NOT `calculate_balance_for_
            # licenses`'s raw Customs figure — that lives separately under
            # `customs_balance` below, for the reconciliation-only
            # consumers that deliberately need the two to stay distinct.
            "balance_cif": financial_balance,
            "total_licence_cif": credit_map.get(lid, DEC_0),
            "debited_cif": debit_map.get(lid, DEC_0),
            "outstanding_allotted_cif": allotment_map.get(lid, DEC_0),
            # "Two engines" fields — see this function's docstring.
            "original_licence_cif": credit_map.get(lid, DEC_0),
            "hidden_boe_total": hidden_total,
            "opening_balance": opening_balance,
            "remaining_tradable_licence": opening_balance,
            "financial_balance": financial_balance,
            "customs_balance": customs_balance,
            "balance_difference": financial_balance - customs_balance,
            # Exact-named fields per the "LicenseBalanceService.
            # get_snapshot()" spec. `difference` here is 0 by definition:
            # `financial_available_balance` IS `financial_balance` (same
            # number, business-vocabulary alias) — a real inconsistency
            # can only be detected by comparing against an INDEPENDENT
            # recomputation, which is exactly what `build_financial_
            # ledger`'s own `mismatched` self-check does (see `build_
            # reconciliation_summary`); this snapshot doesn't build ledger
            # rows, so it has no second computation to diff against.
            "financial_available_balance": financial_balance,
            "customs_available_balance": customs_available_balance,
            # Hidden BOEs ONLY — see `build_financial_ledger`'s "Previous
            # Owner Utilisation" row. Licence Purchase/Sale are separate,
            # independent financial events, never folded in here — exposed
            # as their own fields below.
            "previous_owner_utilisation": hidden_total,
            "purchased_licence_cif": purchase_credit_map.get(lid, DEC_0),
            "sold_licence_cif": sale_debit_map.get(lid, DEC_0),
            "pending_allotments": allotment_map.get(lid, DEC_0),
            "difference": DEC_0,
            "items": items_by_license.get(lid, {}),
        }
    return result


def get_snapshot(license_id) -> Dict[str, Any]:
    """
    Single-license convenience wrapper around `get_snapshot_bulk([license_id])
    [license_id]` — same single-vs-bulk fallback convention as
    `plan_map_for_license`/`plan_map_for_import_items` in `plan_reporting.py`.

    Args:
        license_id: a single license pk.

    Returns:
        `get_snapshot_bulk([license_id])[license_id]`, or `_empty_snapshot()`
        if the id has no items/doesn't exist (defensive fallback — in
        practice `get_snapshot_bulk` always creates an entry for every id it
        is given, mirroring `calculate_balance_for_licenses`'s convention).
    """
    return get_snapshot_bulk([license_id]).get(license_id) or _empty_snapshot()
