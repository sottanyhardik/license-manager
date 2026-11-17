"""Bank statements: import + normalise, duplicate detection, matching (UTR -> exact amount, with
date/party/narration as supporting signals), manual / split / partial matches, suspense and
reclassification through the central posting engine.

Matching never posts an accounting entry. Only suspense and reclassification post, and they do so
through ``post_voucher`` (idempotent, balanced, period-checked).
"""
from __future__ import annotations

import csv
import hashlib
import io
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from apps.accounting.domain.money import ZERO, to_money
from apps.accounting.domain.statement import (
    StatementFormatError, detect_mapping, find_header_row, fingerprint, normalise_row,
)
from apps.accounting.models import (
    Account, BankAccount, BankMatch, Invoice, LineStatus, StatementImport, StatementLine, SuspenseItem, Voucher,
    VoucherLine, VoucherStatus, VoucherType,
)

from . import AccountingError, audit
from .chart import system_account
from .invoices import allocate
from .posting import cr, dr, post_voucher, reverse_voucher

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
DATE_WINDOW_DAYS = 7


# --- import -------------------------------------------------------------------------------------

def _read_rows(file_name: str, content: bytes) -> tuple[str, list[list[object]]]:
    name = file_name.lower()
    if len(content) > MAX_UPLOAD_BYTES:
        raise AccountingError("Statement file is larger than 10 MB.", "file_too_large")
    if name.endswith((".xlsx", ".xlsm")):
        from openpyxl import load_workbook
        try:
            wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        except Exception as exc:  # openpyxl raises many types for corrupt files
            raise AccountingError(f"Could not read the Excel file: {exc}", "bad_file") from exc
        ws = wb.worksheets[0]
        return "XLSX", [list(r) for r in ws.iter_rows(values_only=True)]
    if name.endswith((".csv", ".txt")):
        for encoding in ("utf-8-sig", "cp1252"):
            try:
                text = content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise AccountingError("Could not decode the CSV file.", "bad_file")
        sample = text[:8192]
        delimiter = max(",;\t|", key=sample.count)
        return "CSV", [row for row in csv.reader(io.StringIO(text), delimiter=delimiter)]
    if name.endswith(".pdf"):
        raise AccountingError("PDF statements are not supported yet; export CSV or Excel from net banking.",
                              "pdf_unsupported")
    raise AccountingError("Upload a .csv or .xlsx statement.", "bad_file")


@dataclass
class ImportResult:
    statement_import: StatementImport
    new_lines: list[StatementLine]


@transaction.atomic
def import_statement(bank_account: BankAccount, *, file_name: str, content: bytes,
                     column_mapping: dict[str, str] | None = None, user=None) -> ImportResult:
    """Import a statement. Rows already imported (same fingerprint) are counted as duplicates and skipped."""
    file_format, rows = _read_rows(file_name, content)
    try:
        header_idx = find_header_row(rows) if not column_mapping else 0
        if column_mapping:  # explicit mapping: locate the row containing the mapped headers
            header_idx = next(i for i, r in enumerate(rows[:25])
                              if _maps(r, column_mapping))
        mapping = detect_mapping(list(rows[header_idx]), column_mapping)
    except (StatementFormatError, StopIteration) as exc:
        raise AccountingError(str(exc) or "Column mapping does not match the file.", "bad_columns") from exc

    stmt = StatementImport.objects.create(
        bank_account=bank_account, file_name=file_name[:255], file_format=file_format,
        file_sha256=hashlib.sha256(content).hexdigest(),
        column_mapping={k: str(rows[header_idx][v]) for k, v in mapping.items()},
    )
    errors, normalised = [], []
    for offset, row in enumerate(rows[header_idx + 1:], start=header_idx + 2):
        try:
            line = normalise_row(list(row), mapping, offset)
        except StatementFormatError as exc:
            errors.append({"row": offset, "error": str(exc)})
            continue
        if line:
            normalised.append(line)

    occurrences: Counter = Counter()
    bank_key = f"{bank_account.pk}"
    existing = set(StatementLine.objects.filter(bank_account=bank_account).values_list("fingerprint", flat=True))
    new_lines, duplicates = [], 0
    for line in normalised:
        base = (line.txn_date, line.debit, line.credit, line.narration, line.reference, line.balance)
        occurrences[base] += 1
        fp = fingerprint(bank_key, line, occurrences[base])
        if fp in existing:
            duplicates += 1
            continue
        existing.add(fp)
        new_lines.append(StatementLine(
            bank_account=bank_account, statement_import=stmt, txn_date=line.txn_date, value_date=line.value_date,
            narration=line.narration, reference=line.reference, debit=line.debit, credit=line.credit,
            balance=line.balance, fingerprint=fp,
        ))
    StatementLine.objects.bulk_create(new_lines)
    stmt.rows_total = len(normalised) + len(errors)
    stmt.rows_new, stmt.rows_duplicate, stmt.rows_rejected = len(new_lines), duplicates, len(errors)
    stmt.errors = errors[:200]
    stmt.save(update_fields=["rows_total", "rows_new", "rows_duplicate", "rows_rejected", "errors", "modified_on"])
    audit.record("STATEMENT_IMPORTED", stmt, actor=user, entity=bank_account.entity, new=len(new_lines),
                 duplicates=duplicates, rejected=len(errors), file=file_name)
    return ImportResult(stmt, new_lines)


