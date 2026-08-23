# allotment/serializers.py
from datetime import datetime, date

from rest_framework import serializers

from apps.allotment.models import AllotmentModel, AllotmentItems
from apps.core.serializers.fields import IndianDateField
from apps.license.serializers.license import PlanningOptionSerializer


class AllotmentItemSerializer(serializers.ModelSerializer):
    # Read-only fields from cached properties. allow_null=True on every chain
    # that walks self.item.license.* so an item or license that's been unset
    # doesn't raise AttributeError before DRF's safety net catches it.
    serial_number = serializers.CharField(read_only=True, required=False, allow_null=True)
    ledger = serializers.SerializerMethodField()
    product_description = serializers.CharField(read_only=True, required=False, allow_blank=True)
    hs_code = serializers.CharField(read_only=True, required=False, allow_null=True)
    license_number = serializers.CharField(read_only=True, required=False, allow_null=True)
    license_id = serializers.IntegerField(source='item.license.id', read_only=True)
    license_date = serializers.SerializerMethodField()
    exporter = serializers.CharField(read_only=True, required=False, allow_null=True, source='exporter.name')
    license_expiry = serializers.SerializerMethodField()
    registration_number = serializers.CharField(read_only=True, required=False, allow_null=True)
    registration_date = serializers.SerializerMethodField()
    notification_number = serializers.CharField(read_only=True, required=False, allow_null=True)
    file_number = serializers.CharField(read_only=True, required=False, allow_null=True)
    port_code = serializers.CharField(read_only=True, required=False, allow_null=True, source='port_code.name')
    purchase_status = serializers.SerializerMethodField()
    current_owner = serializers.SerializerMethodField()
    file_transfer_status = serializers.SerializerMethodField()
    condition_type = serializers.SerializerMethodField()
    id = serializers.IntegerField(required=False)

    # Planning options from the related import item — all LicenseItemPlan rows split
    # across this item, each with its own remaining availability after allocations.
    # Loaded via prefetch_related to avoid N+1 queries.
    planning_options = serializers.SerializerMethodField(read_only=True)

    def get_ledger(self, obj):
        ledger = obj.ledger
        if isinstance(ledger, datetime):
            return ledger.date().strftime("%d-%m-%Y")
        elif isinstance(ledger, date):
            return ledger.strftime("%d-%m-%Y")
        return ledger

    def get_license_date(self, obj):
        license_date = obj.license_date
        if isinstance(license_date, datetime):
            return license_date.date().strftime("%d-%m-%Y")
        elif isinstance(license_date, date):
            return license_date.strftime("%d-%m-%Y")
        return license_date

    def get_license_expiry(self, obj):
        license_expiry = obj.license_expiry
        if isinstance(license_expiry, datetime):
            return license_expiry.date().strftime("%d-%m-%Y")
        elif isinstance(license_expiry, date):
            return license_expiry.strftime("%d-%m-%Y")
        return license_expiry

    def get_registration_date(self, obj):
        registration_date = obj.registration_date
        if isinstance(registration_date, datetime):
            return registration_date.date().strftime("%d-%m-%Y")
        elif isinstance(registration_date, date):
            return registration_date.strftime("%d-%m-%Y")
        return registration_date

    def get_purchase_status(self, obj):
        """Get purchase status code safely"""
        if obj.item and obj.item.license and obj.item.license.purchase_status:
            return obj.item.license.purchase_status.code
        return None

    def get_current_owner(self, obj):
        if obj.item and obj.item.license and obj.item.license.current_owner:
            return obj.item.license.current_owner.name
        return None

    def get_file_transfer_status(self, obj):
        if obj.item and obj.item.license:
            return obj.item.license.file_transfer_status
        return None

    def get_condition_type(self, obj):
        return getattr(obj.item, 'condition_type', '') or ''

    def get_planning_options(self, obj):
        """
        Return all LicenseItemPlan rows for the related import item.
        Allows the frontend to display planning options and enforce per-plan-line caps.

        The related LicenseItemPlan objects are loaded via prefetch_related in the view
        (same pattern as the import_item's utilization_plans), so this is O(1) per item.
        Falls back to a fresh query if no prefetch is present (e.g., standalone usage).
        """
        if obj.item is None:
            return []
        # utilization_plans is the related_name on LicenseItemPlan.import_item
        plans = obj.item.utilization_plans.all()
        serializer = PlanningOptionSerializer(plans, many=True)
        return serializer.data

    class Meta:
        model = AllotmentItems
        # Nested updates are resolved explicitly by ID in AllotmentSerializer;
        # running ModelSerializer's create-oriented unique-together validator
        # here would incorrectly reject an unchanged existing allocation.
        validators = []
        fields = [
            'id', 'item', 'allotment', 'cif_inr', 'cif_fc', 'qty', 'is_boe',
            'search_mode', 'allocation_basis', 'planning_target_item', 'plan_line',
            'serial_number', 'ledger', 'product_description', 'hs_code', 'license_number', 'license_id',
            'license_date', 'exporter', 'license_expiry', 'registration_number',
            'registration_date', 'notification_number', 'file_number', 'port_code',
            'purchase_status', 'current_owner', 'file_transfer_status', 'condition_type', 'planning_options',
        ]


