"""Invoice proposals for bank lines that have no book entry yet (owner decisions 2026-11-17).

* Propose, a human confirms: ``proposals_for`` only reads. Nothing reaches the books until
  ``confirm_proposal``, which posts one receipt/payment through ``payments.record_payment`` (the central
  engine), settles the party's open bills oldest-first and links the bank line (``BankMatch.PROPOSAL``).
* Allocation: bills dated on/before the bank date, oldest due first; any excess stays an on-account advance.
* Learning: a confirmation remembers ``counterparty_key(narration) -> party`` per entity and direction
  (``NarrationAlias``); later statements resolve that party first.

Duplicate guards: a line that already has a book candidate (UTR / exact amount, see ``banking.candidates_for``),
an existing payment with the same UTR, or an unaccounted Trade payment of the same amount is never booked
again here - those go through auto-match / ``account_trade_payment`` instead.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import F, Q

from apps.accounting.domain.money import ZERO
from apps.accounting.domain.statement import extract_utr
from apps.accounting.models import (
    NOTE_KINDS, PAYABLE_KINDS, RECEIVABLE_KINDS, BankAccount, BankMatch, DocStatus, Invoice, LineStatus,
    NarrationAlias, Payment, PaymentDirection, StatementLine,
)
from apps.core.models import CompanyModel

from . import AccountingError, audit
from .banking import DATE_WINDOW_DAYS, _match, book_pool, candidates_for, line_remaining, refresh_line_status, unmatch
from .invoices import outstanding_map
from .payments import record_payment, reverse_payment

# Transport / channel words and bank codes that say nothing about the counterparty.
CHANNEL_WORDS = frozenset("""
RTGS NEFT IMPS UPI TRF TRFD FRM FROM TO BY CHQ CHEQUE DEP CIB IB INB MB PG BP REV CR DR TPFT ACH NACH ECS
INWARD OUTWARD PAYMENT TRANSFER FUND FUNDS CLG CLEARING MOB NET BANKING TXN REF NO AC ACCOUNT
SBIN UTIB HDFC ICIC KKBK PUNB BARB IDIB YESB RATN CNRB UBIN BKID IOBA INDB FDRL IDFB MAHB CBIN
""".split())
# Legal-form words carry no identity ("ABC EXIM PVT LTD" is identified by ABC EXIM).
LEGAL_WORDS = frozenset("PVT PRIVATE LTD LIMITED LLP AND THE CO COMPANY CORP CORPORATION INC OF MS".split())
MIN_NAME_SCORE = 0.6
# "BU : 2056141 Transfer 26.11.2025": a bank bulk upload - one debit for several beneficiaries (split it).
BULK_PATTERN = re.compile(r"^\s*BU\s*:", re.IGNORECASE)
TRADE_PAYMENT_WINDOW = timedelta(days=DATE_WINDOW_DAYS)


def _words(text: str) -> list[str]:
    return re.sub(r"[^A-Z0-9]+", " ", (text or "").upper()).split()


def counterparty_key(narration: str) -> str:
    """The narration minus channel words, bank codes and anything with a digit (UTRs, accounts, dates).

    'RTGS-HDFCR52025031012345-ABC EXIM PVT LTD' -> 'ABC EXIM PVT LTD'."""
    kept = [w for w in _words(narration) if len(w) > 1 and w not in CHANNEL_WORDS and not any(c.isdigit() for c in w)]
    return " ".join(kept)[:200]


def _identity_words(name: str) -> list[str]:
    return [w for w in _words(name) if len(w) >= 3 and w not in LEGAL_WORDS and not any(c.isdigit() for c in w)]


def name_score(key: str, party_name: str) -> float:
    """Share of the party's identity words found in the counterparty text. Banks truncate names
    ('JASH MERCAN'), so a narration word of 4+ letters also matches as a prefix of a party word."""
    party_words = _identity_words(party_name)
    key_words = key.split()
    if not party_words or not key_words:
        return 0.0
    hit = sum(1 for p in party_words if any(k == p or (len(k) >= 4 and p.startswith(k)) for k in key_words))
    return hit / len(party_words)


def _direction(line: StatementLine) -> str:
    return PaymentDirection.RECEIPT if line.credit > 0 else PaymentDirection.PAYMENT


def _mode(narration: str) -> str:
    words = set(_words(narration))
    for mode in ("RTGS", "NEFT", "IMPS", "UPI"):
        if mode in words:
            return mode
    return "CHEQUE" if {"CHQ", "CHEQUE"} & words else "OTHER"


@dataclass
class Allocation:
    invoice: Invoice
    outstanding: Decimal
    amount: Decimal


@dataclass
class Proposal:
    line: StatementLine
    direction: str
    counterparty: str
    party: CompanyModel | None = None
    source: str = ""                      # "alias" | "name" | "chosen" | ""
    score: float = 0.0
    options: list[tuple[CompanyModel, float]] = field(default_factory=list)
    allocations: list[Allocation] = field(default_factory=list)
    advance: Decimal = ZERO
    exact_bill: bool = False
    existing_candidates: int = 0
    blocked: str = ""                     # reason the line must not be booked here

    @property
    def is_bulk(self) -> bool:
        return bool(BULK_PATTERN.match(self.line.narration or ""))

    @property
    def confidence(self) -> str:
        if self.blocked:
            return "blocked"
        if self.party is None and self.is_bulk:
            return "bulk"
        if self.party is None:
            return "low" if self.options else "none"
        if self.source == "alias" or (self.score >= 1.0 and (self.exact_bill or (self.allocations and not self.advance))):
            return "high"
        return "medium"


class _Context:
    """Everything a batch of proposals needs, loaded once per bank account."""

    def __init__(self, bank: BankAccount):
        entity = bank.entity
        self.bank, self.entity = bank, entity
        bills = list(Invoice.objects.filter(entity=entity, status=DocStatus.POSTED)
                     .exclude(kind__in=NOTE_KINDS).select_related("party"))
        self.outstanding = outstanding_map(bills)
        self.bills = {PaymentDirection.RECEIPT: {}, PaymentDirection.PAYMENT: {}}
        self.parties = {PaymentDirection.RECEIPT: {}, PaymentDirection.PAYMENT: {}}
        own_company = entity.company_id
        for bill in bills:
            direction = PaymentDirection.RECEIPT if bill.kind in RECEIVABLE_KINDS else (
                PaymentDirection.PAYMENT if bill.kind in PAYABLE_KINDS else None)
            if direction is None or bill.party_id == own_company:
                continue
            self.parties[direction][bill.party_id] = bill.party
            if self.outstanding.get(bill.pk, ZERO) > 0:
                self.bills[direction].setdefault(bill.party_id, []).append(bill)
        for party_bills in (*self.bills[PaymentDirection.RECEIPT].values(), *self.bills[PaymentDirection.PAYMENT].values()):
            party_bills.sort(key=lambda b: (b.due_date or b.date, b.date, b.pk))
        self.aliases = {(a.key, a.direction): a.party
                        for a in NarrationAlias.objects.filter(entity=entity).select_related("party")}
        self.pools = {True: book_pool(bank, deposit=True), False: book_pool(bank, deposit=False)}
        self.used_refs = set(Payment.objects.filter(entity=entity, status=DocStatus.POSTED).exclude(reference="")
                             .values_list("direction", "reference"))
        self.own_company = own_company

    def alias_party(self, key: str, direction: str) -> CompanyModel | None:
        if not key:
            return None
        if (key, direction) in self.aliases:
            return self.aliases[(key, direction)]
        # A learned key inside a longer narration ("ABC EXIM" in "ABC EXIM PVT LTD MUMBAI"); longest wins.
        padded = f" {key} "
        hits = [(len(k), p) for (k, d), p in self.aliases.items() if d == direction and f" {k} " in padded]
        return max(hits, key=lambda h: h[0])[1] if hits else None

    def allocate(self, party_id: int, direction: str, amount: Decimal, as_of) -> tuple[list[Allocation], Decimal, bool]:
        left, out, exact = amount, [], False
        for bill in self.bills[direction].get(party_id, []):
            if bill.date > as_of:
                continue
            due = self.outstanding[bill.pk]
            exact = exact or due == amount
            if left <= 0 or due <= 0:
                continue
            take = min(due, left)
            out.append(Allocation(bill, due, take))
            left -= take
        return out, left, exact


def _build(line: StatementLine, ctx: _Context, party: CompanyModel | None = None) -> Proposal:
    direction = _direction(line)
    key = counterparty_key(line.narration)
    proposal = Proposal(line=line, direction=direction, counterparty=key)
    pool = ctx.pools[line.credit > 0]
    candidates = candidates_for(line, pool, remaining=line.amount - line.matched_amount) if pool else []  # no book entries on this side: nothing to compare
    proposal.existing_candidates = sum(1 for c in candidates if {"utr", "exact_amount"} & set(c.signals))
    reference = line.reference or extract_utr(line.narration)
    if line.status != LineStatus.UNMATCHED or line.matched_amount:
        proposal.blocked = "already_matched"
    elif any("utr" in c.signals for c in candidates):
        proposal.blocked = "existing_book_entry"
    elif reference and (direction, reference) in ctx.used_refs:
        proposal.blocked = "reference_already_booked"
    if party is not None:
        proposal.party, proposal.source, proposal.score = party, "chosen", name_score(key, party.name)
    else:
        aliased = ctx.alias_party(key, direction)
        if aliased is not None and aliased.pk != ctx.own_company:
            proposal.party, proposal.source, proposal.score = aliased, "alias", 1.0
        else:
            scored = sorted(((p, name_score(key, p.name)) for p in ctx.parties[direction].values()),
                            key=lambda ps: (-ps[1], ps[0].name))
            scored = [(p, s) for p, s in scored if s >= MIN_NAME_SCORE][:5]
            proposal.options = scored
            if scored and (len(scored) == 1 or scored[0][1] > scored[1][1]):
                proposal.party, proposal.source, proposal.score = scored[0][0], "name", scored[0][1]
    if proposal.party is not None:
        amount = line.amount
        proposal.allocations, proposal.advance, proposal.exact_bill = ctx.allocate(
            proposal.party.pk, direction, amount, line.txn_date)
    return proposal


def proposals_for(bank: BankAccount, *, include_blocked: bool = False) -> list[Proposal]:
    """Read-only proposals for every unmatched line of one bank account (oldest first)."""
    ctx = _Context(bank)
    lines = (StatementLine.objects.filter(bank_account=bank, status=LineStatus.UNMATCHED, matched_amount=0)
             .order_by("txn_date", "id"))
    out = []
    for line in lines:
        line.bank_account = bank  # same object for every line: no per-line lookup
        out.append(_build(line, ctx))
    return out if include_blocked else [p for p in out if not p.blocked]


def proposal_for(line: StatementLine, party: CompanyModel | None = None) -> Proposal:
    return _build(line, _Context(line.bank_account), party)


def _trade_payment_conflict(proposal: Proposal) -> int | None:
    """An unaccounted Trade payment of the same amount for one of this party's trades, near the bank date."""
    from apps.trade.models import LicenseTradePayment
    trade_ids = Invoice.objects.filter(entity=proposal.line.bank_account.entity, party=proposal.party,
                                       trade__isnull=False).values_list("trade_id", flat=True)
    day = proposal.line.txn_date
    hit = (LicenseTradePayment.objects.filter(trade_id__in=trade_ids, amount=proposal.line.amount,
                                              date__range=(day - TRADE_PAYMENT_WINDOW, day + TRADE_PAYMENT_WINDOW))
           .filter(accounting_payment__isnull=True).values_list("pk", flat=True).first())
    return hit


