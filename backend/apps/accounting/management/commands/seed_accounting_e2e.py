"""Seed the deterministic accounting browser scenario (disposable ``test_*`` databases only).

Two own entities with books, a supplier and a customer, purchase / sale / intercompany / commission
trades (not yet posted — the browser test posts them), a bank account with an opening balance, and
three users: an accounts approver, an accounts viewer and a trade-only user (no accounting role).
"""
from __future__ import annotations

import itertools
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from apps.accounting.services.books import activate_books
from apps.accounting.services.payments import create_bank_account
from apps.accounts.models import User
from apps.core.models import CompanyModel
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel
from apps.trade.models import LicenseTrade, LicenseTradeLine

PASSWORD = "e2e-Accounting-2026!"
USERS = {
    "e2e_approver": ["ACCOUNTS_APPROVER", "TRADE_VIEWER"],
    "e2e_viewer": ["ACCOUNTS_VIEWER"],
    "e2e_trade_only": ["TRADE_VIEWER"],
}
_iec = itertools.count(7_700_000_001)


def _company(name: str, gst: str) -> CompanyModel:
    company, _ = CompanyModel.objects.get_or_create(name=name, defaults={"iec": f"{next(_iec):010d}", "gst_number": gst})
    return company


def _trade(direction: str, seller, buyer, amount: str, number: str, on: date, licence_no: str) -> LicenseTrade:
    exporter = seller if direction in ("PURCHASE", "COMMISSION_PURCHASE") else buyer
    lic, _ = LicenseDetailsModel.objects.get_or_create(
        license_number=licence_no,
        defaults={"exporter": exporter, "license_date": date(2026, 4, 1), "license_expiry_date": date(2027, 4, 1)})
    item, _ = LicenseImportItemsModel.objects.get_or_create(license=lic, serial_number=1,
                                                            defaults={"description": "DFIA item"})
    trade = LicenseTrade.objects.create(direction=direction, from_company=seller, to_company=buyer,
                                        invoice_number=number, invoice_date=on)
    value = Decimal(amount)
    LicenseTradeLine.objects.create(trade=trade, sr_number=item, description=f"DFIA {licence_no}",
                                    mode=LicenseTradeLine.MODE_CIF_INR, qty_kg=Decimal("100.0000"), cif_fc=value,
                                    exc_rate=Decimal("1.0000"), cif_inr=value, pct=Decimal("100.000"), amount_inr=value)
    return trade


class Command(BaseCommand):
    help = "Seed the accounting browser E2E scenario into a disposable test_* database."

    def handle(self, *args, **options):
        db_name = str(connection.settings_dict.get("NAME") or "")
        if not db_name.startswith("test_"):
            raise CommandError(f"seed_accounting_e2e only runs against a test_* database; refusing {db_name!r}.")
        with transaction.atomic():
            for username, roles in USERS.items():
                user, _ = User.objects.get_or_create(username=username)
                user.set_password(PASSWORD)
                user.is_active = True
                user.save()
                for role in roles:
                    user.groups.add(Group.objects.get_or_create(name=role)[0])
            lm = _company("E2E Mercantile LLP", "27AAAFE2E01A1Z5")
            lg = _company("E2E Global LLP", "27AAAFE2E02A1Z5")
            supplier = _company("E2E Exporter Pvt Ltd", "27AAACE2E03A1Z5")
            customer = _company("E2E Importer Ltd", "24AAACE2E04A1Z5")
            books = activate_books(lm, date(2026, 4, 1))
            activate_books(lg, date(2026, 4, 1))
            create_bank_account(books, bank_name="E2E Bank", account_number="E2E-001", ifsc="E2EB0000001",
                                opening_balance=Decimal("500000.00"))
            _trade("PURCHASE", supplier, lm, "300000.00", "E2E/PUR/0001", date(2026, 5, 2), "E2E0000001")
            _trade("SALE", lm, customer, "360000.00", "E2E/SAL/0001", date(2026, 5, 9), "E2E0000002")
            _trade("SALE", lm, lg, "50000.00", "E2E/IC/0001", date(2026, 5, 12), "E2E0000003")
            _trade("COMMISSION_SALE", lm, customer, "5000.00", "E2E/COM/0001", date(2026, 5, 15), "E2E0000004")
        self.stdout.write(self.style.SUCCESS("seed_accounting_e2e: scenario ready"))
