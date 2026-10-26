"""Central business guard: norm classes that may never carry Olive Oil.

Norm classes ``A3627`` and ``E132`` must never be classified as Olive Oil,
whatever the HSN code, description, fallback or database mapping says.
Every classification path calls :func:`guard_product_for_norm` (or
:func:`is_olive_oil_item_name_allowed` for stored item names) so the rule is
enforced in one place rather than per entry point.

A rejected classification is not silently replaced with another product:
the caller receives ``None`` (manual review / unclassified) and a warning is
logged with the rule tag.
"""
from __future__ import annotations

import logging
from typing import Iterable, Optional

logger = logging.getLogger(__name__)

OLIVE_OIL = "OLIVE OIL"
RULE_TAG = "NORM_FORBIDS_OLIVE_OIL"
RESTRICTED_OLIVE_OIL_NORMS = frozenset({"A3627", "E132"})


def normalize_norm_class(value) -> str:
    """Upper-case, whitespace-stripped norm class ('  e132 ' -> 'E132')."""
    return str(value or "").strip().upper()


def normalize_product(value) -> str:
    """Upper-case product name with internal whitespace collapsed."""
    return " ".join(str(value or "").split()).upper()


def product_base_name(item_name: str) -> str:
    """'OLIVE OIL - E5' -> 'OLIVE OIL'. A name without a ' - NORM' suffix is returned as-is."""
    return normalize_product(str(item_name or "").rsplit(" - ", 1)[0])


def is_olive_oil_allowed(norm_class, proposed_product) -> bool:
    """False only when a restricted norm is proposed to carry Olive Oil."""
    norm = normalize_norm_class(norm_class)
    product = normalize_product(proposed_product)
    return not (norm in RESTRICTED_OLIVE_OIL_NORMS and product == OLIVE_OIL)


def guard_product_for_norm(norm_class, proposed_product: Optional[str], *, context: str = "") -> Optional[str]:
    """Return ``proposed_product`` if allowed for ``norm_class``, else ``None``.

    ``None`` means manual review: the caller must not substitute another product.
    """
    if proposed_product is None or is_olive_oil_allowed(norm_class, proposed_product):
        return proposed_product
    logger.warning(
        "%s: rejected %r for norm %r%s",
        RULE_TAG, proposed_product, normalize_norm_class(norm_class),
        f" ({context})" if context else "",
    )
    return None


def is_olive_oil_item_name_allowed(item_name: str, norm_classes: Iterable[str]) -> bool:
    """False when a stored item name is Olive Oil and any of its norms is restricted."""
    if product_base_name(item_name) != OLIVE_OIL:
        return True
    return not any(normalize_norm_class(norm) in RESTRICTED_OLIVE_OIL_NORMS for norm in norm_classes)
