"""
License Overview dashboard — read-only API actions attached to
`LicenseDetailsViewSet` (see `add_license_overview_actions` /
`apps/license/views/license.py`), following the exact
`add_license_balance_ledger_actions` convention already used on this
viewset (`apps/license/views/license_balance_ledger.py`).

Each action is a thin HTTP wrapper around one of the new
`apps/license/services/license_overview_*.py` service functions — this
module ONLY handles request/response shaping and permission enforcement.
Every action reuses `LicenseBalanceLedgerPermission` (already covers the
LICENSE/BOE/TRADE/ALLOTMENT viewer+manager+ACCOUNT_ACCESS domain these
read-only tabs need) and the existing `_json_safe` helper (Decimal ->
float, date/datetime -> ISO string) so response payloads match the numeric/
string types already used across the Balance Workspace endpoints — no
second JSON-safety helper.

The existing `/licenses/{id}/balance-ledger/` endpoint and everything in
`license_balance_ledger.py` are untouched; these are new, parallel,
read-only actions.
"""
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.license.views.license_balance_ledger import _json_safe


def add_license_overview_actions(viewset_class):
    """Attaches the License Overview dashboard's read-only actions to
    `viewset_class`."""

    @action(detail=True, methods=['get'], url_path='overview-summary')
    def overview_summary(self, request, pk=None):
        from apps.license.services.license_overview_summary import get_overview_counts

        license_obj = self.get_object()
        data = get_overview_counts(license_obj)
        return Response(_json_safe(data))

    @action(detail=True, methods=['get'], url_path='overview-boes')
    def overview_boes(self, request, pk=None):
        from apps.license.services.license_overview_boes import list_boe_rows

        license_obj = self.get_object()
        data = list_boe_rows(license_obj)
        return Response(_json_safe(data))

    @action(detail=True, methods=['get'], url_path='overview-allotments')
    def overview_allotments(self, request, pk=None):
        from apps.license.services.license_overview_allotments import list_allotment_rows

        license_obj = self.get_object()
        data = list_allotment_rows(license_obj)
        return Response(_json_safe(data))

    @action(detail=True, methods=['get'], url_path='overview-items')
    def overview_items(self, request, pk=None):
        from apps.license.services.license_overview_items import compute_item_ledger_rows

        license_obj = self.get_object()
        data = compute_item_ledger_rows(license_obj)
        return Response(_json_safe(data))

    @action(detail=True, methods=['get'], url_path='overview-invoice-ledger')
    def overview_invoice_ledger(self, request, pk=None):
        from apps.license.services.license_overview_invoices import build_invoice_ledger

        license_obj = self.get_object()
        data = build_invoice_ledger(license_obj)
        return Response(_json_safe(data))

    @action(detail=True, methods=['get'], url_path='plan-utilization')
    def plan_utilization(self, request, pk=None):
        """
        Exposes the EXISTING `plan_utilization_rows(license_obj)` (already
        used by `LicenseDetailsViewSet.retrieve()` and the Balance Excel
        export) as its own lightweight endpoint, so the Planning tab
        doesn't have to fetch the full license-detail payload. No new
        calculation on the rows themselves — verbatim reuse.

        `norm` is added at the top level (not per-row): `detect_norm()`
        returns a single license-level SION norm ('E1'/'E5'/'E132'/''), not
        a per-plan-group value, so the Planning tab's "SION Norm" column is
        the same value for every row rather than a new per-row field.
        """
        from apps.license.services.norm_plan import detect_norm
        from apps.license.services.plan_utilization import plan_utilization_rows

        license_obj = self.get_object()
        data = {
            "norm": detect_norm(license_obj),
            "rows": plan_utilization_rows(license_obj),
        }
        return Response(_json_safe(data))

    for method in (
        overview_summary, overview_boes, overview_allotments,
        overview_items, overview_invoice_ledger, plan_utilization,
    ):
        setattr(viewset_class, method.__name__, method)

    return viewset_class
