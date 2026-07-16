"""
DFIA (Duty Free Import Authorization) PDF text parser.

Targets the standard DGFT-issued DFIA licence PDF (Transferable DFIA).

Three ingestion paths, tried in order:
  1. Digital PDFs — text is extracted with pypdf.
  2. Scanned PDFs containing a DGFT verification QR code — the QR is decoded,
     the linked DGFT verification page is fetched, the "Download Document"
     link is followed, and the resulting digital PDF is re-parsed via path 1.
     This gives the most accurate data for scanned uploads.
  3. Scanned PDFs without a usable QR — text is recovered via OCR using
     pytesseract + pdf2image. Requires `tesseract` and `poppler` to be
     installed; if either is missing OCR is skipped and the parser degrades
     gracefully (cover-page metadata only).

Field regexes match both digital (English/Hindi bilingual) and OCR'd
(English-only with typical OCR confusions) layouts.
"""
from __future__ import annotations

import io
import re
from datetime import datetime
from typing import Any
from urllib.parse import urljoin

from pypdf import PdfReader

_MIN_TEXT_CHARS = 800  # below this we treat the PDF as scanned

# Hosts we will follow QR links to (defence in depth — we don't want a
# malicious uploaded PDF to coerce the server into making arbitrary outbound
# requests).
_DGFT_HOSTS = ("dgft.gov.in", "www.dgft.gov.in")
_DGFT_TIMEOUT = 30  # seconds for HTTP fetches


# ── Field-level regexes ───────────────────────────────────────────────
_LICENSE_NUMBER_RX = re.compile(
    r"Authorisation Number\s+(\d{8,12})\s+Date\s+(\d{1,2}[/-]\d{1,2}[/-]\d{4})",
)
_IMPORT_VALIDITY_RX = re.compile(r"Import Validity\s+(\d{1,2}[/-]\d{1,2}[/-]\d{4})")

# File Number — the value is an alphanumeric run, may have an OCR-inserted
# space (e.g. "0307627061 AM22" instead of "0307627061AM22") and an OCR-
# substituted "$" for "S" (e.g. "03A$07627061AM22").
_FILE_NUMBER_RX = re.compile(
    r"File Number[^\n]*?[\s|]+([0-9A-Z$]+(?:\s[0-9A-Z$]+)?)\b",
)

# IEC — bilingual digital form has it on the line after "IEC" label; OCR'd
# form may have the value either inline OR floating nearby because the
# "IEC" Hindi label gets garbled. Strategy: look for a 10-char PAN-like or
# all-digit token within a window around any occurrence of "IEC".
_IEC_RX = re.compile(r"IEC[^\n]*\n\s*([A-Z0-9]{10})\b")
_IEC_RX_INLINE = re.compile(r"IEC[\s|:.]+([A-Z0-9]{10})\b")
# Standalone IEC tokens — PAN format (5 letters + 4 digits + 1 letter) is
# very specific; we use this as a last-resort scan across the whole text.
_IEC_PAN_RX = re.compile(r"\b([A-Z]{5}\d{4}[A-Z])\b")

# Applicant Name — digital has bilingual label; OCR strips Hindi.
_NAME_RX_DIGITAL = re.compile(
    r"Name\s*/\s*आवेदक का नाम\s+([^\n]+?)\s*$", re.MULTILINE
)
_NAME_RX_OCR = re.compile(
    r"^Name[\s|:]+([A-Z][A-Z0-9 &.,'()\-]{3,80})\s*$", re.MULTILINE
)

_ADDRESS_RX = re.compile(
    r"Address of Applicant\s*/\s*पता\s+([^\n]+(?:\n(?!IEC|Exporter|Transferable|File)[^\n]+)*)",
)
_FOB_RX = re.compile(
    r"FOB Value \(In Rs\.\)[^\n]*?[\s|]+([\d.,]+)", re.MULTILINE
)
# CIF INR: digital form spans 3 lines with the value on its own line; OCR'd
# form is one line. Accept either, and also tolerate the OCR confusion
# "CIP"↔"CIF".
_CIF_INR_RX_DIGITAL = re.compile(
    r"CI[FP] in Rs[.,] with Late Fee Imposed[^\n]*\n[^\n]*\n\s*([\d.,]+)\s*$",
    re.MULTILINE,
)
_CIF_INR_RX_OCR = re.compile(
    r"CI[FP] in Rs[.,] with Late Fee Imposed[^\n]*?[\s|]+([\d.,]+)",
    re.MULTILINE,
)
# CIF FC: OCR may say "CHE in FFI" / "CIF in FFC" — accept variants.
_CIF_FC_RX = re.compile(
    r"(?:CIF|CHE|CIE)\s+in\s+FF[ECILT][^\n]*?[\s|]+([\d.,]+)",
    re.MULTILINE,
)
# Port code — digital "INNSA1", OCR sometimes "INNSAI" (capital I) or "INNSAL".
_PORT_RX = re.compile(r"Port of Registration[^\n]*?\s+(IN[A-Z0-9][A-Z0-9I]{2,4})\b")
# Notification — OCR may read "Notilication"; accept any letters between "Noti"
# and "Number". Value may be on the same line after "&" or on the next line.
# Accept 2- or 3-digit prefixes (digital uses 3, scanned older licences use 2).
_NOTIFICATION_RX = re.compile(
    r"Custom\s+Noti[a-z]+\s+Number[^\n]*?(?:&[^\n]*?)?(\d{2,3}/\d{4})\s*&",
)
_NOTIFICATION_RX_MULTILINE = re.compile(
    # The 2025 DGFT layout wraps the bilingual label onto two lines so the
    # value lands ≥2 lines below "Custom Notification Number":
    #     Custom Notification Number / ... एवं ितिथ &
    #     Date
    #     025/2023 & Dated 01.04.2023
    # Allow an optional "Date" continuation line between label and value.
    r"Custom\s+Noti[a-z]+\s+Number[^\n]*\n(?:\s*Date[^\n]*\n)?\s*(\d{2,3}/\d{4})",
)
_VALIDITY_MONTHS_RX = re.compile(
    r"Validity of Authorisation\s*/\s*Scrip for Import.*?\n\s*(\d{1,3})\s*$",
    re.DOTALL,
)