class AllotmentSerializer(serializers.ModelSerializer):
    # Nested rows are source/allocation read-only in the edit form.  The one
    # writable field is planning_target_item, persisted by update() below.
    allotment_details = AllotmentItemSerializer(many=True, required=False)

    # Date field handling
    estimated_arrival_date = IndianDateField(required=False, allow_null=True)
    created_on = serializers.SerializerMethodField()
    modified_on = serializers.SerializerMethodField()

    # Calculated at runtime instead of reading from database
    is_boe = serializers.SerializerMethodField(read_only=True)

    # Cached property fields
    required_value = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    dfia_list = serializers.CharField(read_only=True, required=False)
    balanced_quantity = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    alloted_quantity = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    allotted_value = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)

    # Foreign key display fields
    company_name = serializers.CharField(source='company.name', read_only=True, required=False)
    port_name = serializers.CharField(source='port.name', read_only=True, required=False)
    related_company_name = serializers.CharField(source='related_company.name', read_only=True, required=False)

    # Custom label field for dropdown display
    display_label = serializers.SerializerMethodField(read_only=True)

    # Counts for UI display
    allotted_items_count = serializers.SerializerMethodField(read_only=True)
    allocated_licenses_count = serializers.SerializerMethodField(read_only=True)
    # The allocation route is initialized from this persisted canonical target,
    # never from the free-text ``item_name`` description.
    planning_target_item_name = serializers.CharField(
        source='planning_target_item.name', read_only=True, allow_null=True
    )
    planning_target_sion = serializers.SerializerMethodField(read_only=True)

    def get_is_boe(self, obj):
        """
        Calculate is_boe at runtime based on whether the allotment has a bill of entry.
        Returns True if allotment.bill_of_entry.exists(), else False.
        """
        try:
            return obj.bill_of_entry.exists()
        except Exception:
            return False

    def get_display_label(self, obj):
        """Generate display label: Company Name - Invoice - Required Qty"""
        parts = []
        if obj.company:
            parts.append(obj.company.name)
        if obj.invoice:
            parts.append(f"Inv: {obj.invoice}")
        if obj.required_quantity:
            parts.append(f"Qty: {obj.required_quantity}")
        return " | ".join(parts) if parts else obj.item_name

    def get_allotted_items_count(self, obj):
        """Count of items allocated to this allotment"""
        try:
            return obj.allotment_details.count()
        except Exception:
            return 0

    def get_allocated_licenses_count(self, obj):
        """Count of unique licenses that have items allocated to this allotment"""
        try:
            from apps.core.constants import DEC_0

            # Count unique licenses in allotment_details
            # Only count if there's still balanced quantity (otherwise fully allocated)
            if obj.balanced_quantity and obj.balanced_quantity > DEC_0:
                allocated_licenses = obj.allotment_details.values_list('item__license_id', flat=True).distinct()
                return len(set(allocated_licenses))
            return 0
        except Exception:
            return 0

    def get_planning_target_sion(self, obj):
        """Return an unambiguous SION for the target when one can be derived.

        Older allotments do not persist a SION.  In that case returning null is
        intentional: the allocation route still locks to the canonical target
        and does not invent a SION from the free-text description.
        """
        if not obj.planning_target_item_id:
            return None
        from apps.license.models import LicenseItemPlan
        sions = list(
            LicenseItemPlan.objects.filter(item_name_id=obj.planning_target_item_id)
            .values_list('import_item__license__export_license__norm_class__norm_class', flat=True)
            .distinct()[:2]
        )
        return sions[0] if len(sions) == 1 else None

    def get_created_on(self, obj):
        if obj.created_on:
            value = obj.created_on
            if isinstance(value, datetime):
                return value.strftime("%d-%m-%Y %H:%M")
            elif isinstance(value, date):
                return value.strftime("%d-%m-%Y")
        return None

    def get_modified_on(self, obj):
        if obj.modified_on:
            value = obj.modified_on
            if isinstance(value, datetime):
                return value.strftime("%d-%m-%Y %H:%M")
            elif isinstance(value, date):
                return value.strftime("%d-%m-%Y")
        return None

    class Meta:
        model = AllotmentModel
        fields = [
            'id', 'company', 'type', 'required_quantity', 'unit_value_per_unit',
            'cif_fc', 'cif_inr', 'exchange_rate',
            'item_name', 'contact_person', 'contact_number', 'invoice',
            'planning_target_item', 'planning_mapping_status', 'planning_mapping_source',
            'planning_target_item_name', 'planning_target_sion',
            'estimated_arrival_date', 'bl_detail', 'port', 'related_company',
            'is_boe', 'is_approved', 'created_on', 'modified_on', 'created_by', 'modified_by',
            'required_value', 'dfia_list', 'balanced_quantity',
            'alloted_quantity', 'allotted_value', 'company_name', 'port_name',
            'related_company_name', 'display_label', 'allotment_details',
            'allotted_items_count', 'allocated_licenses_count'
        ]

    def create(self, validated_data):
        """Set default values for type and exchange_rate if not provided"""
        # Detail rows are allocated through the allocation workflow.  They
        # are not created from the master edit form (which only maps existing
        # rows), so do not pass a reverse relation to ModelSerializer.create.
        validated_data.pop("allotment_details", None)
        # Set default type to 'AT' (Allotment) if not provided
        if 'type' not in validated_data or not validated_data['type']:
            validated_data['type'] = 'AT'  # ALLOTMENT

        # Set default exchange_rate to active USD rate if not provided
        if 'exchange_rate' not in validated_data or not validated_data.get('exchange_rate'):
            from apps.core.models import ExchangeRateModel
            try:
                # Get the latest (active) exchange rate
                latest_rate = ExchangeRateModel.objects.order_by('-date').first()
                if latest_rate:
                    validated_data['exchange_rate'] = latest_rate.usd
            except Exception:
                pass  # If no exchange rate found, leave it as is

        return super().create(validated_data)

    def update(self, instance, validated_data):
        """Persist mapping changes only; never mutate allocation economics here."""
        allotment_details_data = validated_data.pop("allotment_details", None)
        instance = super().update(instance, validated_data)

        if allotment_details_data is not None:
            existing_by_id = {
                detail.id: detail
                for detail in instance.allotment_details.select_related("item").all()
            }
            for detail_data in allotment_details_data:
                detail_id = detail_data.get("id")
                if not detail_id or detail_id not in existing_by_id:
                    raise serializers.ValidationError({
                        "allotment_details": "Only existing allotment rows may be mapped from this screen."
                    })
                detail = existing_by_id[detail_id]
                # Allocation details are source/quantity records only. Parent
                # AllotmentModel owns the planning target mapping.
                continue

        return instance

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        return representation
