"""Seed the Licence Ledger payment-ledger browser scenario (disposable ``test_*`` databases only).

Runs ``seed_browser_2509`` (licence 3411008090 / id 2509 with one purchase and one sale trade), then links real
accounting records to those two trades through the existing structural relationships only (never by amount):

* purchase trade: a trade payment of half the invoice (→ Partially paid), an accounting purchase invoice whose line
  references the trade, a POSTED bank payment settled against that invoice and fully matched to a bank statement
  line (→ Reconciled), linked to the trade payment;
* sale trade: a full trade receipt (→ Paid), an accounting sales invoice, a POSTED bank receipt linked to that trade
  receipt with no settlement and no statement match (→ Unreconciled, fully unallocated on the receipt).

Users: ``e2e_ledger_accounts`` (TRADE_VIEWER + ACCOUNTS_VIEWER: sees all three ledgers) and ``e2e_ledger_trade``
(TRADE_VIEWER only: purchase/sale ledgers, no bank ledger). Idempotent.
"""
from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from apps.accounting.models import (
    BankMatch, EntityBooks, Invoice, InvoiceLine, Payment, Settlement, StatementImport, StatementLine, Voucher,
)
from apps.accounting.services.books import activate_books
from apps.accounting.services.payments import create_bank_account
from apps.accounts.models import User
from apps.trade.models import LicenseTrade, LicenseTradePayment

LICENCE_ID = 2509
PASSWORD = "e2e-Ledger-2026!"
USERS = {"e2e_ledger_accounts": ["TRADE_VIEWER", "ACCOUNTS_VIEWER"], "e2e_ledger_trade": ["TRADE_VIEWER"]}
PURCHASE_UTR = "E2E-UTR-PUR-2509"
SALE_UTR = "E2E-UTR-SAL-2509"


def _q2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class Command(BaseCommand):
    help = "Seed the payment-ledger browser scenario (licence 2509) into a disposable test_* database."

    def handle(self, *args, **options):
        db_name = str(connection.settings_dict.get("NAME") or "")
        if not db_name.startswith("test_"):
            raise CommandError(f"seed_payment_ledger_e2e only runs against a test_* database; refusing {db_name!r}.")
        call_command("seed_browser_2509")
        with transaction.atomic():
            for username, roles in USERS.items():
                user, _ = User.objects.get_or_create(username=username, defaults={"email": f"{username}@example.invalid"})
                user.set_password(PASSWORD)
                user.is_active = True
                user.save()
                for role in roles:
                    user.groups.add(Group.objects.get_or_create(name=role)[0])
            if Payment.objects.filter(reference=PURCHASE_UTR).exists():
                self.stdout.write("seed_payment_ledger_e2e: scenario already present")
                return

            trades = LicenseTrade.objects.filter(lines__sr_number__license_id=LICENCE_ID).distinct()
            purchase = trades.filter(direction=LicenseTrade.DIR_PURCHASE).first()
            sale = trades.filter(direction=LicenseTrade.DIR_SALE).first()
            if not purchase or not sale:
                raise CommandError("seed_browser_2509 did not create the purchase and sale trades for licence 2509.")

            us = purchase.to_company
            entity = EntityBooks.objects.filter(pk=us.pk).first() or activate_books(us, date(2026, 4, 1))
            bank = entity.bank_accounts.first() or create_bank_account(
                entity, bank_name="E2E Ledger Bank", account_number="E2E-LEDGER-01", ifsc="E2EB0000002",
                opening_balance=Decimal("0.00"))
            fy = entity.financial_years.first()

            def voucher(kind: str, on: date) -> Voucher:
                # DRAFT: these vouchers only anchor the payment / bank-match links in a disposable test DB (a POSTED
                # voucher must balance, which a line-less anchor cannot) — the ledgers read the payment's own status.
                return Voucher.objects.create(entity=entity, financial_year=fy, voucher_type=kind, date=on,
                                              total=Decimal("1.00"), status="DRAFT")

            def invoice(trade: LicenseTrade, kind: str, party) -> Invoice:
                inv = Invoice.objects.create(entity=entity, kind=kind, party=party, number=trade.invoice_number,
                                             date=trade.invoice_date or date(2026, 5, 1))
                InvoiceLine.objects.create(invoice=inv, line_no=1, account=bank.account, amount=_q2(trade.total_amount),
                                           trade=trade)
                return inv

            # Purchase: half paid, settled bill-wise, matched to the bank statement.
            half = _q2(Decimal(purchase.total_amount) / 2)
            paid_on = date(2026, 6, 1)
            tp_purchase = LicenseTradePayment.objects.create(trade=purchase, date=paid_on, amount=half,
                                                             note="E2E part payment")
            inv_purchase = invoice(purchase, "PURCHASE", purchase.from_company)
            payment = Payment.objects.create(
                entity=entity, direction="PAYMENT", party=purchase.from_company, bank_account=bank, date=paid_on,
                amount=half, reference=PURCHASE_UTR, mode="NEFT", status="POSTED",
                voucher=voucher("PAYMENT", paid_on), trade_payment=tp_purchase)
            Settlement.objects.create(entity=entity, invoice=inv_purchase, voucher=payment.voucher, payment=payment,
                                      amount=half)
            imported = StatementImport.objects.create(bank_account=bank, file_name="e2e-ledger.csv", file_format="csv")
            line = StatementLine.objects.create(bank_account=bank, statement_import=imported, txn_date=paid_on,
                                                reference=PURCHASE_UTR, debit=half, fingerprint="e2e-ledger-pur-2509",
                                                status="MATCHED", matched_amount=half)
            BankMatch.objects.create(statement_line=line, voucher=payment.voucher, amount=half, method="MANUAL")

            # Sale: fully received, receipt linked to the trade receipt only (no settlement, no statement match).
            received_on = date(2026, 6, 5)
            full = _q2(Decimal(sale.total_amount))
            tp_sale = LicenseTradePayment.objects.create(trade=sale, date=received_on, amount=full, note="E2E receipt")
            invoice(sale, "SALES", sale.to_company)
            Payment.objects.create(
                entity=entity, direction="RECEIPT", party=sale.to_company, bank_account=bank, date=received_on,
                amount=full, reference=SALE_UTR, mode="RTGS", status="POSTED",
                voucher=voucher("RECEIPT", received_on), trade_payment=tp_sale)
        self.stdout.write(self.style.SUCCESS("seed_payment_ledger_e2e: scenario ready"))