# ── Items-table regexes ───────────────────────────────────────────────
# 2025 template — row data spans two lines:
#   line N   : "<HSN> <qty> <UOM>"
#   line N+1 : "(<short>) <CIF-INR> <CIF-FC>"
_DATA_LINE_RX = re.compile(
    r"^\s*(?P<hsn>\d{8})\s+(?P<qty>[\d,]+\.?\d*)\s+(?P<uom>[A-Z][A-Z ()/]+?)\s*$"
)
_CIF_LINE_RX = re.compile(
    r"^\s*(?:\([A-Z]{2,5}\)\s+)?"
    r"(?P<cif_inr>[\d,]+\.\d{2})\s+"
    r"(?P<cif_fc>[\d,]+\.\d{2})\s*$"
)
# 2021 template — same data on a single line, with the bracketed short-unit
# code inline:
#   "<HSN> <qty> <UOM-WORD> (<short>) <CIF-INR> <CIF-FC>"
_DATA_LINE_SINGLELINE_RX = re.compile(
    r"^\s*(?P<hsn>\d{7,8})\s+(?P<qty>[\d,]+\.?\d*)\s+"
    r"(?P<uom>[A-Z]+(?:\s\([A-Z]+\))?)\s+"
    r"(?P<cif_inr>[\d,]+\.\d{2})\s+"
    r"(?P<cif_fc>[\d,]+\.\d{2})\s*$"
)
_DESC_TAIL_RX = re.compile(r"\d{8}(?P<si>\d{1,2})\s*$")
_DESC_TAIL_FALLBACK_RX = re.compile(r"(?P<si>\d{1,2})\s*$")
_GROUP_HEADER_RX = re.compile(
    r"^(Glass Formers|Intermediates|Modifiers|Other Special Additives|"
    r"Packing Material|Import Item Name|Total)\b",
)
# Table-header artifacts: the DGFT items column header wraps across 2-3 lines
# (e.g. "ITCHS Code Quantity to be\nimported UOM CIF(in INR) CIF(in FCC)").
# We must stop the description walker at any line containing one of these
# header tokens so they don't leak into the captured description.
_TABLE_HEADER_LINE_RX = re.compile(
    r"\bCIF\(in\b|\bUOM\b|\bITCHS\b|Quantity to be|Technical Features"
)
# Continuation-end punctuation. A description line that ends with one of
# these wraps into the line below.
_CONTINUATION_END_RX = re.compile(r"[,:;\-]$|\([A-Za-z]\)$")


def _wraps_into_next(line: str) -> bool:
    """True if this PDF-extracted line continues into the line below it.

    Indicators (any of):
      • trailing space (pypdf preserves the soft-wrap space from the PDF)
      • trailing continuation punctuation: comma, semicolon, colon, dash
      • trailing "(<letter>)" marker (multi-item lists)
    """
    if not line:
        return False
    if line.endswith(" "):
        return True
    return bool(_CONTINUATION_END_RX.search(line))

