"""Read-only API for the canonical licence item balance report.

Every response is produced by `licence_balance_report` — no view or serializer computes a balance.
"""

from datetime import date

from django.db.models import Q
from django.http import Http404
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import LicensePermission
from apps.license.models import LicenseDetailsModel
from apps.license.services.licence_balance_report import (
    build_licence_balance_reports,
    serialise_item,
    serialise_licence_detail,
    serialise_licence_summary,
)

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100


def _int(value, default, minimum=1, maximum=None):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    if number < minimum:
        return default
    if maximum is not None and number > maximum:
        return maximum
    return number


class LicenceBalanceListView(APIView):
    """GET /api/licence-balances/ — one row per licence with CIF and quantity summaries."""

    permission_classes = [LicensePermission]

    def get(self, request):
        qs = LicenseDetailsModel.objects.select_related("exporter")
        search = (request.query_params.get("search") or "").strip()[:200]
        if search:
            qs = qs.filter(Q(license_number__icontains=search) | Q(exporter__name__icontains=search))
        expiry = request.query_params.get("expiry", "all")
        today = date.today()
        if expiry == "active":
            qs = qs.filter(license_expiry_date__gte=today)
        elif expiry == "expired":
            qs = qs.filter(license_expiry_date__lt=today)

        qs = qs.order_by("license_expiry_date", "license_number", "id")
        page_size = _int(request.query_params.get("page_size"), DEFAULT_PAGE_SIZE, maximum=MAX_PAGE_SIZE)
        count = qs.count()
        total_pages = max(1, -(-count // page_size))
        page = min(_int(request.query_params.get("page"), 1), total_pages)
        ids = list(qs.values_list("id", flat=True)[(page - 1) * page_size: page * page_size])

        # The legacy comparison runs the old engine once per licence, so it is opt-in (?legacy=1).
        include_legacy = request.query_params.get("legacy") == "1"
        reports = build_licence_balance_reports(ids, include_legacy=include_legacy)
        results = [serialise_licence_summary(reports[i]) for i in ids if i in reports]
        return Response({
            "count": count,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_previous": page > 1,
            "results": results,
        })


class LicenceBalanceDetailView(APIView):
    """GET /api/licence-balances/<id>/ — licence summary plus every SION item."""

    permission_classes = [LicensePermission]

    def get(self, request, license_id):
        if not LicenseDetailsModel.objects.filter(pk=license_id).exists():
            raise Http404("Licence not found")
        report = build_licence_balance_reports([license_id])[license_id]
        return Response(serialise_licence_detail(report))


class LicenceItemMovementsView(APIView):
    """GET /api/licence-balances/<id>/items/<item_id>/ — one item with its CIF and quantity ledgers."""

    permission_classes = [LicensePermission]

    def get(self, request, license_id, item_id):
        if not LicenseDetailsModel.objects.filter(pk=license_id).exists():
            raise Http404("Licence not found")
        report = build_licence_balance_reports([license_id])[license_id]
        for item in report.items:
            if item.item_id == item_id:
                return Response(serialise_item(item, include_movements=True))
        raise Http404("Item not found on this licence")


class LicenceItemDrilldownView(APIView):
    """GET /api/licence-balances/<id>/items/<item_id>/drilldown/ — BOE, allotment and invoice rows behind one item."""

    permission_classes = [LicensePermission]

    def get(self, request, license_id, item_id):
        from apps.license.services.licence_item_drilldown import build_item_drilldown

        payload = build_item_drilldown(license_id, item_id)
        if payload is None:
            raise Http404("Item not found on this licence")
        return Response(payload)


class LicenceSourceReconciliationView(APIView):
    """GET /api/licence-balances/<id>/source-reconciliation/ — per-item source differences and allocation issues."""

    permission_classes = [LicensePermission]

    def get(self, request, license_id):
        from apps.license.services.licence_item_drilldown import build_licence_source_reconciliation

        if not LicenseDetailsModel.objects.filter(pk=license_id).exists():
            raise Http404("Licence not found")
        return Response(build_licence_source_reconciliation(license_id))


class LicenceTransactionsView(APIView):
    """GET /api/licence-balances/<id>/transactions/ — BOEs, allotments and invoices behind the balance."""

    permission_classes = [LicensePermission]

    def get(self, request, license_id):
        from apps.license.services.licence_balance_report import build_licence_transactions

        if not LicenseDetailsModel.objects.filter(pk=license_id).exists():
            raise Http404("Licence not found")
        return Response(build_licence_transactions(license_id))


class LicenceInvoiceLedgerView(APIView):
    """GET /api/licence-balances/<id>/invoice-ledger/ — purchase/sale ledger with credit and debit notes."""

    permission_classes = [LicensePermission]

    def get(self, request, license_id):
        from apps.license.services.invoice_ledger import load_invoice_ledger

        if not LicenseDetailsModel.objects.filter(pk=license_id).exists():
            raise Http404("Licence not found")
        return Response(load_invoice_ledger(license_id))
