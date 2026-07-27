"""
Licence Balance & Financial Reconciliation Workspace — API actions attached
to `LicenseDetailsViewSet` (see `add_license_balance_ledger_actions` /
`apps/license/views/license.py`, following the same
`add_license_report_action`/`add_active_dfia_report_action` convention
already used on this viewset).

Every write action here delegates to `apps.reconciliation.services
.allocation_service` for validation + the append-only allocation ledger
(never recomputes/duplicates that logic), and every read action delegates
to `LicenseBalanceLedgerBuilder` for the dataset — this module ONLY handles
HTTP request/response shaping and permission enforcement.
"""
from datetime import date, datetime
from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import LicenseBalanceLedgerPermission


def _json_safe(value):
    """Recursively convert Decimal -> float and date/datetime -> ISO string
    so `LicenseBalanceLedgerBuilder`'s plain-Python dataset can be returned
    directly as a DRF `Response` body."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def _validation_error_response(exc):
    return Response({'error': str(exc) if not hasattr(exc, 'message') else exc.message}, status=status.HTTP_400_BAD_REQUEST)


def add_license_balance_ledger_actions(viewset_class):
    """Attaches the Licence Balance Workspace actions to `viewset_class`."""

    @action(detail=True, methods=['get'], url_path='balance-ledger')
    def balance_ledger(self, request, pk=None):
        """GET the full LicenseLedgerData dataset for one licence — the
        single source consumed by the workspace UI, PDF, and Excel."""
        from apps.license.services.license_balance_ledger_builder import LicenseBalanceLedgerBuilder

        license_obj = self.get_object()
        data = LicenseBalanceLedgerBuilder.build(license_obj)
        return Response(_json_safe(data))

    @action(detail=True, methods=['post'], url_path='allocate-invoice-boe')
    def allocate_invoice_boe(self, request, pk=None):
        """
        Body: {trade_line_id, allocations: [{row_details_id, qty, cif_fc, cif_inr, notes?}, ...]}
        Supports the many-to-many case (one invoice split across many BOEs)
        in a single call — each pair is its own `create_invoice_boe_allocation`.
        """
        from apps.reconciliation.services import allocation_service
        from apps.trade.models import LicenseTradeLine
        from apps.bill_of_entry.models import RowDetails

        license_obj = self.get_object()
        trade_line_id = request.data.get('trade_line_id')
        allocations = request.data.get('allocations') or []
        if not trade_line_id or not allocations:
            return Response({'error': 'trade_line_id and at least one allocation are required.'}, status=400)

        try:
            trade_line = LicenseTradeLine.objects.select_related('sr_number__license').get(pk=trade_line_id)
        except LicenseTradeLine.DoesNotExist:
            return Response({'error': 'trade_line not found.'}, status=404)
        if trade_line.sr_number.license_id != license_obj.id:
            return Response({'error': 'trade_line does not belong to this licence.'}, status=400)

        created = []
        try:
            for entry in allocations:
                row_details = RowDetails.objects.select_related('sr_number__license').get(pk=entry['row_details_id'])
                allocation = allocation_service.create_invoice_boe_allocation(
                    trade_line, row_details,
                    qty=entry.get('qty', 0), cif_fc=entry.get('cif_fc', 0), cif_inr=entry.get('cif_inr', 0),
                    user=request.user, notes=entry.get('notes', ''),
                )
                created.append(allocation.id)
        except RowDetails.DoesNotExist:
            return Response({'error': 'row_details not found.'}, status=404)
        except DjangoValidationError as exc:
            return _validation_error_response(exc)

        return Response({'created_allocation_ids': created}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='edit-invoice-boe-allocation')
    def edit_invoice_boe_allocation(self, request, pk=None):
        from apps.reconciliation.models import InvoiceBOEAllocation
        from apps.reconciliation.services import allocation_service

        license_obj = self.get_object()
        try:
            allocation = InvoiceBOEAllocation.objects.get(pk=request.data.get('allocation_id'))
        except (InvoiceBOEAllocation.DoesNotExist, TypeError, ValueError):
            return Response({'error': 'allocation not found.'}, status=404)
        if allocation.trade_line.sr_number.license_id != license_obj.id:
            return Response({'error': 'allocation does not belong to this licence.'}, status=400)

        try:
            new_allocation = allocation_service.edit_invoice_boe_allocation(
                allocation,
                qty=request.data.get('qty', 0), cif_fc=request.data.get('cif_fc', 0), cif_inr=request.data.get('cif_inr', 0),
                user=request.user, notes=request.data.get('notes', ''),
            )
        except DjangoValidationError as exc:
            return _validation_error_response(exc)
        return Response({'new_allocation_id': new_allocation.id})

    @action(detail=True, methods=['post'], url_path='reverse-invoice-boe-allocation')
    def reverse_invoice_boe_allocation(self, request, pk=None):
        from apps.reconciliation.models import InvoiceBOEAllocation
        from apps.reconciliation.services import allocation_service

        license_obj = self.get_object()
        try:
            allocation = InvoiceBOEAllocation.objects.get(pk=request.data.get('allocation_id'))
        except (InvoiceBOEAllocation.DoesNotExist, TypeError, ValueError):
            return Response({'error': 'allocation not found.'}, status=404)
        if allocation.trade_line.sr_number.license_id != license_obj.id:
            return Response({'error': 'allocation does not belong to this licence.'}, status=400)

        reason = request.data.get('reason', '')
        if not reason:
            return Response({'error': 'A reason is required to reverse an allocation.'}, status=400)
        try:
            allocation_service.reverse_invoice_boe_allocation(allocation, user=request.user, reason=reason)
        except DjangoValidationError as exc:
            return _validation_error_response(exc)
        return Response({'status': 'reversed'})

    @action(detail=True, methods=['post'], url_path='allocate-boe-allotment')
    def allocate_boe_allotment(self, request, pk=None):
        """Body: {row_details_id, allocations: [{allotment_item_id, qty, cif_fc, cif_inr, notes?}, ...]}"""
        from apps.reconciliation.services import allocation_service
        from apps.bill_of_entry.models import RowDetails
        from apps.allotment.models import AllotmentItems

        license_obj = self.get_object()
        row_details_id = request.data.get('row_details_id')
        allocations = request.data.get('allocations') or []
        if not row_details_id or not allocations:
            return Response({'error': 'row_details_id and at least one allocation are required.'}, status=400)

        try:
            row_details = RowDetails.objects.select_related('sr_number__license').get(pk=row_details_id)
        except RowDetails.DoesNotExist:
            return Response({'error': 'row_details not found.'}, status=404)
        if row_details.sr_number.license_id != license_obj.id:
            return Response({'error': 'row_details does not belong to this licence.'}, status=400)

        created = []
        try:
            for entry in allocations:
                allotment_item = AllotmentItems.objects.select_related('item__license').get(pk=entry['allotment_item_id'])
                allocation = allocation_service.create_boe_allotment_allocation(
                    row_details, allotment_item,
                    qty=entry.get('qty', 0), cif_fc=entry.get('cif_fc', 0), cif_inr=entry.get('cif_inr', 0),
                    user=request.user, notes=entry.get('notes', ''),
                )
                created.append(allocation.id)
        except AllotmentItems.DoesNotExist:
            return Response({'error': 'allotment_item not found.'}, status=404)
        except DjangoValidationError as exc:
            return _validation_error_response(exc)

        return Response({'created_allocation_ids': created}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='edit-boe-allotment-allocation')
    def edit_boe_allotment_allocation(self, request, pk=None):
        from apps.reconciliation.models import BOEAllotmentAllocation
        from apps.reconciliation.services import allocation_service

        license_obj = self.get_object()
        try:
            allocation = BOEAllotmentAllocation.objects.get(pk=request.data.get('allocation_id'))
        except (BOEAllotmentAllocation.DoesNotExist, TypeError, ValueError):
            return Response({'error': 'allocation not found.'}, status=404)
        if allocation.row_details.sr_number.license_id != license_obj.id:
            return Response({'error': 'allocation does not belong to this licence.'}, status=400)

        try:
            new_allocation = allocation_service.edit_boe_allotment_allocation(
                allocation,
                qty=request.data.get('qty', 0), cif_fc=request.data.get('cif_fc', 0), cif_inr=request.data.get('cif_inr', 0),
                user=request.user, notes=request.data.get('notes', ''),
            )
        except DjangoValidationError as exc:
            return _validation_error_response(exc)
        return Response({'new_allocation_id': new_allocation.id})

    @action(detail=True, methods=['post'], url_path='reverse-boe-allotment-allocation')
    def reverse_boe_allotment_allocation(self, request, pk=None):
        from apps.reconciliation.models import BOEAllotmentAllocation
        from apps.reconciliation.services import allocation_service

        license_obj = self.get_object()
        try:
            allocation = BOEAllotmentAllocation.objects.get(pk=request.data.get('allocation_id'))
        except (BOEAllotmentAllocation.DoesNotExist, TypeError, ValueError):
            return Response({'error': 'allocation not found.'}, status=404)
        if allocation.row_details.sr_number.license_id != license_obj.id:
            return Response({'error': 'allocation does not belong to this licence.'}, status=400)

        reason = request.data.get('reason', '')
        if not reason:
            return Response({'error': 'A reason is required to reverse an allocation.'}, status=400)
        try:
            allocation_service.reverse_boe_allotment_allocation(allocation, user=request.user, reason=reason)
        except DjangoValidationError as exc:
            return _validation_error_response(exc)
        return Response({'status': 'reversed'})

    @action(detail=True, methods=['post'], url_path='mark-external-invoice')
    def mark_external_invoice(self, request, pk=None):
        """Body: {row_details_id, invoice_number, qty, cif_fc, cif_inr, notes?}"""
        from apps.reconciliation.services import allocation_service
        from apps.bill_of_entry.models import RowDetails

        license_obj = self.get_object()
        try:
            row_details = RowDetails.objects.select_related('sr_number__license').get(pk=request.data.get('row_details_id'))
        except (RowDetails.DoesNotExist, TypeError, ValueError):
            return Response({'error': 'row_details not found.'}, status=404)
        if row_details.sr_number.license_id != license_obj.id:
            return Response({'error': 'row_details does not belong to this licence.'}, status=400)

        try:
            link = allocation_service.mark_boe_as_external_invoice(
                row_details,
                invoice_number=request.data.get('invoice_number', ''),
                qty=request.data.get('qty', 0), cif_fc=request.data.get('cif_fc', 0), cif_inr=request.data.get('cif_inr', 0),
                user=request.user, notes=request.data.get('notes', ''),
            )
        except DjangoValidationError as exc:
            return _validation_error_response(exc)
        return Response({'link_id': link.id}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='reverse-external-invoice')
    def reverse_external_invoice(self, request, pk=None):
        from apps.reconciliation.models import ExternalInvoiceLink
        from apps.reconciliation.services import allocation_service

        license_obj = self.get_object()
        try:
            link = ExternalInvoiceLink.objects.get(pk=request.data.get('link_id'))
        except (ExternalInvoiceLink.DoesNotExist, TypeError, ValueError):
            return Response({'error': 'external invoice link not found.'}, status=404)
        if link.row_details.sr_number.license_id != license_obj.id:
            return Response({'error': 'link does not belong to this licence.'}, status=400)

        reason = request.data.get('reason', '')
        if not reason:
            return Response({'error': 'A reason is required to reverse an external invoice link.'}, status=400)
        try:
            allocation_service.reverse_external_invoice_link(link, user=request.user, reason=reason)
        except DjangoValidationError as exc:
            return _validation_error_response(exc)
        return Response({'status': 'reversed'})

    @action(detail=True, methods=['post'], url_path='recalculate')
    def recalculate(self, request, pk=None):
        """
        Recalculates every import item's balance fields (same logic as the
        `RowDetails`/`AllotmentItems` post-save signals) and then refreshes
        the licence's denormalized `balance_cif` — reusing exactly the same
        method as `python manage.py update_balance_cif --license-number ...`
        rather than duplicating that math here.
        """
        from apps.core.scripts.calculate_balance import update_balance_values
        from apps.license.management.commands.update_balance_cif import Command as UpdateBalanceCifCommand
        from apps.reconciliation.models import ReconciliationLog

        license_obj = self.get_object()
        before_balance = license_obj.balance_cif

        for item in license_obj.import_license.all():
            update_balance_values(item)

        new_balance = UpdateBalanceCifCommand().update_license_balance(license_obj, dry_run=False)

        ReconciliationLog.objects.create(
            action=ReconciliationLog.ACTION_RECALCULATE,
            before={'balance_cif': str(before_balance)},
            after={'balance_cif': str(new_balance)},
            reason=request.data.get('reason', ''),
            user=request.user,
        )
        return Response({'balance_cif': float(new_balance)})

    for method in (
        balance_ledger, allocate_invoice_boe, edit_invoice_boe_allocation, reverse_invoice_boe_allocation,
        allocate_boe_allotment, edit_boe_allotment_allocation, reverse_boe_allotment_allocation,
        mark_external_invoice, reverse_external_invoice, recalculate,
    ):
        setattr(viewset_class, method.__name__, method)

    return viewset_class
