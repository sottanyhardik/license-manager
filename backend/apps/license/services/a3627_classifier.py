"""Authoritative classification registry for SION norm A3627 (glass & ceramic).

One place defines the A3627 products. ``product_classification.classify_product``
delegates here for norm A3627, and the item pivot (JSON and Excel) reads the
result from there.

Serial numbers are deliberately NOT a classification gate. The same Sr. No.
carries different products across licenses (Sr. No. 6 holds 50+ "PACKING
MATERIAL / WOODEN PALLETS" lines), so the description and HSN decide. The serial
is accepted and returned for diagnostics only.

Rules are evaluated in order; the first rule that matches decides. A line that
matches a rule but carries a contradiction (for example Sr. No. 6 oxide wording
together with "RUTILE") is returned as AMBIGUOUS and is not classified.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

CONFIRMED = "CONFIRMED"
AMBIGUOUS = "AMBIGUOUS"
UNMATCHED = "UNMATCHED"

NORM = "A3627"

# Canonical display labels. Every consumer (API, pivot JSON, Excel, frontend keys) uses these.
RUTILE = "RUTILE"
ALUMINIUM_OXIDE = "ALUMINIUM OXIDE"
SODA_ASH = "SODA ASH"
TITANIUM_DIOXIDE = "TITANIUM DIOXIDE"
PP = "PP"
BB_BOARD = "BB-BOARD"
PP_LAMINATED_BOARD = "PP LAMINATED BOARD"
KRAFT_LINER = "KRAFT LINER"
WOODEN_SHEETS_PALLETS = "WOODEN SHEETS / PALLETS"
ALUMINIUM_FOIL = "ALUMINIUM FOIL"
SILICA = "SILICA"
BORAX = "BORAX"

# Tolerates the "TITRANIUM" spelling seen in the real Sr. No. 17 records.
TITANIUM_DIOXIDE_PATTERN = re.compile(r"\btit\w*ium dioxide\b")

# Declared HSN of each Sr. No. 22 product. A line's own HSN decides before its description.
SR22_HSN_CATEGORY = {
    "39021000": PP,
    "48070030": BB_BOARD,
    "48115900": PP_LAMINATED_BOARD,
    "48041100": KRAFT_LINER,
}


@dataclass(frozen=True)
class A3627Classification:
    category: Optional[str]
    rule_id: str
    status: str
    reason: str
    multi_product: bool = False


def normalize_hsn(hs_code: str | None) -> str:
    """Digits only, leading zeroes kept: '3206.11.10' -> '32061110'."""
    return re.sub(r"\D", "", hs_code or "")


def normalize_description(description: str | None) -> str:
    """Lower-case, punctuation and hyphens become spaces, whitespace collapsed.

    'BB-Board 2/S Glazed' and 'bb board 2 s glazed' compare equal.
    """
    text = re.sub(r"[^a-z0-9%]+", " ", (description or "").lower())
    return " ".join(text.split())


def _has_any(desc: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in desc for phrase in phrases)


def _has_word(desc: str, word: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(word)}(?![a-z0-9])", desc) is not None


def classify_a3627(serial_no: int | None, hs_code: str | None, description: str | None) -> A3627Classification:
    """Return the A3627 product for one import line.

    ``serial_no`` is accepted for diagnostics and never changes the outcome.
    """
    hsn = normalize_hsn(hs_code)
    desc = normalize_description(description)
    other_than_rutile = "other than rutile" in desc
    glass_formers = "glass former" in desc
    soda_ash = "soda ash" in desc
    titanium_dioxide = bool(TITANIUM_DIOXIDE_PATTERN.search(desc))
    composite = _has_any(desc, ("modifiers namely", "intermediates namely", "other special additives", "glass formers namely", "packing material"))

    # Sr. No. 17: Titanium Dioxide other than Rutile Grade (and its listed siblings).
    # Checked first so the "rutile" wording can never pull these lines into RUTILE.
    if (titanium_dioxide and "other than" in desc) or (hsn.startswith("3206") and other_than_rutile):
        return A3627Classification(TITANIUM_DIOXIDE, "A3627.SR17.TITANIUM_DIOXIDE", CONFIRMED, "titanium dioxide other than rutile")
    if _has_any(desc, ("other special additives", "nucleating agents")) and (titanium_dioxide or hsn.startswith("32061110")):
        return A3627Classification(TITANIUM_DIOXIDE, "A3627.SR17.TITANIUM_DIOXIDE_COMPOSITE", CONFIRMED, "Sr. 17 special additives list")

    # Sr. No. 1: RUTILE. Glass-former lists (Silica, Borax, Phosphoric Acid, Arsenic Trioxide)
    # under HSN 3206 11xx / 2811 0000, and any HSN 3206 line that says RUTILE.
    if not other_than_rutile and not soda_ash:
        if glass_formers and (hsn.startswith(("32061190", "32061110", "28110000")) or "rutile" in desc):
            return A3627Classification(RUTILE, "A3627.SR01.RUTILE_GLASS_FORMERS", CONFIRMED, "glass formers list (Sr. 1)")
        if hsn.startswith("3206") and "rutile" in desc:
            return A3627Classification(RUTILE, "A3627.SR01.RUTILE_HSN_3206", CONFIRMED, "HSN 3206 with RUTILE")
    if hsn.startswith(("32061190", "32061110")) and not glass_formers and "rutile" not in desc and not titanium_dioxide and not composite:
        # HSN 32061110 is also Sr. 17 Titanium Dioxide, so HSN alone cannot decide.
        return A3627Classification(None, "A3627.SR01.RUTILE_HSN_ONLY", AMBIGUOUS, "rutile HSN without description")

    # Sr. No. 6: Aluminium Oxide, with Zinc Oxide and Zirconium Oxide kept as the requested class.
    oxide_names = ("aluminium oxide", "aluminum oxide", "zinc oxide", "zirconium oxide")
    if _has_any(desc, oxide_names):
        if "rutile" in desc:
            return A3627Classification(None, "A3627.SR06.ALUMINIUM_OXIDE", AMBIGUOUS, "oxide list also names RUTILE")
        return A3627Classification(ALUMINIUM_OXIDE, "A3627.SR06.ALUMINIUM_OXIDE", CONFIRMED, "Sr. 6 oxide list")
    if hsn in {"28182000", "28170010", "28256010"}:
        return A3627Classification(None, "A3627.SR06.ALUMINIUM_OXIDE_HSN_ONLY", AMBIGUOUS, "Sr. 6 HSN without description")

    # Sr. No. 11: Soda Ash (Modifiers list).
    if hsn == "28362010" or soda_ash or ("modifiers namely" in desc and "soda" in desc):
        return A3627Classification(SODA_ASH, "A3627.SR11.SODA_ASH", CONFIRMED, "Sr. 11 soda ash")

    # Aluminium foil (HSN 7607 or "7607" in the description) is never PP, matching the matcher.
    if hsn.startswith("7607") or "7607" in desc:
        return A3627Classification(ALUMINIUM_FOIL, "A3627.ALUMINIUM_FOIL_7607", CONFIRMED, "HSN or description 7607")

    # Standalone glass formers (not part of the Sr. 1 list).
    # "Silica (other than Fumed Silica)" is the approved item; only a plain fumed-silica line is excluded.
    if hsn.startswith("28110000") and "silica" in desc and ("fumed silica" not in desc or "other than fumed silica" in desc):
        return A3627Classification(SILICA, "A3627.GLASS_FORMER.SILICA", CONFIRMED, "silica other than fumed")
    if hsn.startswith("28401900") or "borax" in desc:
        return A3627Classification(BORAX, "A3627.GLASS_FORMER.BORAX", CONFIRMED, "borax")

    # Sr. No. 22: packing and board. The declared line HSN decides first; a composite line
    # that names other products is flagged (multi_product), not split, so its value is never duplicated.
    sub_products = [
        (PP_LAMINATED_BOARD, "pp laminated" in desc or (_has_word(desc, "laminated") and _has_word(desc, "pp"))),
        (BB_BOARD, "bb board" in desc),
        (KRAFT_LINER, "kraft liner" in desc),
        (WOODEN_SHEETS_PALLETS, hsn.startswith("4415") or "wooden" in desc or "pallet" in desc),
        # Chapter 48 (paper and board) is never PP by description, matching the approved PP rule.
        (PP, _has_word(desc, "pp") and not hsn.startswith("48")),
    ]
    if hsn in SR22_HSN_CATEGORY or hsn.startswith("4415"):
        category = SR22_HSN_CATEGORY.get(hsn, WOODEN_SHEETS_PALLETS)
        signals = {name for name, hit in sub_products if hit}
        return A3627Classification(category, f"A3627.SR22.HSN.{hsn or 'WOOD'}", CONFIRMED, "declared HSN", multi_product=len(signals) > 1)
    for name, hit in sub_products:
        if hit:
            rule = re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_")
            return A3627Classification(name, f"A3627.SR22.DESC.{rule}", CONFIRMED, "description")

    return A3627Classification(None, "A3627.UNMATCHED", UNMATCHED, "no A3627 rule")


def registry_version() -> str:
    """Fingerprint of the classification code. Changes whenever a rule or label changes.

    Report cache keys include it, so a cached pivot cannot outlive the rules that built it.
    """
    services = Path(__file__).resolve().parent
    digest = hashlib.sha256()
    for name in ("a3627_classifier.py", "product_classification.py"):
        digest.update((services / name).read_bytes())
    return digest.hexdigest()[:16]