# ── OCR normalization map (common tesseract misreads on DGFT layouts) ──
_OCR_FIXUPS = [
    (re.compile(r"\bINNSAI\b"), "INNSA1"),
    (re.compile(r"\bNotilication\b"), "Notification"),
    (re.compile(r"\bCIP in Rs"), "CIF in Rs"),
    (re.compile(r"\bCHE in FF[IL]\b"), "CIF in FFE"),
    (re.compile(r"\bFFL\b"), "FFE"),
]
# File-number internal cleanup: drop spaces, restore "$" → "S" (OCR confuses
# them in the alphanumeric serial like "03A$07627061AM22" → "03AS07627061AM22").
def _clean_file_number(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = re.sub(r"\s+", "", value).replace("$", "S")
    # File numbers are 12–20 alphanumeric chars in practice.
    if 10 <= len(cleaned) <= 30 and cleaned.isalnum():
        return cleaned
    return cleaned or None


def _strip_lakh(value: str | None) -> str | None:
    if not value:
        return value
    return value.replace(",", "").strip()


def _to_iso_date(value: str | None) -> str | None:
    if not value:
        return None
    for fmt in ("%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date().isoformat()
        except ValueError:
            continue
    return None


# ── Condition sheet patterns ──────────────────────────────────────────
# Per-item conditions that appear in the CONDITION SHEET section, e.g.:
#   "Input item sl.No.2, 3 and 4 are subjected to actual user condition."
#   "Cif value of input item sl.no.5 shall not exceed 5% of total CIF value"
# `S.No.`, `Sl.No.`, `Sr.No.`, `Sl.No-3`, `sl.no` — DGFT uses several variants.
# The `[.\s-]*` between "No" and the digit also accepts the hyphen form
# "Sl.No-3" / "Sl.No.-4" seen in newer licences (e.g. 0311044762).
# The trailing `s?` accepts the plural "Nos" form used in some PDFs:
#   "Input item Sl. Nos 2, 3 and 4 are subjected to actual user condition"
_SLNO_PREFIX = r"(?:S|Sl|Sr|S\.\s*L)\.?\s*[Nn]os?[.\s-]*"

_AU_CONDITION_RX = re.compile(
    r"(?:input\s+)?item[s]?\s+" + _SLNO_PREFIX +
    r"((?:\d+\s*(?:,|and|&)?\s*)+)"   # GREEDY digit list so "2, 3 and 4" all captured
    r"\s*(?:\(([^)]+)\))?"            # optional parenthetical with item-name list
    r"(?:\s*\([^)]*\))?\s*together\s*"  # optional "(...) together"
    r"\s*(?:are|is)\s+subjected\s+to\s+actual\s+user",
    re.IGNORECASE,
)
# Looser AU fallback for the common form without the "together" / parens.
_AU_CONDITION_RX_SIMPLE = re.compile(
    r"(?:input\s+)?item[s]?\s+" + _SLNO_PREFIX +
    r"((?:\d+\s*(?:,|and|&)?\s*)+)"
    r"\s+(?:are|is)\s+subjected\s+to\s+actual\s+user",
    re.IGNORECASE,
)
_PCT_CONDITION_RX = re.compile(
    r"(?:cif\s+value\s+of\s+)?input\s+item[s]?\s+" + _SLNO_PREFIX +
    r"(\d+)"
    r"\s*(?:\(([^)]+)\))?"        # optional parenthetical with item-name list
    r"[^.%]*?"                    # allow "(...) together" / extra phrasing
    r"shall\s+not\s+exceed\s+(\d+)\s*%",
    re.IGNORECASE | re.DOTALL,
)

# Newer DFIA condition style — references items by NAME rather than sl.No.
# Observed variants (the format evolved across DGFT RA offices):
#
# AU variants:
#   "IMPORT ITEM Liquid Glucose, Milk & Milk Products IS SUBJECT TO ACTUAL USER CONDITION"
#   "Note5: IMPORT ITEM Liquid Glucose, Milk and Milk Products, Fruit Juice and
#    Citric Acid, IS SUBJECT TO ACTUAL USER CONDITION ."  ← comma before IS
#
# PCT variants:
#   "FOR IMPORT ITEM Essential oils, Food Colours THE CIF VALUE SHALL NOT EXCEED 5%"
#   "FOR IMPORT ITEM Binder / Thickeners / Starch CIF value shall not exceed 3%"
#   "CIF value of input item FOR IMPORT ITEM Essential oils ... shall not exceed 5%"
#
# The non-DOTALL `.+?` keeps each match bounded to ONE condition clause —
# the negative lookahead at each step is a safety net.
_NAMED_STOP = r"(?!IMPORT\s+ITEM)(?!ACTUAL\s+USER)(?!CIF\s+VALUE)"
_AU_NAMED_RX = re.compile(
    # Allow an optional comma (", IS" as in newer PDFs) before IS/ARE.
    rf"IMPORT\s+ITEM\s+((?:{_NAMED_STOP}.){{1,300}}?)\s*,?\s*(?:IS|ARE)\s+SUBJECT\s+TO\s+ACTUAL\s+USER",
    re.IGNORECASE | re.DOTALL,
)
_PCT_NAMED_RX = re.compile(
    # Three trailing forms all handled by making "THE CIF value" optional:
    #   "THE CIF VALUE SHALL NOT EXCEED N%"  (original)
    #   "CIF value shall not exceed N%"      (without THE, _NAMED_STOP stops before CIF)
    #   "shall not exceed N%"                (no CIF qualifier at all)
    rf"(?:FOR\s+)?IMPORT\s+ITEM\s+((?:{_NAMED_STOP}.){{1,300}}?)"
    rf"\s*(?:(?:THE\s+)?CIF\s+value\s+)?shall\s+not\s+exceed\s+(\d+)\s*%",
    re.IGNORECASE | re.DOTALL,
)


def _extract_condition_sheet(text: str) -> str | None:
    """Slice out the CONDITION SHEET section and strip repeated page footers.

    DGFT PDFs repeat a footer at the bottom of every page that includes
    "Authorisation Number ... Date ...", "UDIN...", "This document has been
    digitally signed ..." and sometimes "Signature Not Verified". Without
    pre-stripping these from the full text, the condition section gets
    truncated at the first per-page footer rather than at the end-of-doc note.
    """
    # ── 1) Pre-strip the per-page footer fragments everywhere in the text.
    cleaned = re.sub(
        r"Authorisation Number\s+\d+\s+Date\s+\d{1,2}/\d{1,2}/\d{4}\s*", "", text
    )
    cleaned = re.sub(r"Import Validity\s+\d{1,2}/\d{1,2}/\d{4}\s*", "", cleaned)
    cleaned = re.sub(r"UDIN\w+\s*", "", cleaned)
    cleaned = re.sub(r"This document has been digitally signed[^\n]*", "", cleaned)
    # Multi-line "Digitally Signed.\nName: ...\nDate: ...\nReason: ...\nLocation: ..."
    cleaned = re.sub(
        r"Digitally Signed\.\s*\n"
        r"(?:Name:[^\n]*\n)?"
        r"(?:Date:[^\n]*\n)?"
        r"(?:Reason:[^\n]*\n)?"
        r"(?:[^\n]*@[^\n]*\n)?"      # e.g. an email address line
        r"(?:Location:[^\n]*\n)?",
        "",
        cleaned,
    )
    # Bare standalone markers that appear in page footers.
    cleaned = re.sub(r"^\s*Signature Not Verified\s*$", "", cleaned, flags=re.MULTILINE)

    # ── 2) Now find the CONDITION SHEET section.
    start = cleaned.find("CONDITION SHEET")
    if start < 0:
        return None
    rest = cleaned[start:]

    # Use only the genuine end-of-document marker. "Signature Not Verified"
    # is not a reliable end marker because it can also appear in page footers.
    end = len(rest)
    m = re.search(r"Note:\s+If\s+digitally\s+signed", rest)
    if m:
        end = m.start()

    block = rest[:end]
    block = re.sub(r"\n\s*\n+", "\n\n", block)
    return block.strip() or None


def _split_named_items(blob: str) -> list[str]:
    """Split a "IMPORT ITEM <list>" clause into individual lookup tokens.

    The list uses commas and " or " as separators. Forward slashes in names
    (e.g. "Milk & Milk Products / Milk Solids", "Binder / Thickners") are
    ALSO treated as alternatives — both halves count as match tokens — so
    the matcher can find the item under either phrasing.
    """
    if not blob:
        return []
    # Strip trailing fluff like ", " or final words like "CONDITION" that
    # sometimes get eaten by the non-greedy regex.
    cleaned = re.sub(r"\s+", " ", blob).strip().strip(",.;")
    parts: list[str] = []
    for chunk in re.split(r",|\s+or\s+|\s*/\s*", cleaned, flags=re.IGNORECASE):
        token = chunk.strip(" ,.;\t").strip()
        if len(token) >= 3:
            parts.append(token)
    return parts


# When a captured name matches one of `trigger_tokens`, items whose
# description contains any of `excluder_phrases` are SKIPPED — they don't
# fit the restriction even if a substring matches. Covers user-flagged
# cases:
#   • E5 licence: "Cocoa Paste" in an Edible-Oil item is NOT a Cocoa Powder
#     restriction match.
#   • E132 licence: "Cheese" in an Edible-Oil item doesn't pick up the 3%.
_MATCH_EXCEPTIONS: list[tuple[set[str], list[str]]] = [
    ({"coco", "cocoa"},
     ["edible oil", "vegetable oil", "palmolein", "palm kernel", "cocoa paste"]),
    ({"cheese"},
     ["edible oil", "vegetable oil", "palmolein", "palm kernel"]),
]


def _is_exempt_match(name: str, description_lower: str) -> bool:
    """True when (captured name, item description) hits an exception rule."""
    n = name.lower()
    for trigger_tokens, excluder_phrases in _MATCH_EXCEPTIONS:
        if any(tok in n for tok in trigger_tokens):
            if any(p in description_lower for p in excluder_phrases):
                return True
    return False


# Synonym groups — each set contains terms that should be treated as
# equivalent during licence-condition matching. Add common DGFT shorthand
# spellings here; the matcher tries every alias of each captured name.
_NAME_SYNONYMS: list[set[str]] = [
    {"coco powder", "cocoa powder", "cocoa", "coco"},
    {"thickners", "thickeners", "thickner", "thickener"},
    {"binder", "binders"},
    {"flavours", "flavors", "flavouring", "flavoring"},
    {"colours", "colors"},
    {"milk solids", "milk solid", "milk & milk products", "milk products"},
    {"fruit juice", "fruit / juice", "fruit juices", "juice"},
    {"essential oils", "essential oil"},
    {"food colours", "food colour", "food color", "food colors"},
    {"food flavours", "food flavour", "food flavor", "food flavors"},
    {"liquid glucose", "glucose"},
    # Note: don't synonymise "Citric Acid" with "Anti Oxidant" — they often
    # appear as DIFFERENT items in the same licence (Citric Acid as
    # acidulant vs Anti Oxidant which may also be Citric Acid). Match each
    # term individually.
    {"anti oxidant", "antioxidant"},
    {"emulsifier", "emulsifiers", "stabilizer", "stabiliser"},
    {"dietary fibre", "dietary fiber"},
    {"cane sugar", "refined cane sugar", "sugar"},
]


def _expand_synonyms(name: str) -> list[str]:
    """Return all synonym aliases for a captured name (incl. the name itself)."""
    n = name.lower().strip()
    aliases = {n}
    for group in _NAME_SYNONYMS:
        if any(term in n for term in group):
            aliases |= group
    return list(aliases)


def _resolve_named_items(names: list[str], items: list[dict[str, Any]]) -> list[int]:
    """Match name tokens against item descriptions.

    Three-pass match per (name, synonym alias):
      1) Case-insensitive substring of the alias.
      2) Word-set: all significant words from the alias appear in the
         description (handles "Food Flavours" vs "Food Grade Flavours").
      3) Synonym groups (e.g. "Coco Powder" ⇔ "Cocoa Powder", "Thickners" ⇔
         "Thickeners") — extends to spelling variants DGFT licences commonly use.

    Returns the SORTED list of serial_numbers of matched items.
    """
    def _norm_words(s: str) -> set[str]:
        return {w for w in re.sub(r"[^\w\s]", " ", s.lower()).split() if len(w) > 2}

    matched: set[int] = set()
    normalised_items = [
        (
            it.get("serial_number"),
            (it.get("description") or "").lower(),
            _norm_words(it.get("description") or ""),
        )
        for it in items
        if it.get("serial_number") is not None
    ]
    for name in names:
        for alias in _expand_synonyms(name):
            needle = alias.lower().strip()
            if not needle:
                continue
            alias_words = _norm_words(alias)
            for sn, desc_lower, desc_words in normalised_items:
                # Skip if the captured name + this item hit an exception rule
                # (e.g. "Coco" / "Cocoa" tokens shouldn't restrict an item
                # that is dominated by Edible Oil ingredients).
                if _is_exempt_match(name, desc_lower):
                    continue
                if needle in desc_lower:
                    matched.add(sn)
                    continue
                if alias_words and alias_words.issubset(desc_words):
                    matched.add(sn)
    return sorted(matched)


def _parse_item_conditions(
    condition_text: str | None,
    items: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Detect per-item conditions from the condition-sheet text.

    Returns a list like:
        [{"serial_numbers": [2, 3, 4], "type": "AU"},
         {"serial_numbers": [5],       "type": "5%"}, ...]

    Supports two licence-condition formats:
      • Sl. No. based:    "Input item sl.No.2, 3 ... AU"
      • Item-name based:  "IMPORT ITEM Liquid Glucose, ... IS ... AU"
    For the name-based form, the captured names are matched (case-insensitive
    substring) against the parsed item descriptions in ``items`` to resolve
    them to serial numbers.
    """
    if not condition_text:
        return []
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, tuple[int, ...]]] = set()

    def _emit(serials: list[int], cond_type: str) -> None:
        if not serials:
            return
        key = (cond_type, tuple(sorted(set(serials))))
        if key in seen:
            return
        seen.add(key)
        out.append({"serial_numbers": sorted(set(serials)), "type": cond_type})

    # ── Sl. No. based (with optional parenthetical name-list fallback) ──
    seen_au_spans: set[int] = set()
    for m in _AU_CONDITION_RX.finditer(condition_text):
        seen_au_spans.add(m.start())
        nums = [int(n) for n in re.findall(r"\d+", m.group(1) or "")]
        # Some DFIA layouts reference a PARENT SION sl.no. (e.g. S.No.4)
        # whose actual item rows are numbered separately; in those cases
        # the matched SI# may not exist in `items` at all. Fall back to
        # resolving the parenthetical name list.
        item_sns = {i.get("serial_number") for i in (items or [])}
        if nums and items and not any(n in item_sns for n in nums) and m.group(2):
            names = _split_named_items(m.group(2))
            _emit(_resolve_named_items(names, items), "AU")
        else:
            _emit(nums, "AU")
    # Looser fallback for plain "Sl.No.2, 3 and 4 are subjected to AU" form.
    for m in _AU_CONDITION_RX_SIMPLE.finditer(condition_text):
        if m.start() in seen_au_spans:
            continue
        nums = [int(n) for n in re.findall(r"\d+", m.group(1) or "")]
        _emit(nums, "AU")

    for m in _PCT_CONDITION_RX.finditer(condition_text):
        # groups: 1=sl.no., 2=parenthetical names (or None), 3=pct
        sn = int(m.group(1))
        pct = m.group(3)
        item_sns = {i.get("serial_number") for i in (items or [])}
        if items and sn not in item_sns and m.group(2):
            names = _split_named_items(m.group(2))
            _emit(_resolve_named_items(names, items), f"{pct}%")
        else:
            _emit([sn], f"{pct}%")

    # ── Item-name based (newer DFIA wording) ─────────────────────
    if items:
        for m in _AU_NAMED_RX.finditer(condition_text):
            names = _split_named_items(m.group(1))
            _emit(_resolve_named_items(names, items), "AU")
        for m in _PCT_NAMED_RX.finditer(condition_text):
            names = _split_named_items(m.group(1))
            _emit(_resolve_named_items(names, items), f"{m.group(2)}%")

    return out


def _normalize(text: str) -> str:
    """Fix common OCR misreads so downstream regexes can match cleanly.

    Replaces pipe characters (which OCR uses as label/value separators on
    table-style layouts) with spaces, then applies a small list of known
    word-level fixups for DGFT layouts.
    """
    text = text.replace("|", " ")
    for rx, repl in _OCR_FIXUPS:
        text = rx.sub(repl, text)
    return text


def _find_iec_near_label(text: str) -> str | None:
    """OCR may scramble the IEC label area. Search for a PAN-format IEC token
    anywhere in the text, then within a 200-char window of any "IEC" mention.
    """
    if m := _IEC_RX.search(text):
        return m.group(1)
    if m := _IEC_RX_INLINE.search(text):
        return m.group(1)
    # PAN-format scan is the strongest signal — only one such token usually
    # appears in a DFIA licence.
    matches = _IEC_PAN_RX.findall(text)
    if matches:
        return matches[0]
    return None


def _read_bytes(source) -> bytes:
    if isinstance(source, (bytes, bytearray)):
        return bytes(source)
    if hasattr(source, "read"):
        try:
            source.seek(0)
        except Exception:
            pass
        data = source.read()
        try:
            source.seek(0)
        except Exception:
            pass
        return data
    with open(source, "rb") as f:
        return f.read()


def _digital_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join((p.extract_text() or "") for p in reader.pages)


def _ocr_text(pdf_bytes: bytes) -> str:
    """OCR fallback for scanned PDFs. Returns empty string if OCR tools missing."""
    try:
        from pdf2image import convert_from_bytes
        import pytesseract
    except ImportError:
        return ""
    try:
        images = convert_from_bytes(pdf_bytes, dpi=300)
    except Exception:
        return ""
    parts = []
    for img in images:
        try:
            parts.append(pytesseract.image_to_string(img, lang="eng"))
        except Exception:
            continue
    return "\n".join(parts)


def _decode_qr_urls(pdf_bytes: bytes) -> list[str]:
    """Scan PDF pages for QR codes and return any decoded URLs.

    Returns an empty list if pyzbar/pdf2image aren't installed or no QR is
    found. Scanning is best-effort and never raises.
    """
    try:
        from pdf2image import convert_from_bytes
        from pyzbar.pyzbar import decode as zbar_decode
    except ImportError:
        return []
    urls: list[str] = []
    try:
        images = convert_from_bytes(pdf_bytes, dpi=300)
    except Exception:
        return []
    for img in images:
        try:
            for code in zbar_decode(img):
                data = (code.data or b"").decode(errors="replace").strip()
                if data.startswith("http://") or data.startswith("https://"):
                    urls.append(data)
        except Exception:
            continue
    return urls


def _fetch_dgft_pdf_from_qr(qr_url: str) -> bytes | None:
    """Follow a DGFT verification-page QR URL to download the underlying PDF.

    Returns PDF bytes on success, None otherwise. Restricted to DGFT hosts.
    """
    try:
        import requests
        from urllib.parse import urlparse
    except ImportError:
        return None
    if urlparse(qr_url).hostname not in _DGFT_HOSTS:
        return None
    try:
        session = requests.Session()
        page = session.get(qr_url, timeout=_DGFT_TIMEOUT, allow_redirects=True)
        if page.status_code != 200:
            return None
        # The verification page contains a download link of the form
        #   href="downloadfileservlet/download?isDownload=true&UDIN=..."
        # Pull it out and resolve relative to the page URL.
        m = re.search(
            r'href="([^"]*downloadfileservlet/download\?isDownload=true&[^"]+)"',
            page.text,
        )
        if not m:
            return None
        download_url = urljoin(page.url, m.group(1))
        if urlparse(download_url).hostname not in _DGFT_HOSTS:
            return None
        resp = session.get(download_url, timeout=_DGFT_TIMEOUT, allow_redirects=True)
        if resp.status_code != 200 or not resp.content.startswith(b"%PDF"):
            return None
        return resp.content
    except Exception:
        return None


def _full_text(source) -> tuple[str, str]:
    """Return (text, source_kind). source_kind is one of:
        - "digital"   : text came from pypdf directly
        - "dgft_qr"   : QR was decoded, digital PDF downloaded from DGFT, text from pypdf
        - "ocr"       : neither QR nor digital text worked — OCR fallback used
        - "empty"     : nothing usable
    """
    pdf_bytes = _read_bytes(source)
    text = _digital_text(pdf_bytes)
    if len(text.strip()) >= _MIN_TEXT_CHARS:
        return text, "digital"

    # Scanned upload — try the DGFT QR fast-path first because it yields
    # an authoritative digital PDF.
    for url in _decode_qr_urls(pdf_bytes):
        downloaded = _fetch_dgft_pdf_from_qr(url)
        if not downloaded:
            continue
        dgft_text = _digital_text(downloaded)
        if len(dgft_text.strip()) >= _MIN_TEXT_CHARS:
            return dgft_text, "dgft_qr"

    # OCR fallback — useful only for the header fields. The items table
    # rarely OCRs cleanly enough to parse.
    ocr = _ocr_text(pdf_bytes)
    if len(ocr.strip()) > len(text.strip()):
        return ocr, "ocr"
    return text, "empty" if not text.strip() else "digital"


def _parse_items(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_si: set[int] = set()

    block_start = text.find("Import Item Name")
    if block_start < 0:
        return rows
    block_end = text.find("Name and Address of the Supporting Manufacturer", block_start)
    block = text[block_start:block_end] if block_end > 0 else text[block_start:]

    # Strip per-page footer / header artifacts that sit between rows when an
    # item spans a page break (e.g. row 12's description is on page 2 but its
    # HSN/qty data line lands on page 3 after these markers). Replacing each
    # with an empty string lets the description walker pass over the page
    # boundary and pick up the real description and SI# above.
    block = re.sub(
        r"Authorisation Number\s+\d+\s+Date\s+\d{1,2}[/-]\d{1,2}[/-]\d{4}\s*",
        "", block,
    )
    block = re.sub(
        r"Import Validity\s+\d{1,2}[/-]\d{1,2}[/-]\d{4}\s*",
        "", block,
    )
    block = re.sub(
        r"This document has been digitally signed by[^\n]*",
        "", block,
    )
    block = re.sub(r"UDIN\s*\S+", "", block)
    # Multi-line digital-signing block and the bare "Signature Not Verified"
    # marker land between items when the items table spans a page boundary.
    # Clear them so the page-number heuristic below can recognise a real
    # page break (blank space above the digit).
    block = re.sub(
        r"Digitally Signed\.\s*\n"
        r"(?:Name:[^\n]*\n)?"
        r"(?:[^\n]*\n)?"
        r"(?:Date:[^\n]*\n)?"
        r"(?:Reason:[^\n]*\n)?"
        r"(?:[^\n]*@[^\n]*\n)?"
        r"(?:Location:[^\n]*\n)?",
        "",
        block,
    )
    block = re.sub(r"(?m)^\s*Signature Not Verified\s*$", "", block)
    # Page numbers — strip a standalone short-digit line ONLY when it sits in
    # whitespace (i.e., a page-break signature: the line immediately above is
    # empty after the cleanups above). Real SI numbers in the items table are
    # preceded by description TEXT, so this rule keeps them.
    block = re.sub(
        r"(?m)^[ \t]*\n[ \t]*\d{1,3}[ \t]*\n(?=\s*\n*\s*\d{7,8}\s+\d+(?:\.\d+)?\s)",
        "\n",
        block,
    )

    # 2025 templates use "namely," group headers; we'll include such a line
    # even if its trailing characters don't otherwise look like a wrap.
    multi_line_descriptions = "namely," in block

    lines = block.splitlines()
    i = 0
    while i < len(lines):
        # 2021 single-line variant first (matches the same anchor as the
        # 2-line variant — try the more specific one first).
        m_single = _DATA_LINE_SINGLELINE_RX.match(lines[i])
        if m_single:
            hsn = m_single.group("hsn")
            qty = m_single.group("qty")
            uom = m_single.group("uom")
            cif_inr = m_single.group("cif_inr")
            cif_fc = m_single.group("cif_fc")
            consumed = 1
        else:
            m_data = _DATA_LINE_RX.match(lines[i])
            if not m_data:
                i += 1
                continue
            m_cif = _CIF_LINE_RX.match(lines[i + 1]) if i + 1 < len(lines) else None
            if not m_cif:
                i += 1
                continue
            hsn = m_data.group("hsn")
            qty = m_data.group("qty")
            uom = m_data.group("uom")
            cif_inr = m_cif.group("cif_inr")
            cif_fc = m_cif.group("cif_fc")
            consumed = 2

        # Walk backwards from the data row, collecting the description block.
        # A line is part of the description if it wraps into the line just
        # below it (trailing space / continuation punctuation), or if it's a
        # 2025-style "<Category> namely,"-type group header sitting on top of
        # the description.
        #
        # Lines belonging to the LEFT column (item-name / SION category) do
        # NOT wrap into the right column (technical description) — the
        # extracted text shows a clean break between them — so the walker
        # stops there naturally.
        si = None
        desc_lines: list[str] = []
        j = i - 1
        while j >= 0:
            raw = lines[j]
            if not raw.strip():
                j -= 1
                continue
            stripped = raw.rstrip()
            if (_CIF_LINE_RX.match(stripped) or _DATA_LINE_RX.match(stripped)
                    or _DATA_LINE_SINGLELINE_RX.match(stripped)):
                break
            if stripped.startswith("Import Item Name") or _TABLE_HEADER_LINE_RX.search(stripped):
                break

            # SI# capture — strip the trailing digits but keep any earlier
            # trailing-space marker on the remaining text.
            line_for_storage = raw
            if si is None:
                tail = _DESC_TAIL_RX.search(stripped) or _DESC_TAIL_FALLBACK_RX.search(stripped)
                if tail:
                    si = int(tail.group("si"))
                    # Drop the SI# digits AND any trailing whitespace after.
                    cut = tail.start("si")
                    line_for_storage = stripped[:cut].rstrip()

            # First substantive line we encounter is the natural end of the
            # description. Edge case: if the SI# was on a line of its own,
            # `line_for_storage` is empty — skip it and let the next iteration
            # treat the line above as the first content line.
            if not desc_lines:
                if line_for_storage.strip():
                    desc_lines.append(line_for_storage)
                j -= 1
                continue

            # For each line above the first captured, include it ONLY if its
            # raw form wraps into the line below (trailing space, continuation
            # punctuation), or it's a 2025-style group-header line.
            if _wraps_into_next(raw):
                desc_lines.append(line_for_storage)
                j -= 1
                continue

            if multi_line_descriptions and _GROUP_HEADER_RX.match(stripped):
                desc_lines.append(line_for_storage)
                break

            break

        if si is None or si in seen_si:
            i += consumed
            continue
        seen_si.add(si)

        description = re.sub(r"\s+", " ", " ".join(reversed(desc_lines))).strip()
        # Pad 7-digit HSNs to the canonical 8-digit form (some older DGFT
        # templates drop the leading zero).
        if hsn and len(hsn) == 7 and hsn.isdigit():
            hsn = "0" + hsn
        rows.append({
            "serial_number": si,
            "hsn": hsn,
            "quantity": _strip_lakh(qty),
            "uom": uom.strip(),
            "cif_inr": _strip_lakh(cif_inr),
            "cif_fc": _strip_lakh(cif_fc),
            "description": description,
        })
        i += consumed

    rows.sort(key=lambda r: r["serial_number"])
    return rows


def parse_dfia_pdf(source) -> dict[str, Any]:
    """
    Parse a DFIA licence PDF into a flat dict of extracted fields plus an
    `items` list. Dates are converted to ISO YYYY-MM-DD.

    Returns a `source_kind` field describing where the text came from:
        - "digital"  — text extracted directly from the uploaded PDF
        - "dgft_qr"  — QR code on uploaded scan was followed to DGFT and
                       the authoritative digital PDF was downloaded
        - "ocr"      — OCR fallback (items table likely empty)
        - "empty"    — no usable text found
    Also exposes `is_ocr` for backward compatibility.
    """
    raw_text, source_kind = _full_text(source)
    text = _normalize(raw_text)
    used_ocr = source_kind == "ocr"

    license_number = license_date = None
    if m := _LICENSE_NUMBER_RX.search(text):
        license_number = m.group(1).strip()
        license_date = _to_iso_date(m.group(2))

    expiry = None
    if m := _IMPORT_VALIDITY_RX.search(text):
        expiry = _to_iso_date(m.group(1))

    def _first(rx: re.Pattern[str]) -> str | None:
        if m := rx.search(text):
            return m.group(1).strip()
        return None

    # Name — try bilingual digital pattern first, fall back to OCR-style.
    company_name = _first(_NAME_RX_DIGITAL) or _first(_NAME_RX_OCR)

    # IEC — digital on next line, OCR inline, or scan for PAN-format token.
    iec = _find_iec_near_label(text)

    # CIF INR — try 3-line digital then 1-line OCR variant.
    cif_inr = _first(_CIF_INR_RX_DIGITAL) or _first(_CIF_INR_RX_OCR)

    # Notification — strict variant first (with closing &), then multi-line.
    # DGFT shorthand sometimes drops the leading zero (e.g. "19/2015"); pad
    # to the 3-digit form used in NOTIFICATION_NORM_CHOICES.
    notification = _first(_NOTIFICATION_RX) or _first(_NOTIFICATION_RX_MULTILINE)
    if notification and re.fullmatch(r"\d{2}/\d{4}", notification):
        notification = "0" + notification

    # File number — strip OCR-inserted whitespace and restore "$" → "S".
    file_number = _clean_file_number(_first(_FILE_NUMBER_RX))

    # Items table only works on digital PDFs — OCR'd tables are too lossy.
    items = [] if used_ocr else _parse_items(text)

    condition_sheet = _extract_condition_sheet(text)
    item_conditions = _parse_item_conditions(condition_sheet, items)

    return {
        "license_number": license_number,
        "license_date": license_date,
        "license_expiry_date": expiry,
        "file_number": file_number,
        "iec": iec,
        "company_name": company_name,
        "company_address": (
            re.sub(r"\s+", " ", m.group(1)).strip()
            if (m := _ADDRESS_RX.search(text)) else None
        ),
        "fob_inr": _strip_lakh(_first(_FOB_RX)),
        "cif_inr": _strip_lakh(cif_inr),
        "cif_fc": _strip_lakh(_first(_CIF_FC_RX)),
        "port_code": _first(_PORT_RX),
        "notification_number": notification,
        "validity_months": _first(_VALIDITY_MONTHS_RX),
        "items": items,
        "condition_sheet": condition_sheet,
        "item_conditions": item_conditions,
        "is_ocr": used_ocr,
        "source_kind": source_kind,
    }
