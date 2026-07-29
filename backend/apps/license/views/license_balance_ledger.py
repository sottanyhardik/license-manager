"""
Licence Balance & Financial Reconciliation Workspace — API actions attached
to `LicenseDetailsViewSet` (see `add_license_balance_ledger_actions` /
`apps/license/views/license.py`, following the same
`add_license_report_action`/`add_active_dfia_report_action` convention
already used on this viewset).

Every read action delegates to `LicenseBalanceLedgerBuilder` for the
dataset — this module ONLY handles HTTP request/response shaping and
permission enforcement.
"""
from datetime import date, datetime
from decimal import Decimal

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
            # `license_item` is the only license-identifying FK this log
            # model carries (see its own docstring — it's always associated
            # via an item/trade/BOE, never a bare license); a recalculation
            # covers the whole licence, so pick any one representative item
            # purely so this event is queryable by license (`build_timeline`
            # filters on `license_item__license=license_obj`).
            license_item=license_obj.import_license.first(),
            before={'balance_cif': str(before_balance)},
            after={'balance_cif': str(new_balance)},
            reason=request.data.get('reason', ''),
            user=request.user,
        )
        return Response({'balance_cif': float(new_balance)})

    @action(detail=True, methods=['post'], url_path='ignore-warning')
    def ignore_warning(self, request, pk=None):
        """
        Body: {warning_type, entity_type, entity_id, reason?}. Pure
        workflow bookkeeping — never touches any financial record (see
        `IgnoredWarning`'s docstring). The identity fields must exactly
        match what `build_warnings()` currently computes for this licence;
        rather than trust arbitrary client input, we re-derive the current
        warning set and require the target to actually be present.
        """
        from apps.license.services.license_balance_ledger_builder import LicenseBalanceLedgerBuilder
        from apps.reconciliation.services.warning_service import ignore_warning as ignore_warning_service

        license_obj = self.get_object()
        warning_type = request.data.get('warning_type')
        entity_type = request.data.get('entity_type')
        entity_id = str(request.data.get('entity_id', ''))
        if not warning_type or not entity_type or not entity_id:
            return Response({'error': 'warning_type, entity_type and entity_id are required.'}, status=400)

        data = LicenseBalanceLedgerBuilder.build(license_obj)
        match = next(
            (w for w in data['warnings']
             if w['warning_type'] == warning_type and w['entity_type'] == entity_type and w['entity_id'] == entity_id),
            None,
        )
        if match is None:
            return Response({'error': 'No active warning matches that identity for this licence.'}, status=404)

        obj = ignore_warning_service(
            license_obj, warning_type, entity_type, entity_id,
            user=request.user, reason=request.data.get('reason', ''),
        )
        return Response({'id': obj.id, 'ignored': obj.ignored}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='restore-warning')
    def restore_warning(self, request, pk=None):
        """Body: {warning_type, entity_type, entity_id, reason?}."""
        from apps.reconciliation.models import IgnoredWarning
        from apps.reconciliation.services.warning_service import restore_warning as restore_warning_service

        license_obj = self.get_object()
        warning_type = request.data.get('warning_type')
        entity_type = request.data.get('entity_type')
        entity_id = str(request.data.get('entity_id', ''))
        try:
            ignored = IgnoredWarning.objects.get(
                license=license_obj, warning_type=warning_type, entity_type=entity_type, entity_id=entity_id,
            )
        except IgnoredWarning.DoesNotExist:
            return Response({'error': 'No ignored warning matches that identity for this licence.'}, status=404)

        restore_warning_service(ignored, user=request.user, reason=request.data.get('reason', ''))
        return Response({'id': ignored.id, 'ignored': ignored.ignored})

    for method in (
        balance_ledger, recalculate,
        ignore_warning, restore_warning,
    ):
        setattr(viewset_class, method.__name__, method)

    return viewset_class