def _maps(row, column_mapping) -> bool:
    try:
        detect_mapping(list(row), column_mapping)
        return True
    except StatementFormatError:
        return False


# --- book side: what a bank line can match -------------------------------------------------------

def _bank_side_amount(voucher: Voucher, account: Account, deposit: bool) -> Decimal:
    agg = voucher.lines.filter(account=account).aggregate(d=Sum("debit"), c=Sum("credit"))
    return (agg["d"] or ZERO) - (agg["c"] or ZERO) if deposit else (agg["c"] or ZERO) - (agg["d"] or ZERO)


def voucher_matched(voucher: Voucher) -> Decimal:
    return BankMatch.objects.filter(voucher=voucher, is_active=True).aggregate(t=Sum("amount"))["t"] or ZERO


def voucher_unmatched(voucher: Voucher, bank: BankAccount, deposit: bool) -> Decimal:
    return _bank_side_amount(voucher, bank.account, deposit) - voucher_matched(voucher)


def line_remaining(line: StatementLine) -> Decimal:
    used = line.matches.filter(is_active=True).aggregate(t=Sum("amount"))["t"] or ZERO
    return line.amount - used


def unmatched_book_vouchers(bank: BankAccount, *, deposit: bool, as_of: date | None = None):
    """Posted vouchers touching the bank ledger on the given side with an unmatched balance."""
    side = Q(lines__account=bank.account) & (Q(lines__debit__gt=0) if deposit else Q(lines__credit__gt=0))
    qs = (Voucher.objects.filter(side, status=VoucherStatus.POSTED)
          .exclude(voucher_type=VoucherType.REVERSAL).distinct().select_related("payment__party")
          .order_by("date", "id"))
    if as_of:
        qs = qs.filter(date__lte=as_of)
    return [v for v in qs if voucher_unmatched(v, bank, deposit) > 0]


# --- matching ------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Candidate:
    voucher: Voucher
    unmatched: Decimal
    score: int
    signals: tuple[str, ...]


def _party_name(voucher: Voucher) -> str:
    payment = getattr(voucher, "payment", None)
    return payment.party.name if payment else ""


def candidates_for(line: StatementLine) -> list[Candidate]:
    """Ranked book entries for a statement line. Scores are signals for humans, not auto-posting."""
    bank, deposit = line.bank_account, line.credit > 0
    remaining = line_remaining(line)
    narration = f"{line.narration} {line.reference}".upper()
    out = []
    for voucher in unmatched_book_vouchers(bank, deposit=deposit):
        unmatched = voucher_unmatched(voucher, bank, deposit)
        signals, score = [], 0
        payment = getattr(voucher, "payment", None)
        ref = (payment.reference if payment else "").upper()
        if ref and (ref == line.reference.upper() or ref in narration):
            signals.append("utr"); score += 100
        if unmatched == remaining:
            signals.append("exact_amount"); score += 40
        days = abs((voucher.date - line.txn_date).days)
        if days <= DATE_WINDOW_DAYS:
            signals.append(f"date±{days}d"); score += max(0, 15 - 2 * days)
        party = _party_name(voucher)
        tokens = [t for t in party.upper().split() if len(t) > 3]
        if tokens and any(t in narration for t in tokens):
            signals.append("party_name"); score += 10
        if score:
            out.append(Candidate(voucher, unmatched, score, tuple(signals)))
    return sorted(out, key=lambda c: (-c.score, abs((c.voucher.date - line.txn_date).days), c.voucher.pk))


