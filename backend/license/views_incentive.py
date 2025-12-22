# license/views_incentive.py
from django.db.models import Sum, F, DecimalField, ExpressionWrapper, Q, Case, When, Value, CharField
from django_filters import rest_framework as filters
from core.views.master_view import MasterViewSet
from core.views.views import enhance_config_with_fk
from license.models import IncentiveLicense
from license.serializers import IncentiveLicenseSerializer
from decimal import Decimal


class IncentiveLicenseFilter(filters.FilterSet):
    """Custom filter for sold status - uses the cached sold_status field"""
    sold_status = filters.ChoiceFilter(
        choices=[
            ('NO', 'No'),
            ('YES', 'Yes'),
            ('PARTIAL', 'Partial'),
        ],
        field_name='sold_status',
        label='Sold Status'
    )

    class Meta:
        model = IncentiveLicense
        fields = ['sold_status']


# Create IncentiveLicense ViewSet using MasterViewSet with proper FK enhancement
class IncentiveLicenseViewSetClass(MasterViewSet):
    """Custom ViewSet for IncentiveLicense with sold status filtering"""
    filterset_class = IncentiveLicenseFilter

    def get_queryset(self):
        """Override to add default filter for not sold licenses"""
        queryset = super().get_queryset()

        # By default (when sold_status is None), show only NOT SOLD licenses
        # When sold_status is empty string '', it means "All" - show everything
        sold_status = self.request.query_params.get('sold_status', None)

        if sold_status is None:
            # Default: show only NOT SOLD licenses using the cached field
            queryset = queryset.filter(sold_status='NO')
        # If sold_status is empty string '', it means "All" - return unfiltered queryset

        return queryset


IncentiveLicenseViewSet = IncentiveLicenseViewSetClass.create_viewset(
    model=IncentiveLicense,
    serializer=IncentiveLicenseSerializer,
    config=enhance_config_with_fk(
        IncentiveLicense,
        {
            'search': ['license_number', 'exporter__name'],
            'filter': {
                'license_type': {
                    'type': 'choice',
                    'choices': [
                        ('RODTEP', 'RODTEP'),
                        ('ROSTL', 'ROSTL'),
                        ('MEIS', 'MEIS'),
                    ]
                },
                'exporter': {'type': 'fk'},
                'port_code': {'type': 'fk'},
                'is_active': {'type': 'exact'},
                'license_date': {'type': 'date_range'},
                'sold_status': {
                    'type': 'button_group',
                    'choices': [
                        ('', 'All'),
                        ('YES', 'Yes'),
                        ('NO', 'No'),
                        ('PARTIAL', 'Partial'),
                    ]
                },
            },
            'list_display': [
                'id',
                'license_type',
                'license_number',
                'license_date',
                'license_expiry_date',
                'exporter__name',
                'port_code__name',
                'license_value',
                'sold_value',
                'balance_value',
                'sold_status',
                'is_active',
            ],
            'form_fields': [
                'license_type',
                'license_number',
                'license_date',
                'license_expiry_date',
                'exporter',
                'port_code',
                'license_value',
                'is_active',
                'notes',
            ],
            'ordering': ['-license_date', 'license_number'],
            'field_meta': {
                'license_type': {
                    'type': 'select',
                    'label': 'License Type',
                    'required': True,
                    'choices': [
                        ('RODTEP', 'RODTEP'),
                        ('ROSTL', 'ROSTL'),
                        ('MEIS', 'MEIS'),
                    ]
                },
                'license_number': {
                    'type': 'text',
                    'label': 'License Number',
                    'required': True,
                },
                'license_date': {
                    'type': 'date',
                    'label': 'License Date',
                    'required': True,
                },
                'license_expiry_date': {
                    'type': 'date',
                    'label': 'License Expiry Date',
                    'required': False,
                    'readonly': True,
                    'help_text': 'Auto-calculated as 2 years from license date'
                },
                'license_value': {
                    'type': 'number',
                    'label': 'License Value (INR)',
                    'required': True,
                    'step': '0.01',
                },
                'is_active': {
                    'type': 'checkbox',
                    'label': 'Active',
                    'required': False,
                    'default': True,
                },
                'notes': {
                    'type': 'textarea',
                    'label': 'Notes',
                    'required': False,
                },
                'sold_status': {
                    'type': 'button_group',
                    'label': 'Sold Status',
                    'required': False,
                    'choices': [
                        ('', 'All'),
                        ('YES', 'Yes'),
                        ('NO', 'No'),
                        ('PARTIAL', 'Partial'),
                    ]
                },
            },
            'fk_endpoint_overrides': {
                'exporter': '/api/masters/companies/',
                'port_code': '/api/masters/ports/',
            },
            'label_field_overrides': {
                'exporter': 'name',
                'port_code': 'name',
            },
        }
    )
)
