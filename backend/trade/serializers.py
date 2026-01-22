# trade/serializers.py

from rest_framework import serializers

from .models import (
    LicenseTrade, LicenseTradeLine, IncentiveTradeLine, LicenseTradePayment,
    ChartOfAccounts, BankAccount, JournalEntry, JournalEntryLine
)


class LicenseTradePaymentSerializer(serializers.ModelSerializer):
    """Serializer for payment settlements"""
    id = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    class Meta:
        model = LicenseTradePayment
        fields = ('id', 'date', 'amount', 'note')


class LicenseTradeLineSerializer(serializers.ModelSerializer):
    """Serializer for trade line items"""
    id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    sr_number_label = serializers.SerializerMethodField()
    computed_amount = serializers.SerializerMethodField()

    class Meta:
        model = LicenseTradeLine
        fields = (
            'id', 'sr_number', 'sr_number_label', 'description', 'hsn_code', 'mode',
            'qty_kg', 'rate_inr_per_kg', 'cif_fc', 'exc_rate', 'cif_inr',
            'fob_inr', 'pct', 'amount_inr', 'computed_amount'
        )

    def get_sr_number_label(self, obj):
        """Return license number, SR number, and description"""
        if obj.sr_number:
            # Get license number
            license_number = obj.sr_number.license.license_number if obj.sr_number.license else 'Unknown'

            # Use description if available, otherwise get first item name from ManyToMany
            if obj.sr_number.description:
                item_desc = obj.sr_number.description
            else:
                # Get first item from ManyToMany items field
                first_item = obj.sr_number.items.first()
                item_desc = first_item.name if first_item else 'Unknown'

            return f"{license_number} - SR {obj.sr_number.serial_number}"
        return None

    def get_computed_amount(self, obj):
        """Return computed amount based on mode"""
        return float(obj.compute_amount())


class IncentiveTradeLineSerializer(serializers.ModelSerializer):
    """Serializer for incentive trade line items"""
    id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    incentive_license_label = serializers.SerializerMethodField()

    class Meta:
        model = IncentiveTradeLine
        fields = ('id', 'incentive_license', 'incentive_license_label', 'license_value', 'rate_pct', 'amount_inr')

    def get_incentive_license_label(self, obj):
        """Return formatted incentive license label"""
        if obj.incentive_license:
            return f"{obj.incentive_license.license_type} - {obj.incentive_license.license_number}"
        return None


