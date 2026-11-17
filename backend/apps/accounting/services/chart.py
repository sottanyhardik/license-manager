"""Default chart of accounts (a starting template; the accountant renames/extends it, AD-08).

Only ledgers are seeded — never companies or parties. Idempotent.
"""
from __future__ import annotations

from apps.accounting.models import Account, AccountGroup, AccountKind, EntityBooks, Nature, ReportHead

# (code, name, nature, report_head)
DEFAULT_GROUPS = [
    ("CAP", "Capital / Partners' Accounts", Nature.EQUITY, ReportHead.CAPITAL),
    ("RES", "Reserves and Surplus", Nature.EQUITY, ReportHead.RESERVES),
    ("BRW", "Loans Taken (Borrowings)", Nature.LIABILITY, ReportHead.LOANS_TAKEN),
    ("CRD", "Sundry Creditors", Nature.LIABILITY, ReportHead.PAYABLES),
    ("DTX", "Duties and Taxes", Nature.LIABILITY, ReportHead.TAX_LIABILITIES),
    ("OCL", "Other Current Liabilities", Nature.LIABILITY, ReportHead.OTHER_LIABILITIES),
    ("FXA", "Fixed Assets", Nature.ASSET, ReportHead.FIXED_ASSETS),
    ("STK", "Stock in Hand", Nature.ASSET, ReportHead.INVENTORY),
    ("DBT", "Sundry Debtors", Nature.ASSET, ReportHead.RECEIVABLES),
    ("LNA", "Loans and Advances Given", Nature.ASSET, ReportHead.LOANS_GIVEN),
    ("TXA", "Tax Assets", Nature.ASSET, ReportHead.TAX_ASSETS),
    ("BNK", "Bank Accounts", Nature.ASSET, ReportHead.CASH_BANK),
    ("CSH", "Cash in Hand", Nature.ASSET, ReportHead.CASH_BANK),
    ("OCA", "Other Current Assets", Nature.ASSET, ReportHead.OTHER_ASSETS),
    ("SUS", "Suspense", Nature.ASSET, ReportHead.SUSPENSE),
    ("SAL", "Sales Accounts", Nature.INCOME, ReportHead.SALES),
    ("SRT", "Sales Returns", Nature.INCOME, ReportHead.SALES_RETURNS),
    ("PUR", "Purchase Accounts", Nature.EXPENSE, ReportHead.PURCHASES),
    ("PRT", "Purchase Returns", Nature.EXPENSE, ReportHead.PURCHASE_RETURNS),
    ("STC", "Change in Stock", Nature.EXPENSE, ReportHead.STOCK_CHANGE),
    ("FRT", "Freight", Nature.EXPENSE, ReportHead.FREIGHT),
    ("INS", "Insurance", Nature.EXPENSE, ReportHead.INSURANCE),
    ("CUS", "Customs and Clearing", Nature.EXPENSE, ReportHead.CUSTOMS),
    ("CMX", "Commission Paid", Nature.EXPENSE, ReportHead.COMMISSION_EXPENSE),
    ("BKC", "Bank Charges", Nature.EXPENSE, ReportHead.BANK_CHARGES),
    ("OPX", "Indirect / Operating Expenses", Nature.EXPENSE, ReportHead.OPERATING_EXPENSES),
    ("INX", "Interest Expense", Nature.EXPENSE, ReportHead.INTEREST_EXPENSE),
    ("FXG", "Foreign Exchange Gain/Loss", Nature.INCOME, ReportHead.FOREX),
    ("CMI", "Commission Received", Nature.INCOME, ReportHead.COMMISSION_INCOME),
    ("INI", "Interest Income", Nature.INCOME, ReportHead.INTEREST_INCOME),
    ("OTI", "Other Income", Nature.INCOME, ReportHead.OTHER_INCOME),
]

