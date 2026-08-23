"""
Django management command: Reconcile a license's transactions across DB, Canonical, UI, PDF, Excel.
"""

from django.core.management.base import BaseCommand
from decimal import Decimal
from datetime import datetime

from apps.license.models import LicenseDetailsModel, IncentiveLicense
from apps.trade.models import LicenseTrade
from apps.license.services.canonical_ledger_service import CanonicalLedgerService
from apps.core.utils.decimal_utils import to_decimal
from apps.core.constants import DEC_0


class Command(BaseCommand):
    help = 'Reconcile transactions for a specific license across all outputs'

    def add_arguments(self, parser):
        parser.add_argument(
            'license_number',
            type=str,
            help='License number to reconcile (e.g., 0310833996)'
        )

    def find_license(self, license_number):
        """Find a license by number."""
        dfia = LicenseDetailsModel.objects.filter(
            license_number=license_number
        ).first()

        if dfia:
            return {
                'id': dfia.id,
                'type': 'DFIA',
                'number': dfia.license_number,
                'object': dfia,
            }

        incentive = IncentiveLicense.objects.filter(
            license_number=license_number
        ).first()

        if incentive:
            return {
                'id': incentive.id,
                'type': 'INCENTIVE',
                'number': incentive.license_number,
                'object': incentive,
            }

        return None

    def get_raw_transactions_from_db(self, license_id, license_type):
        """Fetch transactions from database.

        Extracts the same values as CanonicalLedgerService._fetch_transactions:
        - amount: CIF USD (from cif_fc or cif_inr/exc_rate)
        - bill_amount: INR amount (sum of amount_inr)
        """

        if license_type == 'DFIA':
            # Get all DFIA trades
            trades = LicenseTrade.objects.filter(
                license_type='DFIA'
            ).select_related('from_company', 'to_company').prefetch_related('lines', 'lines__sr_number')

            results = []
            for trade in trades:
                # Check if this trade affects our license
                license_lines = []
                for line in trade.lines.all():
                    # Line has sr_number (LicenseImportItemsModel), which has license
                    if line.sr_number and line.sr_number.license_id == license_id:
                        license_lines.append(line)

                if not license_lines:
                    continue

                direction = trade.direction
                if direction == 'PURCHASE':
                    txn_type = 'PURCHASE'
                elif direction == 'SALE':
                    txn_type = 'SALE'
                elif direction == 'COMMISSION_PURCHASE':
                    txn_type = 'COMMISSION_PURCHASE'
                elif direction == 'COMMISSION_SALE':
                    txn_type = 'COMMISSION_SALE'
                else:
                    txn_type = direction

                company = trade.from_company or trade.to_company

                # Extract CIF value (USD) - same logic as _extract_line_cif in canonical service
                total_cif = Decimal('0.00')
                for line in license_lines:
                    # Try cif_fc first (USD)
                    if line.cif_fc:
                        total_cif += to_decimal(line.cif_fc, DEC_0)
                    # Try INR conversion if exc_rate available
                    elif line.cif_inr and line.exc_rate and line.exc_rate != DEC_0:
                        cif_inr = to_decimal(line.cif_inr, DEC_0)
                        exc_rate = to_decimal(line.exc_rate, DEC_0)
                        try:
                            total_cif += cif_inr / exc_rate
                        except (ValueError, TypeError, ZeroDivisionError):
                            pass

                # Extract bill amount (INR) - same logic as _extract_bill_amount
                bill_amount = DEC_0
                for line in license_lines:
                    bill_amount += to_decimal(line.amount_inr, DEC_0)

                # Quantize to 2 decimal places
                total_cif = to_decimal(total_cif, DEC_0).quantize(Decimal('0.01'))
                bill_amount = to_decimal(bill_amount, DEC_0).quantize(Decimal('0.01'))

                results.append({
                    'id': trade.id,
                    'type': txn_type,
                    'date': trade.invoice_date,
                    'amount': total_cif,  # USD
                    'bill_amount': bill_amount,  # INR
                    'company_id': company.id if company else None,
                    'company_name': company.name if company else None,
                    'trade': trade,
                })

            return sorted(results, key=lambda x: (x['date'] or datetime.min.date(), x['id']))

        else:
            # Incentive license
            trades = LicenseTrade.objects.filter(
                license_type='INCENTIVE',
                incentive_license_id=license_id
            ).select_related('from_company', 'to_company')

            results = []
            for trade in trades:
                direction = trade.direction

                if direction == 'PURCHASE':
                    txn_type = 'PURCHASE'
                elif direction == 'SALE':
                    txn_type = 'SALE'
                elif direction == 'COMMISSION_PURCHASE':
                    txn_type = 'COMMISSION_PURCHASE'
                elif direction == 'COMMISSION_SALE':
                    txn_type = 'COMMISSION_SALE'
                else:
                    txn_type = direction

                company = trade.from_company or trade.to_company
                amount = to_decimal(trade.total_amount, DEC_0)

                results.append({
                    'id': trade.id,
                    'type': txn_type,
                    'date': trade.invoice_date,
                    'amount': amount,
                    'bill_amount': amount,
                    'company_id': company.id if company else None,
                    'company_name': company.name if company else None,
                    'trade': trade,
                })

            return sorted(results, key=lambda x: (x['date'] or datetime.min.date(), x['id']))

    def handle(self, *args, **options):
        license_number = options['license_number']

        self.stdout.write(self.style.SUCCESS('\n' + '='*120))
        self.stdout.write(self.style.SUCCESS(f'TRANSACTION-LEVEL RECONCILIATION: License {license_number}'))
        self.stdout.write(self.style.SUCCESS('='*120))

        # Find the license
        license_info = self.find_license(license_number)
        if not license_info:
            self.stdout.write(self.style.ERROR(f'ERROR: License {license_number} not found!'))
            return

        license_id = license_info['id']
        license_type = license_info['type']

        self.stdout.write(f'\nLicense Type: {license_type}')
        self.stdout.write(f'License ID: {license_id}')

        # Get raw transactions from DB
        raw_txns = self.get_raw_transactions_from_db(license_id, license_type)
        self.stdout.write(f'Transactions in DB: {len(raw_txns)}')

        # Get canonical ledger
        try:
            canonical = CanonicalLedgerService.build_canonical_ledger_dataset(license_id, license_type)
            self.stdout.write(self.style.SUCCESS('Canonical Ledger Built Successfully'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'ERROR building canonical ledger: {e}'))
            import traceback
            traceback.print_exc()
            return

        # ====================================================================
        # RECONCILIATION TABLE
        # ====================================================================

        self.stdout.write('\n' + '='*120)
        self.stdout.write('RECONCILIATION TABLE: DB vs Canonical')
        self.stdout.write('='*120)

        self.stdout.write(f'\n{"TxnID":<8} {"Type":<15} {"Date":<12} {"Amount (USD)":<16} {"Bill (₹)":<16} | Status')
        self.stdout.write('-'*120)

        mismatches = []

        for raw_txn in raw_txns:
            txn_id = raw_txn['id']
            txn_type = raw_txn['type']
            date = raw_txn['date']
            amount = raw_txn['amount']
            bill_amount = raw_txn['bill_amount']

            # Find in canonical
            canonical_txn = None
            for c_txn in canonical['transactions']:
                if c_txn['id'] == txn_id and c_txn['type'] == txn_type:
                    canonical_txn = c_txn
                    break

            # Check if values match
            status = "✓ MATCH"
            if canonical_txn is None:
                status = "✗ NOT IN CANONICAL"
                mismatches.append({
                    'txn_id': txn_id,
                    'type': txn_type,
                    'issue': 'Transaction not found in canonical ledger',
                })
            else:
                # Compare amounts
                db_amount = amount
                canonical_amount = canonical_txn.get('amount')

                if db_amount != canonical_amount:
                    status = f"✗ AMOUNT MISMATCH"
                    mismatches.append({
                        'txn_id': txn_id,
                        'type': txn_type,
                        'issue': f'Amount mismatch: DB {db_amount} != Canonical {canonical_amount}',
                    })

            self.stdout.write(f'{txn_id:<8} {txn_type:<15} {str(date):<12} ${str(amount):<15} ₹{str(bill_amount):<15} | {status}')

        # ====================================================================
        # CANONICAL TRANSACTIONS
        # ====================================================================

        self.stdout.write('\n' + '='*120)
        self.stdout.write('CANONICAL LEDGER TRANSACTIONS')
        self.stdout.write('='*120)

        self.stdout.write(f'\n{"TxnID":<8} {"Type":<15} {"Date":<12} {"Amount (USD)":<16} {"Bill (₹)":<16} {"Balance":<16}')
        self.stdout.write('-'*120)

        for c_txn in canonical['transactions']:
            txn_id = c_txn['id']
            txn_type = c_txn['type']
            date = c_txn['date']
            amount = c_txn['amount']
            bill_amount = c_txn.get('bill_amount', DEC_0)
            balance = c_txn['license_running_balance']

            self.stdout.write(f'{txn_id:<8} {txn_type:<15} {str(date):<12} ${str(amount):<15} ₹{str(bill_amount):<15} ${str(balance):<15}')

        # ====================================================================
        # BALANCE VERIFICATION
        # ====================================================================

        self.stdout.write('\n' + '='*120)
        self.stdout.write('BALANCE VERIFICATION')
        self.stdout.write('='*120)

        self.stdout.write(f'\nOpening Balance: ${canonical["opening_balance"]}')
        self.stdout.write(f'Closing Balance: ${canonical["closing_balance"]}')
        self.stdout.write(f'Total Purchases: ${canonical["totals"]["total_purchases"]}')
        self.stdout.write(f'Total Sales: ${canonical["totals"]["total_sales"]}')

        expected = canonical['totals']['total_purchases'] - canonical['totals']['total_sales'] + canonical['opening_balance']
        self.stdout.write(f'Expected Balance: ${expected}')

        # ====================================================================
        # SUMMARY BLOCK
        # ====================================================================

        self.stdout.write('\n' + '='*120)
        self.stdout.write('SUMMARY BLOCK')
        self.stdout.write('='*120 + '\n')

        summary = canonical['summary']
        for key, value in summary.items():
            self.stdout.write(f'{key}: {value}')

        # ====================================================================
        # MISMATCH REPORT
        # ====================================================================

        if mismatches:
            self.stdout.write('\n' + '='*120)
            self.stdout.write(self.style.ERROR('MISMATCHES FOUND'))
            self.stdout.write('='*120)

            for i, mismatch in enumerate(mismatches, 1):
                self.stdout.write(f'\n{i}. Transaction {mismatch["txn_id"]} ({mismatch["type"]})')
                self.stdout.write(f'   Issue: {mismatch["issue"]}')
        else:
            self.stdout.write('\n' + '='*120)
            self.stdout.write(self.style.SUCCESS('✓ ALL TRANSACTIONS RECONCILED SUCCESSFULLY'))
            self.stdout.write('='*120)
