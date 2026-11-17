"""The one posting engine. Every voucher in the system — trade, expense, bank, loan, migration,
manual — is created and posted here.

Guarantees: balanced (service + DB trigger), idempotent (unique idempotency key), gap-free
numbering per entity/FY/type under a row lock, open-period check, immutable once posted,
corrections only by reversal.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounting.domain.money import ZERO, q2
from apps.accounting.models import (
    VOUCHER_PREFIX, Account, EntityBooks, Voucher, VoucherLine, VoucherSequence, VoucherStatus, VoucherType,
)

from . import AccountingError, audit
from .books import open_period_for


@dataclass(frozen=True)
class LineSpec:
    account: Account
    debit: Decimal = ZERO
    credit: Decimal = ZERO
    narration: str = ""
    trade_id: int | None = None
    cost_centre_id: int | None = None


def dr(account: Account, amount: Decimal, narration: str = "", **kw) -> LineSpec:
    return LineSpec(account=account, debit=q2(amount), narration=narration, **kw)


def cr(account: Account, amount: Decimal, narration: str = "", **kw) -> LineSpec:
    return LineSpec(account=account, credit=q2(amount), narration=narration, **kw)


def _normalise(lines: list[LineSpec]) -> list[LineSpec]:
    """Drop zero lines; turn negative amounts into the opposite side."""
    out = []
    for line in lines:
        debit, credit = q2(line.debit), q2(line.credit)
        if debit < 0:
            credit, debit = credit - debit, ZERO
        if credit < 0:
            debit, credit = debit - credit, ZERO
        net = debit - credit
        if net == 0:
            continue
        out.append(LineSpec(line.account, net if net > 0 else ZERO, -net if net < 0 else ZERO,
                            line.narration, line.trade_id, line.cost_centre_id))
    return out


def validate_lines(entity: EntityBooks, lines: list[LineSpec]) -> Decimal:
    if len(lines) < 2:
        raise AccountingError("A voucher needs at least two non-zero lines.", "too_few_lines")
    total_dr = sum((ln.debit for ln in lines), ZERO)
    total_cr = sum((ln.credit for ln in lines), ZERO)
    if total_dr != total_cr:
        raise AccountingError(f"Voucher does not balance: debit {total_dr} ≠ credit {total_cr}.", "unbalanced")
    for ln in lines:
        if ln.account.entity_id != entity.pk:
            raise AccountingError(f"Account {ln.account.code} belongs to another entity.", "cross_entity_account")
        if not ln.account.is_active:
            raise AccountingError(f"Account {ln.account.code} is inactive.", "inactive_account")
    return total_dr


def _next_number(entity: EntityBooks, fy, voucher_type: str) -> str:
    seq, _ = VoucherSequence.objects.get_or_create(entity=entity, financial_year=fy, voucher_type=voucher_type)
    seq = VoucherSequence.objects.select_for_update().get(pk=seq.pk)
    number = f"{VOUCHER_PREFIX[voucher_type]}/{fy.label}/{seq.next_number:05d}"
    VoucherSequence.objects.filter(pk=seq.pk).update(next_number=seq.next_number + 1)
    return number


def make_key(entity: EntityBooks, source_type: str, source_id, source_event: str, source_version: str) -> str:
    return f"{entity.pk}:{source_type}:{source_id}:{source_event}:{source_version}"


def post_voucher(*, entity: EntityBooks, voucher_type: str, voucher_date: date, lines: list[LineSpec],
                 narration: str, source_type: str, source_id=None, source_event: str = "POST",
                 source_version: str = "1", user=None, idempotency_key: str | None = None,
                 reversal_of: Voucher | None = None) -> tuple[Voucher, bool]:
    """Create and post a voucher exactly once. Returns (voucher, created)."""
    if voucher_type not in VoucherType.values:
        raise AccountingError(f"Unknown voucher type {voucher_type}.", "bad_type")
    key = idempotency_key or make_key(entity, source_type, source_id, source_event, source_version)
    existing = Voucher.objects.filter(idempotency_key=key).first()
    if existing:
        return existing, False
    lines = _normalise(lines)
    total = validate_lines(entity, lines)
    try:
        with transaction.atomic():
            fy, _period = open_period_for(entity, voucher_date)
            voucher = Voucher.objects.create(
                entity=entity, financial_year=fy, voucher_type=voucher_type, date=voucher_date,
                narration=narration, total=total, source_type=source_type, source_id=source_id,
                source_event=source_event, source_version=source_version, idempotency_key=key,
                reversal_of=reversal_of, status=VoucherStatus.DRAFT,
            )
            _write_lines(voucher, lines)
            _mark_posted(voucher, user)
    except IntegrityError:
        existing = Voucher.objects.filter(idempotency_key=key).first()
        if existing:  # concurrent duplicate delivery: the first commit wins
            return existing, False
        raise
    return voucher, True


def _write_lines(voucher: Voucher, lines: list[LineSpec]) -> None:
    VoucherLine.objects.bulk_create([
        VoucherLine(voucher=voucher, line_no=i, account=ln.account, debit=ln.debit, credit=ln.credit,
                    narration=ln.narration[:255], trade_id=ln.trade_id, cost_centre_id=ln.cost_centre_id)
        for i, ln in enumerate(lines, start=1)
    ])


def _mark_posted(voucher: Voucher, user) -> None:
    voucher.number = _next_number(voucher.entity, voucher.financial_year, voucher.voucher_type)
    voucher.status = VoucherStatus.POSTED
    voucher.posted_by = user if getattr(user, "is_authenticated", False) else None
    voucher.posted_at = timezone.now()
    voucher.save(update_fields=["number", "status", "posted_by", "posted_at", "modified_on", "modified_by"])
    audit.record("VOUCHER_POSTED", voucher, actor=user, number=voucher.number, total=voucher.total,
                 source=f"{voucher.source_type}:{voucher.source_id}:{voucher.source_event}")


@transaction.atomic
def reverse_voucher(voucher: Voucher, *, reversal_date: date | None = None, reason: str, user=None,
                    _system: bool = False) -> Voucher:
    """Post an exact negating voucher and flag the original REVERSED. History is preserved.
    With maker-checker on, a user cannot reverse a voucher they posted (system re-syncs excepted)."""
    if not reason.strip():
        raise AccountingError("A reversal reason is required.", "reason_required")
    voucher = Voucher.objects.select_for_update().select_related("entity").get(pk=voucher.pk)
    if voucher.status != VoucherStatus.POSTED:
        raise AccountingError(f"Only posted vouchers can be reversed (status {voucher.status}).", "not_posted")
    if (not _system and voucher.entity.require_maker_checker and voucher.posted_by_id
            and getattr(user, "pk", None) == voucher.posted_by_id):
        raise AccountingError("Maker-checker: a different user must reverse this voucher.", "maker_checker")
    lines = [LineSpec(ln.account, ln.credit, ln.debit, f"Reversal: {ln.narration}", ln.trade_id, ln.cost_centre_id)
             for ln in voucher.lines.select_related("account")]
    reversal, _ = post_voucher(
        entity=voucher.entity, voucher_type=VoucherType.REVERSAL, voucher_date=reversal_date or voucher.date,
        lines=lines, narration=f"Reversal of {voucher.number}: {reason}", source_type=voucher.source_type,
        source_id=voucher.source_id, source_event=f"REVERSAL:{voucher.pk}", source_version=voucher.source_version,
        user=user, reversal_of=voucher,
    )
    voucher.status = VoucherStatus.REVERSED
    voucher.save(update_fields=["status", "modified_on", "modified_by"])
    audit.record("VOUCHER_REVERSED", voucher, actor=user, reversal=reversal.number, reason=reason)
    return reversal


# --- manual vouchers (journal, contra, opening, adjustment) --------------------------------------

MANUAL_TYPES = (VoucherType.JOURNAL, VoucherType.CONTRA, VoucherType.OPENING, VoucherType.ADJUSTMENT)


@transaction.atomic
def create_draft(*, entity: EntityBooks, voucher_type: str, voucher_date: date, lines: list[LineSpec],
                 narration: str, user=None) -> Voucher:
    if voucher_type not in MANUAL_TYPES:
        raise AccountingError("Only journal, contra, opening and adjustment vouchers are entered manually.",
                              "bad_manual_type")
    lines = _normalise(lines)
    total = validate_lines(entity, lines)
    fy, _ = open_period_for(entity, voucher_date)
    voucher = Voucher.objects.create(
        entity=entity, financial_year=fy, voucher_type=voucher_type, date=voucher_date, narration=narration,
        total=total, source_type="MANUAL", status=VoucherStatus.DRAFT,
        created_by=user if getattr(user, "is_authenticated", False) else None,
    )
    _write_lines(voucher, lines)
    audit.record("VOUCHER_DRAFTED", voucher, actor=user, total=total)
    return voucher


@transaction.atomic
def post_draft(voucher: Voucher, *, user=None) -> Voucher:
    voucher = Voucher.objects.select_for_update().select_related("entity", "financial_year").get(pk=voucher.pk)
    if voucher.status != VoucherStatus.DRAFT:
        raise AccountingError("Voucher is not a draft.", "not_draft")
    entity = voucher.entity
    if entity.require_maker_checker and voucher.created_by_id and getattr(user, "pk", None) == voucher.created_by_id:
        raise AccountingError("Maker-checker: the voucher must be posted by a different user.", "maker_checker")
    lines = [LineSpec(ln.account, ln.debit, ln.credit) for ln in voucher.lines.select_related("account")]
    validate_lines(entity, lines)
    open_period_for(entity, voucher.date)
    voucher.idempotency_key = make_key(entity, "MANUAL", voucher.pk, "POST", "1")
    voucher.source_id = voucher.pk
    voucher.save(update_fields=["idempotency_key", "source_id"])
    _mark_posted(voucher, user)
    return voucher


@transaction.atomic
def delete_draft(voucher: Voucher, *, user=None) -> None:
    voucher = Voucher.objects.select_for_update().get(pk=voucher.pk)
    if voucher.status != VoucherStatus.DRAFT:
        raise AccountingError("Posted vouchers cannot be deleted; reverse them instead.", "posted_immutable")
    audit.record("VOUCHER_DRAFT_DELETED", voucher, actor=user, total=voucher.total)
    voucher.delete()


#: Vouchers owned by a document must be reversed through that document's own service so its
#: status, settlements and bank matches stay consistent (invoice -> reverse_invoice, payment ->
#: reverse_payment, suspense -> resolve, loans/migration -> their services).
DIRECTLY_REVERSIBLE_SOURCES = ("MANUAL", "BANK_OPENING")


def reverse_manual_voucher(voucher: Voucher, *, reason: str, reversal_date: date | None = None, user=None) -> Voucher:
    if voucher.source_type not in DIRECTLY_REVERSIBLE_SOURCES:
        raise AccountingError(
            f"This voucher belongs to a {voucher.source_type.lower().replace('_', ' ')}; reverse it from that document.",
            "document_owned",
        )
    return reverse_voucher(voucher, reason=reason, reversal_date=reversal_date, user=user)
