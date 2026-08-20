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

import logging
import re
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Dict, List, Any
from datetime import date as date_type

from django.db.models import Q, Sum, Value, DecimalField, Prefetch
from django.db.models.functions import Coalesce

from apps.license.domain.transaction_semantics import (
    LEDGER_COLUMN_CREDIT,
    LEDGER_COLUMN_DEBIT,
    TransactionSemantics,
    ledger_column_for,
    select_display_rows,
)
from apps.license.models import LicenseDetailsModel, IncentiveLicense
from apps.trade.models import LicenseTrade
from apps.core.utils.decimal_utils import to_decimal
from apps.core.constants import DEC_0

logger = logging.getLogger(__name__)

DECIMAL_2DP = Decimal("0.01")


def quantize_2dp(value: Decimal) -> Decimal:
    """Quantize decimal value to 2 decimal places using ROUND_HALF_UP."""
    return to_decimal(value, DEC_0).quantize(DECIMAL_2DP, rounding=ROUND_HALF_UP)


_FIRST_PURCHASE_UNSET = object()


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
    def build_canonical_ledger_dataset(
        license_id: int, license_type: str = "DFIA", *, first_purchase_date=_FIRST_PURCHASE_UNSET,
    ) -> Dict[str, Any]:
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
                # --- identity / metadata (see _extract_license_metadata) ---
                'license_id': int,
                'license_type': str,
                'license_number': str,
                'license_date': date or None,
                'expiry_date': date or None,      # from <license>.license_expiry_date
                'exporter_id': int or None,
                'exporter_name': str,             # '' when unknown
                'port_id': int or None,
                'port_name': str,                 # '' when unknown
                'first_purchase_date': date or None,  # canonical acquisition date

                # --- purchase bill detection ---
                'has_purchase_bill': bool,        # TRUE if license has ≥1 qualifying PURCHASE with non-zero bill
                'purchase_bill_status': str,      # "WITH_PURCHASE_BILL" | "NO_PURCHASE_BILL"

                # --- balances ---
                'opening_balance': Decimal,
                'license_running_balance': Decimal,  # Final balance
                'closing_balance': Decimal,  # Same as running_balance

                'transactions': [
                    {
                        'date': date,
                        'id': int (transaction ID; 0 for the synthetic OPENING row),
                        'type': str,  # OPENING, PURCHASE, SALE,
                                      # COMMISSION_PURCHASE, COMMISSION_SALE
                        'company_id': int or None,
                        'company_name': str or None,
                        'amount': Decimal,
                        'is_commission': bool,
                        'affects_balance': bool,
                        'sion_norms': str,  # PRESENTATION-LAYER DERIVATION, NOT a
                                # ledger fact: the SION norms of the LICENCE ITEMS
                                # billed on this trade (see _extract_sion_norms).
                                # Comma-space joined, '' when none. DFIA only —
                                # always '' for INCENTIVE/RODTEP/ROSTL/MEIS and on
                                # the synthetic OPENING row.
                        'license_running_balance': Decimal,  # Running balance after this txn
                        'company_utilization_after': Decimal or None,  # (if company-scoped;
                                                # absent on the synthetic OPENING row)
                    },
                    ...
                ],

                # --- presentation only; NO financial meaning ---
                # `transactions` above is the complete financial record and is
                # what every balance/total is derived from. These two fields are
                # the display rule applied on top of it (see
                # transaction_semantics.select_display_rows):
                'display_transactions': [...],   # PURCHASE + SALE only, input
                                # order preserved. NEVER contains OPENING.
                'opening_display': dict or None, # the OPENING row, returned
                                # OUTSIDE the transaction collection so it can be
                                # rendered as the starting state. Non-None only
                                # when NO PURCHASE exists (and an opening
                                # balance exists at all).

                # Keyed by company_id (NOT a list).
                'company_utilizations': {
                    company_id: {
                        'company_id': int,
                        'company_name': str,
                        'utilization_balance': Decimal,
                    },
                    ...
                },
                'totals': {
                    'total_purchases': Decimal,
                    'total_sales': Decimal,
                    'total_commission': Decimal,
                },

                # --- on-screen summary block (see _build_summary) ---
                # Derived ENTIRELY from the display rows already selected above.
                # Adds NO new financial concept and costs no query: its one
                # arithmetic operation is `total_purchase_bill_inr − total_sale_bill_inr`.
                'summary': {
                    'total_purchase': Decimal,       # Σ displayed Purchase column = PURCHASE/OPENING
                    'total_sale': Decimal,           # Σ displayed Sale column = SALE
                    'total_purchase_bill_inr': Decimal,  # Σ same rows' bill_amount (INR)
                    'total_sale_bill_inr': Decimal,      # Σ same rows' bill_amount (INR)
                    'bill_currency': 'INR',
                    'opening_balance': Decimal,   # licence metadata; NOT in the identity
                    'opening_in_purchase': bool,     # is opening already inside total_purchase?
                    'current_balance': Decimal,   # total_purchase − total_sale
                    'balance_currency': str,      # 'USD' (DFIA) | 'INR'
                    'total_profit_loss': Decimal, # SAME number as current_balance
                    'profit_currency': str,       # == balance_currency
                    'profit_state': str,          # PROFIT|LOSS|BREAK_EVEN|UNAVAILABLE
                },
            }

        Raises:
            ValueError: If license_id not found or invalid license_type
        """
        # Fetch license object
        license_obj = _get_license_object(license_id, license_type)
        if not license_obj:
            raise ValueError(f"License {license_id} (type {license_type}) not found")

        # License metadata promised by the dataset contract (single shared
        # extraction path for both LicenseDetailsModel and IncentiveLicense).
        metadata = _extract_license_metadata(license_obj)

        # Build dataset
        dataset = {
            'license_id': license_id,
            'license_type': license_type,
            **metadata,
            # License metadata, resolved from every import item on the licence
            # (not merely the items that happen to occur on a trade).  Keeping
            # this here prevents list/PDF/Excel renderers from querying or
            # reverse-engineering SION independently.
            'sion_norms': _extract_license_sion_norms(license_obj, license_type),
            # The licence's canonical acquisition date, from the SAME definition
            # the Purchase & Profit report and the ledger list's Purchase Date
            # Range filter use. Deliberately NOT re-derived as MIN(date) over
            # this dataset's own PURCHASE rows: the ledger includes the internal
            # linked/mirror legs that the canonical definition excludes, so a
            # locally-derived date could disagree with the filter that decides
            # whether this licence appears in the list at all.
            'first_purchase_date': (
                _first_purchase_date_for(license_id, license_type)
                if first_purchase_date is _FIRST_PURCHASE_UNSET else first_purchase_date
            ),
            'opening_balance': Decimal('0.00'),
            'license_running_balance': Decimal('0.00'),
            'closing_balance': Decimal('0.00'),
            'has_purchase_bill': False,  # Will be set after transactions are loaded
            'purchase_bill_status': 'NO_PURCHASE_BILL',  # Will be set after transactions are loaded
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

        # Compute purchase bill presence (check for any PURCHASE with non-zero bill)
        has_purchase_bill = _has_purchase_bill(raw_transactions)
        dataset['has_purchase_bill'] = has_purchase_bill
        dataset['purchase_bill_status'] = 'WITH_PURCHASE_BILL' if has_purchase_bill else 'NO_PURCHASE_BILL'

        # The licence face value is a brought-forward opening only when the
        # effective ledger does not already contain its acquisition.  A valid
        # PURCHASE credit is that acquisition and must be counted exactly once.
        opening_balance = quantize_2dp(
            to_decimal(getattr(license_obj, 'opening_balance', None), DEC_0)
        )
        has_valid_purchase = any(
            # `raw_transactions` is the effective canonical collection: it
            # already has the licence/company scope and canonical inclusion
            # rules applied.  Only its acquisition event may replace an
            # opening; another CREDIT (for example a future credit type) must
            # never accidentally do so.
            row.get('type') == 'PURCHASE'
            and to_decimal(row.get('amount'), DEC_0) > DEC_0
            for row in raw_transactions
        )
        if has_valid_purchase:
            opening_balance = DEC_0
        if opening_balance > DEC_0:
            dataset['opening_balance'] = opening_balance

        # Process transactions in deterministic order (date, then ID)
        running_balance = opening_balance
        company_balances: Dict[int, Decimal] = {}  # Track per-company balances

        # Add opening transaction first (if opening balance exists)
        if opening_balance > DEC_0:
            dataset['transactions'].append({
                'date': metadata['license_date'],
                'id': 0,  # Opening is transaction 0
                'type': 'OPENING',
                'company_id': None,
                'company_name': None,
                # The opening balance is a carried-forward STATE, not a trade:
                # there is no counterparty, no invoice and no billed item. All
                # three stay empty rather than being back-filled from the
                # licence — a fabricated party/bill on the opening row would be
                # presented to a CA as a transaction that never happened.
                'party_id': None,
                'party_name': None,
                'amount': opening_balance,
                'bill_amount': None,
                'item_names': [],
                'is_commission': False,
                'license_running_balance': running_balance,
                'affects_balance': True,
                'sion_norms': '',  # Not trade-derived; no billed items exist.
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
                'party_id': txn_data.get('party_id'),
                'party_name': txn_data.get('party_name'),
                'amount': amount,
                # Carried through verbatim from `_fetch_transactions`: already
                # 2dp, and deliberately NOT folded into any balance — the bill
                # is INR while the balance is CIF USD for DFIA.
                'bill_amount': txn_data.get('bill_amount'),
                'item_names': txn_data.get('item_names') or [],
                # Optional exchange rate copied from the billed lines.  It is
                # deliberately absent when a trade has no single unambiguous
                # rate; bill values are never recalculated from it.
                'rate': txn_data.get('rate'),
                'is_commission': is_commission,
                'license_running_balance': running_balance,
                'company_utilization_after': company_util_after,
                'affects_balance': affects_balance,
                'sion_norms': txn_data.get('sion_norms', ''),
            })

        # Set final balances
        dataset['license_running_balance'] = running_balance
        dataset['closing_balance'] = running_balance

        # Publish debit/credit presentation values ONCE. Every consumer reads
        # these fields verbatim; UI/PDF/Excel must never infer a column from
        # transaction type independently.
        for row in dataset['transactions']:
            column = ledger_column_for(row.get('type'))
            is_purchase = column == LEDGER_COLUMN_CREDIT
            is_sale = column == LEDGER_COLUMN_DEBIT
            row['ledger_column'] = column
            row['purchase_amount'] = row['amount'] if is_purchase else None
            row['sale_amount'] = row['amount'] if is_sale else None
            row['purchase_bill_amount'] = row.get('bill_amount') if is_purchase else None
            row['sale_bill_amount'] = row.get('bill_amount') if is_sale else None

        # ── Display selection (presentation only) ──────────────────────────
        # `transactions` above stays the complete financial record — it still
        # carries the OPENING row, because the running balances, the totals and
        # the balance-by-transaction-id maps used by the PDF/Excel exporters are
        # all derived from it. The display rule is applied on top, once, here:
        # consumers render `display_transactions` (PURCHASE + SALE only) plus
        # `opening_display` (the starting state, present only when there is no
        # PURCHASE). No amount is recomputed, rounded or re-ordered.
        display = select_display_rows(dataset['transactions'])
        dataset['display_transactions'] = display['display_transactions']
        dataset['opening_display'] = display['opening_row']
        dataset['has_purchase_transaction'] = any(
            row.get('purchase_amount') is not None and row.get('type') == 'PURCHASE'
            for row in dataset['transactions']
        )

        # Build company utilizations dict.
        # Company names are resolved in ONE bulk query (previously one query
        # per company inside this loop).
        company_names = _get_company_names_for_ids(company_balances.keys())
        for company_id, balance in company_balances.items():
            company_name = company_names.get(company_id, 'Unknown')
            dataset['company_utilizations'][company_id] = {
                'company_id': company_id,
                'company_name': company_name,
                'utilization_balance': balance,
            }

        # Quantize all totals
        for key in dataset['totals']:
            dataset['totals'][key] = quantize_2dp(dataset['totals'][key])

        # ── Screen reconciliation summary (additive; recomputes nothing) ────
        dataset['summary'] = _build_summary(dataset)
        dataset['license_wise_companies'] = _build_license_wise_companies(dataset)

        # ── Add purchase-not-present detection flag ────
        dataset['has_purchase_bill'] = _has_purchase_bill(dataset['transactions'])

        return dataset

    @staticmethod
    def build_collection_summary(datasets: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate list-page cards strictly from canonical per-license summaries."""
        result = {
            'dfia': {'total_licenses': 0, 'total_value_usd': DEC_0, 'balance_value_usd': DEC_0,
                     'purchase_amount_inr': DEC_0, 'sale_amount_inr': DEC_0, 'profit_loss_inr': DEC_0},
            'incentive': {'total_licenses': 0, 'total_value_inr': DEC_0, 'balance_value_inr': DEC_0,
                          'purchase_amount_inr': DEC_0, 'sale_amount_inr': DEC_0, 'profit_loss_inr': DEC_0},
        }
        for data in datasets:
            summary = data['summary']
            bucket = result['dfia'] if data['license_type'] == 'DFIA' else result['incentive']
            bucket['total_licenses'] += 1
            value_key = 'total_value_usd' if data['license_type'] == 'DFIA' else 'total_value_inr'
            balance_key = 'balance_value_usd' if data['license_type'] == 'DFIA' else 'balance_value_inr'
            bucket[value_key] += summary['total_purchase']
            bucket[balance_key] += summary['current_balance']
            bucket['purchase_amount_inr'] += summary['total_purchase_bill_inr']
            bucket['sale_amount_inr'] += summary['total_sale_bill_inr']
            bucket['profit_loss_inr'] += summary['total_profit_loss']
        for bucket in result.values():
            for key, value in bucket.items():
                if key != 'total_licenses':
                    bucket[key] = quantize_2dp(value)
        return result

    @staticmethod
    def build_collection_company_groups(datasets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Build export/list company groups without presentation-layer sums.

        A licence can contain trades for more than one owning company, so the
        company relationship comes from the already-canonical per-company
        ledger groups rather than exporter/license-holder metadata.
        """
        groups: Dict[int, Dict[str, Any]] = {}
        for data in datasets:
            for company in data.get('license_wise_companies') or []:
                company_id = company['company_id']
                group = groups.setdefault(company_id, {
                    'company_id': company_id,
                    'company_name': company['company_name'],
                    'licenses': [],
                    'total_purchase_bill_inr': DEC_0,
                    'total_sale_bill_inr': DEC_0,
                    'total_balance': DEC_0,
                    'total_profit_loss_inr': DEC_0,
                    'balance_currency': data['summary']['balance_currency'],
                })
                row = {
                    'license_id': data['license_id'],
                    'license_number': data['license_number'],
                    'license_type': data['license_type'],
                    'license_date': data['license_date'],
                    'first_purchase_date': data['first_purchase_date'],
                    'sion_norms': data.get('sion_norms') or '',
                    # The report column is the current balance of the licence.
                    'current_balance': data['summary']['current_balance'],
                    # Kept separately for a company total when a licence has
                    # activity under multiple owning companies.
                    'company_balance': company['current_balance'],
                    'balance_currency': data['summary']['balance_currency'],
                    'purchase_bill_inr': company['purchase_total'],
                    'sale_bill_inr': company['sale_total'],
                    'profit_loss_inr': company['profit_loss'],
                    'profit_state': company['profit_state'],
                    'has_purchase_bill': data['has_purchase_bill'],
                }
                group['licenses'].append(row)
                group['total_purchase_bill_inr'] += company['purchase_total']
                group['total_sale_bill_inr'] += company['sale_total']
                group['total_balance'] += company['current_balance']
                group['total_profit_loss_inr'] += company['profit_loss']

        result = []
        for group in groups.values():
            # Preserve the filtered collection's approved ordering (license
            # date/balance). Insertion into company/SION buckets is stable.
            for key in ('total_purchase_bill_inr', 'total_sale_bill_inr', 'total_balance',
                        'total_profit_loss_inr'):
                group[key] = quantize_2dp(group[key])
            group['profit_state'] = _profit_state(group['total_profit_loss_inr'])
            # Reporting hierarchy is canonical and shared by every consumer:
            # Company -> SION -> Licence.  A multi-norm licence belongs to one
            # deterministic composite group so its financial values can never
            # be duplicated across norm sections.
            sion_groups: Dict[str, Dict[str, Any]] = {}
            for row in group['licenses']:
                sion_norm = _canonical_sion_group(row.get('sion_norms'))
                bucket = sion_groups.setdefault(sion_norm, {
                    'sion_norm': sion_norm,
                    'sion_label': sion_norm or 'N/A / EMPTY',
                    'licenses': [],
                    'license_count': 0,
                    'total_purchase_bill_inr': DEC_0,
                    'total_sale_bill_inr': DEC_0,
                    'total_balance': DEC_0,
                    'total_profit_loss_inr': DEC_0,
                    'balance_currency': group['balance_currency'],
                })
                bucket['licenses'].append(row)
                bucket['license_count'] += 1
                bucket['total_purchase_bill_inr'] += row['purchase_bill_inr']
                bucket['total_sale_bill_inr'] += row['sale_bill_inr']
                bucket['total_balance'] += row['company_balance']
                bucket['total_profit_loss_inr'] += row['profit_loss_inr']

            for bucket in sion_groups.values():
                for key in ('total_purchase_bill_inr', 'total_sale_bill_inr',
                            'total_balance', 'total_profit_loss_inr'):
                    bucket[key] = quantize_2dp(bucket[key])
                bucket['profit_state'] = _profit_state(bucket['total_profit_loss_inr'])
            group['sion_groups'] = sorted(
                sion_groups.values(),
                key=lambda bucket: _sion_sort_key(bucket['sion_norm']),
            )
            result.append(group)
        return sorted(result, key=lambda group: (group['company_name'], group['company_id']))

    @staticmethod
    def build_collection_grand_total(company_groups: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Reconcile the report total from canonical company partitions."""
        total = {
            'license_count': 0,
            'total_purchase_bill_inr': DEC_0,
            'total_sale_bill_inr': DEC_0,
            'total_balance': DEC_0,
            'total_profit_loss_inr': DEC_0,
        }
        for group in company_groups:
            total['license_count'] += len(group.get('licenses') or [])
            for key in ('total_purchase_bill_inr', 'total_sale_bill_inr',
                        'total_balance', 'total_profit_loss_inr'):
                total[key] += group[key]
        for key in ('total_purchase_bill_inr', 'total_sale_bill_inr',
                    'total_balance', 'total_profit_loss_inr'):
            total[key] = quantize_2dp(total[key])
        total['profit_state'] = _profit_state(total['total_profit_loss_inr'])
        return total


# ========== INTERNAL HELPERS ==========

#: License types whose ledger balance is denominated in CIF USD. Everything
#: else (Incentive-scheme licenses) carries an INR license value.
_USD_BALANCE_LICENSE_TYPES = frozenset({'DFIA'})


def _natural_key(value: str):
    """Deterministic human ordering: E1, E5, E132, PP."""
    return tuple(int(part) if part.isdigit() else part.casefold()
                 for part in re.split(r'(\d+)', value))


def _canonical_sion_group(value: Optional[str]) -> str:
    """Return one non-duplicating group key from canonical SION metadata.

    The canonical licence field is a comma-separated set when a licence has
    several norms.  Such a licence is assigned to a single composite group;
    it is never copied into each constituent group because that would duplicate
    Purchase, Sale, Balance and P/L.
    """
    norms = {part.strip() for part in (value or '').split(',') if part.strip()}
    return ', '.join(sorted(norms, key=_natural_key))


def _sion_sort_key(value: str):
    # Empty is always last; configured/master order is not currently exposed
    # by the canonical dataset, so use stable natural ordering.
    return (not bool(value), _natural_key(value) if value else ())

#: Which ledger column a row's amount belongs in — read from the SINGLE
#: definition in `transaction_semantics.ledger_column_for`, never restated here.
#:
#: PURCHASE and OPENING → Credit (they add licence value);
#: SALE → Debit (it consumes licence value).
#:
#: This agrees with `balance_direction`, because the column IS
#: `balance_direction` (see `ledger_column_for`). So `total_credit` cannot
#: disagree with a `balance_direction` of CREDIT — a contradiction the previous
#: inverted presentation actively maintained.


def _has_purchase_bill(transactions: List[Dict[str, Any]]) -> bool:
    """
    Check if this license has at least one qualifying Purchase Bill/transaction.

    A "qualifying purchase" is a PURCHASE transaction with a non-zero bill amount.
    This detection is based on actual trade bills, not inferred from balance state.

    Args:
        transactions: List of transaction dicts from _fetch_transactions

    Returns:
        True if at least one qualifying PURCHASE with non-zero bill exists; False otherwise
    """
    for txn in transactions:
        if txn.get('type') == 'PURCHASE':
            bill_amount = txn.get('bill_amount')
            # Check for non-zero bill amount (even small amounts count)
            if bill_amount and bill_amount > DEC_0:
                return True
    return False


def _build_summary(dataset: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build the ledger `summary` block — the four figures above the transaction
    table, and the SINGLE canonical financial result they all derive from.

    ONE CALCULATION, TWO LABELS
    ---------------------------
    There is exactly one arithmetic operation in this function:

        net_position = total_purchase − total_sale

    It is computed ONCE and published under BOTH `current_balance` and
    `total_profit_loss`, because under the approved business rule they are the
    same number. They are deliberately NOT two independent calculations that
    happen to agree — there is nothing to drift.

    ⚠ ACCOUNTING NOTE — RECORDED, NOT SILENTLY IMPLEMENTED ⚠
    `total_profit_loss` here is the licence's UNUTILISED POSITION (licence value
    acquired minus licence value consumed), not a realised trading margin. A
    realised margin is `sale price − purchase cost` in INR, which is a different
    quantity and still lives — defined exactly once — in
    `apps.license.services.license_profit` for the Purchase & Profit report.
    This block reports the position under the label PROFIT / LOSS because that
    is the approved presentation for this screen. The two figures answer
    different questions and are NOT expected to match.

    WHY THE OPENING BALANCE IS NOT ADDED
    ------------------------------------
    `license_running_balance` is `opening + Σpurchases − Σsales`, and it
    DOUBLE-COUNTS the licence's acquisition whenever a PURCHASE exists: the
    `opening_balance` (Σ `export_license.cif_fc` — the licence's own face value)
    and the PURCHASE trade that acquired that licence are the SAME economic
    event recorded twice. Verified on real data: licence `0311055317` has
    opening 95,464.44 and a single purchase of 95,464.44, giving a running
    balance of 141,964.38 for a licence that only ever held 95,464.44.

    Summing the DISPLAYED rows fixes this exactly, because the display rule
    (`transaction_semantics.select_display_rows`) shows the acquisition ONCE:

        PURCHASE exists  → purchase rows shown, OPENING row suppressed
                           ⇒ acquisition counted via the purchase
        no PURCHASE      → OPENING row shown as the starting state
                           ⇒ acquisition counted via the opening

    Either way the licence's acquisition lands in the Purchase column exactly
    once, so:

        total_purchase − total_sale == current_balance

    holds unconditionally — no `opening_in_*` correction term, and no second
    form of the identity. `opening_balance` is still published (unchanged) as
    licence metadata, and `license_running_balance` is left exactly as it was
    for the consumers that legitimately want the raw running figure.

    NOTHING ELSE IS RECOMPUTED
    --------------------------
    The column totals are summed from the ALREADY-SELECTED display rows
    (`display_transactions` / `opening_display`), and each row's column comes
    from `transaction_semantics.ledger_column_for` — so the summary cannot
    disagree with either the table it sits above or the balance semantics.

    CURRENCIES
    ----------
    `total_sale` / `total_purchase` / `opening_balance` / `current_balance` /
    `total_profit_loss` are ALL in `balance_currency` (CIF **USD** for DFIA, INR
    for incentive licences). `total_purchase_bill_inr` / `total_sale_bill_inr` are in
    `bill_currency` (**INR**) and are supplementary — never added to the
    licence-value figures, and never used to derive profit.

    Cost: ZERO queries. Every input is already in `dataset`.
    """
    display_rows = list(dataset.get('display_transactions') or [])
    opening_row = dataset.get('opening_display')
    opening_balance = dataset.get('opening_balance') or DEC_0

    # The displayed OPENING row is a Purchase-column row like any other (it adds
    # licence value); it is kept out of `display_transactions` only so the UI
    # can render it as a starting state rather than as a transaction. For
    # totalling purposes it is simply one more row.
    if opening_row is not None:
        display_rows.append(opening_row)

    total_sale: Decimal = DEC_0
    total_purchase: Decimal = DEC_0
    # Bill totals are accumulated in the SAME pass over the SAME rows, so a bill
    # column footer can never disagree with the rows above it. Separate
    # currency (INR); published only so the client never sums a money column.
    total_purchase_bill_inr: Decimal = DEC_0
    total_sale_bill_inr: Decimal = DEC_0
    for row in display_rows:
        purchase_amount = row.get('purchase_amount')
        sale_amount = row.get('sale_amount')
        if purchase_amount is not None:
            total_purchase += purchase_amount
            total_purchase_bill_inr += row.get('purchase_bill_amount') or DEC_0
        if sale_amount is not None:
            total_sale += sale_amount
            total_sale_bill_inr += row.get('sale_bill_amount') or DEC_0

    total_purchase = quantize_2dp(total_purchase)
    total_sale = quantize_2dp(total_sale)

    # THE canonical financial result. Computed once; published twice.
    # Signed — a negative position is reported as a negative number and as
    # `profit_state='LOSS'`; it is never absolute-valued or hidden here.
    #
    # CRITICAL: current_balance = opening_balance + total_purchase - total_sale
    #
    # Current balance is ALWAYS: total_purchase - total_sale (from displayed rows)
    # The display rule (`select_display_rows`) ensures the acquisition is shown once:
    # - PURCHASE exists  → OPENING suppressed, acquisition via purchase rows
    # - no PURCHASE      → OPENING shown as starting state
    # Per user definition: "Current Balance = total_purchase - total_sale in USD"
    current_balance = quantize_2dp(total_purchase - total_sale)

    license_type = dataset.get('license_type')
    balance_currency = 'USD' if license_type in _USD_BALANCE_LICENSE_TYPES else 'INR'

    # PROFIT/LOSS CALCULATION (FINAL ACCOUNTING TRUTH)
    # MUST be: TOTAL SALE BILL (₹) - TOTAL PURCHASE BILL (₹)
    # Always in INR, always from bill amounts, never from license values
    total_purchase_bill_inr = quantize_2dp(total_purchase_bill_inr)
    total_sale_bill_inr = quantize_2dp(total_sale_bill_inr)
    profit_loss_inr = quantize_2dp(total_sale_bill_inr - total_purchase_bill_inr)

    return {
        'total_purchase': total_purchase,
        'total_sale': total_sale,
        # Σ of the two BILL columns, in `bill_currency` (INR)
        'total_purchase_bill_inr': total_purchase_bill_inr,
        'total_sale_bill_inr': total_sale_bill_inr,
        'bill_currency': 'INR',
        # Licence metadata, unchanged.
        'opening_balance': opening_balance,
        # True when the OPENING row is on screen (and so is already inside
        # `total_purchase`). Published so no consumer re-derives the display rule.
        'opening_in_purchase': opening_row is not None,
        'current_balance': current_balance,
        'balance_currency': balance_currency,
        # PROFIT/LOSS is ALWAYS: sale_bill_inr - purchase_bill_inr (in INR)
        'total_profit_loss': profit_loss_inr,
        'profit_currency': 'INR',
        'profit_state': _profit_state(profit_loss_inr),
    }


def _build_license_wise_companies(dataset: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Build the list screen's company groups from canonical row values."""
    groups: Dict[int, Dict[str, Any]] = {}
    for row in dataset.get('display_transactions') or []:
        company_id = row.get('company_id')
        if company_id is None:
            continue
        group = groups.setdefault(company_id, {
            'company_id': company_id,
            'company_name': row.get('company_name') or 'Unknown company',
            'purchases': [], 'sales': [],
            'purchase_total': DEC_0, 'sale_total': DEC_0,
            'purchase_value': DEC_0, 'sale_value': DEC_0,
        })
        if row.get('purchase_bill_amount') is not None:
            amount = row.get('purchase_bill_amount') or DEC_0
            group['purchases'].append({'trade_id': row.get('id'), 'invoice_date': row.get('date'), 'amount': amount})
            group['purchase_total'] += amount
            group['purchase_value'] += row.get('purchase_amount') or DEC_0
        if row.get('sale_bill_amount') is not None:
            amount = row.get('sale_bill_amount') or DEC_0
            group['sales'].append({'trade_id': row.get('id'), 'invoice_date': row.get('date'), 'amount': amount})
            group['sale_total'] += amount
            group['sale_value'] += row.get('sale_amount') or DEC_0

    result = []
    for group in groups.values():
        group['purchase_total'] = quantize_2dp(group['purchase_total'])
        group['sale_total'] = quantize_2dp(group['sale_total'])
        group['purchase_value'] = quantize_2dp(group['purchase_value'])
        group['sale_value'] = quantize_2dp(group['sale_value'])
        group['current_balance'] = quantize_2dp(group['purchase_value'] - group['sale_value'])
        group['balance_currency'] = dataset['summary']['balance_currency']
        group['profit_loss'] = quantize_2dp(group['sale_total'] - group['purchase_total'])
        group['profit_state'] = _profit_state(group['profit_loss'])
        result.append(group)
    return sorted(result, key=lambda group: group['company_name'])


def _first_purchase_date_for(license_id, license_type: Optional[str]) -> Optional[date_type]:
    """
    The licence's canonical `first_purchase_date`, or None when it has none.

    ONE query for DFIA, ZERO for incentive licences: the canonical definition is
    expressed over `LicenseTradeLine.sr_number__license_id`, a
    `LicenseDetailsModel` FK that does not reach `IncentiveLicense` at all (see
    `license_profit`'s SCOPE section). Because the two models have independent id
    sequences, asking for an incentive id would return an unrelated DFIA
    licence's date — so incentive licences report None rather than a wrong date.

    Never raises: a metadata lookup must not be able to break the ledger screen.
    A failure degrades to None, and is logged rather than swallowed silently.
    """
    if not license_id:
        return None
    try:
        from apps.license.services.license_profit import (
            first_purchase_date_for_license, incentive_first_purchase_date_by_license,
        )
        if license_type in _USD_BALANCE_LICENSE_TYPES:
            return first_purchase_date_for_license(license_id)
        return incentive_first_purchase_date_by_license([license_id]).get(license_id)
    except Exception:  # pragma: no cover — defensive
        logger.exception(
            "first_purchase_date lookup failed for license_id=%s (%s); reporting None",
            license_id,
            license_type,
        )
        return None


def _profit_state(net_position: Optional[Decimal]) -> str:
    """
    Decide PROFIT / LOSS / BREAK_EVEN / UNAVAILABLE in the BACKEND so no client
    ever branches on the sign of a number (and so Web, and later PDF/Excel, all agree).

    BREAK_EVEN is the exact-zero case — presented as "NO PROFIT / NO LOSS", which is
    a real financial statement.

    UNAVAILABLE is returned when the position is not computable (None), which happens
    for incentive licences whose profit definition does not apply.
    """
    if net_position is None:
        return 'UNAVAILABLE'
    if net_position > DEC_0:
        return 'PROFIT'
    if net_position < DEC_0:
        return 'LOSS'
    return 'BREAK_EVEN'


def _get_license_object(license_id: int, license_type: str):
    """
    Fetch license object by ID and type.

    The exporter/port relations are pulled in with select_related because
    _extract_license_metadata() always reads them (avoids 2 extra queries).
    Note the port FK is named differently on each model: LicenseDetailsModel.port
    vs IncentiveLicense.port_code.
    """
    try:
        if license_type == 'DFIA':
            return (
                LicenseDetailsModel.objects
                .select_related('exporter', 'port')
                .prefetch_related('import_license__items__sion_norm_class')
                .get(id=license_id)
            )
        elif license_type in ['INCENTIVE', 'RODTEP', 'ROSTL', 'MEIS']:
            return (
                IncentiveLicense.objects
                .select_related('exporter', 'port_code')
                .get(id=license_id)
            )
        else:
            return None
    except (LicenseDetailsModel.DoesNotExist, IncentiveLicense.DoesNotExist):
        return None


# The two license models agree on `license_number`, `license_date`,
# `license_expiry_date` and `exporter`, but disagree on the port FK name.
_PORT_FK_ATTRS = ('port', 'port_code')


def _extract_license_metadata(license_obj) -> Dict[str, Any]:
    """
    Extract the license metadata part of the canonical dataset contract.

    ONE shared implementation for BOTH license models:

    | canonical key   | LicenseDetailsModel (DFIA) | IncentiveLicense (INCENTIVE/…) |
    |-----------------|----------------------------|--------------------------------|
    | license_number  | license_number             | license_number                 |
    | license_date    | license_date (nullable)    | license_date                   |
    | expiry_date     | license_expiry_date        | license_expiry_date            |
    | exporter_id     | exporter_id (nullable)     | exporter_id                    |
    | exporter_name   | exporter.name              | exporter.name                  |
    | port_id         | port_id (nullable)         | port_code_id                   |
    | port_name       | port.name                  | port_code.name                 |

    Missing relations degrade to None ids and '' names (never raises), so the
    API contract holds even for partially-populated legacy rows. For DFIA, a
    deleted exporter falls back to the `archived_exporter_name` snapshot.
    """
    exporter = getattr(license_obj, 'exporter', None)
    exporter_name = exporter.name if exporter else ''
    if not exporter_name:
        # DFIA only: name snapshot kept when the company row was deleted.
        exporter_name = getattr(license_obj, 'archived_exporter_name', '') or ''

    port = None
    port_id = None
    for attr in _PORT_FK_ATTRS:
        if hasattr(license_obj, attr):
            port = getattr(license_obj, attr)
            port_id = getattr(license_obj, f'{attr}_id', None)
            break

    return {
        'license_number': getattr(license_obj, 'license_number', '') or '',
        'license_date': getattr(license_obj, 'license_date', None),
        'expiry_date': getattr(license_obj, 'license_expiry_date', None),
        'exporter_id': getattr(license_obj, 'exporter_id', None),
        'exporter_name': exporter_name,
        'port_id': port_id,
        'port_name': (port.name if port else '') or '',
    }


def _extract_license_sion_norms(license_obj, license_type: str) -> str:
    """Return the licence-level SION metadata in deterministic order.

    SION belongs to DFIA licence items, not financial transactions.  The
    licence query prefetches this relationship, so this traversal performs no
    query and does not depend on whether an item has already been traded.
    """
    if license_type != 'DFIA':
        return ''
    norms: List[str] = []
    for import_item in license_obj.import_license.all():
        for item in import_item.items.all():
            norm_class = getattr(item, 'sion_norm_class', None)
            norm = (getattr(norm_class, 'norm_class', '') or '').strip() if norm_class else ''
            if norm and norm not in norms:
                norms.append(norm)
    return ', '.join(norms)


def _fetch_transactions(license_obj, license_type: str) -> List[Dict[str, Any]]:
    """
    Fetch and normalize all transactions for a license.

    Returns list of dicts with keys:
    - date: date of transaction
    - id: transaction ID (for deterministic ordering)
    - type: transaction type (PURCHASE, SALE, COMMISSION, etc.)
    - company_id: company ID (if company-scoped) — OUR side of the trade
    - company_name: company name — OUR side (this is what the table groups by)
    - party_id / party_name: the COUNTERPARTY (see `_resolve_trade_sides`).
      `None` when the relation is absent — never a fabricated stand-in.
    - amount: transaction amount — the LICENSE value (CIF FC for DFIA)
    - bill_amount: the actual INVOICE/BILL value in INR (Σ `amount_inr` of the
      lines). A DIFFERENT figure from `amount`, in a DIFFERENT currency — see
      `_extract_bill_amount`. Never assume the two are equal.
    - item_names: list of billed licence item names, first-seen order, deduped
      (DFIA only; [] for incentive licenses)
    - sion_norms: comma-space joined SION norms of the billed licence items
      (DFIA only; '' for incentive licenses) — presentation metadata, not a
      ledger fact

    Transactions are sorted deterministically: date ASC, then id ASC
    """
    from apps.trade.models import IncentiveTradeLine, LicenseTradeLine

    transactions = []

    # Fetch all trades for this license.
    #
    # The per-license line filter is pushed into a Prefetch(to_attr=...) so the
    # lines for ALL trades are fetched in ONE query. Previously the loop below
    # ran `trade.lines.filter(...)` / `trade.incentive_lines.filter(...)`, i.e.
    # one query per trade (N+1). The Prefetch queryset carries the SAME filter,
    # and both line models declare `ordering = ["id"]`, so the rows and their
    # order — and therefore the amounts computed from them — are unchanged.
    #
    # The `sr_number__items__sion_norm_class` chain rides along on that same
    # Prefetch so `_extract_sion_norms` stays N+1-free (2 extra queries total,
    # regardless of trade count).
    if license_type == 'DFIA':
        license_lines_qs = (
            LicenseTradeLine.objects
            .filter(sr_number__license=license_obj)
            .select_related('sr_number')
            .prefetch_related('sr_number__items__sion_norm_class')
        )
        trades = LicenseTrade.objects.filter(
            license_type='DFIA',
            lines__sr_number__license=license_obj
        ).select_related('from_company', 'to_company').prefetch_related(
            Prefetch('lines', queryset=license_lines_qs, to_attr='license_lines')
        ).distinct()
    else:
        incentive_lines_qs = IncentiveTradeLine.objects.filter(incentive_license=license_obj)
        trades = LicenseTrade.objects.filter(
            license_type='INCENTIVE',
            incentive_lines__incentive_license=license_obj
        ).select_related('from_company', 'to_company').prefetch_related(
            Prefetch('incentive_lines', queryset=incentive_lines_qs, to_attr='license_incentive_lines')
        ).distinct()

    # Process each trade
    for trade in trades:
        # Normalize transaction data
        txn_date = trade.invoice_date or trade.created_at.date()
        trade_direction = trade.direction  # PURCHASE, SALE, COMMISSION_PURCHASE, COMMISSION_SALE

        # Determine transaction type, OUR company, and the COUNTERPARTY.
        # Both sides come from `_resolve_trade_sides` so "which end of the trade
        # is us" is decided exactly once for all four directions.
        if trade_direction not in _TRADE_DIRECTION_SIDES:
            continue  # Unknown trade type
        txn_type = trade_direction
        own, party = _resolve_trade_sides(trade, trade_direction)
        company_id = own.id if own else None
        company_name = own.name if own else 'Unknown'
        # Absent counterparty stays None — the UI renders 'N/A'. Do NOT fall
        # back to the licence holder or to `company_name`: that would silently
        # present our own company as the party we traded with.
        party_id = party.id if party else None
        party_name = (party.name if party else None) or None

        # Calculate total CIF for this trade in this license
        total_cif = Decimal('0.00')

        # SION norms and item names are DFIA-only: incentive trade lines
        # reference an IncentiveLicense directly and carry no licence items.
        sion_norms = ''
        item_names: List[str] = []

        if license_type == 'DFIA':
            # Prefetched above, already filtered to this license.
            for line in trade.license_lines:
                # Extract CIF value (with currency conversion if needed)
                line_cif = _extract_line_cif(line)
                total_cif += line_cif
            sion_norms = _extract_sion_norms(trade.license_lines)
            item_names = _extract_item_names(trade.license_lines)
            bill_amount = _extract_bill_amount(trade.license_lines)
            rate = _extract_exchange_rate(trade.license_lines)
        else:
            # Incentive license (prefetched, already filtered to this license)
            lines = trade.license_incentive_lines
            incentive_line = lines[0] if lines else None
            if incentive_line:
                total_cif = to_decimal(incentive_line.license_value, DEC_0)
            bill_amount = _extract_bill_amount(lines)
            rate = None

        # Include transaction even if zero-amount (per Scenario 7: zero txns visible but not counted)
        # Zero-amount transactions will not affect balance since amount=0
        transactions.append({
            'date': txn_date,
            'id': trade.id,
            'invoice_number': trade.invoice_number or '',
            'type': txn_type,
            'company_id': company_id,
            'company_name': company_name,
            'party_id': party_id,
            'party_name': party_name,
            'amount': total_cif,
            'bill_amount': bill_amount,
            'rate': rate,
            'item_names': item_names,
            'sion_norms': sion_norms,
        })

    # Sort deterministically: date ASC, then trade ID ASC
    transactions.sort(key=lambda x: (x['date'], x['id']))

    return transactions


#: Which end of a `LicenseTrade` is OUR company and which is the COUNTERPARTY,
#: per trade direction: ``{direction: (own_attr, party_attr)}``.
#
#  A LicenseTrade always runs `from_company` → `to_company`. Which end is "us"
#  depends on the direction:
#
#      direction             own (grouped by)  party (Particulars)
#      --------------------  ----------------  -------------------
#      PURCHASE              to_company        from_company   (we bought FROM)
#      SALE                  from_company      to_company     (we sold TO)
#      COMMISSION_PURCHASE   to_company        from_company
#      COMMISSION_SALE       from_company      to_company
#
#  The ledger table GROUPS BY the `own` side, so repeating it in the row's
#  Particulars cell would just echo the group header. Particulars shows the
#  `party` — the company on the other side of the trade.
_TRADE_DIRECTION_SIDES: Dict[str, tuple] = {
    'PURCHASE': ('to_company', 'from_company'),
    'SALE': ('from_company', 'to_company'),
    'COMMISSION_PURCHASE': ('to_company', 'from_company'),
    'COMMISSION_SALE': ('from_company', 'to_company'),
}


def _resolve_trade_sides(trade, direction: str) -> tuple:
    """
    ``(own_company, counterparty)`` for one trade — either may be None.

    Both FKs are `select_related` by `_fetch_transactions`, so this touches no
    database. Direction is validated by the caller against
    `_TRADE_DIRECTION_SIDES`.
    """
    own_attr, party_attr = _TRADE_DIRECTION_SIDES[direction]
    return getattr(trade, own_attr, None), getattr(trade, party_attr, None)


def _extract_item_names(lines) -> List[str]:
    """
    The licence item names billed on one trade — deduped, first-seen order.

    Same traversal as `_extract_sion_norms` (the norm hangs off the item), so it
    rides the SAME `sr_number__items__sion_norm_class` prefetch and costs no
    extra query:

        line.sr_number (LicenseImportItemsModel) -> .items (M2M ItemNameModel).name

    Returned as a LIST, not a joined string: a trade legitimately bills several
    items, and the UI must be able to show "+2 more" / a tooltip without
    re-splitting a string. Returning a list also keeps the caller from being
    tempted to duplicate the transaction row per item — one trade is ONE ledger
    row regardless of how many items it bills.

    DFIA only (callers pass [] for incentive licenses). Empty when no billed
    item resolves to a name.
    """
    names: List[str] = []
    for line in lines:
        sr_number = getattr(line, 'sr_number', None)
        if not sr_number:
            continue
        for item in sr_number.items.all():
            name = (getattr(item, 'name', '') or '').strip()
            if name and name not in names:
                names.append(name)
    return names


def _extract_bill_amount(lines) -> Decimal:
    """
    The actual INVOICE / BILL value of one trade, in **INR** — Σ `amount_inr`
    over the trade's lines for this licence.

    ⚠ NOT THE SAME NUMBER AS `amount` ⚠
    `amount` is the LICENCE value consumed by the trade (CIF FC — USD — for
    DFIA, `license_value` for incentive). `bill_amount` is what was actually
    invoiced, in INR. They are different quantities in different currencies and
    must never be substituted for one another, summed together, or assumed
    equal — a licence can be sold at any margin over the CIF it releases.

    `amount_inr` exists on BOTH `LicenseTradeLine` and `IncentiveTradeLine`
    (same name, same meaning), so this one helper serves both branches.

    Returns `DEC_0` for a trade with no lines — an unbilled trade, not a
    missing-data error.
    """
    total = DEC_0
    for line in lines or ():
        total += to_decimal(getattr(line, 'amount_inr', None), DEC_0)
    return quantize_2dp(total)


def _extract_exchange_rate(lines) -> Optional[Decimal]:
    """Return one real line exchange rate, or ``None`` when unavailable/mixed.

    This is presentation metadata only.  In particular, it is never used to
    calculate the already-canonical INR bill amount.
    """
    rates = []
    for line in lines or ():
        value = to_decimal(getattr(line, 'exc_rate', None), DEC_0)
        if value > DEC_0 and value not in rates:
            rates.append(value)
    return rates[0] if len(rates) == 1 else None


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


def _extract_sion_norms(lines) -> str:
    """
    THE single SION-norm resolution for the ledger: the norms of the licence
    items billed on one trade.

    **This is a PRESENTATION-LAYER DERIVATION, not a ledger fact.** There is no
    transaction→norm relationship in the data model: `LicenseImportItemsModel`
    (what a trade line bills, via `sr_number`) has no norm field at all. The
    norm lives two hops away on the item NAME:

        line.sr_number (LicenseImportItemsModel)
          -> .items (M2M ItemNameModel)
            -> .sion_norm_class (SionNormClassModel).norm_class

    Same traversal, dedup rule (first-seen order) and ', ' join as the legacy
    `build_dfia_ledger_detail`/PDF ledger it replaces, so the string shape is
    unchanged for existing consumers.

    DFIA only — callers pass '' for incentive licenses. Returns '' when no
    billed item carries a norm. Relies on the caller having prefetched
    `sr_number__items__sion_norm_class` (see `_fetch_transactions`); without
    that prefetch this is still correct, just query-heavy.
    """
    norms: List[str] = []
    for line in lines:
        sr_number = getattr(line, 'sr_number', None)
        if not sr_number:
            continue
        for item in sr_number.items.all():
            norm_class = getattr(item, 'sion_norm_class', None)
            norm = getattr(norm_class, 'norm_class', None) if norm_class else None
            if norm and norm not in norms:
                norms.append(norm)
    return ', '.join(norms)


def _get_company_names_for_ids(company_ids) -> Dict[int, str]:
    """
    Resolve {company_id: company_name} for many companies in a SINGLE query.

    Unknown/missing ids are simply absent from the returned map; callers
    default to 'Unknown'.
    """
    ids = [cid for cid in company_ids if cid]
    if not ids:
        return {}
    try:
        from apps.core.models import CompanyModel
        return {
            row['id']: (row['name'] or 'Unknown')
            for row in CompanyModel.objects.filter(id__in=ids).values('id', 'name')
        }
    except Exception:
        return {}
