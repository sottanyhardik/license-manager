# reconciliation/views.py
"""
Read-only detection endpoints (one action per "tab") plus a small set of
auditable write actions for the BOE / Invoice Reconciliation panel
(Phase 1).

Business rule: One physical import may generate multiple documents, but it
must produce exactly one licence debit.

Every write action here is wrapped in `transaction.atomic()` and creates
its `ReconciliationLog` row inside that same transaction, so the log can
never diverge from the actual change. No automatic matching happens
anywhere in this module — every link/merge/ignore is an explicit,
operator-triggered action (see the plan's "no automatic matching" rule).
"""

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from apps.accounts.permissions import ReconciliationPermission
from apps.bill_of_entry.models import BillOfEntryModel
from apps.bill_of_entry.services import boe_service
from apps.license.models import LicenseImportItemsModel
from apps.trade.models import LicenseTrade
from apps.trade.services.trade_service import stamp_boe_invoice_from_trade

from .models import ReconciliationLog, ReconciliationNote
from .services import queries as reconciliation_queries


class ReconciliationResultsPagination(PageNumberPagination):
    """Standard pagination for the panel's potentially-large list endpoints."""
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 500


def _actor(request):
    return request.user if request.user and request.user.is_authenticated else None


def _serialize_log(row: ReconciliationLog) -> dict:
    return {
        "id": row.id,
        "action": row.action,
        "trade_id": row.trade_id,
        "invoice_number": row.trade.invoice_number if row.trade_id and row.trade else None,
        "bill_of_entry_id": row.bill_of_entry_id,
        "bill_of_entry_number": row.bill_of_entry.bill_of_entry_number if row.bill_of_entry_id and row.bill_of_entry else None,
        "license_item_id": row.license_item_id,
        "before": row.before,
        "after": row.after,
        "reason": row.reason,
        "user": row.user.username if row.user_id and row.user else None,
        "created_on": row.created_on,
    }


