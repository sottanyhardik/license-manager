# license/views/license_report.py
from collections import defaultdict
from datetime import date

from django.db.models import Sum, Q
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status


def add_license_report_action(viewset_class):
    """
    Decorator to add license report functionality to LicenseDetailsViewSet.
    Groups licenses by notification number for Parle exporters.
    """

    @action(detail=False, methods=['get'], url_path='parle-report')
    def parle_license_report(self, request):
        """
        Generate license report for Parle exporters, grouped by notification number.

        URL: /api/licenses/parle-report/

        Query params:
            - exporter: filter by exporter ID (optional, defaults to Parle companies)
            - is_expired: filter by expiry status (optional)
            - is_null: filter by null status (optional)
            - notification: filter by specific notification number (optional)
        """
        from license.models import LicenseDetailsModel
        from core.models import CompanyModel

        # Get filtered queryset
        queryset = self.filter_queryset(self.get_queryset())

        # Filter for Parle companies if not specified
        exporter_id = request.query_params.get('exporter')
        if not exporter_id:
            # Get all Parle companies
            parle_companies = CompanyModel.objects.filter(
                Q(name__icontains='PARLE')
            ).values_list('id', flat=True)
            queryset = queryset.filter(exporter_id__in=parle_companies)

        # Filter by notification number if specified
        notification = request.query_params.get('notification')
        if notification:
            queryset = queryset.filter(notification_number=notification)

        # Apply is_expired and is_null filters if specified
        is_expired = request.query_params.get('is_expired')
        if is_expired == 'False' or is_expired == 'false':
            today = date.today()
            queryset = queryset.filter(
                Q(license_expiry_date__gte=today) | Q(license_expiry_date__isnull=True)
            )
        elif is_expired == 'True' or is_expired == 'true':
            queryset = queryset.filter(license_expiry_date__lt=date.today())

        is_null = request.query_params.get('is_null')
        if is_null == 'False' or is_null == 'false':
            queryset = queryset.filter(balance_cif__gte=200)
        elif is_null == 'True' or is_null == 'true':
            queryset = queryset.filter(balance_cif__lt=200)

        # Prefetch related data for performance
        queryset = queryset.select_related(
            'exporter', 'port', 'current_owner'
        ).prefetch_related(
            'export_license', 'import_license'
        ).order_by('notification_number', '-license_date')

        # Group licenses by notification number
        grouped_licenses = defaultdict(list)

        for license_obj in queryset:
            license_data = {
                'id': license_obj.id,
                'license_number': license_obj.license_number,
                'license_date': license_obj.license_date,
                'license_expiry_date': license_obj.license_expiry_date,
                'exporter_name': license_obj.exporter.name if license_obj.exporter else '',
                'port_name': license_obj.port.name if license_obj.port else '',
                'purchase_status': license_obj.purchase_status,
                'balance_cif': float(license_obj.balance_cif) if license_obj.balance_cif else 0.0,
                'notification_number': license_obj.notification_number,
                'scheme_code': license_obj.scheme_code,
                'file_number': license_obj.file_number,
                'is_expired': license_obj.license_expiry_date < date.today() if license_obj.license_expiry_date else False,
            }

            # Calculate total CIF from export license items
            total_cif = license_obj.export_license.aggregate(
                total=Sum('cif_fc')
            )['total'] or 0
            license_data['total_cif'] = float(total_cif)

            # Group export items by type/category if needed
            export_items = []
            for item in license_obj.export_license.all():
                export_items.append({
                    'description': item.description,
                    'cif_fc': float(item.cif_fc) if item.cif_fc else 0.0,
                    'cif_inr': float(item.cif_inr) if item.cif_inr else 0.0,
                    'norm_class': item.norm_class.norm_class if item.norm_class else '',
                })
            license_data['export_items'] = export_items

            # Group import items by category
            import_items = []
            for item in license_obj.import_license.all():
                import_items.append({
                    'serial_number': item.serial_number,
                    'description': item.description,
                    'hs_code': item.hs_code.hs_code if item.hs_code else '',
                    'quantity': float(item.quantity) if item.quantity else 0.0,
                    'unit': item.unit,
                    'cif_fc': float(item.cif_fc) if item.cif_fc else 0.0,
                    'cif_inr': float(item.cif_inr) if item.cif_inr else 0.0,
                })
            license_data['import_items'] = import_items

            grouped_licenses[license_obj.notification_number].append(license_data)

        # Calculate totals for each notification group
        result = []
        for notification, licenses in grouped_licenses.items():
            total_cif_sum = sum(lic['total_cif'] for lic in licenses)
            balance_cif_sum = sum(lic['balance_cif'] for lic in licenses)

            result.append({
                'notification_number': notification,
                'license_count': len(licenses),
                'total_cif_sum': total_cif_sum,
                'balance_cif_sum': balance_cif_sum,
                'licenses': licenses,
            })

        # Sort by notification number
        result.sort(key=lambda x: x['notification_number'])

        return Response({
            'groups': result,
            'summary': {
                'total_licenses': sum(g['license_count'] for g in result),
                'grand_total_cif': sum(g['total_cif_sum'] for g in result),
                'grand_balance_cif': sum(g['balance_cif_sum'] for g in result),
            }
        })

    # Add the method to the viewset class
    viewset_class.parle_license_report = parle_license_report

    return viewset_class