def learn_alias(entity, key: str, direction: str, party: CompanyModel, user=None) -> NarrationAlias | None:
    if not key:
        return None
    alias, created = NarrationAlias.objects.get_or_create(
        entity=entity, key=key, direction=direction, defaults={"party": party, "hits": 1, "created_by": user})
    if created:
        return alias
    if alias.party_id != party.pk:  # the human's latest confirmation is authoritative
        alias.party, alias.hits = party, 1
        alias.save(update_fields=["party", "hits", "modified_on"])
    else:
        NarrationAlias.objects.filter(pk=alias.pk).update(hits=F("hits") + 1)
    return alias


@transaction.atomic
def forget_alias(alias: NarrationAlias, *, user=None) -> None:
    """Remove a wrongly learned mapping (audited). Bookings made with it are untouched."""
    audit.record("NARRATION_ALIAS_DELETED", alias, actor=user, entity=alias.entity, key=alias.key,
                 direction=alias.direction, party=alias.party_id)
    alias.delete()


@transaction.atomic
def confirm_proposal(line: StatementLine, *, party: CompanyModel, user=None, learn: bool = True) -> Payment:
    """Book one bank line: post a receipt/payment for the party, settle its open bills oldest-first
    (excess = on-account advance), and match the bank line to it. Allocations are recomputed here."""
    line = StatementLine.objects.select_for_update().select_related("bank_account__entity").get(pk=line.pk)
    bank = line.bank_account
    entity = bank.entity
    if party.pk == entity.company_id:
        raise AccountingError("This is the entity itself (an own-account transfer), not a customer or supplier.",
                              "own_account")
    proposal = proposal_for(line, party)
    if proposal.blocked:
        messages = {
            "already_matched": "This bank line is already matched.",
            "existing_book_entry": "A book entry with this UTR already exists; use auto-match / manual match instead.",
            "reference_already_booked": "A payment with this UTR is already booked; match the line to it instead.",
        }
        raise AccountingError(messages[proposal.blocked], proposal.blocked)
    trade_payment = _trade_payment_conflict(proposal)
    if trade_payment:
        raise AccountingError(f"Trade payment #{trade_payment} records this money; post it from Trade "
                              "(payments/from-trade-payment) so it is booked once.", "trade_payment_exists")
    amount = line_remaining(line)
    reference = line.reference or extract_utr(line.narration)
    payment = record_payment(
        entity=entity, direction=proposal.direction, party=party, bank_account=bank, payment_date=line.txn_date,
        amount=amount, mode=_mode(line.narration), reference=reference, narration=f"Bank: {line.narration}",
        allocations=[(a.invoice, a.amount) for a in proposal.allocations], user=user,
    )
    _match(line, payment.voucher, amount, BankMatch.PROPOSAL, user)
    refresh_line_status(line)
    if learn:
        learn_alias(entity, proposal.counterparty, proposal.direction, party, user=user)
    audit.record("BANK_PROPOSAL_CONFIRMED", payment, actor=user, entity=entity, line=line.pk,
                 bills=[a.invoice.number for a in proposal.allocations], advance=proposal.advance)
    return payment


