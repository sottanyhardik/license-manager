"""
Inventory Balance Report ViewSet for REST API integration

Provides inventory balance reports by SION norm with:
- List all available SION norms
- Get detailed balance report for specific SION norm
- Export to Excel
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.http import HttpResponse

from core.models import SionNormClassModel
from license.views.inventory_balance_report import InventoryBalanceReportView


class InventoryBalanceViewSet(viewsets.ViewSet):
    """
    ViewSet for Inventory Balance Reports by SION Norm.

    Permissions: AllowAny - accessible to all users without authentication

    Endpoints:
        GET /api/license/inventory-balance/ - List all SION norms with item counts
        GET /api/license/inventory-balance/{sion_norm}/ - Get balance report for specific norm
        GET /api/license/inventory-balance/{sion_norm}/export/ - Export to Excel
    """
    permission_classes = [AllowAny]

    def list(self, request):
        """
        List all SION norms with summary information.

        Returns:
            List of SION norms with:
            - norm_class
            - description
            - head_norm
            - item_count (number of items in licenses with this norm)
        """
        from django.db.models import Count
        from license.models import LicenseImportItemsModel, LicenseDetailsModel

        # Get all SION norms with active licenses
        norms = SionNormClassModel.objects.filter(
            export_item__license__is_active=True
        ).distinct().select_related('head_norm')

        result = []
        for norm in norms:
            # Count unique items across all licenses with this norm
            item_count = LicenseImportItemsModel.objects.filter(
                license__export_license__norm_class=norm,
                license__is_active=True
            ).values('items').distinct().count()

            result.append({
                'norm_class': norm.norm_class,
                'description': norm.description or '',
                'head_norm': norm.head_norm.name if norm.head_norm else '',
                'item_count': item_count,
            })

        # Sort by norm class
        result.sort(key=lambda x: x['norm_class'])

        return Response({
            'count': len(result),
            'results': result
        })

    def retrieve(self, request, pk=None):
        """
        Get detailed inventory balance report for specific SION norm.

        Args:
            pk: SION norm class (e.g., E1, E5)

        Query Parameters:
            include_zero: Include items with zero balance (default: false)

        Returns:
            Detailed balance report with items
        """
        sion_norm = pk
        include_zero = request.query_params.get('include_zero', 'false').lower() == 'true'

        report_view = InventoryBalanceReportView()

        try:
            report_data = report_view.generate_report(sion_norm, include_zero)
            return Response(report_data)
        except SionNormClassModel.DoesNotExist:
            return Response({
                'error': f'SION norm "{sion_norm}" not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'])
    def export(self, request, pk=None):
        """
        Export inventory balance report to Excel.

        Args:
            pk: SION norm class (e.g., E1, E5)

        Query Parameters:
            include_zero: Include items with zero balance (default: false)

        Returns:
            Excel file download
        """
        sion_norm = pk
        include_zero = request.query_params.get('include_zero', 'false').lower() == 'true'

        report_view = InventoryBalanceReportView()

        try:
            report_data = report_view.generate_report(sion_norm, include_zero)
            return report_view.export_to_excel(report_data, sion_norm)
        except SionNormClassModel.DoesNotExist:
            return Response({
                'error': f'SION norm "{sion_norm}" not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """
        Get overall inventory summary across all SION norms.

        Returns:
            Summary statistics for all norms
        """
        from django.db.models import Sum, Count
        from license.models import LicenseImportItemsModel, LicenseDetailsModel

        # Get all active licenses with SION norms
        active_licenses = LicenseDetailsModel.objects.filter(
            is_active=True,
            export_license__norm_class__isnull=False
        ).distinct()

        # Aggregate across all import items
        aggregates = LicenseImportItemsModel.objects.filter(
            license__in=active_licenses
        ).aggregate(
            total_quantity=Sum('quantity'),
            debited_quantity=Sum('debited_quantity'),
            allotted_quantity=Sum('allotted_quantity'),
            available_quantity=Sum('available_quantity'),
            total_cif_value=Sum('cif_fc'),
            available_cif_value=Sum('available_value'),
        )

        # Count unique items and licenses
        unique_items = LicenseImportItemsModel.objects.filter(
            license__in=active_licenses
        ).values('items').distinct().count()

        unique_norms = SionNormClassModel.objects.filter(
            export_item__license__in=active_licenses
        ).distinct().count()

        return Response({
            'total_licenses': active_licenses.count(),
            'total_norms': unique_norms,
            'total_items': unique_items,
            'totals': {
                'total_quantity': float(aggregates['total_quantity'] or 0),
                'debited_quantity': float(aggregates['debited_quantity'] or 0),
                'allotted_quantity': float(aggregates['allotted_quantity'] or 0),
                'available_quantity': float(aggregates['available_quantity'] or 0),
                'total_cif_value': float(aggregates['total_cif_value'] or 0),
                'available_cif_value': float(aggregates['available_cif_value'] or 0),
            }
        })
