"""DB adapter for the generic entitlement planner — ONE licence, ONE norm.

Read-only: never writes plans, debits or balances.  Every figure comes from
the licence's own records through the existing authoritative services:

* product groups   — active ``SionPlanningRule`` rows of the norm, evaluated
                     first-match-wins with ``sion_rule_engine.evaluate_expression``
                     against each licence import item;
* split / prices   — the rule's ``SionPlanningPercentageRow`` rows (or the
                     rule's own ``import_item`` + ``max_unit_price`` = 100 %);
* group quantity   — Σ authorised ``LicenseImportItemsModel.quantity``;
* opening CIF      — ``LicenseBalanceCalculator.calculate_credit``;
* BOE debits       — raw BOE CIF (canonical "BOE CIF = CIF from BOE
                     transactions") from ``LicenseBalanceCalculator.get_debit_rows`` (hidden BOEs
                     excluded, each RowDetails row exactly once — frozen ledger
                     rows included once, never re-added).  Invoice-represented
                     BOE netting done by the financial engine surfaces as the
                     AUTHORITATIVE_BALANCE_DIFFERENCE adjustment;
* allotments       — ``LicenseBalanceCalculator.get_allotment_rows``
                     ``contributed`` / ``contributed_qty`` (BOE-linked and
                     formally allocated parts already excluded);
* remaining CIF    — ``LicenseDetailsModel.get_balance_cif`` (financial engine).

Presentation metadata (labels, product → entitlement mapping, valuation,
sequence) comes from ``sion_planner_config.entitlement_profiles``.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Iterable

from apps.core.models import SionNormClassModel
from apps.license.models import LicenseDetailsModel, SionPlanningRule
from apps.license.services.balance_calculator import LicenseBalanceCalculator
from apps.license.services.entitlement_planning import (
    ALLOTMENT,
    AMBIGUOUS,
    BOE,
    MAPPED,
    OUTSIDE,
    RATE,
    UNMAPPED,
    Debit,
    EntitlementSpec,
    GroupSpec,
    _issue,
    compute_entitlement_plan,
    d,
)
from apps.license.services.scoped_sion_planning import ScopedPlanningError
from apps.license.services.sion_legacy_configurations import LEGACY_PLANNER_CONFIGURATIONS
from apps.license.services.sion_planner_config.entitlement_profiles import entitlement_profile
from apps.license.services.sion_rule_engine import _item_context, evaluate_expression

QTY_MATCH_TOLERANCE = Decimal("0.001")


# ── Pure helpers (unit-tested without the DB) ───────────────────────────────
def resolve_entitlement(texts: Iterable[str | None], products: list[dict], entitlement_keys: list[str]) -> tuple[str, str | None]:
    """Map debit texts (most authoritative first) to ONE entitlement.

    Each product carries ``entitlement`` and upper-case ``aliases``; without
    configured products the entitlement keys themselves are the aliases.  The
    first text that matches anything decides: one entitlement → MAPPED,
    several → AMBIGUOUS (never guessed).  Nothing matches → UNMAPPED.
    """
    catalogue = products or [{"entitlement": key, "aliases": [key]} for key in entitlement_keys]
    for text in texts:
        norm = " ".join(str(text or "").upper().split())
        if not norm:
            continue
        if norm in entitlement_keys:
            return MAPPED, norm
        hits = {p["entitlement"] for p in catalogue if any(a.upper() in norm for a in p.get("aliases", ()))}
        if len(hits) == 1:
            return MAPPED, hits.pop()
        if len(hits) > 1:
            return AMBIGUOUS, None
    return UNMAPPED, None


def split_action_targets(norm: str, action_key: str | None) -> dict[str, Decimal]:
    for action in LEGACY_PLANNER_CONFIGURATIONS.get(norm, {}).get("actions", []):
        if action.get("stable_key") == action_key:
            return {k: Decimal(str(v)) for k, v in action.get("config", {}).get("targets", {}).items()}
    return {}


# ── Service ──────────────────────────────────────────────────────────────────
class EntitlementPlanningService:
    @classmethod
    def build(cls, license_number: str, sion_code: str) -> dict[str, Any]:
        licence, sion = cls._resolve(license_number, sion_code)
        norm = sion.norm_class.upper()
        profile = entitlement_profile(norm)
        issues: list[dict] = []

        groups, item_group, meta = cls._groups(licence, sion, norm, profile, issues)
        debits = cls._debits(licence, groups, item_group, meta, issues)
        opening_cif, authoritative = cls._cif(licence, sion, issues)

        result = compute_entitlement_plan(
            opening_cif=opening_cif, groups=groups, debits=debits,
            authoritative_balance=authoritative, extra_issues=issues,
        )
        result.update({
            "licence_id": licence.pk,
            "licence_number": licence.license_number,
            "sion": sion.norm_class,
            "read_only": True,
            "group_config": [meta[g.key]["public"] for g in groups],
            "sources": {
                "groups": "SionPlanningRule (active, priority order) + sion_rule_engine.evaluate_expression",
                "split": "SionPlanningPercentageRow",
                "opening_cif": "LicenseBalanceCalculator.calculate_credit",
                "boe_debits": "LicenseBalanceCalculator.get_debit_rows (hidden BOEs excluded)",
                "allotments": "LicenseBalanceCalculator.get_allotment_rows (contributed)",
                "remaining_cif": "LicenseDetailsModel.get_balance_cif" if authoritative is not None
                else "opening − BOE − allotments (multi-norm licence)",
            },
        })
        return result

    # -- scope ---------------------------------------------------------------
    @staticmethod
    def _resolve(license_number, sion_code):
        if not str(license_number or "").strip() or not str(sion_code or "").strip():
            raise ScopedPlanningError("Both exact license_number and sion are required; no fallback is used.")
        matches = list(LicenseDetailsModel.objects.filter(license_number=str(license_number).strip())[:2])
        if not matches:
            raise ScopedPlanningError(f"Licence number {license_number!r} was not found.")
        if len(matches) > 1:
            raise ScopedPlanningError(f"Licence number {license_number!r} is not unique; refusing to pick one.")
        licence = matches[0]
        sion = SionNormClassModel.objects.filter(norm_class__iexact=str(sion_code).strip()).first()
        if not sion:
            raise ScopedPlanningError(f"SION {sion_code!r} was not found.")
        if licence.export_license.exists() and not licence.export_license.filter(norm_class=sion).exists():
            raise ScopedPlanningError(
                f"Licence {licence.license_number} does not contain SION {sion.norm_class} in its export manifest.")
        return licence, sion

    # -- groups --------------------------------------------------------------
    @classmethod
    def _groups(cls, licence, sion, norm, profile, issues):
        rules = list(SionPlanningRule.objects.filter(sion=sion, is_active=True)
                     .select_related("import_item")
                     .prefetch_related("percentage_rows__import_item")
                     .order_by("priority", "pk"))
        if not rules:
            raise ScopedPlanningError(f"SION {sion.norm_class} has no active planning rules.")
        items = list(licence.import_license.select_related("hs_code").prefetch_related("items")
                     .order_by("serial_number", "pk"))

        matched: dict[int, list] = {rule.pk: [] for rule in rules}
        for item in items:
            context = _item_context(item, None)
            for rule in rules:
                try:
                    hit = evaluate_expression(rule.expression or {}, context)
                except (ValueError, TypeError, KeyError) as exc:
                    issues.append(_issue("INVALID_RULE_EXPRESSION", True, None, None,
                                         f"Rule {rule.name} (#{rule.pk}) cannot be evaluated: {exc}"))
                    hit = False
                if hit:
                    matched[rule.pk].append(item)
                    break

        groups: list[GroupSpec] = []
        item_group: dict[int, str] = {}
        meta: dict[str, dict] = {}
        for rule in rules:
            members = matched[rule.pk]
            if not members:
                continue
            entitlements, item_ids = cls._entitlements(rule, profile)
            pgroup = cls._profile_group(profile, [e.key for e in entitlements])
            key = pgroup.get("key") or f"RULE_{rule.pk}"
            label = pgroup.get("label") or rule.name
            products = pgroup.get("products", [])
            ordered = tuple(sorted(entitlements, key=lambda e: (
                profile["entitlements"].get(e.key, {}).get("sequence", 0), entitlements.index(e))))
            groups.append(GroupSpec(key, label, sum((d(i.quantity) for i in members), Decimal("0")),
                                    ordered, len(members)))
            for item in members:
                item_group[item.pk] = key
            meta[key] = {"products": products, "keys": [e.key for e in ordered], "item_ids": item_ids,
                         "public": {"group": key, "label": label, "rule_id": rule.pk, "rule_name": rule.name,
                                    "source_rule": pgroup.get("source_rule"), "split_action": pgroup.get("split_action"),
                                    "products": [{"name": p["name"], "entitlement": p["entitlement"]} for p in products],
                                    "import_item_ids": [i.pk for i in members]}}
            cls._check_products(key, label, products, [e.key for e in ordered], issues)
            cls._check_split_action(norm, key, label, pgroup, ordered, profile, issues)
        return groups, item_group, meta

    @staticmethod
    def _entitlements(rule, profile):
        rows = sorted(rule.percentage_rows.all(), key=lambda r: (r.priority, r.pk))
        if rows:
            raw = [(r.import_item.name if r.import_item_id else rule.name, r.import_item_id,
                    d(r.percentage), d(r.unit_price) if r.unit_price is not None else d(rule.max_unit_price)) for r in rows]
        else:
            raw = [(rule.import_item.name if rule.import_item_id else rule.name, rule.import_item_id,
                    Decimal("100"), d(rule.max_unit_price))]
        out, ids = [], {}
        for name, item_id, pct, price in raw:
            key = " ".join(str(name).upper().split())
            cfg = profile["entitlements"].get(key, {})
            out.append(EntitlementSpec(key, cfg.get("label") or str(name).title(), pct, price,
                                       cfg.get("valuation", RATE), tuple(cfg.get("products", ()))))
            if item_id:
                ids[item_id] = key
        return out, ids

    @staticmethod
    def _profile_group(profile, keys):
        for group in profile.get("groups", []):
            if set(group.get("entitlement_items", [])) == set(keys):
                return group
        return {}

    @staticmethod
    def _check_products(key, label, products, ent_keys, issues):
        for product in products:
            if product.get("entitlement") not in ent_keys:
                issues.append(_issue("PRODUCT_MAPPING_INVALID", True, key, product.get("entitlement"),
                                     f"{label}: product {product.get('name')} maps to an entitlement "
                                     f"that is not configured on the rule."))

    @staticmethod
    def _check_split_action(norm, key, label, pgroup, ordered, profile, issues):
        targets = split_action_targets(norm, pgroup.get("split_action"))
        if not targets:
            return
        for ent in ordered:
            target = profile["entitlements"].get(ent.key, {}).get("split_target")
            if target in targets and targets[target] * 100 != ent.percentage:
                issues.append(_issue(
                    "SPLIT_ACTION_MISMATCH", False, key, ent.key,
                    f"{label}: {ent.label} is {ent.percentage}% on the planning rule but "
                    f"{targets[target] * 100}% in {pgroup.get('split_action')}."))

    # -- debits --------------------------------------------------------------
    @classmethod
    def _debits(cls, licence, groups, item_group, meta, issues) -> list[Debit]:
        single = {g.key: g.entitlements[0].key for g in groups if len(g.entitlements) == 1}
        debits: list[Debit] = []

        boe_rows = (LicenseBalanceCalculator.get_debit_rows(licence)
                    .select_related("bill_of_entry__planning_target_item", "sr_number")
                    .prefetch_related("bill_of_entry__allotment")
                    .order_by("bill_of_entry__bill_of_entry_date", "pk"))
        unlinked_boes = []
        for row in boe_rows:
            boe = row.bill_of_entry
            linked = list(boe.allotment.all())
            texts = [boe.planning_target_item.name if boe.planning_target_item_id else None, boe.product_name,
                     *[a.item_name for a in linked]]
            debit = cls._debit(BOE, boe.bill_of_entry_number, row.qty, row.cif_fc, row.sr_number_id,
                               item_group, single, meta, texts, boe.planning_target_item_id, {
                                   "row_id": row.pk, "date": boe.bill_of_entry_date.isoformat() if boe.bill_of_entry_date else None,
                                   "product": boe.product_name, "serial_number": row.sr_number.serial_number,
                                   "is_frozen": row.is_frozen, "allotment_ids": [a.pk for a in linked]})
            debits.append(debit)
            if not linked:
                unlinked_boes.append((row, debit))

        allot_rows = (LicenseBalanceCalculator.get_allotment_rows(licence)
                      .filter(contributed__gt=0)
                      .select_related("allotment__planning_target_item", "item")
                      .order_by("allotment_id", "pk"))
        full_unlinked = []
        for row in allot_rows:
            allot = row.allotment
            target = getattr(row, "planning_target_item", None) or allot.planning_target_item
            texts = [target.name if target else None, allot.item_name]
            debit = cls._debit(ALLOTMENT, str(allot.pk), row.contributed_qty, row.contributed, row.item_id,
                               item_group, single, meta, texts, target.pk if target else None, {
                                   "allotment_item_id": row.pk, "item_name": allot.item_name,
                                   "serial_number": row.item.serial_number, "type": allot.type})
            debits.append(debit)
            if abs(d(row.contributed_qty) - d(row.qty)) <= QTY_MATCH_TOLERANCE:
                full_unlinked.append((row, debit))

        cls._duplicate_checks(unlinked_boes, full_unlinked, issues)
        return debits

    @staticmethod
    def _debit(kind, ref, qty, cif, item_id, item_group, single, meta, texts, target_id, detail) -> Debit:
        group_key = item_group.get(item_id)
        if group_key is None:
            return Debit(kind, ref, d(qty), d(cif), OUTSIDE, None, None, detail)
        if group_key in single:
            return Debit(kind, ref, d(qty), d(cif), MAPPED, single[group_key], group_key, detail)
        info = meta[group_key]
        if target_id and target_id in info["item_ids"]:
            return Debit(kind, ref, d(qty), d(cif), MAPPED, info["item_ids"][target_id], group_key, detail)
        status, ent = resolve_entitlement(texts, info["products"], info["keys"])
        return Debit(kind, ref, d(qty), d(cif), status, ent, group_key, detail)

    @staticmethod
    def _duplicate_checks(unlinked_boes, full_unlinked, issues):
        """An unlinked BOE and a wholly outstanding, unlinked allotment of the same
        quantity on the same import item is likely ONE shipment counted twice.
        Reported, never auto-netted (linking is a reconciliation decision)."""
        used: set[int] = set()
        for row, boe_debit in unlinked_boes:
            for allot_row, allot_debit in full_unlinked:
                if allot_row.pk in used or allot_row.item_id != row.sr_number_id:
                    continue
                if abs(d(allot_row.qty) - d(row.qty)) <= QTY_MATCH_TOLERANCE:
                    used.add(allot_row.pk)
                    issues.append(_issue(
                        "POSSIBLE_DUPLICATE_UTILISATION", True, boe_debit.group_key, boe_debit.entitlement_key,
                        f"BOE {boe_debit.reference} ({row.qty} qty, {row.cif_fc} CIF) is not linked to any "
                        f"allotment, while allotment {allot_debit.reference} ({allot_row.qty} qty, "
                        f"{allot_row.contributed} CIF) on the same item is still outstanding with no BOE. "
                        f"If they are the same shipment, link them in Reconciliation; both are counted today.",
                        reference=boe_debit.reference, allotment=allot_debit.reference))
                    break

    # -- CIF -----------------------------------------------------------------
    @staticmethod
    def _cif(licence, sion, issues):
        norms = set(licence.export_license.values_list("norm_class_id", flat=True))
        if len(norms) > 1:
            opening = sum((d(x) for x in licence.export_license.filter(norm_class=sion)
                           .values_list("cif_fc", flat=True)), Decimal("0"))
            issues.append(_issue("MULTI_NORM_LICENCE", True, None, None,
                                 f"Licence carries {len(norms)} SION norms: opening CIF is the {sion.norm_class} "
                                 f"manifest only, but debits on other norms' items are deducted from it as "
                                 f"'outside planned groups', so the residual balance is understated. "
                                 f"Confirmation is blocked; use the licence-wide balance views."))
            return opening, None
        return d(LicenseBalanceCalculator.calculate_credit(licence)), d(licence.get_balance_cif)
