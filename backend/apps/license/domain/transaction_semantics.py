"""
Transaction Semantics Definition — Authoritative Classification

This module defines the business semantics for every transaction type used in
the License Manager system. Each transaction type is classified with explicit
rules for balance calculation, visibility, and financial impact.

**AUTHORITATIVE SOURCE:** All ledger calculations must use this definition.
Consumers: canonical_ledger_service, dual_run verification, tests.

**Do NOT modify without approval.** Changes to transaction semantics require
business/technical sign-off.
"""

from enum import Enum
from typing import Dict, Any
from decimal import Decimal


class TransactionDirection(Enum):
    """Direction of transaction flow (PURCHASE vs SALE)."""
    PURCHASE = "PURCHASE"
    SALE = "SALE"


class TransactionSemantics:
    """
    Authoritative definition of transaction behavior in license ledger calculations.

    Each transaction type specifies:
    - affects_license_balance: Whether it changes the license running balance
    - balance_direction: Which way it moves the balance (CREDIT/DEBIT/NONE)
    - visible_in_ledger: Whether it appears in transaction lists
    - commission_treatment: How commission is handled (NORMAL/EXCLUDED)
    - display_status: User-facing marker (e.g., "Excluded from License Balance")
    """

    DEFINITIONS: Dict[str, Dict[str, Any]] = {
        # ========== OPENING ==========
        # The initial balance of a license. Not a transaction, a state snapshot.
        "OPENING": {
            "affects_license_balance": True,
            "affects_company_utilization": False,  # Opening is not company-scoped
            "balance_direction": "CREDIT",  # Adds to available balance
            "visible_in_ledger": True,
            "is_balance_affecting": True,  # Used by canonical calculator
            "commission_treatment": "NORMAL",
            "display_status": "Opening Balance",
            "description": "Initial license balance at issuance",
            "business_meaning": "Sets the license' starting financial position",
        },

        # ========== PURCHASE ==========
        # Import/purchase transaction: company buys goods, license is debited.
        # PURCHASE increases available balance (credit to the license).
        "PURCHASE": {
            "affects_license_balance": True,
            "affects_company_utilization": True,
            "balance_direction": "CREDIT",  # Adds to license balance
            "visible_in_ledger": True,
            "is_balance_affecting": True,  # Used by canonical calculator
            "commission_treatment": "NORMAL",
            "display_status": None,  # Normal transaction, no marker
            "description": "Import/purchase transaction",
            "business_meaning": "Company purchases goods; increases available license balance",
        },

        # ========== SALE ==========
        # Export/sale transaction: company sells goods, license is credited.
        # SALE decreases available balance (debit from the license).
        "SALE": {
            "affects_license_balance": True,
            "affects_company_utilization": True,
            "balance_direction": "DEBIT",  # Removes from license balance
            "visible_in_ledger": True,
            "is_balance_affecting": True,  # Used by canonical calculator
            "commission_treatment": "NORMAL",
            "display_status": None,  # Normal transaction, no marker
            "description": "Export/sale transaction",
            "business_meaning": "Company sells goods; decreases available license balance",
        },

        # ========== COMMISSION ==========
        # Internal administrative charge/fee. APPROVED SEMANTICS (Gate 3):
        # COMMISSION is visible for auditability but NOT counted in balance.
        # This is non-negotiable per LEDGER_APPROVED_SEMANTICS.md.
        "COMMISSION": {
            "affects_license_balance": False,  # APPROVED: Not counted
            "affects_company_utilization": False,  # APPROVED: Not counted
            "balance_direction": "NONE",
            "visible_in_ledger": True,  # Must be visible for audits
            "is_balance_affecting": False,  # Excluded from balance
            "commission_treatment": "EXCLUDED",
            "display_status": "Excluded from License Balance",
            "description": "Commission/administrative charge (internal)",
            "business_meaning": (
                "Internal administrative fee or charge. Not a balance-affecting transaction. "
                "Visible for auditability only. Approved per business decision (Gate 3)."
            ),
        },

        # ========== COMMISSION_PURCHASE ==========
        # Commission variant of purchase. Legacy naming from trade.direction choices.
        # Semantics: same as COMMISSION (excluded from balance).
        "COMMISSION_PURCHASE": {
            "affects_license_balance": False,  # Excluded
            "affects_company_utilization": False,  # Excluded
            "balance_direction": "NONE",
            "visible_in_ledger": True,
            "is_balance_affecting": False,
            "commission_treatment": "EXCLUDED",
            "display_status": "Excluded from License Balance",
            "description": "Commission on purchase (internal)",
            "business_meaning": "Administrative fee on purchase transaction. Excluded from balance.",
        },

        # ========== COMMISSION_SALE ==========
        # Commission variant of sale. Legacy naming from trade.direction choices.
        # Semantics: same as COMMISSION (excluded from balance).
        "COMMISSION_SALE": {
            "affects_license_balance": False,  # Excluded
            "affects_company_utilization": False,  # Excluded
            "balance_direction": "NONE",
            "visible_in_ledger": True,
            "is_balance_affecting": False,
            "commission_treatment": "EXCLUDED",
            "display_status": "Excluded from License Balance",
            "description": "Commission on sale (internal)",
            "business_meaning": "Administrative fee on sale transaction. Excluded from balance.",
        },
    }

    @classmethod
    def get_semantics(cls, transaction_type: str) -> Dict[str, Any]:
        """
        Get semantics definition for a transaction type.

        Args:
            transaction_type: Transaction type key (e.g., 'PURCHASE', 'SALE', 'COMMISSION')

        Returns:
            Dict of semantics (affects_license_balance, balance_direction, etc.)

        Raises:
            KeyError: If transaction type is not defined
        """
        if transaction_type not in cls.DEFINITIONS:
            raise KeyError(
                f"Unknown transaction type: {transaction_type}. "
                f"Valid types: {', '.join(cls.DEFINITIONS.keys())}"
            )
        return cls.DEFINITIONS[transaction_type]

    @classmethod
    def is_balance_affecting(cls, transaction_type: str) -> bool:
        """
        Check if a transaction type affects the license running balance.

        Args:
            transaction_type: Transaction type (e.g., 'PURCHASE')

        Returns:
            True if transaction should be counted in balance calculation

        Note:
            COMMISSION and COMMISSION_* types return False (excluded by approved semantics)
        """
        semantics = cls.get_semantics(transaction_type)
        return semantics.get("is_balance_affecting", False)

    @classmethod
    def get_balance_direction(cls, transaction_type: str) -> str:
        """
        Get the balance direction for a transaction type.

        Args:
            transaction_type: Transaction type

        Returns:
            'CREDIT' (adds to balance), 'DEBIT' (removes), or 'NONE' (no impact)
        """
        semantics = cls.get_semantics(transaction_type)
        return semantics.get("balance_direction", "NONE")

    @classmethod
    def is_commission(cls, transaction_type: str) -> bool:
        """
        Check if a transaction is commission-type.

        Args:
            transaction_type: Transaction type

        Returns:
            True if type is COMMISSION, COMMISSION_PURCHASE, or COMMISSION_SALE
        """
        return transaction_type in {"COMMISSION", "COMMISSION_PURCHASE", "COMMISSION_SALE"}

    @classmethod
    def is_visible(cls, transaction_type: str) -> bool:
        """
        Check if a transaction should be visible in ledger reports.

        Args:
            transaction_type: Transaction type

        Returns:
            True if transaction should appear in screens, PDF, Excel
        """
        semantics = cls.get_semantics(transaction_type)
        return semantics.get("visible_in_ledger", False)

    @classmethod
    def get_display_status(cls, transaction_type: str) -> str:
        """
        Get user-facing status marker for a transaction type.

        Args:
            transaction_type: Transaction type

        Returns:
            Display string (e.g., "Excluded from License Balance") or None
        """
        semantics = cls.get_semantics(transaction_type)
        return semantics.get("display_status")

    @classmethod
    def validate_transaction_type(cls, transaction_type: str) -> bool:
        """
        Validate that a transaction type is defined.

        Args:
            transaction_type: Transaction type to validate

        Returns:
            True if type is valid, False otherwise
        """
        return transaction_type in cls.DEFINITIONS

    @classmethod
    def all_types(cls) -> list[str]:
        """Get list of all defined transaction types."""
        return list(cls.DEFINITIONS.keys())

    @classmethod
    def balance_affecting_types(cls) -> list[str]:
        """Get list of transaction types that affect balance."""
        return [
            txn_type for txn_type in cls.DEFINITIONS
            if cls.is_balance_affecting(txn_type)
        ]

    @classmethod
    def commission_types(cls) -> list[str]:
        """Get list of commission transaction types."""
        return [
            txn_type for txn_type in cls.DEFINITIONS
            if cls.is_commission(txn_type)
        ]


