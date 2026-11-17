"""Loans given/taken. Principal never touches P&L; interest accrues to its own ledger and to P&L.

Accrual is per calendar month (actual/365), idempotent per (loan, period end), and stops at closure.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction

from apps.accounting.domain.interest import BalanceSegment, accrue, month_end
from apps.accounting.domain.money import ZERO, to_money
from apps.accounting.models import (
    Account, AccountKind, BankAccount, EntityBooks, Loan, LoanAccrual, Voucher, VoucherType,
)
from apps.accounting.selectors.ledger import account_balance, posted_lines
from apps.core.models import CompanyModel

from . import AccountingError, audit
from .chart import group, next_code, system_account
from .posting import cr, dr, post_voucher


@transaction.atomic
def create_loan(*, entity: EntityBooks, party: CompanyModel, direction: str, principal, interest_rate,
                start_date: date, bank_account: BankAccount, maturity_date: date | None = None,
                compound: bool = False, repayment_type: str = "FLEXIBLE", tenure_months: int | None = None,
                loan_type: str = "", disburse: bool = True, user=None) -> Loan:
    if direction not in (Loan.GIVEN, Loan.TAKEN):
        raise AccountingError("Direction must be GIVEN or TAKEN.", "bad_direction")
    if bank_account.entity_id != entity.pk:
        raise AccountingError("The bank account belongs to another entity.", "cross_entity")
    given = direction == Loan.GIVEN
    label = f"{'Loan to' if given else 'Loan from'} {party.name}"
    principal_acct = Account.objects.create(
        entity=entity, group=group(entity, "LNA" if given else "BRW"), code=next_code(entity, "L"),
        name=f"{label} — principal", kind=AccountKind.LOAN, party=None,
    )
    interest_acct = Account.objects.create(
        entity=entity, group=group(entity, "LNA" if given else "OCL"), code=next_code(entity, "L"),
        name=f"{label} — interest {'receivable' if given else 'payable'}", kind=AccountKind.LOAN,
    )
    loan = Loan.objects.create(
        entity=entity, party=party, direction=direction, principal=to_money(principal),
        interest_rate=Decimal(str(interest_rate)), compound=compound, start_date=start_date,
        maturity_date=maturity_date, bank_account=bank_account, principal_account=principal_acct,
        interest_account=interest_acct, repayment_type=repayment_type, tenure_months=tenure_months,
        loan_type=loan_type,
    )
    audit.record("LOAN_CREATED", loan, actor=user, principal=loan.principal, rate=loan.interest_rate)
    if disburse:
        disburse_loan(loan, amount=loan.principal, on=start_date, user=user)
    return loan


@transaction.atomic
def disburse_loan(loan: Loan, *, amount, on: date, user=None):
    loan = Loan.objects.select_for_update().select_related("bank_account__account", "principal_account").get(pk=loan.pk)
    if loan.status == Loan.CLOSED:
        raise AccountingError("The loan is closed.", "loan_closed")
    amount = to_money(amount)
    bank = loan.bank_account.account
    given = loan.direction == Loan.GIVEN
    lines = [dr(loan.principal_account, amount), cr(bank, amount)] if given else \
        [dr(bank, amount), cr(loan.principal_account, amount)]
    voucher, _ = post_voucher(entity=loan.entity, voucher_type=VoucherType.LOAN_DISBURSEMENT, voucher_date=on,
                              lines=lines, narration=f"Loan #{loan.pk} disbursement", source_type="LOAN",
                              source_id=loan.pk, source_event=f"DISBURSE#{_next_event_no(loan, 'DISBURSE')}",
                              user=user)
    return voucher


def _next_event_no(loan: Loan, prefix: str) -> int:
    """Per-loan sequence (caller holds the loan row lock or a fresh loan), so two genuine identical
    repayments on one day are two vouchers, never silently merged."""
    return Voucher.objects.filter(source_type="LOAN", source_id=loan.pk, source_event__startswith=f"{prefix}#").count() + 1


def principal_outstanding(loan: Loan, *, end: date | None = None) -> Decimal:
    bal = account_balance(loan.principal_account, end=end)
    return bal if loan.direction == Loan.GIVEN else -bal


def interest_outstanding(loan: Loan, *, end: date | None = None) -> Decimal:
    bal = account_balance(loan.interest_account, end=end)
    return bal if loan.direction == Loan.GIVEN else -bal


def _segments(loan: Loan, start: date, end: date) -> list[BalanceSegment]:
    """Constant-balance segments in [start, end], split at every principal/interest movement date."""
    change_dates = sorted({ln.voucher.date for ln in posted_lines(loan.entity)
                           .filter(account__in=[loan.principal_account, loan.interest_account],
                                   voucher__date__gt=start, voucher__date__lte=end).select_related("voucher")})
    points = [start] + change_dates + [end + timedelta(days=1)]
    segs = []
    for a, b in zip(points, points[1:]):
        if a >= b:
            continue
        # Interest runs on each day's closing balance (movements dated that day count from that day).
        segs.append(BalanceSegment(a, b - timedelta(days=1), principal_outstanding(loan, end=a),
                                   max(interest_outstanding(loan, end=a), ZERO)))
    return segs


@transaction.atomic
def accrue_interest(loan: Loan, *, period_end: date, user=None) -> LoanAccrual | None:
    """Accrue interest from the day after the last accrual (or the start date) to ``period_end``."""
    loan = Loan.objects.select_for_update().get(pk=loan.pk)
    last = loan.accruals.order_by("-period_end").first()
    start = (last.period_end + timedelta(days=1)) if last else loan.start_date
    if loan.status == Loan.CLOSED and loan.closed_on:
        period_end = min(period_end, loan.closed_on)
    if loan.maturity_date:
        period_end = min(period_end, max(loan.maturity_date, start - timedelta(days=1)))
    existing = loan.accruals.filter(period_end=period_end).first()
    if existing:
        return existing
    if period_end < start:
        return None
    amount = accrue(_segments(loan, start, period_end), loan.interest_rate, loan.compound)
    accrual = LoanAccrual.objects.create(loan=loan, period_start=start, period_end=period_end, amount=amount)
    if amount > 0:
        given = loan.direction == Loan.GIVEN
        pl = system_account(loan.entity, "INTEREST_INCOME" if given else "INTEREST_EXPENSE")
        lines = [dr(loan.interest_account, amount), cr(pl, amount)] if given else \
            [dr(pl, amount), cr(loan.interest_account, amount)]
        voucher, _ = post_voucher(entity=loan.entity, voucher_type=VoucherType.INTEREST_ACCRUAL,
                                  voucher_date=period_end, lines=lines,
                                  narration=f"Interest on loan #{loan.pk} {start:%d-%m-%Y}..{period_end:%d-%m-%Y}",
                                  source_type="LOAN", source_id=loan.pk, source_event=f"ACCRUE:{period_end}",
                                  user=user)
        accrual.voucher = voucher
        accrual.save(update_fields=["voucher"])
    return accrual


def accrue_month_end(on: date, *, user=None) -> int:
    """Run accrual for every active loan up to the month end of ``on`` (Celery-friendly)."""
    n = 0
    for loan in Loan.objects.filter(status=Loan.ACTIVE, start_date__lte=on):
        if accrue_interest(loan, period_end=month_end(on), user=user):
            n += 1
    return n


@transaction.atomic
def record_repayment(loan: Loan, *, on: date, principal=ZERO, interest=ZERO, tds=ZERO, user=None,
                     reference: str = ""):
    """Principal and interest are always separate lines. For loans GIVEN, TDS is what the borrower withheld."""
    principal, interest, tds = to_money(principal), to_money(interest), to_money(tds)
    loan = Loan.objects.select_for_update().get(pk=loan.pk)
    if loan.status == Loan.CLOSED:
        raise AccountingError("The loan is closed.", "loan_closed")
    if principal > principal_outstanding(loan):
        raise AccountingError("Repayment exceeds the principal outstanding.", "over_repayment")
    accrue_interest(loan, period_end=on - timedelta(days=1), user=user)  # interest up to the day before
    bank = loan.bank_account.account
    given = loan.direction == Loan.GIVEN
    cash = principal + interest - tds
    if given:
        lines = [dr(bank, cash), cr(loan.principal_account, principal), cr(loan.interest_account, interest)]
        if tds:
            lines.append(dr(system_account(loan.entity, "TDS_RECEIVABLE"), tds))
    else:
        lines = [cr(bank, cash), dr(loan.principal_account, principal), dr(loan.interest_account, interest)]
        if tds:
            lines.append(cr(system_account(loan.entity, "TDS_PAYABLE"), tds))
    voucher, _ = post_voucher(entity=loan.entity, voucher_type=VoucherType.LOAN_REPAYMENT, voucher_date=on,
                              lines=lines, narration=f"Loan #{loan.pk} repayment {reference}".strip(),
                              source_type="LOAN", source_id=loan.pk,
                              source_event=f"REPAY#{_next_event_no(loan, 'REPAY')}", user=user)
    audit.record("LOAN_REPAYMENT", loan, actor=user, principal=principal, interest=interest, tds=tds)
    return voucher


@transaction.atomic
def close_loan(loan: Loan, *, on: date, user=None) -> Loan:
    loan = Loan.objects.select_for_update().get(pk=loan.pk)
    accrue_interest(loan, period_end=on, user=user)
    if principal_outstanding(loan) != 0 or interest_outstanding(loan) != 0:
        raise AccountingError("Settle principal and interest before closing the loan.", "not_settled")
    loan.status, loan.closed_on = Loan.CLOSED, on
    loan.save(update_fields=["status", "closed_on", "modified_on"])
    audit.record("LOAN_CLOSED", loan, actor=user, on=on)
    return loan