def _refresh_line_status(line: StatementLine) -> StatementLine:
    remaining = line_remaining(line)
    matched = line.amount - remaining
    has_suspense = line.matches.filter(is_active=True, method=BankMatch.SUSPENSE).exists()
    resolved = SuspenseItem.objects.filter(statement_line_id=line.pk, status=SuspenseItem.RESOLVED).exists()
    if resolved and remaining == 0:
        status = LineStatus.RESOLVED
    elif has_suspense and remaining == 0:
        status = LineStatus.SUSPENSE
    elif remaining == 0:
        status = LineStatus.MATCHED
    elif matched > 0:
        status = LineStatus.PARTIAL
    else:
        status = LineStatus.UNMATCHED
    StatementLine.objects.filter(pk=line.pk).update(status=status, matched_amount=matched)
    line.status, line.matched_amount = status, matched
    return line


def _match(line: StatementLine, voucher: Voucher, amount: Decimal, method: str, user) -> BankMatch:
    amount = to_money(amount)
    deposit = line.credit > 0
    if amount <= 0:
        raise AccountingError("Match amount must be positive.", "bad_amount")
    if voucher.entity_id != line.bank_account.entity_id:
        raise AccountingError("The voucher belongs to another entity.", "cross_entity")
    if voucher.status != VoucherStatus.POSTED:
        raise AccountingError("Only posted, unreversed vouchers can be matched.", "not_posted")
    if amount > line_remaining(line):
        raise AccountingError(f"Match {amount} exceeds the line's unmatched {line_remaining(line)}.", "over_match")
    if amount > voucher_unmatched(voucher, line.bank_account, deposit):
        raise AccountingError("Match exceeds the voucher's unmatched bank amount (wrong side or already matched).",
                              "over_match")
    match = BankMatch.objects.create(statement_line=line, voucher=voucher, amount=amount, method=method)
    audit.record("BANK_MATCHED", match, actor=user, entity=line.bank_account.entity, line=line.pk,
                 voucher=voucher.number, amount=amount, method=method)
    return match


@transaction.atomic
def auto_match(bank: BankAccount, *, user=None) -> dict:
    """Stage 1: UTR/reference. Stage 2: exact amount with a unique best date/party candidate.
    Ambiguous lines stay UNMATCHED with suggestions; nothing is posted."""
    result = Counter()
    lines = StatementLine.objects.select_for_update().filter(
        bank_account=bank, status__in=[LineStatus.UNMATCHED, LineStatus.PARTIAL]
    ).order_by("txn_date", "id")
    for line in lines:
        cands = candidates_for(line)
        remaining = line_remaining(line)
        utr = [c for c in cands if "utr" in c.signals]
        if len(utr) == 1:
            _match(line, utr[0].voucher, min(remaining, utr[0].unmatched), BankMatch.AUTO_REFERENCE, user)
            result["utr"] += 1
        else:
            exact = [c for c in cands if "exact_amount" in c.signals and any(s.startswith("date") for s in c.signals)]
            best = [c for c in exact if c.score == exact[0].score] if exact else []
            if len(best) == 1:
                _match(line, best[0].voucher, remaining, BankMatch.AUTO_AMOUNT, user)
                result["amount"] += 1
            else:
                result["ambiguous" if exact else "unmatched"] += 1
        _refresh_line_status(line)
    return dict(result)


@transaction.atomic
def manual_match(line: StatementLine, allocations: list[tuple[Voucher, Decimal]], *, user=None) -> StatementLine:
    """Match one statement line to one or more vouchers (split). Partial totals leave the line PARTIAL."""
    line = StatementLine.objects.select_for_update().select_related("bank_account").get(pk=line.pk)
    if not allocations:
        raise AccountingError("Choose at least one voucher.", "no_allocations")
    if sum((to_money(a) for _v, a in allocations), ZERO) > line_remaining(line):
        raise AccountingError("Split total exceeds the statement line's unmatched amount.", "over_match")
    for voucher, amount in allocations:
        _match(line, voucher, amount, BankMatch.MANUAL, user)
    return _refresh_line_status(line)