# Convenience constants for common operations

# Transaction types that should be counted in balance calculation
BALANCE_AFFECTING_TYPES = TransactionSemantics.balance_affecting_types()

# Commission types that should be excluded
COMMISSION_TYPES = TransactionSemantics.commission_types()

# All transaction types
ALL_TRANSACTION_TYPES = TransactionSemantics.all_types()


def apply_transaction_to_balance(
    current_balance: Decimal,
    transaction_type: str,
    amount: Decimal,
) -> Decimal:
    """
    Apply a transaction to a balance using approved semantics.

    Args:
        current_balance: Current balance (Decimal)
        transaction_type: Transaction type (e.g., 'PURCHASE', 'SALE')
        amount: Transaction amount (Decimal)

    Returns:
        New balance after applying transaction

    Example:
        >>> balance = Decimal("1000.00")
        >>> balance = apply_transaction_to_balance(balance, "PURCHASE", Decimal("500.00"))
        >>> balance
        Decimal('1500.00')

        >>> balance = apply_transaction_to_balance(balance, "COMMISSION", Decimal("100.00"))
        >>> balance  # COMMISSION doesn't change balance
        Decimal('1500.00')
    """
    # Only apply if transaction affects balance
    if not TransactionSemantics.is_balance_affecting(transaction_type):
        return current_balance

    direction = TransactionSemantics.get_balance_direction(transaction_type)

    if direction == "CREDIT":
        return current_balance + amount
    elif direction == "DEBIT":
        return current_balance - amount
    else:
        return current_balance


