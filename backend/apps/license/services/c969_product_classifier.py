"""Product-name classification for SION norm C969 (automotive and engineering items).

The classifier is decided by the product name in an import item's description
only. ITC-HS codes are deliberately not consulted: the source product list
carries them for reference, and they never choose a classifier.

Each mapping names the source product, the ItemNameModel classifier it links to,
and the description condition that must hold. The classifier is the stored
ItemNameModel name for C969 (for example ``FRONT WHEELRIM``), so existing links
keep working; the source spelling is kept in ``product_name`` for reference.

Matching is deliberately narrow: an item gets a classifier only when exactly one
mapping's condition holds. Missing, unknown, or ambiguous names return ``None``,
which leaves the item unlinked as before.
"""
import re
from dataclasses import dataclass

C969_NORM = "C969"


@dataclass(frozen=True)
class C969ProductMapping:
    product_name: str
    classifier: str
    # Every pattern in ``requires`` must match the normalized description.
    requires: tuple[str, ...]
    # No pattern in ``excludes`` may match the normalized description.
    excludes: tuple[str, ...] = ()


C969_PRODUCT_NAME_MAPPINGS: tuple[C969ProductMapping, ...] = (
    C969ProductMapping("Air Filter", "AIR FILTER", (r"AIR\s*FILTER",)),
    C969ProductMapping(
        "Automotive Battery",
        "AUTOMOTIVE BATTERY",
        (r"(AUTO(MOTIVE|MATIVE)\s+BATTERY|BATTERY\s+AUTO(MOTIVE|MATIVE))",),
    ),
    C969ProductMapping(
        "Ball, Taper Roller, Needle Roller and Cylindrical Roller Bearings (excluding engine bearings)",
        "BEARING",
        (
            r"(BALL\s+BEARINGS?|TAPP?ER\s+(ROLLER\s+)?BEARINGS?|NEEDLE\s+ROLLER\s+BEARINGS?"
            r"|CYLIN[A-Z]*\s+(ROLLER\s+)?BEARINGS?)",
        ),
        # "Bearing (all types other than engine bearing)" is the standard wording
        # for the included types, so only a bare "engine bearing" excludes.
        (r"(?<!OTHER THAN )ENGINE\s+BEARINGS?",),
    ),
    C969ProductMapping("Brake Assembly (Prime and/or Secondary)", "BRAKE ASSEMBLY", (r"BRAKE\s+ASSEMBL(Y|IES)",)),
    C969ProductMapping("Clutch Assembly (including Split/Torque Type)", "CLUTCH ASSEMBLY", (r"CLUTCH\s+ASSEMBL(Y|IES)",)),
    C969ProductMapping("Internal Combustion Engine Complete", "INTERNAL COMBUSTION ENGINE", (r"INTERNAL\s+COMBUSTION\s+ENGINE",)),
    C969ProductMapping("Front Axle (2WD/4WD), Complete and/or Parts/Accessories", "FRONT AXLE", (r"FRONT\s*AXLE",)),
    C969ProductMapping("Fuel Filter", "FUEL FILTER", (r"FUEL\s*FILTER",)),
    C969ProductMapping("Hydraulic Pump (including Auxiliary Hydraulic Pump)", "HYDRAULIC PUMP", (r"HYDRAULIC\s+PUMP",)),
    C969ProductMapping("Hydraulic Cylinder", "HYDRAULIC CYLINDER", (r"HYDRAULIC\s+CYLINDER",)),
    C969ProductMapping("Hydraulic Valves", "HYDRAULIC VALVES", (r"HYDRAULIC\s+VALVES?",)),
    C969ProductMapping("Oil Pump", "OIL PUMP", (r"OIL\s+PUMP",)),
    C969ProductMapping("Radiator", "RADIATOR", (r"RADIATOR",)),
    C969ProductMapping("Seat Assembly", "SEAT ASSEMBLY", (r"SEAT\s+ASSEMBL(Y|IES)",)),
    C969ProductMapping("Alternator", "ALTERNATOR", (r"ALTERNATOR",)),
    C969ProductMapping("Starter Motor", "STARTER MOTOR", (r"STARTER\s+MOTOR",)),
    C969ProductMapping("Turbo Charger", "TURBO CHARGER", (r"TURBO\s*CHARGER",)),
    # "HANRNESS" is the spelling already stored on the classifier and used by
    # licence data; "HARNESS" is the source spelling.
    C969ProductMapping("Wiring Harness", "WIRING HANRNESS", (r"WIRING\s+(HARNESS|HANRNESS)",)),
    C969ProductMapping(
        "Alloy Steel Rods/Bars (carbon content less than 2%)",
        "ALLOY STEEL",
        (r"ALLOY\s+STEEL", r"(RODS?|BARS?)", r"CARBON\s+CONTENTS?\s+LESS\s+THAN\s+2(?!\s*\d)"),
    ),
    # Licence lines that name the product as "Relevant Alloy Steel Rods/Rounds/Billets"
    # (often with an ITC HS list) but state no carbon figure. They were linked to
    # ALLOY STEEL before this mapping existed, and removing that link would lose data.
    # A stated carbon figure other than 2% still excludes the line.
    C969ProductMapping(
        "Relevant Alloy Steel Rods/Rounds/Billets (no carbon figure stated)",
        "ALLOY STEEL",
        (r"ALLOY\s+STEEL", r"(RODS?|ROUNDS?|BILLETS?)"),
        (r"CARBON\s+CONTENTS?\s+LESS\s+THAN\s+(?!2(?!\s*\d))\d",),
    ),
    C969ProductMapping(
        "Cold Rolled Steel (Sheets/Wide Coils)",
        "COLD ROLLED STEEL",
        # "COLDS" is a spelling in the licence data, so it is accepted too.
        (r"COLDS?\s+ROLLED\s+STEEL", r"(SHEETS?|WIDE\s+COILS?)"),
    ),
    C969ProductMapping("Front Wheel Rim", "FRONT WHEELRIM", (r"FRONT\s*WHEEL\s*RIMS?",)),
    C969ProductMapping("Rear Wheel Rim", "REAR WHEELRIM", (r"REAR\s*WHEEL\s*RIMS?",)),
)