class LicenseTradeSerializer(serializers.ModelSerializer):
    """Nested serializer for LicenseTrade with lines and payments"""
    lines = LicenseTradeLineSerializer(many=True, required=False)
    incentive_lines = IncentiveTradeLineSerializer(many=True, required=False)
    payments = LicenseTradePaymentSerializer(many=True, required=False)

    # Display fields
    from_company_label = serializers.CharField(source='from_company.name', read_only=True)
    to_company_label = serializers.CharField(source='to_company.name', read_only=True)
    from_company = serializers.CharField(source='from_company.name', read_only=True)
    to_company = serializers.CharField(source='to_company.name', read_only=True)
    boe_label = serializers.CharField(source='boe.boe_number', read_only=True, allow_null=True)
    direction_label = serializers.CharField(source='get_direction_display', read_only=True)
    license_type_label = serializers.CharField(source='get_license_type_display', read_only=True)
    incentive_license = serializers.SerializerMethodField()

    # Computed fields
    paid_or_received = serializers.DecimalField(max_digits=20, decimal_places=2, read_only=True)
    due_amount = serializers.DecimalField(max_digits=20, decimal_places=2, read_only=True)

    def get_incentive_license(self, obj):
        """Return all license numbers (DFIA and Incentive) comma-separated"""
        license_numbers = set()

        # Get DFIA license numbers from trade lines
        for line in obj.lines.all():
            if line.sr_number and line.sr_number.license:
                license_numbers.add(line.sr_number.license.license_number)

        # Get Incentive license numbers from incentive_lines
        for line in obj.incentive_lines.all():
            if line.incentive_license:
                license_numbers.add(line.incentive_license.license_number)

        return ', '.join(sorted(license_numbers)) if license_numbers else None

    class Meta:
        model = LicenseTrade
        fields = '__all__'

    def create(self, validated_data):
        """Create trade with nested lines and payments"""
        lines_data = validated_data.pop('lines', [])
        incentive_lines_data = validated_data.pop('incentive_lines', [])
        payments_data = validated_data.pop('payments', [])

        # Create trade header
        trade = LicenseTrade.objects.create(**validated_data)

        # Snapshot party details
        trade.snapshot_parties()

        # Create lines (DFIA)
        for line_data in lines_data:
            line_data.pop('id', None)  # Remove temp ID
            LicenseTradeLine.objects.create(trade=trade, **line_data)

        # Create incentive lines (RODTEP/ROSTL/MEIS)
        for line_data in incentive_lines_data:
            line_data.pop('id', None)  # Remove temp ID
            IncentiveTradeLine.objects.create(trade=trade, **line_data)

        # Create payments
        for payment_data in payments_data:
            payment_data.pop('id', None)  # Remove temp ID
            LicenseTradePayment.objects.create(trade=trade, **payment_data)

        # Recompute totals
        trade.recompute_totals()
        trade.refresh_from_db()

        # Update BOE invoice_no if BOE is linked
        if trade.boe and trade.invoice_number:
            trade.boe.invoice_no = trade.invoice_number
            trade.boe.save(update_fields=['invoice_no'])

        return trade

    def update(self, instance, validated_data):
        """Update trade with nested lines and payments"""
        from core.helpers import _sync_nested

        lines_data = validated_data.pop('lines', None)
        incentive_lines_data = validated_data.pop('incentive_lines', None)
        payments_data = validated_data.pop('payments', None)

        # Track old BOE before update to clear invoice_no if BOE changes
        old_boe = instance.boe

        # Update header fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Snapshot party details if companies changed
        instance.snapshot_parties()

        # Sync nested lines if provided (DFIA)
        if lines_data is not None:
            _sync_nested(
                instance,
                LicenseTradeLine,
                lines_data,
                fk_field='trade',
                treat_empty_list_as_delete=False
            )

        # Sync nested incentive lines if provided (RODTEP/ROSTL/MEIS)
        if incentive_lines_data is not None:
            _sync_nested(
                instance,
                IncentiveTradeLine,
                incentive_lines_data,
                fk_field='trade',
                treat_empty_list_as_delete=False
            )

        # Sync nested payments if provided
        if payments_data is not None:
            _sync_nested(
                instance,
                LicenseTradePayment,
                payments_data,
                fk_field='trade',
                treat_empty_list_as_delete=False
            )

        # Recompute totals
        instance.recompute_totals()
        instance.refresh_from_db()

        # Handle BOE invoice_no updates
        # If BOE changed, clear invoice_no from old BOE
        if old_boe and old_boe != instance.boe:
            # Only clear if this trade's invoice is still on the old BOE
            if old_boe.invoice_no == instance.invoice_number:
                old_boe.invoice_no = None
                old_boe.save(update_fields=['invoice_no'])

        # Update new BOE with invoice_no if BOE is linked
        if instance.boe and instance.invoice_number:
            instance.boe.invoice_no = instance.invoice_number
            instance.boe.save(update_fields=['invoice_no'])

        return instance


class TradeLineSimpleSerializer(serializers.ModelSerializer):
    """Simple serializer for trade lines without nested data"""
    sr_number_label = serializers.CharField(source='sr_number.__str__', read_only=True)
    mode_label = serializers.CharField(source='get_mode_display', read_only=True)

    class Meta:
        model = LicenseTradeLine
        fields = '__all__'


# =============================================================================
# LEDGER MODULE SERIALIZERS
# =============================================================================

class ChartOfAccountsSerializer(serializers.ModelSerializer):
    """Serializer for Chart of Accounts"""
    parent_name = serializers.CharField(source='parent.__str__', read_only=True)
    company_name = serializers.CharField(source='linked_company.name', read_only=True)
    balance = serializers.DecimalField(max_digits=20, decimal_places=2, read_only=True)
    account_type_display = serializers.CharField(source='get_account_type_display', read_only=True)

    class Meta:
        model = ChartOfAccounts
        fields = [
            'id', 'code', 'name', 'account_type', 'account_type_display',
            'parent', 'parent_name', 'linked_company', 'company_name',
            'description', 'is_active', 'balance', 'created_on', 'modified_on'
        ]
        read_only_fields = ['balance', 'created_on', 'modified_on']