@transaction.atomic
def unmatch(match: BankMatch, *, reason: str, user=None) -> StatementLine:
    match = BankMatch.objects.select_for_update().get(pk=match.pk)
    if not match.is_active:
        return match.statement_line
    if match.method == BankMatch.SUSPENSE:
        raise AccountingError("Suspense entries are cleared by resolving the suspense item.", "suspense_match")
    match.is_active = False
    match.save(update_fields=["is_active", "modified_on"])
    audit.record("BANK_UNMATCHED", match, actor=user, entity=match.voucher.entity, reason=reason)
    return _refresh_line_status(match.statement_line)


# --- suspense -----------------------------------------------------------------------------------

@transaction.atomic
def move_to_suspense(line: StatementLine, *, reason: str, owner=None, user=None,
                     follow_up_on: date | None = None) -> SuspenseItem:
    """Bring an unidentified bank line into the books against Suspense (never into income/expense)."""
    line = StatementLine.objects.select_for_update().select_related("bank_account__entity").get(pk=line.pk)
    if not reason.strip():
        raise AccountingError("Give a reason for moving the line to suspense.", "reason_required")
    already = SuspenseItem.objects.filter(statement_line_id=line.pk).first()
    if already:
        return already
    amount = line_remaining(line)
    if amount <= 0:
        raise AccountingError("The line is already fully matched.", "already_matched")
    bank, entity, deposit = line.bank_account, line.bank_account.entity, line.credit > 0
    suspense = system_account(entity, "SUSPENSE")
    narr = f"Unidentified bank {'receipt' if deposit else 'payment'}: {line.narration[:120]}"
    lines = [dr(bank.account, amount, narr), cr(suspense, amount, narr)] if deposit else \
        [dr(suspense, amount, narr), cr(bank.account, amount, narr)]
    voucher, _ = post_voucher(entity=entity, voucher_type=VoucherType.RECEIPT if deposit else VoucherType.PAYMENT,
                              voucher_date=line.txn_date, lines=lines, narration=narr, source_type="BANK_LINE",
                              source_id=line.pk, source_event="SUSPENSE", user=user)
    item = SuspenseItem.objects.create(entity=entity, statement_line=line, voucher=voucher, amount=amount,
                                       is_receipt=deposit, reason=reason, owner=owner, follow_up_on=follow_up_on)
    BankMatch.objects.create(statement_line=line, voucher=voucher, amount=amount, method=BankMatch.SUSPENSE)
    audit.record("SUSPENSE_OPENED", item, actor=user, entity=entity, amount=amount, reason=reason)
    _refresh_line_status(line)
    return item


@transaction.atomic
def reclassify_suspense(item: SuspenseItem, *, target: Account, note: str, user=None,
                        allocations: list[tuple[Invoice, Decimal]] | None = None,
                        resolution_date: date | None = None) -> SuspenseItem:
    """Move a suspense amount to its correct head (party, expense, income, loan, transfer) via a journal.
    If the target is a party ledger, the amount can be allocated to that party's bills."""
    item = SuspenseItem.objects.select_for_update().select_related("entity").get(pk=item.pk)
    if item.status != SuspenseItem.OPEN:
        raise AccountingError("This suspense item is already resolved.", "already_resolved")
    if target.entity_id != item.entity_id:
        raise AccountingError("The target account belongs to another entity.", "cross_entity")
    if target.kind in ("SUSPENSE",):
        raise AccountingError("Choose an account other than Suspense.", "bad_target")
    if not note.strip():
        raise AccountingError("A resolution note is required.", "note_required")
    suspense = system_account(item.entity, "SUSPENSE")
    narr = f"Suspense #{item.pk} reclassified to {target.name}: {note}"
    lines = [dr(suspense, item.amount, narr), cr(target, item.amount, narr)] if item.is_receipt else \
        [dr(target, item.amount, narr), cr(suspense, item.amount, narr)]
    voucher, _ = post_voucher(entity=item.entity, voucher_type=VoucherType.JOURNAL,
                              voucher_date=resolution_date or item.voucher.date, lines=lines, narration=narr,
                              source_type="SUSPENSE", source_id=item.pk, source_event="RECLASSIFY", user=user)
    for invoice, amount in allocations or []:
        if target.kind != "PARTY" or invoice.party_id != target.party_id:
            raise AccountingError("Bills can only be allocated when reclassifying to that party's ledger.",
                                  "party_mismatch")
        allocate(invoice, voucher, amount, user=user)
    _close_item(item, voucher, note, user)
    return item