@transaction.atomic
def undo_confirmation(payment: Payment, *, user=None) -> StatementLine:
    """Undo a confirmed proposal: unmatch the bank line, reverse the receipt/payment (posted entries are
    immutable, so a reversal voucher on the same date nets it off) and roll back the alias it taught."""
    payment = Payment.objects.select_for_update(of=("self",)).select_related("entity", "party", "voucher").get(pk=payment.pk)
    if payment.status != DocStatus.POSTED:
        raise AccountingError("Only a posted receipt/payment can be undone.", "not_posted")
    matches = list(BankMatch.objects.filter(voucher=payment.voucher, is_active=True, method=BankMatch.PROPOSAL)
                   .select_related("statement_line"))
    if not matches:
        raise AccountingError("This receipt/payment was not booked from a bank proposal.", "not_a_proposal")
    line = matches[0].statement_line
    for match in matches:
        unmatch(match, reason="Undo bank proposal", user=user)
    reverse_payment(payment, reason=f"Undo bank proposal (line {line.pk})", user=user, reversal_date=payment.date)
    alias = NarrationAlias.objects.filter(entity=payment.entity, key=counterparty_key(line.narration),
                                          direction=payment.direction, party=payment.party).first()
    if alias is not None:
        if alias.hits <= 1:
            alias.delete()
        else:
            NarrationAlias.objects.filter(pk=alias.pk).update(hits=F("hits") - 1)
    audit.record("BANK_PROPOSAL_UNDONE", payment, actor=user, entity=payment.entity, line=line.pk)
    line.refresh_from_db()
    return line


