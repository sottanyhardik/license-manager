"""Bank accounts, payments and receipts, bill-wise allocation, advances, linking existing trade payments."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from apps.accounting.domain.money import ZERO, to_money
from apps.accounting.models import (
    PAYABLE_KINDS, RECEIVABLE_KINDS, Account, AccountKind, BankAccount, DocStatus, EntityBooks, Invoice,
    Payment, PaymentDirection, VoucherType,
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
    if tds_amount and any(inv.tds_amount for inv, _a in allocations):
        raise AccountingError("TDS on this bill is already booked on the invoice; do not enter it again on the receipt.",
                              "tds_already_on_bill")

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
    # Bank matches are kept: the bank really moved (e.g. a cheque that later bounced). The reversal
    # voucher is a new book entry that matches the bank's return line; a payment and its reversal
    # that never reached the bank net off in the reconciliation (see banking.unmatched_book_vouchers).
    payment.status = DocStatus.REVERSED
    payment.save(update_fields=["status", "modified_on"])
    audit.record("PAYMENT_REVERSED", payment, actor=user, reason=reason)
    return payment


@transaction.atomic
def account_trade_payment(trade_payment_id: int, *, bank_account: BankAccount | None, user=None,
                          existing_payment: Payment | None = None) -> Payment:
    """Account an existing LicenseTradePayment exactly once.

    * Normal case: post a payment/receipt and settle it against the trade's posted bill.
    * The same cash was already entered as a manual payment/receipt (``existing_payment``): link it,
      post nothing (never count the cash twice).
    * The bill is already settled by other documents: refuse with ``possible_duplicate`` instead of
      posting the cash again as an unexplained advance.
    * Trade dated before books start (covered by opening balances) but paid within the books
      period: post on account against the party (no bill to settle).
    """
    linked = Payment.objects.filter(trade_payment_id=trade_payment_id).first()
    if linked:
        return linked
    from apps.trade.models import LicenseTradePayment

    from .invoices import entity_for_trade
    tp = LicenseTradePayment.objects.select_related("trade").get(pk=trade_payment_id)
    invoice = Invoice.objects.filter(trade_id=tp.trade_id, status=DocStatus.POSTED).first()
    entity = invoice.entity if invoice else entity_for_trade(tp.trade)
    if entity is None:
        raise AccountingError("The trade's own company has no active books.", "no_books")
    if existing_payment is not None:
        return _link_existing(tp, existing_payment, entity, user)
    if bank_account is None or bank_account.entity_id != entity.pk:
        raise AccountingError("Choose a bank account of this entity.", "cross_entity")
    if tp.date < entity.books_start_date:
        raise AccountingError("This trade payment is dated before the books start; it is in the opening balances.",
                              "before_books_start")
    amount = to_money(tp.amount)
    if invoice is None:
        trade_date = tp.trade.invoice_date
        if trade_date is None or trade_date >= entity.books_start_date:
            raise AccountingError("Post the trade's invoice before accounting its payments.", "invoice_not_posted")
        return _post_on_account(tp, entity, bank_account, amount, user)
    due = outstanding(invoice)
    if amount > due:
        raise AccountingError(
            f"The bill {invoice.number} has only {due} outstanding; this {amount} may already be recorded as a "
            "separate payment/receipt. Link that document instead of posting the cash again.", "possible_duplicate")
    direction = PaymentDirection.PAYMENT if invoice.kind in PAYABLE_KINDS else PaymentDirection.RECEIPT
    return record_payment(
        entity=entity, direction=direction, party=invoice.party, bank_account=bank_account,
        payment_date=tp.date, amount=amount, reference="", mode="OTHER",
        narration=f"Trade payment #{tp.pk} on {invoice.number}: {tp.note}".strip(),
        allocations=[(invoice, amount)], trade_payment_id=tp.pk, user=user,
    )


def _trade_direction(trade) -> str:
    return PaymentDirection.PAYMENT if trade.direction in ("PURCHASE", "COMMISSION_PURCHASE") else PaymentDirection.RECEIPT


def _link_existing(tp, payment: Payment, entity: EntityBooks, user) -> Payment:
    payment = Payment.objects.select_for_update().get(pk=payment.pk)
    from apps.accounting.selectors.trade_source import view_of
    view = view_of(tp.trade)
    if payment.entity_id != entity.pk or payment.party_id != view.party_company_id:
        raise AccountingError("The payment belongs to another entity or party.", "party_mismatch")
    if payment.direction != _trade_direction(tp.trade) or payment.status != DocStatus.POSTED:
        raise AccountingError("The payment's direction/status does not fit this trade payment.", "direction_mismatch")
    if payment.trade_payment_id:
        raise AccountingError("That payment is already linked to another trade payment.", "already_linked")
    if payment.amount != to_money(tp.amount):
        raise AccountingError("Amounts differ; link only the document that records this exact cash.", "amount_mismatch")
    Payment.objects.filter(pk=payment.pk).update(trade_payment_id=tp.pk)
    payment.trade_payment_id = tp.pk
    audit.record("TRADE_PAYMENT_LINKED", payment, actor=user, trade_payment=tp.pk)
    return payment


def _post_on_account(tp, entity: EntityBooks, bank_account: BankAccount, amount: Decimal, user) -> Payment:
    from apps.accounting.selectors.trade_source import view_of
    view = view_of(tp.trade)
    if not view.party_company_id:
        raise AccountingError("The trade has no counterparty company.", "no_party")
    return record_payment(
        entity=entity, direction=_trade_direction(tp.trade), party=CompanyModel.objects.get(pk=view.party_company_id),
        bank_account=bank_account, payment_date=tp.date, amount=amount, mode="OTHER",
        narration=f"Trade payment #{tp.pk} on pre-books trade {view.invoice_number} (on account; bill is in "
                  f"opening balances): {tp.note}".strip(),
        trade_payment_id=tp.pk, user=user,
    )


# --- on-account amounts from any settling voucher (e.g. suspense reclassified to a party) ---------

def voucher_party_unallocated(voucher, party_account_obj, *, receipt_side: bool) -> Decimal:
    """Party-side amount of ``voucher`` not yet allocated to bills."""
    from django.db.models import Sum as _Sum
    agg = voucher.lines.filter(account=party_account_obj).aggregate(d=_Sum("debit"), c=_Sum("credit"))
    side = (agg["c"] or ZERO) - (agg["d"] or ZERO) if receipt_side else (agg["d"] or ZERO) - (agg["c"] or ZERO)
    used = voucher.settlements.filter(is_active=True).aggregate(t=_Sum("amount"))["t"] or ZERO
    return side - used


@transaction.atomic
def allocate_on_account(voucher, invoice: Invoice, amount, *, user=None):
    """Allocate the on-account part of a posted settling voucher (journal/suspense reclassification)."""
    from apps.accounting.models import Voucher, VoucherStatus
    voucher = Voucher.objects.select_for_update().get(pk=voucher.pk)
    amount = to_money(amount)
    if voucher.status != VoucherStatus.POSTED or voucher.entity_id != invoice.entity_id:
        raise AccountingError("The voucher is not a posted voucher of this entity.", "not_posted")
    payment = Payment.objects.filter(voucher=voucher).first()
    if payment:
        return allocate_payment(payment, invoice, amount, user=user)
    receipt_side = invoice.kind in RECEIVABLE_KINDS
    acct = party_account(invoice.entity, invoice.party, payable=not receipt_side)
    free = voucher_party_unallocated(voucher, acct, receipt_side=receipt_side)
    if amount > free:
        raise AccountingError(f"Only {free} of this voucher is unallocated for {invoice.party.name}.", "over_allocation")
    return allocate(invoice, voucher, amount, user=user)
