"""
Canonical Ledger Service — Single Authoritative Source for License Ledger Calculations

This service implements the approved semantics (Gate 3, Option C) for license ledger
calculations. It is the ONLY authoritative source for ledger data. All consumers
(API, screens, PDF, Excel) must use this service or receive pre-calculated results.

**Responsibilities:**
- Fetch transactions from database
- Normalize transaction data
- Classify using TransactionSemantics
- Calculate license running balance (deterministic order)
- Calculate company utilization (independent, per-company)
- Handle COMMISSION exclusion (approved policy)
- Return canonical dataset

**Non-Responsibilities:**
- HTTP/REST logic (API views handle this)
- UI rendering (views and templates handle this)
- PDF/Excel formatting (exporters handle this)
- Authentication (assume caller is authorized)
- Database writes (read-only)

**Consumers (Phase 4C+):**
- LicenseLedgerViewSet (API endpoint)
- Ledger screens (frontend data fetching)
- PDF exporters (ledger_pdf.py)
- Excel exporters (license_balance_excel.py)

**Tested Against:**
- All 14 golden scenarios (LEDGER_GOLDEN_DATASET.md)
- Dual-run verification vs. legacy implementation
- Real-data shadow verification
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Dict, List, Any
from datetime import date as date_type

from django.db.models import Q, Sum, Value, DecimalField
from django.db.models.functions import Coalesce

from apps.license.domain.transaction_semantics import TransactionSemantics
from apps.license.models import LicenseDetailsModel, IncentiveLicense
from apps.trade.models import LicenseTrade
from apps.core.utils.decimal_utils import to_decimal
from apps.core.constants import DEC_0


DECIMAL_2DP = Decimal("0.01")


def quantize_2dp(value: Decimal) -> Decimal:
    """Quantize decimal value to 2 decimal places using ROUND_HALF_UP."""
    return to_decimal(value, DEC_0).quantize(DECIMAL_2DP, rounding=ROUND_HALF_UP)


class CanonicalLedgerService:
    """
    Single authoritative source for License Ledger calculations.

    Implements approved semantics:
    - PURCHASE: increases balance
    - SALE: decreases balance
    - COMMISSION: visible but excluded from balance
    - OPENING: sets initial balance
    """

    @staticmethod
    def build_canonical_ledger_dataset(license_id: int, license_type: str = "DFIA") -> Dict[str, Any]:
        """
        Build the authoritative ledger dataset for a license.

        This is the ONLY method that should be called by external consumers.
        It returns a complete, deterministically-calculated ledger dataset.

        Args:
            license_id: License ID (LicenseDetailsModel or IncentiveLicense)
            license_type: License type (DFIA, INCENTIVE, RODTEP, ROSTL, MEIS)

        Returns:
            Dict with structure:
            {
                'license_id': int,
                'license_type': str,
                'opening_balance': Decimal,
                'license_running_balance': Decimal,  # Final balance
                'closing_balance': Decimal,  # Same as running_balance
                'transactions': [
                    {
                        'date': date,
                        'id': int (transaction ID),
                        'type': str,  # OPENING, PURCHASE, SALE, COMMISSION
                        'company_id': int or None,
                        'company_name': str or None,
                        'amount': Decimal,
                        'is_commission': bool,
                        'license_running_balance': Decimal,  # Running balance after this txn
                        'company_utilization_after': Decimal,  # Company util after (if company-scoped)
                    },
                    ...
                ],
                'company_utilizations': [
                    {
                        'company_id': int,
                        'company_name': str,
                        'utilization_balance': Decimal,
                    },
                    ...
                ],
                'totals': {
                    'total_purchases': Decimal,
                    'total_sales': Decimal,
                    'total_commission': Decimal,
                }
            }

        Raises:
            ValueError: If license_id not found or invalid license_type
        """
        # Fetch license object
        license_obj = _get_license_object(license_id, license_type)
        if not license_obj:
            raise ValueError(f"License {license_id} (type {license_type}) not found")

        # Build dataset
        dataset = {
            'license_id': license_id,
            'license_type': license_type,
            'opening_balance': Decimal('0.00'),
            'license_running_balance': Decimal('0.00'),
            'closing_balance': Decimal('0.00'),
            'transactions': [],
            'company_utilizations': {},
            'totals': {
                'total_purchases': Decimal('0.00'),
                'total_sales': Decimal('0.00'),
                'total_commission': Decimal('0.00'),
            }
        }

        # Fetch and normalize transactions
        raw_transactions = _fetch_transactions(license_obj, license_type)

        # Calculate opening balance (if any)
        opening_balance = quantize_2dp(
            to_decimal(getattr(license_obj, 'opening_balance', None), DEC_0)
        )
        if opening_balance > DEC_0:
            dataset['opening_balance'] = opening_balance

        # Process transactions in deterministic order (date, then ID)
        running_balance = opening_balance
        company_balances: Dict[int, Decimal] = {}  # Track per-company balances

        # Add opening transaction first (if opening balance exists)
        if opening_balance > DEC_0:
            dataset['transactions'].append({
                'date': license_obj.license_date if hasattr(license_obj, 'license_date') else None,
                'id': 0,  # Opening is transaction 0
                'type': 'OPENING',
                'company_id': None,
                'company_name': None,
                'amount': opening_balance,
                'is_commission': False,
                'license_running_balance': running_balance,
                'affects_balance': True,
            })

        # Process all other transactions
        for txn_data in raw_transactions:
            txn_type = txn_data['type']
            company_id = txn_data.get('company_id')
            company_name = txn_data.get('company_name')
            amount = txn_data.get('amount', Decimal('0.00'))
            txn_date = txn_data.get('date')
            txn_id = txn_data.get('id')

            # Quantize amount to 2dp
            amount = quantize_2dp(amount)

            # Determine if this transaction affects balance
            is_commission = TransactionSemantics.is_commission(txn_type)
            affects_balance = TransactionSemantics.is_balance_affecting(txn_type)

            # Update license running balance
            if affects_balance:
                direction = TransactionSemantics.get_balance_direction(txn_type)
                if direction == 'CREDIT':
                    running_balance += amount
                elif direction == 'DEBIT':
                    running_balance -= amount

                # Update totals
                if txn_type == 'PURCHASE':
                    dataset['totals']['total_purchases'] += amount
                elif txn_type == 'SALE':
                    dataset['totals']['total_sales'] += amount
            else:
                # COMMISSION or other non-balance-affecting
                dataset['totals']['total_commission'] += amount

            # Quantize final running balance
            running_balance = quantize_2dp(running_balance)

            # Update company-scoped utilization (if company-scoped)
            company_util_after = None
            if company_id and TransactionSemantics.is_balance_affecting(txn_type):
                if company_id not in company_balances:
                    company_balances[company_id] = Decimal('0.00')

                direction = TransactionSemantics.get_balance_direction(txn_type)
                if direction == 'CREDIT':
                    company_balances[company_id] += amount
                elif direction == 'DEBIT':
                    company_balances[company_id] -= amount

                company_balances[company_id] = quantize_2dp(company_balances[company_id])
                company_util_after = company_balances[company_id]

            # Add transaction to dataset
            dataset['transactions'].append({
                'date': txn_date,
                'id': txn_id,
                'type': txn_type,
                'company_id': company_id,
                'company_name': company_name,
                'amount': amount,
                'is_commission': is_commission,
                'license_running_balance': running_balance,
                'company_utilization_after': company_util_after,
                'affects_balance': affects_balance,
            })

        # Set final balances
        dataset['license_running_balance'] = running_balance
        dataset['closing_balance'] = running_balance

        # Build company utilizations dict
        for company_id, balance in company_balances.items():
            # Fetch company name
            company_name = _get_company_name_for_id(company_id)
            dataset['company_utilizations'][company_id] = {
                'company_id': company_id,
                'company_name': company_name,
                'utilization_balance': balance,
            }

        # Quantize all totals
        for key in dataset['totals']:
            dataset['totals'][key] = quantize_2dp(dataset['totals'][key])

        return dataset


# ========== INTERNAL HELPERS ==========

def _get_license_object(license_id: int, license_type: str):
    """Fetch license object by ID and type."""
    try:
        if license_type == 'DFIA':
            return LicenseDetailsModel.objects.get(id=license_id)
        elif license_type in ['INCENTIVE', 'RODTEP', 'ROSTL', 'MEIS']:
            return IncentiveLicense.objects.get(id=license_id)
        else:
            return None
    except (LicenseDetailsModel.DoesNotExist, IncentiveLicense.DoesNotExist):
        return None


def _fetch_transactions(license_obj, license_type: str) -> List[Dict[str, Any]]:
    """
    Fetch and normalize all transactions for a license.

    Returns list of dicts with keys:
    - date: date of transaction
    - id: transaction ID (for deterministic ordering)
    - type: transaction type (PURCHASE, SALE, COMMISSION, etc.)
    - company_id: company ID (if company-scoped)
    - company_name: company name
    - amount: transaction amount

    Transactions are sorted deterministically: date ASC, then id ASC
    """
    transactions = []

    # Fetch all trades for this license
    if license_type == 'DFIA':
        trades = LicenseTrade.objects.filter(
            license_type='DFIA',
            lines__sr_number__license=license_obj
        ).prefetch_related('lines__sr_number', 'from_company', 'to_company').distinct()
    else:
        trades = LicenseTrade.objects.filter(
            license_type='INCENTIVE',
            incentive_lines__incentive_license=license_obj
        ).prefetch_related('incentive_lines', 'from_company', 'to_company').distinct()

    # Process each trade
    for trade in trades:
        # Normalize transaction data
        txn_date = trade.invoice_date or trade.created_at.date()
        trade_direction = trade.direction  # PURCHASE, SALE, COMMISSION_PURCHASE, COMMISSION_SALE

        # Determine transaction type and company
        if trade_direction == 'PURCHASE':
            txn_type = 'PURCHASE'
            company_id = trade.to_company.id if trade.to_company else None
            company_name = trade.to_company.name if trade.to_company else 'Unknown'
        elif trade_direction == 'SALE':
            txn_type = 'SALE'
            company_id = trade.from_company.id if trade.from_company else None
            company_name = trade.from_company.name if trade.from_company else 'Unknown'
        elif trade_direction == 'COMMISSION_PURCHASE':
            txn_type = 'COMMISSION_PURCHASE'
            company_id = trade.to_company.id if trade.to_company else None
            company_name = trade.to_company.name if trade.to_company else 'Unknown'
        elif trade_direction == 'COMMISSION_SALE':
            txn_type = 'COMMISSION_SALE'
            company_id = trade.from_company.id if trade.from_company else None
            company_name = trade.from_company.name if trade.from_company else 'Unknown'
        else:
            continue  # Unknown trade type

        # Calculate total CIF for this trade in this license
        total_cif = Decimal('0.00')

        if license_type == 'DFIA':
            lines = trade.lines.filter(sr_number__license=license_obj)
            for line in lines:
                # Extract CIF value (with currency conversion if needed)
                line_cif = _extract_line_cif(line)
                total_cif += line_cif
        else:
            # Incentive license
            incentive_line = trade.incentive_lines.filter(incentive_license=license_obj).first()
            if incentive_line:
                total_cif = to_decimal(incentive_line.license_value, DEC_0)

        # Include transaction even if zero-amount (per Scenario 7: zero txns visible but not counted)
        # Zero-amount transactions will not affect balance since amount=0
        transactions.append({
            'date': txn_date,
            'id': trade.id,
            'type': txn_type,
            'company_id': company_id,
            'company_name': company_name,
            'amount': total_cif,
        })

    # Sort deterministically: date ASC, then trade ID ASC
    transactions.sort(key=lambda x: (x['date'], x['id']))

    return transactions


def _extract_line_cif(line) -> Decimal:
    """Extract CIF value from a BOE/trade line, handling currency conversion."""
    try:
        # Try cif_fc first (common field)
        if hasattr(line, 'cif_fc') and line.cif_fc:
            return to_decimal(line.cif_fc, DEC_0)

        # Try INR conversion if exc_rate available
        if hasattr(line, 'cif_inr') and hasattr(line, 'exc_rate'):
            cif_inr = to_decimal(line.cif_inr, DEC_0)
            exc_rate = to_decimal(line.exc_rate, DEC_0)
            if cif_inr and exc_rate and exc_rate != DEC_0:
                return cif_inr / exc_rate

        return DEC_0
    except (ValueError, TypeError, ZeroDivisionError):
        return DEC_0


def _get_company_name_for_id(company_id: int) -> str:
    """Fetch company name by ID."""
    try:
        from apps.core.models import CompanyModel
        company = CompanyModel.objects.get(id=company_id)
        return company.name
    except Exception:
        return 'Unknown'
