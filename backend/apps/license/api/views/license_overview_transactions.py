"""
`GET licenses/<id>/overview-transactions/` — grouped BOE / Allotment read
endpoint (spec: `docs/modernization/frontend-audit/06_UNIFIED_LICENCE_WORKSPACE.md`
§7.4). Thin HTTP wrapper around
`apps.license.services.license_overview_transactions`.

Permissions are identical to `overview-boes/`: `LicenseBalanceLedgerPermission`
(GET → its SAFE_METHODS/read_roles branch), and the licence is resolved the
same way `LicenseDetailsViewSet.get_object` does for the overview actions
(numeric id first, then `license_number`; no default list filters).

Modes:
  * no `supplier_id`/`product_key` → paged supplier groups with product
    summaries and licence totals;
  * `supplier_id` (int or `null`) + `product_key` → paged record lines of
    that one supplier × product group.
"""
from django.http import Http404
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import LicenseBalanceLedgerPermission
from apps.license.api.views.license_balance_ledger import _json_safe
from apps.license.models import LicenseDetailsModel
from apps.license.services.license_overview_transactions import (
    TransactionQueryError,
    get_overview_transactions,
)


def _resolve_license(license_id: str) -> LicenseDetailsModel:
    queryset = LicenseDetailsModel.objects.all()
    license_obj = None
    if license_id.isdigit():
        license_obj = queryset.filter(pk=int(license_id)).first()
    if license_obj is None:
        license_obj = queryset.filter(license_number=license_id).first()
    if license_obj is None:
        raise Http404(f"License with identifier '{license_id}' not found")
    return license_obj


class LicenseOverviewTransactionsView(APIView):
    permission_classes = [LicenseBalanceLedgerPermission]

    def get(self, request, license_id: str):
        license_obj = _resolve_license(license_id)
        self.check_object_permissions(request, license_obj)
        try:
            data = get_overview_transactions(license_obj, request.query_params)
        except TransactionQueryError as exc:
            raise ValidationError({exc.field: [exc.message]})
        return Response(_json_safe(data))