def confirm_many(bank: BankAccount, items: list[tuple[int, int]], *, user=None) -> dict:
    """[(line_id, party_id)] -> each booked in its own transaction; failures are reported, not fatal."""
    confirmed, errors = [], []
    parties = CompanyModel.objects.in_bulk({p for _l, p in items})
    lines = StatementLine.objects.filter(bank_account=bank).in_bulk({ln for ln, _p in items})
    for line_id, party_id in items:
        line, party = lines.get(line_id), parties.get(party_id)
        if line is None or party is None:
            errors.append({"line_id": line_id, "code": "not_found", "detail": "Line or party not found for this bank."})
            continue
        try:
            payment = confirm_proposal(line, party=party, user=user)
        except AccountingError as exc:
            errors.append({"line_id": line_id, "code": exc.code, "detail": str(exc)})
            continue
        confirmed.append({"line_id": line_id, "payment_id": payment.pk, "voucher": payment.voucher.number})
    return {"confirmed": confirmed, "errors": errors}


# --- record payment/receipt screen: pick the bank transaction it came through ------------------------

def party_bank_lines(entity, party: CompanyModel, direction: str, *, search: str = "", limit: int = 50) -> list[dict]:
    """Unmatched / partly matched bank lines of these books on one side, ranked for ``party``
    (learned alias first, then name match). Without ``search`` only lines that look like this party."""
    qs = StatementLine.objects.filter(bank_account__entity=entity,
                                      status__in=[LineStatus.UNMATCHED, LineStatus.PARTIAL]).select_related("bank_account")
    qs = qs.filter(credit__gt=0) if direction == PaymentDirection.RECEIPT else qs.filter(debit__gt=0)
    if search:
        qs = qs.filter(Q(narration__icontains=search) | Q(reference__icontains=search))
    keys = [a for a in NarrationAlias.objects.filter(entity=entity, party=party, direction=direction)
            .values_list("key", flat=True)]
    rows = []
    for line in qs.order_by("-txn_date", "-id")[:2000]:
        key = counterparty_key(line.narration)
        padded = f" {key} "
        if any(f" {k} " in padded for k in keys):
            score, source = 1.0, "alias"
        else:
            score, source = name_score(key, party.name), "name"
        if not search and score < MIN_NAME_SCORE:
            continue
        rows.append({"line": line, "score": score, "source": source if score else "",
                     "remaining": line.amount - line.matched_amount, "mode": _mode(line.narration)})
    rows.sort(key=lambda r: (-r["score"], -r["line"].txn_date.toordinal(), -r["line"].pk))
    return rows[:limit]


