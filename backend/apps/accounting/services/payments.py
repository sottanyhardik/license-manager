"""Bank accounts, payments and receipts, bill-wise allocation, advances, linking existing trade payments."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from apps.accounting.domain.money import ZERO, to_money
from apps.accounting.models import (
    PAYABLE_KINDS, RECEIVABLE_KINDS, Account, AccountKind, BankAccount, BankMatch, DocStatus, EntityBooks, Invoice,
    Payment, PaymentDirection, StatementLine, VoucherType,
)
from apps.core.models import CompanyModel

from . import AccountingError, audit
from .books import party_account
from .chart import group, next_code, system_account
from .invoices import allocate, outstanding
from .posting import cr, dr, post_voucher, reverse_voucher


@transaction.atomic
def create_bank_account(entity: EntityBooks, *, bank_name: str, account_number: str, ifsc: str = "",
                        is_cash: bool = False, opening_balance: Decimal | None = None,
                        opening_date: date | None = None, user=None) -> BankAccount:
    if BankAccount.objects.filter(entity=entity, account_number=account_number).exists():
        raise AccountingError("This bank account already exists for the entity.", "duplicate_bank")
    account = Account.objects.create(
        entity=entity, group=group(entity, "CSH" if is_cash else "BNK"), code=next_code(entity, "B"),
        name=f"{bank_name} {account_number}".strip(), kind=AccountKind.CASH if is_cash else AccountKind.BANK,
    )
    bank = BankAccount.objects.create(entity=entity, account=account, bank_name=bank_name,
                                      account_number=account_number, ifsc=ifsc, is_cash=is_cash)
    opening = to_money(opening_balance) if opening_balance is not None else ZERO
    if opening:
        diff = system_account(entity, "OPENING_DIFFERENCE")
        lines = [dr(account, opening), cr(diff, opening)] if opening > 0 else [dr(diff, -opening), cr(account, -opening)]
        post_voucher(entity=entity, voucher_type=VoucherType.OPENING, voucher_date=opening_date or entity.books_start_date,
                     lines=lines, narration=f"Opening balance {bank}", source_type="BANK_OPENING", source_id=bank.pk,
                     user=user)
    audit.record("BANK_ACCOUNT_CREATED", bank, actor=user, entity=entity, opening=opening)
    return bank


def check_direction(direction: str, invoice: Invoice) -> None:
    ok = invoice.kind in PAYABLE_KINDS if direction == PaymentDirection.PAYMENT else invoice.kind in RECEIVABLE_KINDS
    if not ok:
        raise AccountingError(f"A {direction.lower()} cannot settle a {invoice.get_kind_display().lower()}.",
                              "direction_mismatch")


@transaction.atomic
def record_payment(*, entity: EntityBooks, direction: str, party: CompanyModel, bank_account: BankAccount,
                   payment_date: date, amount, tds_amount=ZERO, mode: str = "NEFT", reference: str = "",
                   narration: str = "", allocations: list[tuple[Invoice, Decimal]] | None = None,
                   trade_payment_id: int | None = None, user=None) -> Payment:
    """Create, post and allocate a payment/receipt in one transaction."""
    amount, tds_amount = to_money(amount), to_money(tds_amount)
    if direction not in PaymentDirection.values:
        raise AccountingError("Direction must be PAYMENT or RECEIPT.", "bad_direction")
    if bank_account.entity_id != entity.pk:
        raise AccountingError("The bank account belongs to another entity.", "cross_entity")
    if amount <= 0:
        raise AccountingError("Amount must be positive.", "bad_amount")
    if tds_amount and direction != PaymentDirection.RECEIPT:
        raise AccountingError("TDS on payments is deducted on the purchase bill, not on the payment.", "tds_on_payment")
    allocations = allocations or []
    for invoice, _amt in allocations:
        if invoice.party_id != party.pk or invoice.entity_id != entity.pk:
            raise AccountingError(f"Bill {invoice.number} belongs to another party or entity.", "party_mismatch")
        check_direction(direction, invoice)
    if sum((to_money(a) for _i, a in allocations), ZERO) > amount + tds_amount:
        raise AccountingError("Allocations exceed the payment amount.", "over_allocation")

    payment = Payment.objects.create(
        entity=entity, direction=direction, party=party, bank_account=bank_account, date=payment_date, amount=amount,
        tds_amount=tds_amount, mode=mode, reference=reference.strip(), narration=narration,
        trade_payment_id=trade_payment_id,
    )
    payable_side = direction == PaymentDirection.PAYMENT
    party_acct = party_account(entity, party, payable=payable_side)
    bank = bank_account.account
    label = f"{'Paid to' if payable_side else 'Received from'} {party.name} {reference}".strip()
    if payable_side:
        lines = [dr(party_acct, amount, label), cr(bank, amount, label)]
    else:
        lines = [dr(bank, amount, label), cr(party_acct, amount + tds_amount, label)]
        if tds_amount:
            lines.append(dr(system_account(entity, "TDS_RECEIVABLE"), tds_amount, "TDS deducted by customer"))
    voucher, _ = post_voucher(
        entity=entity, voucher_type=VoucherType.PAYMENT if payable_side else VoucherType.RECEIPT,
        voucher_date=payment_date, lines=lines, narration=narration or label, source_type="PAYMENT",
        source_id=payment.pk, user=user,
    )
    payment.voucher, payment.status = voucher, DocStatus.POSTED
    payment.save(update_fields=["voucher", "status", "modified_on"])
    for invoice, amt in allocations:
        allocate(invoice, voucher, amt, payment=payment, user=user)
    audit.record("PAYMENT_POSTED", payment, actor=user, voucher=voucher.number, amount=amount)
    return payment


def unallocated(payment: Payment) -> Decimal:
    used = payment.settlements.filter(is_active=True).aggregate(t=Sum("amount"))["t"] or ZERO
    return payment.party_amount - used


@transaction.atomic
def allocate_payment(payment: Payment, invoice: Invoice, amount, *, user=None):
    """Allocate an advance / on-account amount to a bill later."""
    payment = Payment.objects.select_for_update().get(pk=payment.pk)
    amount = to_money(amount)
    if payment.status != DocStatus.POSTED:
        raise AccountingError("The payment is not posted.", "not_posted")
    if invoice.party_id != payment.party_id or invoice.entity_id != payment.entity_id:
        raise AccountingError("Bill and payment belong to different parties or entities.", "party_mismatch")
    check_direction(payment.direction, invoice)
    if amount > unallocated(payment):
        raise AccountingError(f"Only {unallocated(payment)} of this payment is unallocated.", "over_allocation")
    return allocate(invoice, payment.voucher, amount, payment=payment, user=user)


@transaction.atomic
def reverse_payment(payment: Payment, *, reason: str, user=None, reversal_date: date | None = None) -> Payment:
    payment = Payment.objects.select_for_update().get(pk=payment.pk)
    if payment.status != DocStatus.POSTED:
        raise AccountingError("Only posted payments can be reversed.", "not_posted")
    reverse_voucher(payment.voucher, reversal_date=reversal_date, reason=reason, user=user)
    payment.settlements.filter(is_active=True).update(is_active=False)
    lines = list(StatementLine.objects.filter(matches__voucher=payment.voucher, matches__is_active=True).distinct())
    BankMatch.objects.filter(voucher=payment.voucher, is_active=True).update(is_active=False)
    from .banking import refresh_line_status
    for line in lines:  # those statement lines are unmatched again and must reappear in the workbench/BRS
        refresh_line_status(line)
    payment.status = DocStatus.REVERSED
    payment.save(update_fields=["status", "modified_on"])
    audit.record("PAYMENT_REVERSED", payment, actor=user, reason=reason)
    return payment


@transaction.atomic
def account_trade_payment(trade_payment_id: int, *, bank_account: BankAccount, user=None) -> Payment:
    """Account an existing LicenseTradePayment exactly once and settle it against the trade's bill."""
    existing = Payment.objects.filter(trade_payment_id=trade_payment_id).first()
    if existing:
        return existing
    from apps.trade.models import LicenseTradePayment
    tp = LicenseTradePayment.objects.select_related("trade").get(pk=trade_payment_id)
    invoice = Invoice.objects.filter(trade_id=tp.trade_id).first()
    if invoice is None or invoice.status != DocStatus.POSTED:
        raise AccountingError("Post the trade's invoice before accounting its payments.", "invoice_not_posted")
    if bank_account.entity_id != invoice.entity_id:
        raise AccountingError("The bank account belongs to another entity.", "cross_entity")
    direction = PaymentDirection.PAYMENT if invoice.kind in PAYABLE_KINDS else PaymentDirection.RECEIPT
    alloc = min(to_money(tp.amount), outstanding(invoice))
    return record_payment(
        entity=invoice.entity, direction=direction, party=invoice.party, bank_account=bank_account,
        payment_date=tp.date, amount=tp.amount, reference="", mode="OTHER",
        narration=f"Trade payment #{tp.pk} on {invoice.number}: {tp.note}".strip(),
        allocations=[(invoice, alloc)] if alloc > 0 else [], trade_payment_id=tp.pk, user=user,
    )
