# trade/views.py

from datetime import datetime, date
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status

from accounts.permissions import TradePermission
from core.views import MasterViewSet
from .models import LicenseTrade, LicenseTradeLine, LicenseTradePayment
from .serializers import (
    LicenseTradeSerializer,
    TradeLineSimpleSerializer,
    LicenseTradePaymentSerializer
)


def _parse_date_strict(date_str):
    """
    Parse date string in strict ISO format (YYYY-MM-DD) only.

    Args:
        date_str: Date string to parse

    Returns:
        date object if successful, None otherwise

    Raises:
        ValueError: If date string is not in YYYY-MM-DD format
    """
    if not date_str:
        return None

    try:
        # Only accept ISO format YYYY-MM-DD
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError as e:
        raise ValueError(f"Invalid date format. Expected YYYY-MM-DD, got: {date_str}") from e


# Trade transactions ViewSet
LicenseTradeViewSet = MasterViewSet.create_viewset(
    LicenseTrade,
    LicenseTradeSerializer,
    config={
        "search": [
            "invoice_number",
            "from_company__name",
            "to_company__name",
            "remarks",
            "lines__sr_number__license__license_number",  # DFIA license number
            "incentive_license__license_number",  # Incentive license number (header)
            "incentive_lines__incentive_license__license_number"  # Incentive license number (lines)
        ],
        "filter": {
            "direction": {
                "type": "exact",
                "choices": LicenseTrade.DIR_CHOICES
            },
            "license_type": {
                "type": "exact",
                "choices": LicenseTrade.LICENSE_TYPE_CHOICES
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
            "incentive_license": {
                "type": "fk",
                "fk_endpoint": "/incentive-licenses/",
                "label_field": "license_number"
            },
            "invoice_date": {
                "type": "date_range"
            }
        },
        "list_display": [
            "direction",
            "license_type",
            "invoice_number",
            "invoice_date",
            "from_company_label",
            "to_company_label",
            "incentive_license",
            "total_amount",
            "paid_or_received",
            "due_amount"
        ],
        "form_fields": [
            "direction",
            "license_type",
            "incentive_license",
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
            "boe": "/bill-of-entries/",
            "incentive_license": "/incentive-licenses/"
        },
        "nested_list_display": {
            "lines": ["sr_number_label", "mode", "qty_kg", "rate_inr_per_kg", "cif_fc", "exc_rate", "cif_inr", "fob_inr", "pct", "amount_inr"],
            "incentive_lines": ["incentive_license_label", "license_value", "rate_pct", "amount_inr"],
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
            "incentive_lines": {
                "label": "Incentive License Lines",
                "fields": [
                    {
                        "name": "incentive_license",
                        "type": "fk",
                        "label": "Incentive License",
                        "fk_endpoint": "/incentive-licenses/",
                        "label_field": "license_number",
                        "required": True
                    },
                    {
                        "name": "incentive_license_label",
                        "type": "text",
                        "label": "License",
                        "read_only": True
                    },
                    {
                        "name": "license_value",
                        "type": "number",
                        "label": "License Value (INR)",
                        "step": "0.01",
                        "required": True
                    },
                    {
                        "name": "rate_pct",
                        "type": "number",
                        "label": "Rate (%)",
                        "step": "0.001",
                        "required": True
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
        "ordering": ["-invoice_date", "-invoice_number", "-created_on"]
    }
)

# Add permission classes
LicenseTradeViewSet.permission_classes = [TradePermission]


# Add custom actions to TradeViewSet
class EnhancedLicenseTradeViewSet(LicenseTradeViewSet):
    def get_queryset(self):
        qs = super().get_queryset()
        qs = qs.select_related(
            'from_company', 'to_company', 'boe', 'incentive_license', 'linked_trade',
            'created_by', 'modified_by',
        )
        qs = qs.prefetch_related(
            'lines',
            'lines__sr_number',
            'lines__sr_number__license',
            'lines__sr_number__items',
            'incentive_lines',
            'incentive_lines__incentive_license',
            'payments',
        )
        return qs

    def create(self, request, *args, **kwargs):
        """Override create to log request data"""
        import logging
        logger = logging.getLogger(__name__)

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("VIEW CREATE called")
            logger.debug("request.data keys: %s", list(request.data.keys()))
            logger.debug("request.content_type: %s", request.content_type)

            if 'lines' in request.data:
                logger.debug("request.data['lines'] type: %s", type(request.data['lines']).__name__)
            else:
                logger.debug("'lines' NOT in request.data")

        return super().create(request, *args, **kwargs)

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

    @action(detail=True, methods=['get'], url_path='generate-purchase-invoice')
    def generate_purchase_invoice(self, request, pk=None):
        """
        Generate Purchase Invoice PDF for PURCHASE transactions.

        Query Parameters:
        - include_signature: Boolean (default: true) - include signature and stamp in PDF
        """
        from django.http import HttpResponse
        from trade.purchase_invoice_pdf import generate_purchase_invoice_pdf

        # Fetch trade with company relationships
        trade = self.get_queryset().select_related('from_company', 'to_company').get(pk=self.kwargs['pk'])

        # Validate that this is a PURCHASE transaction
        if trade.direction != 'PURCHASE':
            return Response(
                {"error": "Purchase Invoice can only be generated for PURCHASE transactions"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Get query parameter for signature inclusion (default: True)
            include_signature_param = request.query_params.get('include_signature', 'true').lower()
            include_signature = include_signature_param in ['true', '1', 'yes']

            pdf = generate_purchase_invoice_pdf(trade, include_signature=include_signature)

            # Create response
            response = HttpResponse(pdf, content_type='application/pdf')
            sig_suffix = "_with_sign" if include_signature else "_without_sign"
            filename = f"Purchase_Invoice_{trade.invoice_number}_{trade.invoice_date.strftime('%Y%m%d') if trade.invoice_date else 'NA'}{sig_suffix}.pdf"
            response['Content-Disposition'] = f'inline; filename="{filename}"'

            return response

        except Exception as e:
            return Response(
                {"error": f"Failed to generate PDF: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='prefill-invoice-number')
    def prefill_invoice_number(self, request):
        """
        Generate next invoice number based on direction, company, and invoice date.

        Query Parameters:
        - direction: 'PURCHASE', 'SALE', 'COMMISSION_PURCHASE', or 'COMMISSION_SALE' (required)
        - company_id: Company ID (required)
        - invoice_date: Invoice date in YYYY-MM-DD or dd-mm-yyyy format (optional, defaults to today)

        Returns:
        - invoice_number: Generated invoice number in format:
          PURCHASE: P-PREFIX/YYYY-YY/NNNN
          SALE: PREFIX/YYYY-YY/NNNN
          COMMISSION_PURCHASE: COM-P-PREFIX/YYYY-YY/NNNN
          COMMISSION_SALE: COM-PREFIX/YYYY-YY/NNNN
        """
        from datetime import datetime
        from trade.models import get_next_invoice_number

        direction = request.query_params.get('direction')
        company_id = request.query_params.get('company_id')
        invoice_date_str = request.query_params.get('invoice_date')

        # Validate required parameters
        if not direction:
            return Response(
                {"error": "direction is required (PURCHASE, SALE, COMMISSION_PURCHASE, or COMMISSION_SALE)"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not company_id:
            return Response(
                {"error": "company_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate direction
        if direction not in ['PURCHASE', 'SALE', 'COMMISSION_PURCHASE', 'COMMISSION_SALE']:
            return Response(
                {"error": "direction must be 'PURCHASE', 'SALE', 'COMMISSION_PURCHASE', or 'COMMISSION_SALE'"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Parse invoice_date string to date object (strict ISO format only)
        invoice_date = None
        if invoice_date_str:
            try:
                invoice_date = _parse_date_strict(invoice_date_str)
            except ValueError as e:
                return Response(
                    {"error": str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )

        from core.models import CompanyModel
        try:
            company = CompanyModel.objects.get(pk=company_id)
            invoice_number = get_next_invoice_number(
                direction=direction,
                company_name=company.name,
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

    @action(detail=True, methods=['post'], url_path='link-trade')
    def link_trade(self, request, pk=None):
        """
        Bidirectionally link two trades.
        POST body: {"partner_id": <int>}  — set link on both trades.
        POST body: {"partner_id": null}   — clear link on both trades.
        """
        trade = self.get_object()
        partner_id = request.data.get('partner_id')

        # Unlink
        if partner_id is None:
            old_partner_id = trade.linked_trade_id
            LicenseTrade.objects.filter(pk=trade.pk).update(linked_trade=None)
            if old_partner_id:
                LicenseTrade.objects.filter(pk=old_partner_id, linked_trade=trade.pk).update(linked_trade=None)
            trade.refresh_from_db()
            from trade.serializers import LicenseTradeSerializer
            return Response(LicenseTradeSerializer(trade, context={'request': request}).data)

        # Link
        try:
            partner = LicenseTrade.objects.get(pk=partner_id)
        except LicenseTrade.DoesNotExist:
            return Response({"error": "Partner trade not found"}, status=status.HTTP_404_NOT_FOUND)

        if partner.pk == trade.pk:
            return Response({"error": "Cannot link a trade to itself"}, status=status.HTTP_400_BAD_REQUEST)

        # Clear any old links on both sides first
        old_trade_partner = trade.linked_trade_id
        old_partner_partner = partner.linked_trade_id
        if old_trade_partner and old_trade_partner != partner.pk:
            LicenseTrade.objects.filter(pk=old_trade_partner).update(linked_trade=None)
        if old_partner_partner and old_partner_partner != trade.pk:
            LicenseTrade.objects.filter(pk=old_partner_partner).update(linked_trade=None)

        LicenseTrade.objects.filter(pk=trade.pk).update(linked_trade=partner)
        LicenseTrade.objects.filter(pk=partner.pk).update(linked_trade=trade)

        trade.refresh_from_db()
        from trade.serializers import LicenseTradeSerializer
        return Response(LicenseTradeSerializer(trade, context={'request': request}).data)

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