class ReconciliationViewSet(viewsets.ViewSet):
    """
    Not model-backed (no default `queryset`/`serializer_class`) — a plain
    DRF ViewSet exposing one `@action` per detection query in
    `services/queries.py`, plus the write actions below.

    Permissions: reads only require view access to trade OR BOE data;
    writes require BOTH `TradePermission` and `BillOfEntryPermission`'s
    write roles, since a write here can touch both trade and BOE records.
    See `ReconciliationPermission` in `apps.accounts.permissions`.
    """

    permission_classes = [ReconciliationPermission]
    pagination_class = ReconciliationResultsPagination

    def _paginate(self, request, rows):
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(rows, request, view=self)
        if page is not None:
            return paginator.get_paginated_response(page)
        return Response(rows)

    # ------------------------------------------------------------------
    # Read (detection) actions
    # ------------------------------------------------------------------

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        return Response(reconciliation_queries.summary())

    @action(detail=False, methods=["get"], url_path="missing-boe")
    def missing_boe(self, request):
        return self._paginate(request, reconciliation_queries.missing_boe())

    @action(detail=False, methods=["get"], url_path="missing-invoice")
    def missing_invoice(self, request):
        return self._paginate(request, reconciliation_queries.missing_invoice())

    @action(detail=False, methods=["get"], url_path="duplicate-debits")
    def duplicate_debits(self, request):
        return self._paginate(request, reconciliation_queries.duplicate_debits())

    @action(detail=False, methods=["get"], url_path="duplicate-boes")
    def duplicate_boes(self, request):
        return self._paginate(request, reconciliation_queries.duplicate_boes())

    @action(detail=False, methods=["get"], url_path="cif-comparison")
    def cif_comparison(self, request):
        return self._paginate(request, reconciliation_queries.cif_comparison())

    @action(detail=False, methods=["get"], url_path="qty-comparison")
    def qty_comparison(self, request):
        return self._paginate(request, reconciliation_queries.qty_comparison())

    @action(detail=False, methods=["get"], url_path="multi-boe")
    def multi_boe(self, request):
        return self._paginate(request, reconciliation_queries.multi_boe_per_invoice())

    @action(detail=False, methods=["get"], url_path="multi-invoice")
    def multi_invoice(self, request):
        return self._paginate(request, reconciliation_queries.multi_invoice_per_boe())

    @action(detail=False, methods=["get"], url_path="audit-log")
    def audit_log(self, request):
        qs = ReconciliationLog.objects.select_related(
            "trade", "bill_of_entry", "license_item", "user"
        ).order_by("-created_on")
        if request.query_params.get("scope") == "today":
            qs = qs.filter(created_on__date=timezone.now().date())

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request, view=self)
        if page is not None:
            return paginator.get_paginated_response([_serialize_log(row) for row in page])
        return Response([_serialize_log(row) for row in qs])

    # ------------------------------------------------------------------
    # Write actions
    # ------------------------------------------------------------------

    @action(detail=False, methods=["post"], url_path="link")
    def link(self, request):
        """
        Attach an existing BOE to an existing trade (`trade.boes.add()` —
        never replaces the existing set) and re-stamp the BOE's
        invoice_no/invoice_date, via the SAME helper
        `LicenseTradeSerializer.update()` uses
        (`stamp_boe_invoice_from_trade`), so the two "attach a BOE" code
        paths can't drift apart.
        """
        trade_id = request.data.get("trade_id")
        boe_id = request.data.get("boe_id")
        if not trade_id or not boe_id:
            return Response({"detail": "trade_id and boe_id are required."}, status=400)

        trade = get_object_or_404(LicenseTrade, pk=trade_id)
        boe = get_object_or_404(BillOfEntryModel, pk=boe_id)

        with transaction.atomic():
            before = {"boe_ids": list(trade.boes.values_list("id", flat=True))}
            trade.boes.add(boe)
            stamp_boe_invoice_from_trade(trade, boe)
            after = {"boe_ids": list(trade.boes.values_list("id", flat=True))}

            ReconciliationLog.objects.create(
                action=ReconciliationLog.ACTION_LINK,
                trade=trade,
                bill_of_entry=boe,
                before=before,
                after=after,
                user=_actor(request),
            )

        return Response({"trade_id": trade.id, "boe_id": boe.id, "linked_boe_ids": after["boe_ids"]})

    @action(detail=False, methods=["post"], url_path="merge-boe")
    def merge_boe(self, request):
        """
        Merge a literal duplicate BOE record into another — delegates
        entirely to the existing `boe_service.merge_boe()`
        (`apps/bill_of_entry/services/boe_service.py:203-285`); no merge
        logic is reimplemented here.
        """
        target_boe_id = request.data.get("target_boe_id")
        source_boe_id = request.data.get("source_boe_id")
        if not target_boe_id or not source_boe_id:
            return Response(
                {"detail": "target_boe_id and source_boe_id are required."}, status=400
            )

        target_boe = get_object_or_404(BillOfEntryModel, pk=target_boe_id)
        before = {"target_boe_id": target_boe.id, "source_boe_id": int(source_boe_id)}

        try:
            with transaction.atomic():
                result = boe_service.merge_boe(target_boe, int(source_boe_id))
                ReconciliationLog.objects.create(
                    action=ReconciliationLog.ACTION_MERGE_BOE,
                    bill_of_entry=target_boe,
                    before=before,
                    after={"message": result["message"]},
                    user=_actor(request),
                )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)

        return Response(result)

    @action(detail=False, methods=["post"], url_path="note")
    def note(self, request):
        """
        Create/update a `ReconciliationNote` (ignore or defer a flagged
        row) on exactly one of a trade, a BOE, or a licence item.
        """
        status_value = request.data.get("status")
        if status_value not in (ReconciliationNote.STATUS_IGNORED, ReconciliationNote.STATUS_PENDING):
            return Response({"detail": "status must be IGNORED or PENDING."}, status=400)

        trade_id = request.data.get("trade_id")
        bill_of_entry_id = request.data.get("bill_of_entry_id")
        license_item_id = request.data.get("license_item_id")
        provided = [v for v in (trade_id, bill_of_entry_id, license_item_id) if v]
        if len(provided) != 1:
            return Response(
                {"detail": "Exactly one of trade_id, bill_of_entry_id, license_item_id is required."},
                status=400,
            )

        trade = get_object_or_404(LicenseTrade, pk=trade_id) if trade_id else None
        boe = get_object_or_404(BillOfEntryModel, pk=bill_of_entry_id) if bill_of_entry_id else None
        license_item = (
            get_object_or_404(LicenseImportItemsModel, pk=license_item_id) if license_item_id else None
        )
        reason = request.data.get("reason", "")
        action_name = (
            ReconciliationLog.ACTION_IGNORE
            if status_value == ReconciliationNote.STATUS_IGNORED
            else ReconciliationLog.ACTION_MARK_PENDING
        )

        with transaction.atomic():
            note_obj = ReconciliationNote.objects.filter(
                trade=trade, bill_of_entry=boe, license_item=license_item,
            ).first()
            before = None
            if note_obj is None:
                note_obj = ReconciliationNote(trade=trade, bill_of_entry=boe, license_item=license_item)
            else:
                before = {"status": note_obj.status, "reason": note_obj.reason}

            note_obj.status = status_value
            note_obj.reason = reason
            note_obj.full_clean()
            note_obj.save()

            after = {"status": note_obj.status, "reason": note_obj.reason}
            ReconciliationLog.objects.create(
                action=action_name,
                trade=trade,
                bill_of_entry=boe,
                license_item=license_item,
                reason=reason,
                before=before,
                after=after,
                user=_actor(request),
            )

        return Response({"id": note_obj.id, "status": note_obj.status, "reason": note_obj.reason})

    @action(detail=False, methods=["post"], url_path="recalculate")
    def recalculate(self, request):
        """
        Trigger the existing bulk balance-recalculation Celery task
        (`apps.license.tasks.update_all_license_balances`) — same
        fire-and-return-task_id pattern as
        `ItemPivotViewSet.update_balance`
        (apps/license/views/item_pivot_report.py:1801-1832); no
        recalculation logic is reimplemented here.

        LIMITATION: the underlying task only accepts a `license_status`
        filter ('active'/'inactive'/'all'), not specific license ids.
        `license_ids` in the request body is accepted for forward
        compatibility but currently ignored — this always recalculates
        `license_status='all'`. Extending the task to accept explicit ids
        was judged too risky to bundle with this change; flagged as a
        follow-up.

        Poll status on the SAME existing endpoint the Item Pivot Report's
        balance-update button already uses — do not add a new one:
        GET /api/item-pivot/task-status/<task_id>/
        """
        from apps.license.tasks import update_all_license_balances

        license_status = "all"

        with transaction.atomic():
            task = update_all_license_balances.apply_async(
                args=[license_status],
                priority=9,
            )
            ReconciliationLog.objects.create(
                action=ReconciliationLog.ACTION_RECALCULATE,
                before=None,
                after={"task_id": task.id, "license_status": license_status},
                user=_actor(request),
            )

        return Response({
            "task_id": task.id,
            "status": "PENDING",
            "license_status": license_status,
            "message": f"Balance update started for {license_status} licenses. Use the task_id to check status.",
        }, status=202)