# (code, name, group_code, kind, system_role)
DEFAULT_ACCOUNTS = [
    ("1001", "Capital Account", "CAP", AccountKind.GENERAL, "CAPITAL"),
    ("1002", "Opening Balance Difference", "RES", AccountKind.GENERAL, "OPENING_DIFFERENCE"),
    ("1003", "Retained Profit (prior years)", "RES", AccountKind.GENERAL, "RETAINED_EARNINGS"),
    ("2101", "Input CGST", "TXA", AccountKind.TAX, "INPUT_CGST"),
    ("2102", "Input SGST", "TXA", AccountKind.TAX, "INPUT_SGST"),
    ("2103", "Input IGST", "TXA", AccountKind.TAX, "INPUT_IGST"),
    ("2104", "TDS Receivable", "TXA", AccountKind.TAX, "TDS_RECEIVABLE"),
    ("2201", "Output CGST", "DTX", AccountKind.TAX, "OUTPUT_CGST"),
    ("2202", "Output SGST", "DTX", AccountKind.TAX, "OUTPUT_SGST"),
    ("2203", "Output IGST", "DTX", AccountKind.TAX, "OUTPUT_IGST"),
    ("2204", "TDS Payable", "DTX", AccountKind.TAX, "TDS_PAYABLE"),
    ("2301", "Closing Stock (Licences)", "STK", AccountKind.GENERAL, "CLOSING_STOCK"),
    ("2401", "Bank Suspense", "SUS", AccountKind.SUSPENSE, "SUSPENSE"),
    ("3001", "Licence Sales", "SAL", AccountKind.GENERAL, "SALES"),
    ("3002", "Intercompany Sales", "SAL", AccountKind.GENERAL, "INTERCOMPANY_SALES"),
    ("3003", "Sales Returns", "SRT", AccountKind.GENERAL, "SALES_RETURNS"),
    ("3101", "Commission Received", "CMI", AccountKind.GENERAL, "COMMISSION_INCOME"),
    ("3201", "Interest Received", "INI", AccountKind.GENERAL, "INTEREST_INCOME"),
    ("3301", "Foreign Exchange Gain/Loss", "FXG", AccountKind.GENERAL, "FOREX"),
    ("3401", "Round Off", "OTI", AccountKind.GENERAL, "ROUND_OFF"),
    ("3402", "Other Income", "OTI", AccountKind.GENERAL, "OTHER_INCOME"),
    ("4001", "Licence Purchases", "PUR", AccountKind.GENERAL, "PURCHASES"),
    ("4002", "Intercompany Purchases", "PUR", AccountKind.GENERAL, "INTERCOMPANY_PURCHASES"),
    ("4003", "Purchase Returns", "PRT", AccountKind.GENERAL, "PURCHASE_RETURNS"),
    ("4004", "Change in Stock", "STC", AccountKind.GENERAL, "STOCK_CHANGE"),
    ("4101", "Freight", "FRT", AccountKind.GENERAL, "FREIGHT"),
    ("4102", "Insurance", "INS", AccountKind.GENERAL, "INSURANCE"),
    ("4103", "Customs and Clearing", "CUS", AccountKind.GENERAL, "CUSTOMS"),
    ("4104", "Port Charges", "CUS", AccountKind.GENERAL, "PORT_CHARGES"),
    ("4201", "Commission Paid", "CMX", AccountKind.GENERAL, "COMMISSION_EXPENSE"),
    ("4202", "Brokerage", "CMX", AccountKind.GENERAL, "BROKERAGE"),
    ("4301", "Bank Charges", "BKC", AccountKind.GENERAL, "BANK_CHARGES"),
    ("4401", "Rent", "OPX", AccountKind.GENERAL, "RENT"),
    ("4402", "Salary", "OPX", AccountKind.GENERAL, "SALARY"),
    ("4403", "Professional Fees", "OPX", AccountKind.GENERAL, "PROFESSIONAL_FEES"),
    ("4404", "Office Expenses", "OPX", AccountKind.GENERAL, "OFFICE_EXPENSES"),
    ("4405", "Travel", "OPX", AccountKind.GENERAL, "TRAVEL"),
    ("4406", "Miscellaneous Expenses", "OPX", AccountKind.GENERAL, "MISC_EXPENSES"),
    ("4501", "Interest Paid", "INX", AccountKind.GENERAL, "INTEREST_EXPENSE"),
]

#: Expense category -> system role (used by the expense entry screen).
EXPENSE_CATEGORY_ROLES = {
    "FREIGHT": "FREIGHT", "INSURANCE": "INSURANCE", "CUSTOMS": "CUSTOMS", "CLEARING": "CUSTOMS",
    "PORT": "PORT_CHARGES", "BROKERAGE": "BROKERAGE", "COMMISSION": "COMMISSION_EXPENSE", "RENT": "RENT",
    "SALARY": "SALARY", "PROFESSIONAL_FEES": "PROFESSIONAL_FEES", "BANK_CHARGES": "BANK_CHARGES",
    "TRAVEL": "TRAVEL", "OFFICE": "OFFICE_EXPENSES", "INTEREST": "INTEREST_EXPENSE", "OTHER": "MISC_EXPENSES",
}


def ensure_default_chart(entity: EntityBooks) -> int:
    """Create any missing default groups/accounts. Returns the number of rows created."""
    created = 0
    groups: dict[str, AccountGroup] = {}
    for code, name, nature, head in DEFAULT_GROUPS:
        group, was_created = AccountGroup.objects.get_or_create(
            entity=entity, code=code,
            defaults={"name": name, "nature": nature, "report_head": head, "is_system": True},
        )
        groups[code] = group
        created += int(was_created)
    for code, name, group_code, kind, role in DEFAULT_ACCOUNTS:
        if Account.objects.filter(entity=entity, system_role=role).exists():
            continue
        Account.objects.create(entity=entity, code=code, name=name, group=groups[group_code], kind=kind, system_role=role)
        created += 1
    return created


def system_account(entity: EntityBooks, role: str) -> Account:
    try:
        return Account.objects.get(entity=entity, system_role=role)
    except Account.DoesNotExist:
        ensure_default_chart(entity)
        return Account.objects.get(entity=entity, system_role=role)


def group(entity: EntityBooks, code: str) -> AccountGroup:
    ensure_default_chart(entity)
    return AccountGroup.objects.get(entity=entity, code=code)


def next_code(entity: EntityBooks, prefix: str) -> str:
    """Next free numeric code under a prefix (party/bank/loan ledgers), e.g. P00012."""
    existing = Account.objects.filter(entity=entity, code__startswith=prefix).values_list("code", flat=True)
    numbers = [int(c[len(prefix):]) for c in existing if c[len(prefix):].isdigit()]
    return f"{prefix}{(max(numbers) + 1 if numbers else 1):05d}"
