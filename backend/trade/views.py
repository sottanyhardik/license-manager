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
            "from_company_label",
            "to_company_label",
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
        "nested_list_display": {
            "lines": ["sr_number_label", "mode", "qty_kg", "rate_inr_per_kg", "cif_fc", "exc_rate", "cif_inr", "fob_inr", "pct", "amount_inr"],
            "payments": ["date", "amount", "note"]
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
                        "name": "sr_number_label",
                        "type": "text",
                        "label": "SR Number",
                        "read_only": True
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
    @action(detail=True, methods=['get'], url_path='generate-bill-of-supply')
    def generate_bill_of_supply(self, request, pk=None):
        """
        Generate Bill of Supply PDF for SALE transactions.

        Query Parameters:
        - include_signature: Boolean (default: true) - include signature and stamp in PDF
        """
        from django.http import HttpResponse
        from trade.bill_of_supply_pdf import generate_bill_of_supply_pdf

        # Fetch trade with company relationships
        trade = self.get_queryset().select_related('from_company', 'to_company').get(pk=self.kwargs['pk'])

        # Validate that this is a SALE transaction
        if trade.direction != 'SALE':
            return Response(
                {"error": "Bill of Supply can only be generated for SALE transactions"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Get query parameter for signature inclusion (default: True)
            include_signature_param = request.query_params.get('include_signature', 'true').lower()
            include_signature = include_signature_param in ['true', '1', 'yes']

            pdf = generate_bill_of_supply_pdf(trade, include_signature=include_signature)

            # Create response
            response = HttpResponse(pdf, content_type='application/pdf')
            sig_suffix = "_with_sign" if include_signature else "_without_sign"
            filename = f"Bill_of_Supply_{trade.invoice_number}_{trade.invoice_date.strftime('%Y%m%d') if trade.invoice_date else 'NA'}{sig_suffix}.pdf"
            response['Content-Disposition'] = f'inline; filename="{filename}"'

            return response

        except Exception as e:
            return Response(
                {"error": f"Failed to generate PDF: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def generate_invoice_number(self, request):
        """Generate next invoice number for SALE"""
        from datetime import datetime
        seller_company_id = request.query_params.get('seller_company_id')
        invoice_date_str = request.query_params.get('invoice_date')

        if not seller_company_id:
            return Response(
                {"error": "seller_company_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Parse invoice_date string to date object
        invoice_date = None
        if invoice_date_str:
            try:
                invoice_date = datetime.strptime(invoice_date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {"error": "Invalid date format. Use YYYY-MM-DD"},
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

    @action(detail=True, methods=['post'], url_path='generate-transfer-letter')
    def generate_transfer_letter(self, request, pk=None):
        """
        Generate transfer letter for Trade transaction.

        Required in request.data:
        - template_id: ID of the TransferLetterModel template to use
        - company_name: (optional) Company name override
        - address_line1: (optional) Address line 1 override
        - address_line2: (optional) Address line 2 override
        - include_license_copy: (optional) Boolean, default True
        - selected_items: (optional) List of line IDs to include
        - cif_edits: (optional) Dict of line_id -> edited CIF value
        """
        from core.utils.transfer_letter import generate_transfer_letter_generic

        trade = self.get_object()
        return generate_transfer_letter_generic(trade, request, instance_type='trade')


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
