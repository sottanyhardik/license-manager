# trade/serializers.py

from rest_framework import serializers

from .models import LicenseTrade, LicenseTradeLine, LicenseTradePayment


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


class LicenseTradeSerializer(serializers.ModelSerializer):
    """Nested serializer for LicenseTrade with lines and payments"""
    lines = LicenseTradeLineSerializer(many=True, required=False)
    payments = LicenseTradePaymentSerializer(many=True, required=False)

    # Display fields
    from_company_label = serializers.CharField(source='from_company.name', read_only=True)
    to_company_label = serializers.CharField(source='to_company.name', read_only=True)
    boe_label = serializers.CharField(source='boe.boe_number', read_only=True, allow_null=True)
    direction_label = serializers.CharField(source='get_direction_display', read_only=True)

    # Computed fields
    paid_or_received = serializers.DecimalField(max_digits=20, decimal_places=2, read_only=True)
    due_amount = serializers.DecimalField(max_digits=20, decimal_places=2, read_only=True)

    class Meta:
        model = LicenseTrade
        fields = '__all__'

    def create(self, validated_data):
        """Create trade with nested lines and payments"""
        lines_data = validated_data.pop('lines', [])
        payments_data = validated_data.pop('payments', [])

        # Create trade header
        trade = LicenseTrade.objects.create(**validated_data)

        # Snapshot party details
        trade.snapshot_parties()

        # Create lines
        for line_data in lines_data:
            line_data.pop('id', None)  # Remove temp ID
            LicenseTradeLine.objects.create(trade=trade, **line_data)

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
        payments_data = validated_data.pop('payments', None)

        # Track old BOE before update to clear invoice_no if BOE changes
        old_boe = instance.boe

        # Update header fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Snapshot party details if companies changed
        instance.snapshot_parties()

        # Sync nested lines if provided
        if lines_data is not None:
            _sync_nested(
                instance,
                LicenseTradeLine,
                lines_data,
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
