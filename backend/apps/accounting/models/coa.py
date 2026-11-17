"""Chart of accounts: groups (with report heads) and ledgers."""
from django.db import models

from apps.core.models import AuditModel, CompanyModel

from .books import EntityBooks


class Nature(models.TextChoices):
    ASSET = "ASSET", "Asset"
    LIABILITY = "LIABILITY", "Liability"
    EQUITY = "EQUITY", "Equity"
    INCOME = "INCOME", "Income"
    EXPENSE = "EXPENSE", "Expense"


PL_NATURES = (Nature.INCOME, Nature.EXPENSE)


class ReportHead(models.TextChoices):
    # Profit & Loss
    SALES = "SALES", "Sales"
    SALES_RETURNS = "SALES_RETURNS", "Sales returns"
    PURCHASES = "PURCHASES", "Purchases"
    PURCHASE_RETURNS = "PURCHASE_RETURNS", "Purchase returns"
    STOCK_CHANGE = "STOCK_CHANGE", "Change in stock"
    FREIGHT = "FREIGHT", "Freight"
    INSURANCE = "INSURANCE", "Insurance"
    CUSTOMS = "CUSTOMS", "Customs and clearing"
    COMMISSION_EXPENSE = "COMMISSION_EXPENSE", "Commission paid"
    BANK_CHARGES = "BANK_CHARGES", "Bank charges"
    OPERATING_EXPENSES = "OPERATING_EXPENSES", "Operating expenses"
    INTEREST_EXPENSE = "INTEREST_EXPENSE", "Interest expense"
    FOREX = "FOREX", "Foreign exchange gain/loss"
    COMMISSION_INCOME = "COMMISSION_INCOME", "Commission received"
    INTEREST_INCOME = "INTEREST_INCOME", "Interest income"
    OTHER_INCOME = "OTHER_INCOME", "Other income"
    # Balance sheet
    CAPITAL = "CAPITAL", "Capital / partners' accounts"
    RESERVES = "RESERVES", "Reserves and surplus"
    LOANS_TAKEN = "LOANS_TAKEN", "Borrowings"
    PAYABLES = "PAYABLES", "Trade payables"
    TAX_LIABILITIES = "TAX_LIABILITIES", "Duties and taxes payable"
    OTHER_LIABILITIES = "OTHER_LIABILITIES", "Other current liabilities"
    FIXED_ASSETS = "FIXED_ASSETS", "Fixed assets"
    INVENTORY = "INVENTORY", "Inventory"
    RECEIVABLES = "RECEIVABLES", "Trade receivables"
    LOANS_GIVEN = "LOANS_GIVEN", "Loans and advances given"
    TAX_ASSETS = "TAX_ASSETS", "Tax assets (input GST, TDS receivable)"
    CASH_BANK = "CASH_BANK", "Cash and bank"
    OTHER_ASSETS = "OTHER_ASSETS", "Other current assets"
    SUSPENSE = "SUSPENSE", "Suspense"


class AccountGroup(AuditModel):
    entity = models.ForeignKey(EntityBooks, on_delete=models.PROTECT, related_name="account_groups")
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=128)
    nature = models.CharField(max_length=10, choices=Nature.choices)
    report_head = models.CharField(max_length=24, choices=ReportHead.choices)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="children")
    is_system = models.BooleanField(default=False)

    class Meta:
        ordering = ["code"]
        constraints = [models.UniqueConstraint(fields=["entity", "code"], name="acct_group_unique_code")]

    def __str__(self) -> str:
        return f"{self.code} {self.name}"


class AccountKind(models.TextChoices):
    GENERAL = "GENERAL", "General"
    PARTY = "PARTY", "Party"
    BANK = "BANK", "Bank"
    CASH = "CASH", "Cash"
    TAX = "TAX", "Tax"
    SUSPENSE = "SUSPENSE", "Suspense"
    LOAN = "LOAN", "Loan"


class Account(AuditModel):
    entity = models.ForeignKey(EntityBooks, on_delete=models.PROTECT, related_name="accounts")
    group = models.ForeignKey(AccountGroup, on_delete=models.PROTECT, related_name="accounts")
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=160)
    kind = models.CharField(max_length=10, choices=AccountKind.choices, default=AccountKind.GENERAL)
    system_role = models.CharField(
        max_length=40, null=True, blank=True,
        help_text="Stable role used by posting rules (e.g. SALES, TDS_PAYABLE). Unique per entity.",
    )
    party = models.ForeignKey(CompanyModel, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    intercompany_entity = models.ForeignKey(
        EntityBooks, null=True, blank=True, on_delete=models.PROTECT, related_name="+",
        help_text="Set when this account records dealings with another entity of the group (eliminated on consolidation).",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(fields=["entity", "code"], name="acct_account_unique_code"),
            models.UniqueConstraint(
                fields=["entity", "system_role"], condition=models.Q(system_role__isnull=False),
                name="acct_account_unique_role",
            ),
            models.UniqueConstraint(
                fields=["entity", "party"], condition=models.Q(kind="PARTY"), name="acct_account_unique_party",
            ),
            models.CheckConstraint(
                condition=~models.Q(kind="PARTY") | models.Q(party__isnull=False), name="acct_party_account_has_party",
            ),
        ]
        indexes = [models.Index(fields=["entity", "kind"])]

    def __str__(self) -> str:
        return f"{self.code} {self.name}"
