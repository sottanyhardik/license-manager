"""
Bill of Entry (ICEGATE / Indian Customs) PDF text parser.

The PDF layout we target is the standard ICEGATE Assessed Copy / Final
First Copy. Text extraction is done with pypdf and the resulting text is
parsed with regexes - labels and values are far apart in extraction order,
so we rely on the well-known value patterns rather than label proximity.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from pypdf import PdfReader


_BE_HEADER_RX = re.compile(r"^\s*(\d{6,10})\s+(\d{2}/\d{2}/\d{4})\s*$", re.MULTILINE)
_IEC_RX = re.compile(r"\b(\d{10})\s*/\s*(\d{1,3})\b")
_PORT_CODE_RX = re.compile(r"\b(IN[A-Z]{3}\d{0,2})\b")
_GSTIN_RX = re.compile(r"\b(\d{2}[A-Z]{5}\d{4}[A-Z]\d[A-Z]{2})\b")
_FX_RX = re.compile(r"\b1\s*([A-Z]{3})\s*=\s*([\d.]+)\s*INR", re.IGNORECASE)

_INVOICE_SUMMARY_RX = re.compile(
    r"^\s*(\d{1,3})\s+([A-Z0-9][A-Z0-9/\-_]{2,40})\s+([\d.,]+)\s+([A-Z]{3})\s*$",
    re.MULTILINE,
)

_ITEM_RX = re.compile(
    r"^\s*(\d{1,3})\s+([\d.]+)\s+([\d.]+)\s+([A-Z]{2,4})\s+([\d.]+)([A-Z][A-Z0-9 ()\-]+?)\s*$",
    re.MULTILINE,
)

_LICENCE_RX = re.compile(
    r"^\s*(\d{1,3})\s+(\d{1,3})\s+(\d{1,4})\s+"
    r"(\d{8,12})\s+"
    r"(\d{1,2}-[A-Z]{3}-\d{2,4})\s+"
    r"(\d{1,3})\s+"
    r"(IN[A-Z]{3}\d{0,2})\s+"
    r"([\d.]+)\s+([\d.]+)\s+([A-Z]{2,4})\s*$",
    re.MULTILINE,
)

_COMPANY_NAME_RX = re.compile(
    r"^([A-Z][A-Z0-9 &.,'()\-]{3,80}"
    r"(?:PRIVATE LIMITED|PVT\.?\s*LTD\.?|LIMITED|LTD\.?|LLP|INC\.?))\s*$",
    re.MULTILINE,
)


def _to_iso_date(value):
    if not value:
        return None
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d-%b-%y", "%d-%b-%Y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _to_float(value):
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _extract_address_block(page_text: str, company_name: str) -> str:
    if not company_name:
        return ""
    lines = page_text.splitlines()
    out: list[str] = []
    started = False
    for raw in lines:
        line = raw.strip()
        if not started:
            if line == company_name:
                started = True
            continue
        if not line:
            if out:
                break
            continue
        if re.fullmatch(r"\d{6}", line):
            out.append(line)
            break
        if re.match(r"^\d", line) and len(line) > 6 and " " in line:
            break
        out.append(line)
        if len(out) >= 6:
            break
    return "\n".join(out).strip()


def extract_pages(source) -> list[str]:
    reader = PdfReader(source)
    return [(p.extract_text() or "") for p in reader.pages]


def parse_boe_pdf(source) -> dict[str, Any]:
    pages = extract_pages(source)
    if not pages:
        return {}

    page1 = pages[0]
    page2 = pages[1] if len(pages) > 1 else ""
    page4 = pages[3] if len(pages) > 3 else ""

    result: dict[str, Any] = {
        "be_number": None,
        "be_date": None,
        "port_code": None,
        "iec": None,
        "gstin": None,
        "exchange_rate": None,
        "currency": None,
        "buyer_name": None,
        "buyer_address": None,
        "seller_name": None,
        "invoice_no": None,
        "invoice_amount": None,
        "invoice_currency": None,
        "item_description": None,
        "item_quantity": None,
        "item_uqc": None,
        "licences": [],
    }

    m = _BE_HEADER_RX.search(page1)
    if m:
        result["be_number"] = m.group(1)
        result["be_date"] = _to_iso_date(m.group(2))

    m = _PORT_CODE_RX.search(page1)
    if m:
        result["port_code"] = m.group(1)

    m = _IEC_RX.search(page1)
    if m:
        result["iec"] = m.group(1)

    m = _GSTIN_RX.search(page1)
    if m:
        result["gstin"] = m.group(1)

    m = _FX_RX.search(page1)
    if m:
        result["currency"] = m.group(1).upper()
        result["exchange_rate"] = _to_float(m.group(2))

    # Invoice summary line — different BOE types place it on page 1 or in
    # Part IV (page 5–7+); scan all pages and stop at the first valid match.
    for _page in pages:
        matched_invoice = False
        for sm in _INVOICE_SUMMARY_RX.finditer(_page):
            cur = sm.group(4)
            if cur in {"USD", "EUR", "GBP", "INR", "CNY", "JPY", "AED", "SGD"}:
                result["invoice_no"] = sm.group(2)
                result["invoice_amount"] = _to_float(sm.group(3))
                result["invoice_currency"] = cur
                matched_invoice = True
                break
        if matched_invoice:
            break

    m = _COMPANY_NAME_RX.search(page1)
    if m:
        result["buyer_name"] = m.group(1).strip()
        result["buyer_address"] = _extract_address_block(page1, result["buyer_name"])

    if page2:
        for m in _COMPANY_NAME_RX.finditer(page2):
            name = m.group(1).strip()
            if name != result.get("buyer_name"):
                result["seller_name"] = name
                break

    if page2:
        im = _ITEM_RX.search(page2)
        if im:
            result["item_quantity"] = _to_float(im.group(3))
            result["item_uqc"] = im.group(4)
            result["item_description"] = im.group(6).strip()

    licences = []
    # Try the inline (row-wise) layout on every page from page 3 onwards —
    # different BOE types put the licence section on different pages.
    for page_text in pages[2:]:
        for lm in _LICENCE_RX.finditer(page_text):
            licences.append({
                "invoice_sno": int(lm.group(1)),
                "item_sno": int(lm.group(2)),
                "licence_slno": int(lm.group(3)),
                "licence_number": lm.group(4),
                "licence_date": _to_iso_date(lm.group(5)),
                "scheme_code": int(lm.group(6)),
                "port_code": lm.group(7),
                "debit_value_inr": _to_float(lm.group(8)),
                "qty": _to_float(lm.group(9)),
                "uqc": lm.group(10),
            })

    # Fallback: columnar layout (pypdf extracts each cell on its own line)
    if not licences:
        for page_text in pages:
            if "LIC SLNO" in page_text or "F. LICENCE DETAILS" in page_text:
                licences = _parse_licences_columnar(page_text)
                if licences:
                    break

    result["licences"] = licences

    return result


# ---------------------------------------------------------------------
# Columnar fallback parser
# ---------------------------------------------------------------------

_COL_LIC_NO_RX = re.compile(r"^\d{10,12}$")
_COL_DATE_RX  = re.compile(r"^\d{1,2}-[A-Z]{3}-\d{2,4}$")
_COL_INT_RX   = re.compile(r"^\d{1,4}$")
_COL_PORT_RX  = re.compile(r"^IN[A-Z]{3}\d{0,2}$")
_COL_DEC_RX   = re.compile(r"^\d+(?:\.\d+)?$")
_COL_UQC_RX   = re.compile(r"^[A-Z]{2,4}$")


def _find_run(lines, start, n, pat):
    """Return index where n consecutive lines from `start` match `pat`, else None."""
    i = start
    while i <= len(lines) - n:
        if all(pat.match(lines[i + k]) for k in range(n)):
            return i
        i += 1
    return None


def _parse_licences_columnar(page_text):
    """
    Parse the LICENCE DETAILS section when pypdf flattens it column-wise
    (each cell on its own line, with column values stacked).

    Strategy: find the longest run of consecutive license-number lines (the
    anchor); count = number of rows N. Then look forwards for N consecutive
    dates -> codes -> ports -> two decimal blocks (debit_value, qty) -> UQCs.
    Look backwards for the last N consecutive small ints to recover lic_slno.
    """
    lines = [l.strip() for l in page_text.splitlines() if l.strip()]

    # All license-number indices, then find the longest contiguous run
    lic_idxs = [i for i, l in enumerate(lines) if _COL_LIC_NO_RX.match(l)]
    if not lic_idxs:
        return []
    runs = []
    s = e = lic_idxs[0]
    for i in lic_idxs[1:]:
        if i == e + 1:
            e = i
        else:
            runs.append((s, e))
            s = e = i
    runs.append((s, e))
    runs.sort(key=lambda r: r[1] - r[0], reverse=True)
    lic_start, lic_end = runs[0]
    N = lic_end - lic_start + 1
    if N < 1:
        return []

    lic_numbers = lines[lic_start:lic_end + 1]
    after = lines[lic_end + 1:]
    before = lines[:lic_start]

    # Required columns after lic_no block
    dates_at = _find_run(after, 0, N, _COL_DATE_RX)
    if dates_at is None:
        return []
    dates = after[dates_at:dates_at + N]

    codes_at = _find_run(after, dates_at + N, N, _COL_INT_RX)
    codes = after[codes_at:codes_at + N] if codes_at is not None else [None] * N

    ports_after_from = (codes_at + N) if codes_at is not None else (dates_at + N)
    ports_at = _find_run(after, ports_after_from, N, _COL_PORT_RX)
    ports = after[ports_at:ports_at + N] if ports_at is not None else [None] * N

    dec_after_from = (ports_at + N) if ports_at is not None else ports_after_from
    debits_at = _find_run(after, dec_after_from, N, _COL_DEC_RX)
    debits = after[debits_at:debits_at + N] if debits_at is not None else [None] * N

    qty_after_from = (debits_at + N) if debits_at is not None else dec_after_from
    qty_at = _find_run(after, qty_after_from, N, _COL_DEC_RX)
    qtys = after[qty_at:qty_at + N] if qty_at is not None else [None] * N

    uqc_from = (qty_at + N) if qty_at is not None else qty_after_from
    uqc_at = _find_run(after, uqc_from, N, _COL_UQC_RX)
    uqcs = after[uqc_at:uqc_at + N] if uqc_at is not None else [None] * N

    # lic_slno = last N consecutive small ints before lic_numbers
    slno_at = None
    for i in range(len(before) - N, -1, -1):
        if all(_COL_INT_RX.match(before[i + k]) for k in range(N)):
            slno_at = i
            break
    slnos = before[slno_at:slno_at + N] if slno_at is not None else [None] * N

    out = []
    for i in range(N):
        out.append({
            "invoice_sno": 1,
            "item_sno": i + 1,
            "licence_slno": int(slnos[i]) if slnos[i] and slnos[i].isdigit() else None,
            "licence_number": lic_numbers[i],
            "licence_date": _to_iso_date(dates[i]) if dates[i] else None,
            "scheme_code": int(codes[i]) if codes[i] and codes[i].isdigit() else None,
            "port_code": ports[i],
            "debit_value_inr": _to_float(debits[i]),
            "qty": _to_float(qtys[i]),
            "uqc": uqcs[i],
        })
    return out
