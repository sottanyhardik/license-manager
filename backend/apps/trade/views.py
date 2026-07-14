# trade/views.py
"""
ViewSets for the Trade module.

Design rules:
  - Permission enforced via TradePermission.
  - All list responses are paginated (StandardPagination from shared.pagination).
  - Envelope pattern: {"success": true/false, "data": ..., "message": ...}
    List responses use the StandardPagination envelope automatically.
    Detail / action responses return explicit Response(EnvelopeMixin.wrap(...)).
  - PDF generation is synchronous (direct HttpResponse), matching legacy behaviour.
"""
import logging

from django.http import HttpResponse
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from shared.pagination import StandardPagination
from shared.serializers import EnvelopeMixin

from apps.accounts.permissions import TradePermission
from apps.trade.filters import TradeFilter
from apps.trade.models import LicenseTrade, LicenseTradeLine, LicenseTradePayment
from apps.trade.serializers import (
    LicenseTradeSerializer,
    LicenseTradePaymentSerializer,
    TradeLineSimpleSerializer,
)
from apps.trade.services.trade_service import (
    build_trade_summary,
    get_prefilled_invoice_number,
    link_trades,
    parse_date_strict,
    PartnerTradeNotFound,
)

logger = logging.getLogger(__name__)


class LicenseTradeViewSet(viewsets.ModelViewSet):
    """
    CRUD ViewSet for LicenseTrade.

    GET    /api/v1/trades/trades/              -> list (paginated, filterable)
    POST   /api/v1/trades/trades/              -> create
    GET    /api/v1/trades/trades/{id}/         -> retrieve
    PUT    /api/v1/trades/trades/{id}/         -> full update
    PATCH  /api/v1/trades/trades/{id}/         -> partial update
    DELETE /api/v1/trades/trades/{id}/         -> destroy

    Extra actions:
      GET  /api/v1/trades/trades/{id}/generate-purchase-invoice/ -> PDF
      GET  /api/v1/trades/trades/{id}/generate-bill-of-supply/   -> PDF
      GET  /api/v1/trades/trades/prefill-invoice-number/         -> next invoice no
      GET  /api/v1/trades/trades/{id}/summary/                   -> trade summary
      POST /api/v1/trades/trades/{id}/link-trade/                -> link/unlink partner
    """

    permission_classes = [TradePermission]
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = TradeFilter
    search_fields = [
        "invoice_number",
        "from_company__name",
        "to_company__name",
        "remarks",
        "lines__sr_number__license__license_number",
        "incentive_license__license_number",
        "incentive_lines__incentive_license__license_number",
    ]
    ordering_fields = ["invoice_date", "invoice_number", "created_on", "total_amount"]
    ordering = ["-invoice_date", "-invoice_number", "-created_on"]

    def get_queryset(self):
        return (
            LicenseTrade.objects.select_related(
                "from_company",
                "to_company",
                "boe",
                "incentive_license",
                "linked_trade",
                "created_by",
                "modified_by",
            )
            .prefetch_related(
                "lines",
                "lines__sr_number",
                "lines__sr_number__license",
                "lines__sr_number__items",
                "incentive_lines",
                "incentive_lines__incentive_license",
                "payments",
            )
            .order_by("-invoice_date", "-invoice_number", "-created_on")
        )

    def get_serializer_class(self):
        return LicenseTradeSerializer

    def list(self, request, *args, **kwargs):
        """Paginated list -- envelope provided automatically by StandardPagination."""
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        trade = serializer.save()
        out = self.get_serializer(trade)
        return Response(
            EnvelopeMixin.wrap(data=out.data, message="Trade created successfully."),
            status=status.HTTP_201_CREATED,
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(EnvelopeMixin.wrap(data=serializer.data))

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        trade = serializer.save()
        out = self.get_serializer(trade)
        return Response(EnvelopeMixin.wrap(data=out.data, message="Trade updated successfully."))

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(
            EnvelopeMixin.wrap(message="Trade deleted successfully."),
            status=status.HTTP_204_NO_CONTENT,
        )

    # -------------------------------------------------------------------------
    # PDF actions
    # -------------------------------------------------------------------------

    @action(detail=True, methods=["get"], url_path="generate-purchase-invoice")
    def generate_purchase_invoice(self, request, pk=None):
        """
        Generate Purchase Invoice PDF for PURCHASE transactions.

        Query Parameters:
        - include_signature: Boolean (default: true)
        """
        from apps.trade.purchase_invoice_pdf import generate_purchase_invoice_pdf

        trade = self.get_queryset().select_related("from_company", "to_company").get(pk=pk)

        if trade.direction != "PURCHASE":
            return Response(
                EnvelopeMixin.wrap(
                    success=False,
                    message="Purchase Invoice can only be generated for PURCHASE transactions.",
                ),
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            include_signature_param = request.query_params.get("include_signature", "true").lower()
            include_signature = include_signature_param in ("true", "1", "yes")
            pdf = generate_purchase_invoice_pdf(trade, include_signature=include_signature)

            sig_suffix = "_with_sign" if include_signature else "_without_sign"
            date_str = trade.invoice_date.strftime("%Y%m%d") if trade.invoice_date else "NA"
            filename = f"Purchase_Invoice_{trade.invoice_number}_{date_str}{sig_suffix}.pdf"

            response = HttpResponse(pdf, content_type="application/pdf")
            response["Content-Disposition"] = f'inline; filename="{filename}"'
            return response
        except Exception as exc:
            logger.exception("Failed to generate purchase invoice PDF for trade %s", pk)
            return Response(
                EnvelopeMixin.wrap(success=False, message=f"Failed to generate PDF: {exc}"),
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["get"], url_path="generate-bill-of-supply")
    def generate_bill_of_supply(self, request, pk=None):
        """
        Generate Bill of Supply PDF for SALE transactions.

        Query Parameters:
        - include_signature: Boolean (default: true)
        """
        from apps.trade.bill_of_supply_pdf import generate_bill_of_supply_pdf

        trade = self.get_queryset().select_related("from_company", "to_company").get(pk=pk)

        if trade.direction != "SALE":
            return Response(
                EnvelopeMixin.wrap(
                    success=False,
                    message="Bill of Supply can only be generated for SALE transactions.",
                ),
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            include_signature_param = request.query_params.get("include_signature", "true").lower()
            include_signature = include_signature_param in ("true", "1", "yes")
            pdf = generate_bill_of_supply_pdf(trade, include_signature=include_signature)

            sig_suffix = "_with_sign" if include_signature else "_without_sign"
            date_str = trade.invoice_date.strftime("%Y%m%d") if trade.invoice_date else "NA"
            filename = f"Bill_of_Supply_{trade.invoice_number}_{date_str}{sig_suffix}.pdf"

            response = HttpResponse(pdf, content_type="application/pdf")
            response["Content-Disposition"] = f'inline; filename="{filename}"'
            return response
        except Exception as exc:
            logger.exception("Failed to generate bill of supply PDF for trade %s", pk)
            return Response(
                EnvelopeMixin.wrap(success=False, message=f"Failed to generate PDF: {exc}"),
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # -------------------------------------------------------------------------
    # Other actions
    # -------------------------------------------------------------------------

    @action(detail=False, methods=["get"], url_path="prefill-invoice-number")
    def prefill_invoice_number(self, request):
        """
        Generate next invoice number based on direction, company, and invoice date.

        Query Parameters:
        - direction: PURCHASE | SALE | COMMISSION_PURCHASE | COMMISSION_SALE (required)
        - company_id: Company PK (required)
        - invoice_date: YYYY-MM-DD (optional, defaults to today)
        """
        from apps.core.models import CompanyModel

        direction = request.query_params.get("direction")
        company_id = request.query_params.get("company_id")
        invoice_date_str = request.query_params.get("invoice_date")

        if not direction:
            return Response(
                EnvelopeMixin.wrap(
                    success=False,
                    message="direction is required (PURCHASE, SALE, COMMISSION_PURCHASE, or COMMISSION_SALE)",
                ),
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not company_id:
            return Response(
                EnvelopeMixin.wrap(success=False, message="company_id is required"),
                status=status.HTTP_400_BAD_REQUEST,
            )

        invoice_date = None
        if invoice_date_str:
            try:
                invoice_date = parse_date_strict(invoice_date_str)
            except ValueError as exc:
                return Response(
                    EnvelopeMixin.wrap(success=False, message=str(exc)),
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            invoice_number = get_prefilled_invoice_number(
                direction=direction,
                company_id=int(company_id),
                invoice_date=invoice_date,
            )
            return Response(EnvelopeMixin.wrap(data={"invoice_number": invoice_number}))
        except ValueError as exc:
            return Response(
                EnvelopeMixin.wrap(success=False, message=str(exc)),
                status=status.HTTP_400_BAD_REQUEST,
            )
        except CompanyModel.DoesNotExist:
            return Response(
                EnvelopeMixin.wrap(success=False, message="Company not found"),
                status=status.HTTP_404_NOT_FOUND,
            )

    @action(detail=True, methods=["get"])
    def summary(self, request, pk=None):
        """Get trade summary with computed fields."""
        trade = self.get_object()
        data = build_trade_summary(trade)
        return Response(EnvelopeMixin.wrap(data=data))

    @action(detail=True, methods=["post"], url_path="link-trade")
    def link_trade(self, request, pk=None):
        """
        Bidirectionally link two trades.
        POST body: {"partner_id": <int>}  -- set link on both trades.
        POST body: {"partner_id": null}   -- clear link on both trades.
        """
        trade = self.get_object()
        partner_id = request.data.get("partner_id")

        try:
            updated_trade = link_trades(
                trade_pk=trade.pk,
                partner_pk=int(partner_id) if partner_id is not None else None,
            )
        except ValueError as exc:
            return Response(
                EnvelopeMixin.wrap(success=False, message=str(exc)),
                status=status.HTTP_400_BAD_REQUEST,
            )
        except PartnerTradeNotFound as exc:
            return Response(
                EnvelopeMixin.wrap(success=False, message=str(exc)),
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = LicenseTradeSerializer(updated_trade, context={"request": request})
        return Response(EnvelopeMixin.wrap(data=serializer.data))


class TradeLineViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only access to trade lines."""

    permission_classes = [TradePermission]
    serializer_class = TradeLineSimpleSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["description"]
    ordering_fields = ["id", "trade__invoice_number"]
    ordering = ["trade", "id"]

    def get_queryset(self):
        return LicenseTradeLine.objects.select_related(
            "trade", "sr_number", "sr_number__license"
        ).order_by("trade", "id")


class TradePaymentViewSet(viewsets.ModelViewSet):
    """CRUD for trade payments."""

    permission_classes = [TradePermission]
    serializer_class = LicenseTradePaymentSerializer
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["note"]
    ordering_fields = ["date", "id"]
    ordering = ["-date", "-id"]

    def get_queryset(self):
        return LicenseTradePayment.objects.select_related("trade").order_by("-date", "-id")
