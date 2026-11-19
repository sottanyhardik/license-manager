"""Approved Alias Registry (matching only — never the planning-rule ``SionInputAliasConfig``).

An alias turns a future identical (normalised) description into a 100 % *suggestion*
for its master item; approval is still required and every hard validation still runs.
"""
from __future__ import annotations

from collections import defaultdict

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core.models import ItemNameModel, SionNormClassModel
from apps.license.models import ProductAlias, ProductIntelAuditEvent
from apps.license.services.product_matching import MatchValidationError, normalise, product_segments


def legit_sions(item: ItemNameModel) -> set[str]:
    return {n.norm_class for n in item.norms.all()} or ({item.sion_norm_class.norm_class} if item.sion_norm_class_id else set())


def alias_index(sion_codes: set[str]) -> dict[str, dict[str, list[tuple[int, int, str]]]]:
    """{sion: {normalised alias: [(item_id, alias_id, alias_text)]}} for active aliases usable under each SION."""
    index: dict[str, dict[str, list[tuple[int, int, str]]]] = defaultdict(lambda: defaultdict(list))
    rows = ProductAlias.objects.filter(is_active=True).select_related("sion", "item", "item__sion_norm_class").prefetch_related("item__norms")
    for alias in rows:
        scope = {alias.sion.norm_class} if alias.sion_id else legit_sions(alias.item)
        for code in scope & sion_codes:
            index[code][alias.normalized_alias].append((alias.item_id, alias.pk, alias.alias_text))
    return index


def create_alias(*, text: str, item_id: int, sion: str | None, user, source: str = ProductAlias.REVIEWER, decision=None) -> ProductAlias:
    normalised = normalise(text)
    if not normalised:
        raise MatchValidationError("Alias is empty after normalisation")
    if len(product_segments(text)) > 1:
        raise MatchValidationError("An alias must name one product; this text lists several")
    item = ItemNameModel.objects.prefetch_related("norms").select_related("sion_norm_class").filter(pk=item_id, is_active=True).first()
    if item is None:
        raise MatchValidationError("Unknown or inactive master item")
    sion_obj = None
    if sion:
        sion_obj = SionNormClassModel.objects.filter(norm_class=sion).first()
        if sion_obj is None:
            raise MatchValidationError(f"Unknown SION {sion}")
        if sion not in legit_sions(item):
            raise MatchValidationError(f"{item.name} is not a legitimate item for {sion}")
    clash = ProductAlias.objects.filter(is_active=True, normalized_alias=normalised).exclude(item_id=item_id)
    clash = clash.filter(sion__norm_class=sion) | clash.filter(sion__isnull=True) if sion else clash
    if clash.exists():
        other = clash.select_related("item").first()
        raise MatchValidationError(f"'{text}' is already an alias of {other.item.name} — deactivate that alias first")
    try:
        with transaction.atomic():
            alias, created = _store_alias(normalised, item, sion_obj, text, source, decision, user, sion)
    except IntegrityError as exc:  # a concurrent create of the same alias
        raise MatchValidationError(f"'{text}' was just registered by another reviewer — reload and retry") from exc
    return alias


def _store_alias(normalised, item, sion_obj, text, source, decision, user, sion):
    with transaction.atomic():
        alias, created = ProductAlias.objects.get_or_create(
            normalized_alias=normalised[:500], item=item, sion=sion_obj,
            defaults={"alias_text": text.strip()[:500], "source": source, "decision": decision, "created_by": user},
        )
        if not created and not alias.is_active:
            alias.is_active, alias.deactivated_on = True, None
            alias.save(update_fields=["is_active", "deactivated_on"])
        ProductIntelAuditEvent.objects.create(action="alias_create", user=user, detail={
            "alias_id": alias.pk, "text": text[:500], "normalised": normalised[:500], "item_id": item.pk, "item": item.name,
            "sion": sion, "source": source, "decision_id": getattr(decision, "pk", None), "created": created})
    return alias, created


def deactivate_alias(*, alias_id: int, user) -> ProductAlias:
    alias = ProductAlias.objects.filter(pk=alias_id).first()
    if alias is None:
        raise MatchValidationError("Unknown alias")
    with transaction.atomic():
        alias.is_active, alias.deactivated_on = False, timezone.now()
        alias.save(update_fields=["is_active", "deactivated_on"])
        ProductIntelAuditEvent.objects.create(action="alias_deactivate", user=user, detail={"alias_id": alias.pk, "item_id": alias.item_id})
    return alias