@transaction.atomic
def record_payment_for_line(line: StatementLine, *, entity, direction: str, party: CompanyModel, amount,
                            tds_amount=ZERO, payment_date=None, mode: str = "", reference: str = "",
                            narration: str = "", allocations=None, user=None) -> Payment:
    """Post a payment/receipt that came through ``line`` and match the line to it in one transaction.
    The same never-book-twice guards as ``confirm_proposal``; a line may be settled in parts."""
    line = StatementLine.objects.select_for_update().select_related("bank_account__entity").get(pk=line.pk)
    bank = line.bank_account
    if bank.entity_id != entity.pk:
        raise AccountingError("The bank transaction belongs to another entity.", "cross_entity")
    if direction != _direction(line):
        raise AccountingError("A deposit is a receipt and a withdrawal is a payment; switch the direction.",
                              "direction_mismatch")
    if line.status not in (LineStatus.UNMATCHED, LineStatus.PARTIAL):
        raise AccountingError("This bank transaction is already matched.", "already_matched")
    if party.pk == entity.company_id:
        raise AccountingError("This is the entity itself (an own-account transfer), not a customer or supplier.",
                              "own_account")
    remaining = line_remaining(line)
    if amount > remaining:
        raise AccountingError(f"Amount exceeds the bank transaction's unmatched {remaining}.", "over_match")
    reference = (reference or line.reference or extract_utr(line.narration)).strip()
    pool = book_pool(bank, deposit=line.credit > 0)
    if pool and any("utr" in c.signals for c in candidates_for(line, pool, remaining=remaining)):
        raise AccountingError("A book entry with this UTR already exists; match the bank line to it instead.",
                              "existing_book_entry")
    if reference and Payment.objects.filter(entity=entity, direction=direction, status=DocStatus.POSTED,
                                            reference=reference).exists():
        raise AccountingError("A payment with this UTR is already booked; match the bank line to it instead.",
                              "reference_already_booked")
    trade_payment = _trade_payment_conflict(Proposal(line=line, direction=direction, counterparty="", party=party))
    if trade_payment:
        raise AccountingError(f"Trade payment #{trade_payment} records this money; post it from Trade "
                              "(payments/from-trade-payment) so it is booked once.", "trade_payment_exists")
    payment = record_payment(
        entity=entity, direction=direction, party=party, bank_account=bank, payment_date=payment_date or line.txn_date,
        amount=amount, tds_amount=tds_amount, mode=mode or _mode(line.narration), reference=reference,
        narration=narration or f"Bank: {line.narration}", allocations=allocations, user=user,
    )
    _match(line, payment.voucher, amount, BankMatch.MANUAL, user)
    refresh_line_status(line)
    learn_alias(entity, counterparty_key(line.narration), direction, party, user=user)
    audit.record("BANK_LINE_PAYMENT_RECORDED", payment, actor=user, entity=entity, line=line.pk, amount=amount)
    return payment


