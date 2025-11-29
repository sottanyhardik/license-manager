# trade/views.py

from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status

from core.views import MasterViewSet
from .models import LicenseTrade, LicenseTradeLine, LicenseTradePayment
from .serializers import (
    LicenseTradeSerializer,
    TradeLineSimpleSerializer,
    LicenseTradePaymentSerializer
)


# Trade transactions ViewSet
LicenseTradeViewSet = MasterViewSet.create_viewset(
    LicenseTrade,
    LicenseTradeSerializer,
    config={
        "search": [
            "invoice_number",
            "from_company__name",
            "to_company__name",
            "remarks"
        ],
        "filter": {
            "direction": {
                "type": "exact",
                "choices": LicenseTrade.DIR_CHOICES
            },
            "from_company": {
                "type": "fk",
                "fk_endpoint": "/masters/companies/",
                "label_field": "name"
            },
            "to_company": {
                "type": "fk",
                "fk_endpoint": "/masters/companies/",
                "label_field": "name"
            },
            "boe": {
                "type": "fk",
                "fk_endpoint": "/bill-of-entries/",
                "label_field": "boe_number"
            },
            "invoice_date": {
                "type": "date_range"
            }
        },
        "list_display": [
            "direction",
            "invoice_number",
            "invoice_date",
            "from_company__name",
            "to_company__name",
            "total_amount",
            "paid_or_received",
            "due_amount"
        ],
        "form_fields": [
            "direction",
            "boe",
            "from_company",
            "to_company",
            "invoice_number",
            "invoice_date",
            "remarks",
            "purchase_invoice_copy"
        ],
        "fk_endpoint_overrides": {
            "from_company": "/masters/companies/",
            "to_company": "/masters/companies/",
            "boe": "/bill-of-entries/"
        },
        "nested_field_defs": {
            "lines": {
                "label": "Trade Lines",
                "fields": [
                    {
                        "name": "sr_number",
                        "type": "fk",
                        "label": "SR Number",
                        "fk_endpoint": "/license-items/",
                        "label_field": "label",
                        "required": True
                    },
                    {
                        "name": "description",
                        "type": "textarea",
                        "label": "Description"
                    },
                    {
                        "name": "hsn_code",
                        "type": "text",
                        "label": "HSN Code",
                        "default": "49070000"
                    },
                    {
                        "name": "mode",
                        "type": "select",
                        "label": "Billing Mode",
                        "choices": LicenseTradeLine.MODE_CHOICES,
                        "required": True
                    },
                    {
                        "name": "qty_kg",
                        "type": "number",
                        "label": "Quantity (KG)",
                        "step": "0.0001"
                    },
                    {
                        "name": "rate_inr_per_kg",
                        "type": "number",
                        "label": "Rate (INR/KG)",
                        "step": "0.01"
                    },
                    {
                        "name": "cif_fc",
                        "type": "number",
                        "label": "CIF (FC)",
                        "step": "0.01"
                    },
                    {
                        "name": "exc_rate",
                        "type": "number",
                        "label": "Exchange Rate",
                        "step": "0.0001"
                    },
                    {
                        "name": "cif_inr",
                        "type": "number",
                        "label": "CIF (INR)",
                        "step": "0.01"
                    },
                    {
                        "name": "fob_inr",
                        "type": "number",
                        "label": "FOB (INR)",
                        "step": "0.01"
                    },
                    {
                        "name": "pct",
                        "type": "number",
                        "label": "Percentage (%)",
                        "step": "0.001"
                    },
                    {
                        "name": "amount_inr",
                        "type": "number",
                        "label": "Amount (INR)",
                        "step": "0.01",
                        "readonly": True
                    }
                ]
            },
            "payments": {
                "label": "Payments",
                "fields": [
                    {
                        "name": "date",
                        "type": "date",
                        "label": "Payment Date",
                        "required": True
                    },
                    {
                        "name": "amount",
                        "type": "number",
                        "label": "Amount (INR)",
                        "step": "0.01",
                        "required": True
                    },
                    {
                        "name": "note",
                        "type": "text",
                        "label": "Note"
                    }
                ]
            }
        },
        "ordering": ["-invoice_date", "-created_on"]
    }
)


# Add custom actions to TradeViewSet
class EnhancedLicenseTradeViewSet(LicenseTradeViewSet):
    @action(detail=False, methods=['get'])
    def generate_invoice_number(self, request):
        """Generate next invoice number for SALE"""
        seller_company_id = request.query_params.get('seller_company_id')
        invoice_date = request.query_params.get('invoice_date')

        if not seller_company_id:
            return Response(
                {"error": "seller_company_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        from core.models import CompanyModel
        try:
            seller = CompanyModel.objects.get(pk=seller_company_id)
            invoice_number = LicenseTrade.next_invoice_number(
                seller_company=seller,
                invoice_date=invoice_date
            )
            return Response({"invoice_number": invoice_number})
        except CompanyModel.DoesNotExist:
            return Response(
                {"error": "Company not found"},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=['get'])
    def summary(self, request, pk=None):
        """Get trade summary with computed fields"""
        trade = self.get_object()
        return Response({
            "id": trade.id,
            "direction": trade.direction,
            "invoice_number": trade.invoice_number,
            "invoice_date": trade.invoice_date,
            "subtotal_amount": str(trade.subtotal_amount),
            "roundoff": str(trade.roundoff),
            "total_amount": str(trade.total_amount),
            "paid_or_received": str(trade.paid_or_received),
            "due_amount": str(trade.due_amount),
            "lines_count": trade.lines.count(),
            "payments_count": trade.payments.count()
        })


# Override the auto-generated viewset
LicenseTradeViewSet = EnhancedLicenseTradeViewSet


# Simple ViewSets for nested models (optional, for direct access)
TradeLineViewSet = MasterViewSet.create_viewset(
    LicenseTradeLine,
    TradeLineSimpleSerializer,
    config={
        "search": ["description"],
        "filter": {
            "trade": {
                "type": "fk",
                "fk_endpoint": "/trade/trades/",
                "label_field": "invoice_number"
            },
            "mode": {
                "type": "exact",
                "choices": LicenseTradeLine.MODE_CHOICES
            }
        },
        "list_display": [
            "id",
            "trade__invoice_number",
            "mode",
            "qty_kg",
            "amount_inr"
        ],
        "ordering": ["trade", "id"]
    }
)


TradePaymentViewSet = MasterViewSet.create_viewset(
    LicenseTradePayment,
    LicenseTradePaymentSerializer,
    config={
        "search": ["note"],
        "filter": {
            "trade": {
                "type": "fk",
                "fk_endpoint": "/trade/trades/",
                "label_field": "invoice_number"
            },
            "date": {
                "type": "date_range"
            }
        },
        "list_display": [
            "id",
            "trade__invoice_number",
            "date",
            "amount",
            "note"
        ],
        "ordering": ["-date", "-id"]
    }
)