# ========== VALIDATION & DOCUMENTATION ==========
# This section documents the semantics contract for integration tests.

"""
LEDGER CALCULATION CONTRACT
============================

This contract defines how transactions flow through the license ledger calculation:

1. OPENING Transaction
   - Sets initial balance
   - Counted in license running balance
   - Not company-scoped (no utilization per company)
   - Visible in ledger

2. PURCHASE Transaction (Company X)
   - Company imports/purchases goods
   - Increases license running balance (+)
   - Company X utilization increases (+)
   - Visible in ledger

3. SALE Transaction (Company X)
   - Company exports/sells goods
   - Decreases license running balance (-)
   - Company X utilization decreases (-)
   - Visible in ledger

4. COMMISSION Transaction (Company X)
   - Administrative fee or internal charge
   - Does NOT affect license running balance (excluded by policy)
   - Does NOT affect company utilization (excluded by policy)
   - Visible in ledger with marker "Excluded from License Balance"
   - **APPROVED SEMANTICS** (Gate 3 business decision, non-negotiable)

License Running Balance Formula:
================================
Running Balance = Opening + SUM(PURCHASE amounts) - SUM(SALE amounts)
                  (COMMISSION excluded from sum)

Company Utilization Formula:
=============================
For each company:
Company Util = SUM(PURCHASE for that company) - SUM(SALE for that company)
               (COMMISSION excluded, reset to zero for that company)

Critical Properties:
====================
- COMMISSION is visible in all ledger outputs (auditability)
- COMMISSION is NOT counted in any balance calculation (policy)
- Company utilizations are independent (isolated calculations)
- SUM(Company Utilizations) ≠ License Running Balance (by design)
- All balances use Decimal type with 2 decimal places
- Transaction ordering is deterministic (date ASC, ID ASC)

Testing:
========
Every golden scenario test must verify:
1. Balance-affecting transactions counted correctly
2. COMMISSION excluded from balance
3. Company utilizations calculated independently
4. Decimal precision maintained (2 places)
5. Deterministic ordering
"""
