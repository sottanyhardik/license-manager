from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.db.models import Prefetch, Q
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response


DECIMAL_ZERO = Decimal("0")


class OptionalQueryBooleanField(serializers.BooleanField):
    default_empty_html = serializers.empty


class ParleLicenseReportQuerySerializer(serializers.Serializer):
    exporter = serializers.IntegerField(required=False, min_value=1)
    is_expired = OptionalQueryBooleanField(required=False)
    is_null = OptionalQueryBooleanField(required=False)
    notification = serializers.CharField(required=False, trim_whitespace=True, allow_blank=False, max_length=50)


def add_license_report_action(viewset_class):
    """
    Decorator to add license report functionality to LicenseDetailsViewSet.
    Groups licenses by notification number for Parle exporters.
    """

    @action(detail=False, methods=["get"], url_path="parle-report")
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
        from apps.core.models import CompanyModel
        from apps.license.models import LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel

        params = ParleLicenseReportQuerySerializer(data=request.query_params)
        if not params.is_valid():
            return Response(params.errors, status=status.HTTP_400_BAD_REQUEST)
        filters = params.validated_data

        # Start from the model queryset, then apply this report's explicitly
        # validated filters. The generic CRUD viewset queryset/filter stack also
        # inspects report-only params like `exporter`, which can over-filter.
        queryset = LicenseDetailsModel.objects.all()

        # Filter for Parle companies if not specified
        exporter_id = filters.get("exporter")
        if exporter_id is None:
            # Get all Parle companies
            parle_companies = CompanyModel.objects.filter(
                Q(name__icontains="PARLE")
            ).values_list("id", flat=True)
            queryset = queryset.filter(exporter_id__in=parle_companies)
        else:
            queryset = queryset.filter(exporter_id=exporter_id)

        # Filter by notification number if specified
        notification = filters.get("notification")
        if notification:
            queryset = queryset.filter(notification_number__code=notification)

        # Apply is_expired and is_null filters if specified
        is_expired = filters.get("is_expired")
        today = date.today()
        if is_expired is False:
            queryset = queryset.filter(
                Q(license_expiry_date__gte=today) | Q(license_expiry_date__isnull=True)
            )
        elif is_expired is True:
            queryset = queryset.filter(license_expiry_date__lt=today)

        is_null = filters.get("is_null")
        if is_null is False:
            queryset = queryset.filter(balance__balance_cif__gte=200)
        elif is_null is True:
            queryset = queryset.filter(balance__balance_cif__lt=200)

        # Prefetch related data for performance
        export_items_qs = LicenseExportItemModel.objects.select_related("norm_class")
        import_items_qs = LicenseImportItemsModel.objects.select_related("hs_code")
        queryset = queryset.prefetch_related(
            "exporter",
            "port",
            "notification_number",
            "scheme_code",
            "purchase_status",
            "balance",
            Prefetch("export_license", queryset=export_items_qs, to_attr="prefetched_export_items"),
            Prefetch("import_license", queryset=import_items_qs, to_attr="prefetched_import_items"),
        ).order_by("license_expiry_date", "license_date")

        # Group licenses by notification number
        grouped_licenses = defaultdict(list)

        for license_obj in queryset:
            license_data = {
                "id": license_obj.id,
                "license_number": license_obj.license_number,
                "license_date": license_obj.license_date,
                "license_expiry_date": license_obj.license_expiry_date,
                "exporter_name": license_obj.exporter.name if license_obj.exporter else "",
                "port_name": license_obj.port.name if license_obj.port else "",
                "purchase_status": license_obj.purchase_status.code if license_obj.purchase_status_id else "",
                "purchase_status_label": license_obj.purchase_status.label if license_obj.purchase_status_id else "",
                "balance_cif": float(license_obj.balance_cif) if license_obj.balance_cif else 0.0,
                "notification_number": license_obj.notification_number.code if license_obj.notification_number_id else "",
                "scheme_code": license_obj.scheme_code.code if license_obj.scheme_code_id else "",
                "file_number": license_obj.file_number,
                "is_expired": license_obj.license_expiry_date < today if license_obj.license_expiry_date else False,
            }

            # Calculate total CIF from export license items
            export_items_for_license = license_obj.prefetched_export_items
            total_cif = sum((item.cif_fc or DECIMAL_ZERO for item in export_items_for_license), DECIMAL_ZERO)
            license_data["total_cif"] = float(total_cif)

            # Group export items by type/category if needed
            export_items = []
            for item in export_items_for_license:
                export_items.append({
                    "description": item.description,
                    "cif_fc": float(item.cif_fc) if item.cif_fc else 0.0,
                    "cif_inr": float(item.cif_inr) if item.cif_inr else 0.0,
                    "norm_class": item.norm_class.norm_class if item.norm_class else "",
                })
            license_data["export_items"] = export_items

            # Group import items by category
            import_items = []
            for item in license_obj.prefetched_import_items:
                import_items.append({
                    "serial_number": item.serial_number,
                    "description": item.description,
                    "hs_code": item.hs_code.hs_code if item.hs_code else "",
                    "quantity": float(item.quantity) if item.quantity else 0.0,
                    "unit": item.unit,
                    "cif_fc": float(item.cif_fc) if item.cif_fc else 0.0,
                    "cif_inr": float(item.cif_inr) if item.cif_inr else 0.0,
                })
            license_data["import_items"] = import_items

            notif_key = license_obj.notification_number.code if license_obj.notification_number_id else "N/A"
            grouped_licenses[notif_key].append(license_data)

        # Calculate totals for each notification group
        result = []
        for notification, licenses in grouped_licenses.items():
            total_cif_sum = sum(lic["total_cif"] for lic in licenses)
            balance_cif_sum = sum(lic["balance_cif"] for lic in licenses)

            result.append({
                "notification_number": notification,
                "license_count": len(licenses),
                "total_cif_sum": total_cif_sum,
                "balance_cif_sum": balance_cif_sum,
                "licenses": licenses,
            })

        # Sort by notification number
        result.sort(key=lambda x: x["notification_number"])

        return Response({
            "groups": result,
            "summary": {
                "total_licenses": sum(g["license_count"] for g in result),
                "grand_total_cif": sum(g["total_cif_sum"] for g in result),
                "grand_balance_cif": sum(g["balance_cif_sum"] for g in result),
            }
        })

    # Add the method to the viewset class
    viewset_class.parle_license_report = parle_license_report

    return viewset_class