class BankAccountSerializer(serializers.ModelSerializer):
    """Serializer for Bank Accounts"""
    ledger_account_name = serializers.CharField(source='ledger_account.__str__', read_only=True)
    current_balance = serializers.DecimalField(max_digits=20, decimal_places=2, read_only=True)

    class Meta:
        model = BankAccount
        fields = [
            'id', 'account_name', 'bank_name', 'account_number', 'ifsc_code', 'branch',
            'ledger_account', 'ledger_account_name', 'opening_balance', 'opening_balance_date',
            'current_balance', 'is_active', 'created_on', 'modified_on'
        ]
        read_only_fields = ['current_balance', 'created_on', 'modified_on']


class JournalEntryLineSerializer(serializers.ModelSerializer):
    """Serializer for Journal Entry Lines"""
    account_name = serializers.CharField(source='account.__str__', read_only=True)
    account_code = serializers.CharField(source='account.code', read_only=True)

    class Meta:
        model = JournalEntryLine
        fields = [
            'id', 'account', 'account_name', 'account_code',
            'debit_amount', 'credit_amount', 'description'
        ]


class JournalEntrySerializer(serializers.ModelSerializer):
    """Serializer for Journal Entries"""
    lines = JournalEntryLineSerializer(many=True, required=False)
    total_debit = serializers.DecimalField(max_digits=20, decimal_places=2, read_only=True)
    total_credit = serializers.DecimalField(max_digits=20, decimal_places=2, read_only=True)
    is_balanced = serializers.BooleanField(read_only=True)
    entry_type_display = serializers.CharField(source='get_entry_type_display', read_only=True)
    linked_trade_invoice = serializers.CharField(source='linked_trade.invoice_number', read_only=True)
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = JournalEntry
        fields = [
            'id', 'entry_number', 'entry_date', 'entry_type', 'entry_type_display',
            'linked_trade', 'linked_trade_invoice', 'linked_payment',
            'narration', 'reference_number', 'is_posted', 'is_auto_generated',
            'total_debit', 'total_credit', 'is_balanced', 'lines',
            'created_by', 'created_by_username', 'created_on', 'modified_on'
        ]
        read_only_fields = ['total_debit', 'total_credit', 'is_balanced', 'created_on', 'modified_on']

    def create(self, validated_data):
        """Create journal entry with lines"""
        lines_data = validated_data.pop('lines', [])
        journal_entry = JournalEntry.objects.create(**validated_data)

        for line_data in lines_data:
            JournalEntryLine.objects.create(journal_entry=journal_entry, **line_data)

        return journal_entry

    def update(self, instance, validated_data):
        """Update journal entry and its lines"""
        lines_data = validated_data.pop('lines', None)

        # Check if entry is posted
        if instance.is_posted and not validated_data.get('is_posted', True):
            # Unposting is allowed
            pass
        elif instance.is_posted:
            raise serializers.ValidationError("Cannot modify posted entries")

        # Update journal entry fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update lines if provided
        if lines_data is not None:
            # Delete existing lines
            instance.lines.all().delete()

            # Create new lines
            for line_data in lines_data:
                JournalEntryLine.objects.create(journal_entry=instance, **line_data)

        return instance


class PartyLedgerSerializer(serializers.Serializer):
    """Serializer for party-wise ledger report"""
    company_id = serializers.IntegerField()
    company_name = serializers.CharField()
    date = serializers.DateField()
    transaction_type = serializers.CharField()  # SALE, PURCHASE, PAYMENT, RECEIPT, JOURNAL
    reference_number = serializers.CharField()
    narration = serializers.CharField()
    debit = serializers.DecimalField(max_digits=20, decimal_places=2)
    credit = serializers.DecimalField(max_digits=20, decimal_places=2)
    balance = serializers.DecimalField(max_digits=20, decimal_places=2)


class AccountLedgerSerializer(serializers.Serializer):
    """Serializer for account-wise ledger report"""
    account_id = serializers.IntegerField()
    account_code = serializers.CharField()
    account_name = serializers.CharField()
    date = serializers.DateField()
    entry_number = serializers.CharField()
    narration = serializers.CharField()
    debit = serializers.DecimalField(max_digits=20, decimal_places=2)
    credit = serializers.DecimalField(max_digits=20, decimal_places=2)
    balance = serializers.DecimalField(max_digits=20, decimal_places=2)