# --- split one bank line into several payments/receipts (bulk uploads "BU : ...") ---------------------

@dataclass
class SplitRow:
    party: CompanyModel
    amount: Decimal
    allocations: list[Allocation]
    advance: Decimal


def plan_split(line: StatementLine, rows: list[tuple[CompanyModel, Decimal]]) -> list[SplitRow]:
    """Oldest-first bills for each (party, amount) row against this line's side. Read-only."""
    ctx = _Context(line.bank_account)
    direction = _direction(line)
    out = []
    for party, amount in rows:
        allocations, advance, _exact = ctx.allocate(party.pk, direction, amount, line.txn_date)
        for a in allocations:  # a party listed twice must not settle the same bill twice
            ctx.outstanding[a.invoice.pk] -= a.amount
        out.append(SplitRow(party, amount, allocations, advance))
    return out


def _validate_split(line: StatementLine, rows: list[tuple[CompanyModel, Decimal]]) -> None:
    if not rows:
        raise AccountingError("Add at least one row.", "no_rows")
    if any(amount <= 0 for _p, amount in rows):
        raise AccountingError("Every row needs a positive amount.", "bad_amount")
    if any(party.pk == line.bank_account.entity.company_id for party, _a in rows):
        raise AccountingError("A row names the entity itself (an own-account transfer).", "own_account")
    total, remaining = sum((a for _p, a in rows), ZERO), line_remaining(line)
    if total != remaining:
        raise AccountingError(f"Rows total {total} but the bank line has {remaining} unmatched; they must be equal.",
                              "split_total_mismatch")


@transaction.atomic
def split_line(line: StatementLine, rows: list[tuple[CompanyModel, Decimal]], *, user=None) -> list[Payment]:
    """Book one payment/receipt per row (each settling that party's bills oldest first, excess = advance)
    and match them all to the single bank line. All rows or none."""
    line = StatementLine.objects.select_for_update().select_related("bank_account__entity").get(pk=line.pk)
    if line.status != LineStatus.UNMATCHED or line.matched_amount:
        raise AccountingError("This bank line is already (partly) matched.", "already_matched")
    _validate_split(line, rows)
    pool = book_pool(line.bank_account, deposit=line.credit > 0)
    if pool and any("utr" in c.signals for c in candidates_for(line, pool, remaining=line.amount)):
        raise AccountingError("A book entry with this UTR already exists; match the bank line to it instead.",
                              "existing_book_entry")
    entity, direction = line.bank_account.entity, _direction(line)
    payments = []
    for row in plan_split(line, rows):
        payment = record_payment(
            entity=entity, direction=direction, party=row.party, bank_account=line.bank_account,
            payment_date=line.txn_date, amount=row.amount, mode="OTHER", reference=line.reference,
            narration=f"Bank (split): {line.narration}", allocations=[(a.invoice, a.amount) for a in row.allocations],
            user=user,
        )
        _match(line, payment.voucher, row.amount, BankMatch.SPLIT, user)
        payments.append(payment)
    refresh_line_status(line)
    audit.record("BANK_LINE_SPLIT", line, actor=user, entity=entity, payments=[p.pk for p in payments],
                 parties=[p.party_id for p in payments])
    return payments


@transaction.atomic
def undo_split(line: StatementLine, *, user=None) -> StatementLine:
    """Reverse every payment a split booked and unmatch the line (back to UNMATCHED)."""
    line = StatementLine.objects.select_for_update().get(pk=line.pk)
    matches = list(BankMatch.objects.filter(statement_line=line, is_active=True, method=BankMatch.SPLIT)
                   .select_related("voucher__payment"))
    if not matches:
        raise AccountingError("This bank line has no split to undo.", "not_a_split")
    for match in matches:
        unmatch(match, reason="Undo split", user=user)
        reverse_payment(match.voucher.payment, reason=f"Undo split of bank line {line.pk}", user=user,
                        reversal_date=match.voucher.date)
    audit.record("BANK_LINE_SPLIT_UNDONE", line, actor=user, entity=matches[0].voucher.entity)
    line.refresh_from_db()
    return line
