"""Canonical Product Resolver — one entry point for any page (Item Pivot, Licence Planning,
Product Master, SION configuration). Read-only: returns the same validated, explained
suggestion the review workspace shows; it never links or merges anything.
"""
from __future__ import annotations

from apps.license.services.product_matching import normalise, source_key, suggest


def resolve(description: str, *, hsn: str = "", sion: str | None = None) -> dict:
    from apps.license.services.product_matching_semantic import finalise

    group = {"source_key": source_key(normalise(description), hsn, sion), "kind": "UNMAPPED", "description": description,
             "aliases": [description], "hsn_code": hsn, "hsn_codes": [hsn] if hsn else [], "sion": sion,
             "import_item_ids": [], "license_numbers": [], "source_records": []}
    row = finalise(suggest([group]))[0]
    keep = ("source_key", "description", "hsn_code", "sion", "band", "action", "confidence", "matcher", "model", "alias_match",
            "suggestion", "explanation", "conflicts", "checks", "candidates", "entitlement_hits", "history", "semantic")
    return {k: row.get(k) for k in keep}
