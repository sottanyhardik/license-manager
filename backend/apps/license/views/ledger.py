"""
License Ledger Views - Unified view for DFIA and Incentive license balances
"""
from django.http import FileResponse
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import LicenseLedgerViewPermission
from apps.license.models import LicenseDetailsModel, IncentiveLicense

class LicenseLedgerViewSet(viewsets.GenericViewSet):
    """
    Unified ledger view for both DFIA and Incentive licenses.
    Shows available balance for selling licenses.

    Access is role-based.  Ledger users can view the shared ledger regardless
    of whether their account has a company assignment.

    Returns:
    - DFIA licenses: balance_cif (available CIF $ balance)
    - Incentive licenses: balance_value (available INR balance)
    """
    permission_classes = [LicenseLedgerViewPermission]

    def list(self, request):
        """Preserve the router's established collection endpoint."""
        return self.license_wise(request)

    def retrieve(self, request, pk=None):
        """Preserve the router's established per-license endpoint."""
        return self.ledger_detail(request, pk=pk)

    def _authorized_license(self, request, license_ref, license_type='AUTO'):
        """Resolve a license for an already-authorized ledger user."""
        from rest_framework.exceptions import APIException, ValidationError

        requested_type = str(license_type or 'AUTO').strip().upper()
        allowed_types = {'AUTO', 'DFIA', 'INCENTIVE', 'ALL_INCENTIVE', 'RODTEP', 'ROSTL', 'MEIS'}
        if requested_type not in allowed_types:
            raise ValidationError({'license_type': f"Invalid license type '{license_type}'."})

        if requested_type == 'DFIA':
            found_type, license_obj = self._find_license_by_id_or_number(license_ref, True, False)
        elif requested_type in {'INCENTIVE', 'ALL_INCENTIVE', 'RODTEP', 'ROSTL', 'MEIS'}:
            found_type, license_obj = self._find_license_by_id_or_number(license_ref, False, True)
        else:
            found_type, license_obj = self._find_license_by_id_or_number(license_ref, True, True)
        if (license_obj and requested_type in {'RODTEP', 'ROSTL', 'MEIS'}
                and found_type != requested_type):
            license_obj = None
        if not license_obj:
            class LicenseNotFound(APIException):
                status_code = 404
                default_code = 'not_found'
            raise LicenseNotFound(detail={'error': f'License not found: {license_ref}'})

        return found_type, license_obj

    def _find_license_by_id_or_number(self, pk, search_dfia=True, search_incentive=True):
        """
        Helper method to find license in DFIA and/or Incentive tables by ID or license_number.

        Args:
            pk: License ID (int) or license_number (str)
            search_dfia: Whether to search in DFIA licenses
            search_incentive: Whether to search in Incentive licenses

        Returns:
            Tuple of (license_type, license_object) or (None, None) if not found
        """
        # Search DFIA if requested
        if search_dfia:
            try:
                if pk.isdigit() and not pk.startswith('0'):
                    try:
                        license = LicenseDetailsModel.objects.select_related('exporter', 'port').get(pk=int(pk))
                        return ('DFIA', license)
                    except LicenseDetailsModel.DoesNotExist:
                        license = LicenseDetailsModel.objects.select_related('exporter', 'port').get(license_number=pk)
                        return ('DFIA', license)
                else:
                    try:
                        license = LicenseDetailsModel.objects.select_related('exporter', 'port').get(license_number=pk)
                        return ('DFIA', license)
                    except LicenseDetailsModel.DoesNotExist:
                        try:
                            license = LicenseDetailsModel.objects.select_related('exporter', 'port').get(pk=int(pk))
                            return ('DFIA', license)
                        except (ValueError, TypeError, LicenseDetailsModel.DoesNotExist):
                            pass
            except LicenseDetailsModel.DoesNotExist:
                pass

        # Search Incentive if requested
        if search_incentive:
            try:
                if pk.isdigit() and not pk.startswith('0'):
                    try:
                        license = IncentiveLicense.objects.select_related('exporter', 'port_code').get(pk=int(pk))
                        return (license.license_type, license)
                    except IncentiveLicense.DoesNotExist:
                        license = IncentiveLicense.objects.select_related('exporter', 'port_code').get(license_number=pk)
                        return (license.license_type, license)
                else:
                    try:
                        license = IncentiveLicense.objects.select_related('exporter', 'port_code').get(license_number=pk)
                        return (license.license_type, license)
                    except IncentiveLicense.DoesNotExist:
                        try:
                            license = IncentiveLicense.objects.select_related('exporter', 'port_code').get(pk=int(pk))
                            return (license.license_type, license)
                        except (ValueError, TypeError, IncentiveLicense.DoesNotExist):
                            pass
            except IncentiveLicense.DoesNotExist:
                pass

        return (None, None)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """
        Get canonical summary statistics for every authorized ledger licence.
        """
        from apps.license.services.license_ledger_export import build_license_ledger_data
        return Response(build_license_ledger_data(
            request.query_params,
        )['summary'])

    @action(detail=True, methods=['get'])
    def ledger_detail(self, request, pk=None):
        """
        Get detailed ledger view for a specific license showing all transactions.
        Works for both DFIA and Incentive licenses.
        Accepts either ID (integer) or license_number (string) as pk parameter.
        Auto-searches both tables if license_type not specified.

        **Phase 4C:** API consumes CanonicalLedgerService as the single source of truth.
        All financial calculations are performed by CanonicalLedgerService; the API layer
        is a transparent serialization layer with no business logic.
        """
        from apps.license.services.canonical_ledger_service import CanonicalLedgerService
        from apps.license.serializers import CanonicalLedgerSerializer
        from rest_framework.exceptions import ValidationError
        license_type = request.query_params.get('license_type', 'AUTO')
        company_value = request.query_params.get('company')
        try:
            company_id = int(company_value) if company_value else None
        except (TypeError, ValueError):
            raise ValidationError({'company': 'Company must be a valid numeric ID.'})
        found_type, license = self._authorized_license(request, pk, license_type)

        # Delegate all calculation to CanonicalLedgerService (single source of truth).
        # The API is a transparent serialization layer with NO business logic.
        dataset = CanonicalLedgerService.build_canonical_ledger_dataset(
            license_id=license.id,
            license_type=found_type,
            company_id=company_id,
        )

        from apps.license.services.license_ledger_export import enrich_invoice_documents
        enrich_invoice_documents(
            {"licenses": [dataset]}, user=request.user,
            base_url=request.build_absolute_uri("/"),
        )

        # Serialize for response (representation only; no calculations)
        serializer = CanonicalLedgerSerializer(dataset)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='license-wise')
    def license_wise(self, request):
        """
        Returns trades grouped by license, then by company within each license.
        Structure: license → [company → purchases/sales/totals]

        The collection is role-authorized and accepts the public ledger filters.
        """
        from apps.license.services.license_ledger_export import build_license_ledger_data
        collection = build_license_ledger_data(
            request.query_params,
        )
        datasets = collection['licenses']
        return Response({'licenses': [{
            'license_id': data['license_id'],
            'license_number': data['license_number'],
            'license_date': data['license_date'],
            'expiry_date': data.get('expiry_date'),
            'license_type': data['license_type'],
            'sion_norms': data.get('sion_norms') or '',
            # Flat, transaction-level rows for the screen ledger.  Keep the
            # established company summary alongside it for older consumers.
            'transactions': data.get('display_transactions') or [],
            'summary': data.get('summary') or {},
            'individual_ledger_projection': data.get('individual_ledger_projection') or {},
            'companies': data['license_wise_companies'],
        } for data in datasets],
            # Canonical reporting hierarchy. The UI consumes this verbatim;
            # the flat license-wise shape remains for detail compatibility.
            'company_groups': collection['company_groups'],
            'grand_total': collection['grand_total'],
        })

    @action(detail=False, methods=['get'], url_path='export')
    def export(self, request):
        """Render PDF or Excel from the same canonical datasets used by the UI."""
        from apps.license.services.license_ledger_export import (
            build_license_ledger_data,
            render_license_ledger,
        )

        file_format = request.query_params.get('file_format', '').lower()
        if file_format not in {'pdf', 'xlsx'}:
            return Response({'error': "format must be 'pdf' or 'xlsx'"}, status=400)

        license_ref = None
        requested_license = request.query_params.get('license_id')
        if requested_license:
            found_type, license_obj = self._authorized_license(
                request,
                requested_license,
                request.query_params.get('license_type', 'AUTO'),
            )
            license_ref = (license_obj.id, found_type)

        canonical_data = build_license_ledger_data(
            request.query_params, license_ref=license_ref,
        )
        from apps.license.services.license_ledger_export import enrich_invoice_documents
        enrich_invoice_documents(
            canonical_data, user=request.user, base_url=request.build_absolute_uri("/"),
        )
        datasets = canonical_data['licenses']
        if not datasets:
            return Response({'error': 'No License Ledger data available for export.'}, status=404)

        output = render_license_ledger(canonical_data, file_format)
        if len(datasets) == 1:
            slug = f"license-ledger-{datasets[0]['license_id']}"
            item_id = request.query_params.get('item_id')
            if item_id:
                slug += f"-{item_id}"
        else:
            slug = 'license-ledger'
        content_type = 'application/pdf' if file_format == 'pdf' else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        response = FileResponse(output, as_attachment=file_format == 'xlsx', filename=f'{slug}.{file_format}', content_type=content_type)
        if file_format == 'pdf':
            response['Content-Disposition'] = f'inline; filename="{slug}.pdf"'
        return response