@transaction.atomic
def resolve_suspense_by_match(item: SuspenseItem, voucher: Voucher, *, note: str, user=None) -> SuspenseItem:
    """The transaction was already booked (e.g. a payment entered later): reverse the suspense entry and
    match the bank line to the existing voucher, so it is not counted twice."""
    item = SuspenseItem.objects.select_for_update(of=("self",)).select_related("statement_line").get(pk=item.pk)
    if item.status != SuspenseItem.OPEN or not item.statement_line_id:
        raise AccountingError("Only open suspense items from a bank line can be resolved by matching.", "bad_item")
    reversal = reverse_voucher(item.voucher, reversal_date=item.voucher.date, reason=f"Matched to {voucher.number}",
                               user=user)
    BankMatch.objects.filter(voucher=item.voucher, is_active=True).update(is_active=False)
    line = item.statement_line
    _match(line, voucher, item.amount, BankMatch.MANUAL, user)
    _close_item(item, reversal, note, user)
    _refresh_line_status(line)
    return item


def _close_item(item: SuspenseItem, voucher: Voucher, note: str, user) -> None:
    item.status, item.resolution_voucher, item.resolution_note = SuspenseItem.RESOLVED, voucher, note
    item.resolved_by = user if getattr(user, "is_authenticated", False) else None
    item.resolved_at = timezone.now()
    item.save(update_fields=["status", "resolution_voucher", "resolution_note", "resolved_by", "resolved_at",
                             "modified_on"])
    audit.record("SUSPENSE_RESOLVED", item, actor=user, entity=item.entity, voucher=voucher.number, note=note)
    if item.statement_line_id:
        _refresh_line_status(item.statement_line)


# --- reconciliation -------------------------------------------------------------------------------

def bank_reconciliation(bank: BankAccount, as_of: date) -> dict:
    """Bank reconciliation statement: books vs statement, with every unreconciled item listed."""
    from apps.accounting.selectors.ledger import account_balance
    book = account_balance(bank.account, end=as_of)
    last = (StatementLine.objects.filter(bank_account=bank, txn_date__lte=as_of, balance__isnull=False)
            .order_by("-txn_date", "-id").first())
    statement_balance = last.balance if last else None
    unpresented = []  # in books, not yet on the statement
    for deposit in (True, False):
        for v in unmatched_book_vouchers(bank, deposit=deposit, as_of=as_of):
            unpresented.append({"voucher_id": v.pk, "number": v.number, "date": v.date, "deposit": deposit,
                                "amount": voucher_unmatched(v, bank, deposit)})
    unrecorded = [  # on the statement, not yet in books
        {"line_id": ln.pk, "date": ln.txn_date, "narration": ln.narration, "reference": ln.reference,
         "deposit": ln.credit > 0, "amount": line_remaining(ln), "status": ln.status}
        for ln in StatementLine.objects.filter(bank_account=bank, txn_date__lte=as_of,
                                               status__in=[LineStatus.UNMATCHED, LineStatus.PARTIAL])
    ]
    uncleared_deposits = sum((i["amount"] for i in unpresented if i["deposit"]), ZERO)
    unpresented_payments = sum((i["amount"] for i in unpresented if not i["deposit"]), ZERO)
    unrecorded_credits = sum((i["amount"] for i in unrecorded if i["deposit"]), ZERO)
    unrecorded_debits = sum((i["amount"] for i in unrecorded if not i["deposit"]), ZERO)
    expected_statement = book - uncleared_deposits + unpresented_payments + unrecorded_credits - unrecorded_debits
    return {
        "bank_account_id": bank.pk, "as_of": as_of, "book_balance": book, "statement_balance": statement_balance,
        "uncleared_deposits": uncleared_deposits, "unpresented_payments": unpresented_payments,
        "unrecorded_credits": unrecorded_credits, "unrecorded_debits": unrecorded_debits,
        "expected_statement_balance": expected_statement,
        "difference": (statement_balance - expected_statement) if statement_balance is not None else None,
        "unpresented": unpresented, "unrecorded": unrecorded,
        "open_suspense": SuspenseItem.objects.filter(entity=bank.entity, status=SuspenseItem.OPEN).count(),
    }