C969_CLASSIFIERS = frozenset(m.classifier for m in C969_PRODUCT_NAME_MAPPINGS)
# Classifiers in mapping order (source-list order), without repeats.
C969_CLASSIFIER_ORDER = tuple(dict.fromkeys(m.classifier for m in C969_PRODUCT_NAME_MAPPINGS))

_NON_ALNUM = re.compile(r"[^A-Z0-9%]+")


def normalize_c969_description(text: str | None) -> str:
    """Uppercase, fold punctuation to spaces, and collapse whitespace.

    Keeps ``%`` so "2%" stays distinguishable from a bare "2".
    """
    if not text:
        return ""
    return " ".join(_NON_ALNUM.sub(" ", text.upper()).split())


def _compile(pattern: str) -> re.Pattern:
    # Whole-word boundaries on letters only, so "ALTERNATOR1" still matches.
    return re.compile(rf"(?<![A-Z])(?:{pattern})(?![A-Z])")


_COMPILED = tuple(
    (
        mapping.classifier,
        tuple(_compile(p) for p in mapping.requires),
        tuple(_compile(p) for p in mapping.excludes),
    )
    for mapping in C969_PRODUCT_NAME_MAPPINGS
)


def classify_c969_product_name(description: str | None) -> str | None:
    """Return the C969 classifier for a product description, or ``None``.

    ``None`` means no mapping matched, or more than one classifier matched and
    the name is therefore ambiguous. Callers leave the item unlinked in both cases.
    """
    normalized = normalize_c969_description(description)
    if not normalized:
        return None

    matches = {
        classifier
        for classifier, requires, excludes in _COMPILED
        if all(p.search(normalized) for p in requires)
        and not any(p.search(normalized) for p in excludes)
    }
    if len(matches) != 1:
        return None
    return matches.pop()


# Product categories for the generic C969 rules that already exist outside the 22 names.
# Same names and text conditions as the linking rules in utils/item_matcher.py, so the pivot
# names these lines the way the linker already does. Each category lists alternatives; an
# alternative matches when all of its patterns match the normalized description.
C969_GENERIC_CATEGORIES: tuple[tuple[str, tuple[tuple[str, ...], ...]], ...] = (
    ("HOT ROLLED STEEL", ((r"HOT\s+ROLLED",), (r"NON\s+ALLOY",))),
    ("HYDROSTATIC TRANSMISSION", ((r"HYDROSTATIC", r"TRANSMISSION"),)),
    ("REARWHEEL TYRE", ((r"REAR\s*WHEEL\s*TYRE",),)),
    ("FRONTWHEEL TYRE", ((r"FRONT\s*WHEEL\s*TYRE",),)),
    ("WATER PUMP", ((r"WATER\s+PUMP",),)),
    ("AUXILIARY VALVES", ((r"AUXILIARY\s+VALVES",),)),
    ("FUEL INJECTION PUMP", ((r"FUEL\s+INJECTION\s+PUMP",),)),
    ("SYNCHROPACKS", ((r"SYNCHROPACKS",),)),
    ("'O' RING", ((r"O\s+RING",),)),
    ("SAFETY NEUTRAL SWITCH", ((r"SAFETY\s+NEUTRAL\s+SWITCH",),)),
    ("OIL SEPERATOR", ((r"OIL\s+SEPERATOR",),)),
    ("OIL SEAL", ((r"OIL\s+SEALS?",),)),
)
NO_DESCRIPTION = "NO DESCRIPTION"
UNRECOGNISED = "UNRECOGNISED (C969)"
def _compile_generic(pattern: str) -> re.Pattern:
    # The linking rules are substring matches, so only the leading boundary applies here.
    return re.compile(rf"(?<![A-Z]){pattern}")


_GENERIC_COMPILED = tuple(
    (name, tuple(tuple(_compile_generic(p) for p in alt) for alt in alternatives))
    for name, alternatives in C969_GENERIC_CATEGORIES
)
_NO_DESCRIPTION_TEXT = {"", "DELETED"}


def classify_c969_category(description: str | None) -> str:
    """Pivot category for a C969 line: product name first, then generic product, then a bucket.

    Never returns None. Blank or deleted lines go to NO DESCRIPTION; any other line that names no
    product goes to UNRECOGNISED (C969), so every C969 line lands in a named category.
    """
    name = classify_c969_product_name(description)
    if name:
        return name
    normalized = normalize_c969_description(description)
    if not normalized or normalized in _NO_DESCRIPTION_TEXT:
        return NO_DESCRIPTION
    for category, alternatives in _GENERIC_COMPILED:
        if any(all(p.search(normalized) for p in alt) for alt in alternatives):
            return category
    return UNRECOGNISED


C969_CATEGORY_ORDER = (
    C969_CLASSIFIER_ORDER
    + tuple(name for name, _ in C969_GENERIC_CATEGORIES)
    + (NO_DESCRIPTION, UNRECOGNISED)
)
