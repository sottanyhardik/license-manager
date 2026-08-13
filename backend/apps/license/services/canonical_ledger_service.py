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

from django.db.models import Q, Sum, Value, DecimalField, Prefetch
from django.db.models.functions import Coalesce

from apps.license.domain.transaction_semantics import (
    TransactionSemantics,
    select_display_rows,
)
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
                }
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
                'date': metadata['license_date'],
                'id': 0,  # Opening is transaction 0
                'type': 'OPENING',
                'company_id': None,
                'company_name': None,
                'amount': opening_balance,
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
                'amount': amount,
                'is_commission': is_commission,
                'license_running_balance': running_balance,
                'company_utilization_after': company_util_after,
                'affects_balance': affects_balance,
                'sion_norms': txn_data.get('sion_norms', ''),
            })

        # Set final balances
        dataset['license_running_balance'] = running_balance
        dataset['closing_balance'] = running_balance

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

        return dataset


# ========== INTERNAL HELPERS ==========

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

        # SION norms are DFIA-only: incentive trade lines reference an
        # IncentiveLicense directly and carry no licence items, hence no norms.
        sion_norms = ''

        if license_type == 'DFIA':
            # Prefetched above, already filtered to this license.
            for line in trade.license_lines:
                # Extract CIF value (with currency conversion if needed)
                line_cif = _extract_line_cif(line)
                total_cif += line_cif
            sion_norms = _extract_sion_norms(trade.license_lines)
        else:
            # Incentive license (prefetched, already filtered to this license)
            lines = trade.license_incentive_lines
            incentive_line = lines[0] if lines else None
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
            'sion_norms': sion_norms,
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
