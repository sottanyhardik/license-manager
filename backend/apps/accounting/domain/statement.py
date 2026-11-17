"""Bank statement normalisation (pure): header mapping, dates, amounts, debit/credit, UTR, fingerprints."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

FIELD_ALIASES = {
    "txn_date": ("txn date", "transaction date", "tran date", "date", "posting date", "trans date"),
    "value_date": ("value date", "value dt", "val date"),
    "narration": ("narration", "description", "particulars", "remarks", "transaction details", "details"),
    "reference": ("utr", "utr no", "reference", "ref no", "ref no./cheque no.", "chq/ref no", "cheque no",
                  "chq no", "chq./ref.no.", "reference no", "ref"),
    "debit": ("debit", "withdrawal", "withdrawals", "withdrawal amt", "withdrawal amount", "dr", "debit amount",
              "withdrawl amt", "withdrawl amount", "withdrawl"),  # bank exports misspell "withdrawal"
    "credit": ("credit", "deposit", "deposits", "deposit amt", "deposit amount", "cr", "credit amount"),
    "amount": ("amount", "transaction amount", "txn amount"),
    "dr_cr": ("dr/cr", "cr/dr", "type", "debit/credit", "transaction type"),
    "balance": ("balance", "closing balance", "running balance", "available balance"),
}
REQUIRED = ("txn_date",)
DATE_FORMATS = ("%d-%m-%Y", "%d/%m/%Y", "%d-%m-%y", "%d/%m/%y", "%Y-%m-%d", "%d %b %Y", "%d-%b-%Y", "%d-%b-%y",
                "%d %B %Y", "%d.%m.%Y")
UTR_PATTERN = re.compile(r"\b([A-Z]{4}[RHN0-9][A-Z0-9]{10,17}|[A-Z]?\d{12,22})\b")


class StatementFormatError(ValueError):
    pass


def _norm(header: object) -> str:
    """'Withdrawal Amt.' -> 'withdrawal amt'; 'Chq./Ref.No.' -> 'chq ref no'."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", str(header or "").lower())).strip()


def detect_mapping(headers: list[object], override: dict[str, str] | None = None) -> dict[str, int]:
    """Map canonical fields to column indexes. ``override`` maps field -> header text."""
    normed = [_norm(h) for h in headers]
    mapping: dict[str, int] = {}
    for field, header in (override or {}).items():
        if _norm(header) not in normed:
            raise StatementFormatError(f"Column '{header}' not found for {field}.")
        mapping[field] = normed.index(_norm(header))
    for field, aliases in FIELD_ALIASES.items():
        if field in mapping:
            continue
        for alias in (_norm(a) for a in aliases):
            if alias in normed and normed.index(alias) not in mapping.values():
                mapping[field] = normed.index(alias)
                break
    missing = [f for f in REQUIRED if f not in mapping]
    if missing:
        raise StatementFormatError(f"Missing required column(s): {', '.join(missing)}.")
    if not ({"debit", "credit"} & mapping.keys() or "amount" in mapping):
        raise StatementFormatError("Need debit/credit columns or an amount column.")
    one_sided = {"debit", "credit"} - mapping.keys()
    if len(one_sided) == 1 and "amount" not in mapping:
        # A file with deposits but no recognised withdrawal column (or vice versa) would silently drop one side.
        raise StatementFormatError(f"Found a {'credit' if 'debit' in one_sided else 'debit'} column but no "
                                   f"{one_sided.pop()} column; map it explicitly.")
    return mapping


def find_header_row(rows: list[list[object]], scan: int = 60) -> int:
    """Banks put preamble lines above the table; the header is the first row that maps."""
    for i, row in enumerate(rows[:scan]):
        try:
            detect_mapping(list(row))
            return i
        except StatementFormatError:
            continue
    raise StatementFormatError("Could not find a header row with a date and amount columns.")


def parse_date(value: object) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip().split(" ")[0] if ":" in str(value) else str(value).strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise StatementFormatError(f"Unrecognised date '{value}'.")


def parse_amount(value: object) -> Decimal:
    if value in (None, ""):
        return Decimal("0.00")
    if isinstance(value, float):
        value = repr(value)
    text = str(value).strip().replace(",", "").replace("₹", "").replace("INR", "").strip()
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()").strip()
    suffix = text[-2:].upper() if len(text) > 2 else ""
    if suffix in ("CR", "DR"):
        text = text[:-2].strip()
    if text in ("", "-"):
        return Decimal("0.00")
    try:
        amount = Decimal(text).quantize(Decimal("0.01"))
    except InvalidOperation as exc:
        raise StatementFormatError(f"Unrecognised amount '{value}'.") from exc
    return -amount if negative else amount


def extract_utr(*texts: str) -> str:
    for text in texts:
        match = UTR_PATTERN.search((text or "").upper())
        if match:
            return match.group(1)
    return ""


@dataclass(frozen=True)
class NormalisedLine:
    row_no: int
    txn_date: date
    value_date: date | None
    narration: str
    reference: str
    debit: Decimal
    credit: Decimal
    balance: Decimal | None


def _cell(row: list[object], mapping: dict[str, int], field: str) -> object:
    idx = mapping.get(field)
    return row[idx] if idx is not None and idx < len(row) else None


def normalise_row(row: list[object], mapping: dict[str, int], row_no: int) -> NormalisedLine | None:
    """Return None for blank/summary rows; raise StatementFormatError for malformed rows."""
    raw_date = _cell(row, mapping, "txn_date")
    if raw_date in (None, "") or not any(c not in (None, "") for c in row):
        return None
    txn_date = parse_date(raw_date)
    debit = abs(parse_amount(_cell(row, mapping, "debit"))) if "debit" in mapping else Decimal("0.00")
    credit = abs(parse_amount(_cell(row, mapping, "credit"))) if "credit" in mapping else Decimal("0.00")
    if "amount" in mapping and not (debit or credit):
        amount = parse_amount(_cell(row, mapping, "amount"))
        flag = str(_cell(row, mapping, "dr_cr") or "").strip().upper()
        raw_amount = str(_cell(row, mapping, "amount") or "").upper()
        is_debit = flag.startswith("D") or raw_amount.endswith("DR") or (not flag and amount < 0)
        debit, credit = (abs(amount), Decimal("0.00")) if is_debit else (Decimal("0.00"), abs(amount))
    if debit and credit:
        raise StatementFormatError(f"Row {row_no}: both debit and credit are set.")
    if not (debit or credit):
        return None
    narration = str(_cell(row, mapping, "narration") or "").strip()
    reference = str(_cell(row, mapping, "reference") or "").strip()
    if reference.endswith(".0") and reference[:-2].isdigit():
        reference = reference[:-2]
    balance_raw = _cell(row, mapping, "balance")
    return NormalisedLine(
        row_no=row_no, txn_date=txn_date, value_date=parse_date(_cell(row, mapping, "value_date")),
        narration=narration[:500], reference=(reference or extract_utr(narration))[:128],
        debit=debit, credit=credit, balance=parse_amount(balance_raw) if balance_raw not in (None, "") else None,
    )


def fingerprint(bank_key: str, line: NormalisedLine, occurrence: int) -> str:
    """Stable identity of a bank transaction. ``occurrence`` separates genuinely identical rows in one file."""
    parts = [bank_key, line.txn_date.isoformat(), str(line.debit), str(line.credit),
             re.sub(r"\s+", " ", line.narration.upper()), line.reference.upper(),
             "" if line.balance is None else str(line.balance), str(occurrence)]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()
