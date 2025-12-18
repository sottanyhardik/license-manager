# trade/ledger_views.py
"""
Ledger Module Views - API endpoints for accounting system
"""

from decimal import Decimal
from datetime import datetime, timedelta
from django.db.models import Sum, Q, F, Case, When, Value, CharField
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from .models import (
    ChartOfAccounts, BankAccount, JournalEntry, JournalEntryLine,
    LicenseTrade, LicenseTradePayment, q2
)
from .serializers import (
    ChartOfAccountsSerializer, BankAccountSerializer,
    JournalEntrySerializer, JournalEntryLineSerializer,
    PartyLedgerSerializer, AccountLedgerSerializer
)
from core.models import CompanyModel


class ChartOfAccountsViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Chart of Accounts

    list: Get all accounts
    retrieve: Get specific account
    create: Create new account
    update: Update account
    destroy: Delete account (soft delete by setting is_active=False)
    """
    queryset = ChartOfAccounts.objects.all()
    serializer_class = ChartOfAccountsSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['account_type', 'is_active', 'parent']
    search_fields = ['code', 'name', 'description', 'linked_company__name']
    ordering_fields = ['code', 'name', 'account_type', 'created_on']
    ordering = ['code']

    def get_queryset(self):
        """Optimize queryset with select_related"""
        return super().get_queryset().select_related('parent', 'linked_company')

    @action(detail=False, methods=['get'])
    def balance_sheet(self, request):
        """
        Get balance sheet - all accounts grouped by type with balances

        GET /api/chart-of-accounts/balance_sheet/?as_of_date=2024-12-31
        """
        as_of_date = request.query_params.get('as_of_date', timezone.now().date())
        accounts = self.get_queryset().filter(is_active=True)

        assets = []
        liabilities = []
        equity = []

        total_assets = Decimal('0.00')
        total_liabilities = Decimal('0.00')
        total_equity = Decimal('0.00')

        for account in accounts:
            balance = account.balance
            data = {
                'code': account.code,
                'name': account.name,
                'balance': float(balance)
            }

            if account.account_type == 'ASSET':
                assets.append(data)
                total_assets += balance
            elif account.account_type == 'LIABILITY':
                liabilities.append(data)
                total_liabilities += balance
            elif account.account_type == 'EQUITY':
                equity.append(data)
                total_equity += balance

        return Response({
            'assets': assets,
            'liabilities': liabilities,
            'equity': equity,
            'total_assets': float(total_assets),
            'total_liabilities': float(total_liabilities),
            'total_equity': float(total_equity),
            'total_liabilities_and_equity': float(total_liabilities + total_equity),
            'as_of_date': as_of_date
        })

    @action(detail=False, methods=['get'])
    def trial_balance(self, request):
        """
        Get trial balance - all accounts with debit/credit totals

        GET /api/chart-of-accounts/trial_balance/?as_of_date=2024-12-31&account_type=ASSET
        """
        as_of_date = request.query_params.get('as_of_date', timezone.now().date())
        account_type = request.query_params.get('account_type')

        accounts = self.get_queryset().filter(is_active=True)
        if account_type:
            accounts = accounts.filter(account_type=account_type)

        trial_balance_data = []
        total_debit = Decimal('0.00')
        total_credit = Decimal('0.00')
        summary_by_type = {}

        for account in accounts:
            balance = account.balance

            # Determine if balance is debit or credit
            if account.account_type in ['ASSET', 'EXPENSE']:
                # Debit balance accounts
                debit_balance = balance if balance > 0 else Decimal('0.00')
                credit_balance = abs(balance) if balance < 0 else Decimal('0.00')
            else:
                # Credit balance accounts
                credit_balance = balance if balance > 0 else Decimal('0.00')
                debit_balance = abs(balance) if balance < 0 else Decimal('0.00')

            total_debit += debit_balance
            total_credit += credit_balance

            # Add to summary by type
            if account.account_type not in summary_by_type:
                summary_by_type[account.account_type] = {
                    'total_debit': Decimal('0.00'),
                    'total_credit': Decimal('0.00')
                }
            summary_by_type[account.account_type]['total_debit'] += debit_balance
            summary_by_type[account.account_type]['total_credit'] += credit_balance

            trial_balance_data.append({
                'code': account.code,
                'name': account.name,
                'account_type': account.account_type,
                'balance': float(balance),
                'debit_balance': float(debit_balance),
                'credit_balance': float(credit_balance)
            })

        # Format summary
        summary_list = []
        for acc_type, totals in summary_by_type.items():
            summary_list.append({
                'account_type': acc_type,
                'total_debit': float(totals['total_debit']),
                'total_credit': float(totals['total_credit']),
                'net_balance': float(totals['total_debit'] - totals['total_credit'])
            })

        return Response({
            'accounts': trial_balance_data,
            'total_debit': float(total_debit),
            'total_credit': float(total_credit),
            'difference': float(total_debit - total_credit),
            'summary_by_type': summary_list,
            'as_of_date': as_of_date
        })

    @action(detail=False, methods=['get'])
    def profit_loss(self, request):
        """
        Get profit & loss statement

        GET /api/chart-of-accounts/profit_loss/?date_from=2024-04-01&date_to=2025-03-31
        """
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')

        if not date_from or not date_to:
            # Default to current financial year
            today = timezone.now().date()
            if today.month >= 4:
                date_from = f"{today.year}-04-01"
                date_to = f"{today.year + 1}-03-31"
            else:
                date_from = f"{today.year - 1}-04-01"
                date_to = f"{today.year}-03-31"

        # Get revenue and expense accounts
        revenue_accounts = self.get_queryset().filter(account_type='REVENUE', is_active=True)
        expense_accounts = self.get_queryset().filter(account_type='EXPENSE', is_active=True)

        revenue = []
        expenses = []
        total_revenue = Decimal('0.00')
        total_expenses = Decimal('0.00')

        for account in revenue_accounts:
            balance = account.balance
            revenue.append({
                'code': account.code,
                'name': account.name,
                'balance': float(balance)
            })
            total_revenue += balance

        for account in expense_accounts:
            balance = account.balance
            expenses.append({
                'code': account.code,
                'name': account.name,
                'balance': float(balance)
            })
            total_expenses += balance

        net_profit = total_revenue - total_expenses

        return Response({
            'revenue': revenue,
            'expenses': expenses,
            'total_revenue': float(total_revenue),
            'total_expenses': float(total_expenses),
            'net_profit': float(net_profit),
            'date_from': date_from,
            'date_to': date_to
        })


class BankAccountViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Bank Accounts
    """
    queryset = BankAccount.objects.all()
    serializer_class = BankAccountSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['bank_name', 'is_active']
    search_fields = ['account_name', 'bank_name', 'account_number', 'ifsc_code']
    ordering_fields = ['account_name', 'bank_name', 'created_on']
    ordering = ['bank_name', 'account_name']

    def get_queryset(self):
        """Optimize queryset with select_related"""
        return super().get_queryset().select_related('ledger_account')

    @action(detail=True, methods=['get'])
    def statement(self, request, pk=None):
        """
        Get bank statement for specific account

        GET /api/bank-accounts/{id}/statement/?from_date=2024-01-01&to_date=2024-12-31
        """
        bank_account = self.get_object()
        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date')

        # Get all journal entry lines for this bank account's ledger
        lines = JournalEntryLine.objects.filter(
            account=bank_account.ledger_account,
            journal_entry__is_posted=True
        ).select_related('journal_entry')

        if from_date:
            lines = lines.filter(journal_entry__entry_date__gte=from_date)
        if to_date:
            lines = lines.filter(journal_entry__entry_date__lte=to_date)

        lines = lines.order_by('journal_entry__entry_date', 'journal_entry__id')

        # Build statement
        transactions = []
        running_balance = bank_account.opening_balance

        for line in lines:
            debit = line.debit_amount
            credit = line.credit_amount
            running_balance += (debit - credit)

            transactions.append({
                'date': line.journal_entry.entry_date,
                'entry_number': line.journal_entry.entry_number,
                'narration': line.journal_entry.narration,
                'debit': float(debit),
                'credit': float(credit),
                'balance': float(running_balance)
            })

        return Response({
            'bank_account': self.get_serializer(bank_account).data,
            'opening_balance': float(bank_account.opening_balance),
            'closing_balance': float(running_balance),
            'transactions': transactions,
            'from_date': from_date,
            'to_date': to_date
        })


class JournalEntryViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Journal Entries
    """
    queryset = JournalEntry.objects.all()
    serializer_class = JournalEntrySerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['entry_type', 'is_posted', 'is_auto_generated', 'entry_date']
    search_fields = ['entry_number', 'narration', 'reference_number']
    ordering_fields = ['entry_date', 'entry_number', 'created_on']
    ordering = ['-entry_date', '-entry_number']

    def get_queryset(self):
        """Optimize queryset with prefetch_related"""
        return super().get_queryset().select_related(
            'linked_trade', 'linked_payment', 'created_by'
        ).prefetch_related('lines__account')

    def perform_create(self, serializer):
        """Set created_by on create"""
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def post(self, request, pk=None):
        """
        Post a journal entry (make immutable)

        POST /api/journal-entries/{id}/post/
        """
        entry = self.get_object()

        try:
            entry.post()
            return Response({
                'message': 'Journal entry posted successfully',
                'entry': self.get_serializer(entry).data
            })
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'])
    def unpost(self, request, pk=None):
        """
        Unpost a journal entry (allow modifications)

        POST /api/journal-entries/{id}/unpost/
        """
        entry = self.get_object()

        try:
            entry.unpost()
            return Response({
                'message': 'Journal entry unposted successfully',
                'entry': self.get_serializer(entry).data
            })
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['post'])
    def generate_from_trade(self, request):
        """
        Auto-generate journal entry from a trade

        POST /api/journal-entries/generate_from_trade/
        Body: {"trade_id": 123}
        """
        trade_id = request.data.get('trade_id')

        if not trade_id:
            return Response(
                {'error': 'trade_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            trade = LicenseTrade.objects.get(id=trade_id)
        except LicenseTrade.DoesNotExist:
            return Response(
                {'error': 'Trade not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check if journal entry already exists
        if trade.journal_entries.exists():
            return Response(
                {'error': 'Journal entry already exists for this trade'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Generate journal entry based on direction
        try:
            if trade.direction == 'PURCHASE':
                entry = self._generate_purchase_entry(trade, request.user)
            else:
                entry = self._generate_sale_entry(trade, request.user)

            return Response({
                'message': 'Journal entry generated successfully',
                'entry': self.get_serializer(entry).data
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response(
                {'error': f'Failed to generate journal entry: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

    def _generate_purchase_entry(self, trade, user):
        """Generate journal entry for purchase"""
        from django.db import transaction

        with transaction.atomic():
            # Create journal entry
            entry = JournalEntry.objects.create(
                entry_number=f"PE-{trade.invoice_number}",
                entry_date=trade.invoice_date,
                entry_type='PURCHASE',
                linked_trade=trade,
                narration=f"Purchase from {trade.from_company.name} - Invoice {trade.invoice_number}",
                reference_number=trade.invoice_number,
                is_auto_generated=True,
                created_by=user
            )

            # Get or create accounts
            purchase_account, _ = ChartOfAccounts.objects.get_or_create(
                code='5000',
                defaults={
                    'name': 'Purchase',
                    'account_type': 'EXPENSE'
                }
            )

            creditor_account, _ = ChartOfAccounts.objects.get_or_create(
                code=f'2-{trade.from_company.id}',
                defaults={
                    'name': f'Sundry Creditor - {trade.from_company.name}',
                    'account_type': 'LIABILITY',
                    'linked_company': trade.from_company
                }
            )

            # Debit: Purchase
            JournalEntryLine.objects.create(
                journal_entry=entry,
                account=purchase_account,
                debit_amount=trade.total_amount,
                credit_amount=Decimal('0.00'),
                description=f"Purchase from {trade.from_company.name}"
            )

            # Credit: Sundry Creditor
            JournalEntryLine.objects.create(
                journal_entry=entry,
                account=creditor_account,
                debit_amount=Decimal('0.00'),
                credit_amount=trade.total_amount,
                description=f"Amount payable to {trade.from_company.name}"
            )

            # Auto-post
            entry.post()

            return entry

    def _generate_sale_entry(self, trade, user):
        """Generate journal entry for sale"""
        from django.db import transaction

        with transaction.atomic():
            # Create journal entry
            entry = JournalEntry.objects.create(
                entry_number=f"SE-{trade.invoice_number}",
                entry_date=trade.invoice_date,
                entry_type='SALES',
                linked_trade=trade,
                narration=f"Sale to {trade.to_company.name} - Invoice {trade.invoice_number}",
                reference_number=trade.invoice_number,
                is_auto_generated=True,
                created_by=user
            )

            # Get or create accounts
            sales_account, _ = ChartOfAccounts.objects.get_or_create(
                code='4000',
                defaults={
                    'name': 'Sales',
                    'account_type': 'REVENUE'
                }
            )

            debtor_account, _ = ChartOfAccounts.objects.get_or_create(
                code=f'1-{trade.to_company.id}',
                defaults={
                    'name': f'Sundry Debtor - {trade.to_company.name}',
                    'account_type': 'ASSET',
                    'linked_company': trade.to_company
                }
            )

            # Debit: Sundry Debtor
            JournalEntryLine.objects.create(
                journal_entry=entry,
                account=debtor_account,
                debit_amount=trade.total_amount,
                credit_amount=Decimal('0.00'),
                description=f"Amount receivable from {trade.to_company.name}"
            )

            # Credit: Sales
            JournalEntryLine.objects.create(
                journal_entry=entry,
                account=sales_account,
                debit_amount=Decimal('0.00'),
                credit_amount=trade.total_amount,
                description=f"Sale to {trade.to_company.name}"
            )

            # Auto-post
            entry.post()

            return entry


class PartyLedgerView(APIView):
    """
    Party-wise ledger - all transactions with a specific company

    GET /api/ledger/party/{company_id}/?from_date=2024-01-01&to_date=2024-12-31
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, company_id):
        try:
            company = CompanyModel.objects.get(id=company_id)
        except CompanyModel.DoesNotExist:
            return Response(
                {'error': 'Company not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date')

        # Get all trades with this company
        trades_from = LicenseTrade.objects.filter(from_company=company)
        trades_to = LicenseTrade.objects.filter(to_company=company)

        if from_date:
            trades_from = trades_from.filter(invoice_date__gte=from_date)
            trades_to = trades_to.filter(invoice_date__gte=from_date)
        if to_date:
            trades_from = trades_from.filter(invoice_date__lte=to_date)
            trades_to = trades_to.filter(invoice_date__lte=to_date)

        # Get payments for trades with this company
        payments_for = LicenseTradePayment.objects.filter(
            Q(trade__from_company=company) | Q(trade__to_company=company)
        )

        if from_date:
            payments_for = payments_for.filter(date__gte=from_date)
        if to_date:
            payments_for = payments_for.filter(date__lte=to_date)

        # Build ledger entries
        transactions = []

        # Add purchases (we bought from this company - Credit balance)
        for trade in trades_from:
            transactions.append({
                'date': trade.invoice_date,
                'type': 'PURCHASE',
                'reference': trade.invoice_number,
                'description': f"Purchase - {trade.invoice_number}",
                'debit': 0.00,
                'credit': float(trade.total_amount)
            })

        # Add sales (we sold to this company - Debit balance)
        for trade in trades_to:
            transactions.append({
                'date': trade.invoice_date,
                'type': 'SALE',
                'reference': trade.invoice_number,
                'description': f"Sale - {trade.invoice_number}",
                'debit': float(trade.total_amount),
                'credit': 0.00
            })

        # Add payments
        for payment in payments_for:
            trade = payment.trade
            if trade.direction == 'PURCHASE':
                # Payment made to supplier
                trans_type = 'PAYMENT'
                debit = float(payment.amount)
                credit = 0.00
                description = f"Payment for {trade.invoice_number}"
            else:
                # Receipt from customer
                trans_type = 'RECEIPT'
                debit = 0.00
                credit = float(payment.amount)
                description = f"Receipt for {trade.invoice_number}"

            transactions.append({
                'date': payment.date,
                'type': trans_type,
                'reference': f"PAY-{payment.id}",
                'description': description,
                'debit': debit,
                'credit': credit
            })

        # Sort by date
        transactions.sort(key=lambda x: x['date'])

        # Calculate running balance
        running_balance = Decimal('0.00')
        for trans in transactions:
            running_balance += (Decimal(str(trans['debit'])) - Decimal(str(trans['credit'])))
            trans['balance'] = float(running_balance)

        # Calculate totals
        total_debit = sum(Decimal(str(t['debit'])) for t in transactions)
        total_credit = sum(Decimal(str(t['credit'])) for t in transactions)

        return Response({
            'company_name': company.name,
            'opening_balance': 0.00,  # Can be calculated from prior period
            'transactions': transactions,
            'total_debit': float(total_debit),
            'total_credit': float(total_credit),
            'closing_balance': float(running_balance),
            'from_date': from_date,
            'to_date': to_date
        })


class AccountLedgerView(APIView):
    """
    Account-wise ledger - all journal entries for a specific account

    GET /api/ledger/account/{account_id}/?from_date=2024-01-01&to_date=2024-12-31
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, account_id):
        try:
            account = ChartOfAccounts.objects.get(id=account_id)
        except ChartOfAccounts.DoesNotExist:
            return Response(
                {'error': 'Account not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date')

        # Get all journal entry lines for this account
        lines = JournalEntryLine.objects.filter(
            account=account,
            journal_entry__is_posted=True
        ).select_related('journal_entry')

        if from_date:
            lines = lines.filter(journal_entry__entry_date__gte=from_date)
        if to_date:
            lines = lines.filter(journal_entry__entry_date__lte=to_date)

        lines = lines.order_by('journal_entry__entry_date', 'journal_entry__id')

        # Build ledger entries
        transactions = []
        running_balance = Decimal('0.00')

        for line in lines:
            debit = line.debit_amount
            credit = line.credit_amount

            # Calculate balance based on account type
            if account.account_type in ['ASSET', 'EXPENSE']:
                running_balance += (debit - credit)
            else:
                running_balance += (credit - debit)

            transactions.append({
                'date': line.journal_entry.entry_date,
                'entry_number': line.journal_entry.entry_number,
                'narration': line.journal_entry.narration,
                'debit': float(debit),
                'credit': float(credit),
                'balance': float(running_balance)
            })

        # Calculate totals
        total_debit = sum(Decimal(str(t['debit'])) for t in transactions)
        total_credit = sum(Decimal(str(t['credit'])) for t in transactions)

        return Response({
            'account': {
                'id': account.id,
                'code': account.code,
                'name': account.name,
                'account_type': account.account_type
            },
            'transactions': transactions,
            'summary': {
                'total_debit': float(total_debit),
                'total_credit': float(total_credit),
                'balance': float(running_balance)
            },
            'from_date': from_date,
            'to_date': to_date
        })


class OutstandingInvoicesView(APIView):
    """
    Outstanding invoices report - receivables and payables

    GET /api/ledger/reports/outstanding-invoices/?type=receivable&as_of_date=2024-12-31
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        as_of_date_str = request.query_params.get('as_of_date')
        if as_of_date_str:
            as_of_date = datetime.strptime(as_of_date_str, '%Y-%m-%d').date()
        else:
            as_of_date = timezone.now().date()

        report_type = request.query_params.get('type')  # receivable, payable, or all

        # Get all trades up to the as_of_date
        trades = LicenseTrade.objects.filter(
            invoice_date__lte=as_of_date
        ).select_related('to_company', 'from_company')

        # Filter by type if specified
        if report_type == 'receivable':
            trades = trades.filter(direction='SALE')
        elif report_type == 'payable':
            trades = trades.filter(direction='PURCHASE')

        invoices = []
        total_receivables = Decimal('0.00')
        total_payables = Decimal('0.00')
        aging = {
            'current': Decimal('0.00'),
            'days_1_30': Decimal('0.00'),
            'days_31_60': Decimal('0.00'),
            'over_60_days': Decimal('0.00')
        }

        for trade in trades:
            due = trade.due_amount
            if due > 0:
                company = trade.to_company if trade.direction == 'SALE' else trade.from_company

                # Calculate days outstanding
                days_outstanding = (as_of_date - trade.invoice_date).days

                # Calculate aging
                if days_outstanding <= 0:
                    aging['current'] += due
                elif days_outstanding <= 30:
                    aging['days_1_30'] += due
                elif days_outstanding <= 60:
                    aging['days_31_60'] += due
                else:
                    aging['over_60_days'] += due

                invoice_data = {
                    'type': 'RECEIVABLE' if trade.direction == 'SALE' else 'PAYABLE',
                    'party_name': company.name if company else 'Unknown',
                    'invoice_number': trade.invoice_number,
                    'invoice_date': trade.invoice_date.isoformat(),
                    'due_date': None,  # Can be added if due_date field exists
                    'total_amount': float(trade.total_amount),
                    'paid_amount': float(trade.paid_or_received),
                    'outstanding_amount': float(due),
                    'days_outstanding': days_outstanding
                }
                invoices.append(invoice_data)

                if trade.direction == 'SALE':
                    total_receivables += due
                else:
                    total_payables += due

        # Sort by days outstanding (descending)
        invoices.sort(key=lambda x: x['days_outstanding'], reverse=True)

        return Response({
            'invoices': invoices,
            'total_outstanding': float(total_receivables + total_payables),
            'total_receivables': float(total_receivables),
            'total_payables': float(total_payables),
            'aging': {
                'current': float(aging['current']),
                'days_1_30': float(aging['days_1_30']),
                'days_31_60': float(aging['days_31_60']),
                'over_60_days': float(aging['over_60_days'])
            },
            'as_of_date': as_of_date.isoformat()
        })


class AgingAnalysisView(APIView):
    """
    Aging analysis report - categorize outstanding by age

    GET /api/ledger/reports/aging-analysis/?type=receivable
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        report_type = request.query_params.get('type', 'receivable')

        if report_type == 'receivable':
            trades = LicenseTrade.objects.filter(direction='SALE').select_related('to_company')
        else:
            trades = LicenseTrade.objects.filter(direction='PURCHASE').select_related('from_company')

        aging = {
            '0-30': [],
            '31-60': [],
            '61-90': [],
            '90+': []
        }

        totals = {
            '0-30': Decimal('0.00'),
            '31-60': Decimal('0.00'),
            '61-90': Decimal('0.00'),
            '90+': Decimal('0.00')
        }

        today = timezone.now().date()

        for trade in trades:
            due = trade.due_amount
            if due > 0:
                days = (today - trade.invoice_date).days
                company = trade.to_company if report_type == 'receivable' else trade.from_company

                entry = {
                    'invoice_number': trade.invoice_number,
                    'invoice_date': trade.invoice_date,
                    'company': company.name if company else 'Unknown',
                    'amount': float(due),
                    'days': days
                }

                if days <= 30:
                    aging['0-30'].append(entry)
                    totals['0-30'] += due
                elif days <= 60:
                    aging['31-60'].append(entry)
                    totals['31-60'] += due
                elif days <= 90:
                    aging['61-90'].append(entry)
                    totals['61-90'] += due
                else:
                    aging['90+'].append(entry)
                    totals['90+'] += due

        return Response({
            'type': report_type,
            'aging': aging,
            'totals': {
                '0-30': float(totals['0-30']),
                '31-60': float(totals['31-60']),
                '61-90': float(totals['61-90']),
                '90+': float(totals['90+']),
                'total': float(sum(totals.values()))
            }
        })
