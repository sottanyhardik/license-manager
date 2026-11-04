# license/views/license.py
import logging
from decimal import Decimal
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import BooleanField, DateField, DecimalField, ForeignKey, IntegerField, Prefetch
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

logger = logging.getLogger(__name__)

from apps.accounts.permissions import LicenseBalanceLedgerPermission, LicensePermission, LicenseReadOnlyPermission
from apps.core.constants import SCHEME_CODE_CHOICES, \
    NOTIFICATION_NORM_CHOICES, UNIT_CHOICES, \
    CURRENCY_CHOICES
from apps.core.filters import CombinedFilterBackend, EnhancedSearchFilter, AdvancedOrderingFilter
from apps.core.filtersets import LicenseFilterSet
from apps.core.views.master_view import MasterViewSet
from apps.license.models import LicenseDetailsModel, LicenseDocumentModel
from apps.license.serializers import LicenseDetailsSerializer, LicenseListSerializer, LicenseExportItemSerializer, LicenseImportItemSerializer, \
    LicenseDocumentSerializer
from apps.license.serializers.license import IndividualItemCifOverrideSerializer
from apps.license.views.active_dfia_report import add_active_dfia_report_action
from apps.license.views.license_report import add_license_report_action
from apps.license.views.license_balance_ledger import add_license_balance_ledger_actions
from apps.license.views.license_overview import add_license_overview_actions


# Helper function to get default purchase status IDs from codes
def get_default_purchase_status_ids():
    """Default purchase-status filter = every status the master marks active.

    The Purchase Status master (`PurchaseStatus.is_active`) is the single
    source of truth for what's "active" — no code list is hardcoded here,
    so this stays correct as statuses are added/retired in the master
    without a matching code change here (see the global filter
    standardization: Purchase Status must always come from the master).
    """
    from apps.core.models import PurchaseStatus
    ids = list(PurchaseStatus.objects.filter(is_active=True).values_list('id', flat=True))
    return ','.join(map(str, ids)) if ids else ''

# Nested field definitions for LicenseDetails
license_nested_field_defs = {
    "export_license": [
        {"name": "id", "type": "text", "label": "ID", "read_only": True, "show_in_list": False},
        {"name": "description", "type": "text", "label": "Description"},
        {"name": "norm_class", "type": "fk", "label": "Norm Class", "fk_endpoint": "/masters/sion-classes/",
         "label_field": "norm_class", "display_field": "norm_class_label"},
        {"name": "start_serial_number", "type": "number", "label": "Start Serial Number", "default": 0},
        {"name": "net_quantity", "type": "number", "label": "Net Quantity", "default": 0},
        {"name": "fob_inr", "type": "number", "label": "FOB (INR)", "default": 0},
        {"name": "currency", "type": "select", "label": "Currency", "choices": list(CURRENCY_CHOICES),
         "default": "usd"},
        {"name": "cif_fc", "type": "number", "label": "CIF (FC)", "default": 0},
        {"name": "cif_inr", "type": "number", "label": "CIF (INR)", "default": 0},
    ],
    "import_license": [
        {"name": "id", "type": "text", "label": "ID", "read_only": True, "show_in_list": False},
        {"name": "serial_number", "type": "number", "label": "Serial Number", "default": 0},
        {"name": "hs_code", "type": "fk", "label": "HS Code", "fk_endpoint": "/masters/hs-codes/",
         "label_field": "hs_code", "display_field": "hs_code_label"},
        {"name": "description", "type": "textarea", "label": "Description"},
        {"name": "items", "type": "fk_multi", "label": "Items", "fk_endpoint": "/masters/item-names/",
         "label_field": "name", "show_in_list": False},
        {"name": "quantity", "type": "number", "label": "Quantity", "default": 0},
        {"name": "unit", "type": "select", "label": "Unit", "choices": list(UNIT_CHOICES), "default": "kg"},
        {"name": "cif_fc", "type": "number", "label": "CIF (FC)", "default": 0},
        {"name": "cif_inr", "type": "number", "label": "CIF (INR)", "default": 0},
        # `is_restricted` is derived from `condition_type` (set on save) —
        # hidden from the editable form, surfaced only via the Condition badge.
        {"name": "is_restricted", "type": "boolean", "label": "Is Restricted", "read_only": True, "show_in_list": False, "show_in_form": False},
        {"name": "condition_type", "type": "select", "label": "Condition", "choices": [
            {"value": "", "label": "—"},
            {"value": "AU", "label": "AU (Actual User)"},
            {"value": "2%", "label": "2% restriction"},
            {"value": "3%", "label": "3% restriction"},
            {"value": "5%", "label": "5% restriction"},
            {"value": "10%", "label": "10% restriction"},
        ], "default": "", "show_in_list": False},
    ],
    "license_documents": [
        {"name": "id", "type": "text", "label": "ID", "read_only": True, "show_in_list": False},
        {
            "name": "type",
            "type": "select",
            "label": "Document Type",
            "choices": [
                {"value": "LICENSE COPY", "label": "LICENSE COPY"},
                {"value": "TRANSFER LETTER", "label": "TRANSFER LETTER"},
                {"value": "OTHER", "label": "OTHER"}
            ]
        },
        {"name": "file", "type": "file", "label": "File"},
    ],
}

# Create base viewset
_LicenseDetailsViewSetBase = MasterViewSet.create_viewset(
    LicenseDetailsModel,
    LicenseDetailsSerializer,
    config={
        "search": ["license_number", "file_number", "exporter__name"],
        "filter": {
            "exporter": {"type": "fk", "fk_endpoint": "/masters/companies/", "label_field": "name"},
            "exclude_exporter": {"type": "exclude_fk", "fk_endpoint": "/masters/companies/", "label_field": "name",
                                 "filter_field": "exporter"},
            "port": {"type": "fk", "fk_endpoint": "/masters/ports/", "label_field": "name"},
            "exclude_port": {"type": "exclude_fk", "fk_endpoint": "/masters/ports/", "label_field": "name",
                             "filter_field": "port"},
            "export_license__norm_class": {"type": "fk", "fk_endpoint": "/masters/sion-classes/",
                                           "label_field": "norm_class"},
            "notification_number": {"type": "fk", "fk_endpoint": "/masters/notification-numbers/", "label_field": "code", "value_field": "code"},
            "scheme_code": {"type": "fk", "fk_endpoint": "/masters/scheme-codes/", "label_field": "code", "value_field": "code"},
            "purchase_status": {"type": "fk", "fk_endpoint": "/masters/purchase-statuses/", "label_field": "label", "filter_params": {"is_active": "true"}},
            "license_date": {"type": "date_range"},
            "license_expiry_date": {"type": "date_range"},
            "balance__balance_cif": {"type": "range"},
            "is_expired": {
                "type": "button_group",
                "label": "License Status",
                "choices": [
                    {"value": "all", "label": "All Licenses"},
                    {"value": "False", "label": "Active"},
                    {"value": "True", "label": "Expired"},
                ],
            },
            "flags__is_null": {"type": "exact"},
            "is_planned": {"type": "exact"},
        },
        "default_filters": {
            "is_expired": "False",
            "flags__is_null": "False",
        },
        "list_display": [
            "license_number",
            "license_date",
            "license_expiry_date",
            "exporter__name",
            "exporter__iec",
            "port__name",
            "purchase_status_label",
            "balance_cif",
            "latest_transfer",
            "get_norm_class",
            "ledger_date"
        ],
        "form_fields": [
            "scheme_code",
            "notification_number",
            "license_number",
            "license_date",
            "license_expiry_date",
            "port",
            "registration_number",
            "registration_date",
            "file_number",
            "exporter",
            "purchase_status",
            "condition_sheet",
        ],
        "nested_field_defs": license_nested_field_defs,
        "nested_list_display": {
            "export_license": ["norm_class_label", "fob_inr", "cif_fc", "cif_inr"],
            "import_license": ["serial_number", "hs_code_label", "description", "quantity", "unit", "cif_fc",
                               "cif_inr", "allotted_quantity", "allotted_value", "debited_quantity", "debited_value",
                               "available_quantity", "available_value"],
            "license_documents": ["type", "file"],
        },
        "field_meta": {
            "exporter": {
                "type": "fk",
                "fk_endpoint": "/masters/companies/",
                "label_field": "name"
            },
            "port": {
                "type": "fk",
                "fk_endpoint": "/masters/ports/",
                "label_field": "name"
            },
            "current_owner": {
                "type": "fk",
                "fk_endpoint": "/masters/companies/",
                "label_field": "name"
            },
            "purchase_status": {
                "type": "fk",
                "fk_endpoint": "/masters/purchase-statuses/",
                "label_field": "label",
                "filter_params": {"is_active": "true"}
            },
            "scheme_code": {
                "type": "fk",
                "fk_endpoint": "/masters/scheme-codes/",
                "label_field": "code",
                "value_field": "code",
            },
            "notification_number": {
                "type": "fk",
                "fk_endpoint": "/masters/notification-numbers/",
                "label_field": "code",
                "value_field": "code",
            },
        }
    }
)


# Extend the base viewset to add custom filter logic for is_expired and is_null
class LicenseDetailsViewSet(_LicenseDetailsViewSetBase):
    """
    Custom license viewset with special handling for is_expired and is_null filters.

    Filter Logic:
    - is_expired: True when license_expiry_date < today, False when license_expiry_date >= today
    - is_null: True when balance_cif < 200, False when balance_cif >= 200
    """
    permission_classes = [LicensePermission]
    lookup_value_regex = '[^/]+'  # Allow both numbers and strings
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    # Actions attached by add_license_balance_ledger_actions — gated by their
    # own fine-grained permission class rather than LicensePermission,
    # since several of them require BOE/TRADE/ALLOTMENT write roles, not
    # just LICENSE_MANAGER. See LicenseBalanceLedgerPermission's docstring.
    _BALANCE_LEDGER_ACTIONS = {
        'balance_ledger', 'recalculate',
        'ignore_warning', 'restore_warning',
        'hide_boe', 'restore_boe', 'hide_boe_bulk', 'restore_boe_bulk',
        # License Overview dashboard actions (add_license_overview_actions) —
        # all read-only (GET), so they only ever hit LicenseBalanceLedgerPermission's
        # SAFE_METHODS/read_roles branch, never write_action_roles.
        'overview_summary', 'overview_boes', 'overview_allotments',
        'overview_items', 'overview_invoice_ledger', 'plan_utilization',
    }

    def get_permissions(self):
        # bulk_balance_excel uses POST only because the licence-number list
        # goes in the request body; behaviour is read-only. Allow any role
        # that can read licences.
        if getattr(self, 'action', None) == 'bulk_balance_excel':
            return [LicenseReadOnlyPermission()]
        if getattr(self, 'action', None) in self._BALANCE_LEDGER_ACTIONS:
            return [LicenseBalanceLedgerPermission()]
        return super().get_permissions()

    # Apply advanced filter backends
    filterset_class = LicenseFilterSet
    filter_backends = [CombinedFilterBackend, EnhancedSearchFilter, AdvancedOrderingFilter]
    search_fields = ['license_number', 'file_number', 'exporter__name']
    # Database columns only. `balance_cif` is a property, not a field, so
    # ordering by it raised FieldError (HTTP 500); live balance is not sortable.
    ordering_fields = ['license_date', 'license_expiry_date', 'exporter__name', 'license_number']
    # Default order when the request has no `ordering` param: closest expiry
    # first, then licence number. `id` is the final tie-breaker.
    ordering = ['license_expiry_date', 'license_number', 'id']

    @action(detail=True, methods=['patch'], url_path='individual-item-cif-override')
    def individual_item_cif_override(self, request, pk=None):
        """Atomically opt a licence into (or out of) per-import-item CIF.

        This deliberately accepts just one strictly typed field.  It uses the
        normal ViewSet permission/object lookup path and queues the existing
        durable replan mechanism only after a successful outer commit.
        """
        payload = IndividualItemCifOverrideSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        if set(request.data.keys()) != {"individual_item_cif_override"}:
            from rest_framework.exceptions import ValidationError
            raise ValidationError("Only individual_item_cif_override may be updated by this action.")

        with transaction.atomic():
            licence = LicenseDetailsModel.objects.select_for_update().get(pk=self.get_object().pk)
            old_value = licence.individual_item_cif_override
            new_value = payload.validated_data["individual_item_cif_override"]
            if old_value != new_value:
                licence.individual_item_cif_override = new_value
                licence.modified_by = request.user
                licence.save(update_fields=["individual_item_cif_override", "modified_by", "modified_on"])
                from apps.license.services.replan_requests import mark_license_replan_source_changed
                mark_license_replan_source_changed(
                    license_id=licence.pk,
                    reason="individual_item_cif_override_changed",
                    source_model="license.LicenseDetailsModel",
                    source_pk=licence.pk,
                )

        return Response({
            "id": licence.pk,
            "individual_item_cif_override": licence.individual_item_cif_override,
            "old_individual_item_cif_override": old_value,
        })

    def get_serializer_class(self):
        # List rows carry the accordion header's summary. Every other action keeps the detail shape.
        if self.action == 'list':
            return LicenseListSerializer
        return super().get_serializer_class()

    def paginate_queryset(self, queryset):
        """
        Stash the current page's license ids so `get_serializer_context()`
        can batch-compute LIVE balances for exactly this page (see
        `LicenseBalanceCalculator.calculate_balance_for_licenses` — a fixed
        4 queries total for the whole page, not 4×N). This is what makes it
        possible for the list view to show the SAME live Balance CIF as the
        detail view / License Overview without reintroducing the N+1 that
        the stored `LicenseBalance.balance_cif` column was originally
        caching to avoid.
        """
        page = super().paginate_queryset(queryset)
        self._live_balance_page_ids = [obj.id for obj in page] if page is not None else None
        return page

    def get_serializer_context(self):
        context = super().get_serializer_context()
        page_ids = getattr(self, '_live_balance_page_ids', None)
        if page_ids:
            from apps.license.services.balance_calculator import LicenseBalanceCalculator
            # Financial Ledger formula -- see `LicenseDetailsModel.
            # get_balance_cif`'s docstring; the list view must show the
            # SAME "Balance CIF" as everywhere else in the app.
            context['live_balance_map'] = LicenseBalanceCalculator.calculate_financial_balance_for_licenses(page_ids)
            # The accordion header's Available CIF: the canonical figure the licence workspace shows.
            from apps.license.services.licence_balance_report import available_cif_by_licence
            context['canonical_available_map'] = available_cif_by_licence(page_ids)

        # The generic MasterViewSet export action serializes each object while
        # building the workbook.  Supply the one batch-calculated map prepared
        # by that action so the exported Balance CIF is live and does not
        # recalculate it once per licence.
        export_balance_map = getattr(self, '_live_balance_export_map', None)
        if export_balance_map is not None:
            context['live_balance_map'] = export_balance_map
        return context

    def prepare_export_context(self, queryset):
        """Prepare live list values once for the generic XLSX/PDF exporter."""
        from apps.license.services.balance_calculator import LicenseBalanceCalculator

        license_ids = list(queryset.values_list('id', flat=True))
        self._live_balance_export_map = (
            LicenseBalanceCalculator.calculate_financial_balance_for_licenses(license_ids)
        )

    def list(self, request, *args, **kwargs):
        """Override list to add dynamic purchase_status default to metadata"""
        response = super().list(request, *args, **kwargs)

        # Add purchase_status default to metadata if present
        if isinstance(response.data, dict) and 'default_filters' in response.data:
            default_ps_ids = get_default_purchase_status_ids()
            if default_ps_ids:
                response.data['default_filters']['purchase_status'] = default_ps_ids

        return response

    def retrieve(self, request, *args, **kwargs):
        """
        Attach each import item's utilization-plan status (Original/Used/
        Remaining) to the detail response — the SAME `plan_status_for` the
        Allotment screen's Max-allotment cap and the Balance tab's Plan
        metrics read (see `nested_items` below and
        `apps/allotment/views_actions.py`). The Plan tab
        (`PlanningEditor.tsx`) builds its groups from THIS endpoint's
        `import_license`, not `nested_items` — without this, its own
        "Over Planned" badge compares the immutable Original Plan against
        current Available Qty, which trips every time a plan gets
        mostly/fully allotted even though nothing is actually wrong (Original
        was fully — or nearly fully — used as intended).

        Reimplemented rather than wrapping `super().retrieve()` so
        `get_object()` (and its permission check) runs only once. Bounded to
        one license's items per call — `list` (many licenses) is unaffected,
        since `import_license` is emptied there for performance (see the
        serializer's `is_list_view` branch).

        Also attaches a top-level `plan_utilization` key: one row per
        planning-item GROUP (see `plan_utilization_rows`) rather than one row
        per raw `import_license` entry — e.g. three S.No rows that share a
        description merge into a single row whose `serials` list carries all
        three. Purely additive: `import_license` keeps its existing raw,
        ungrouped shape (other UI — the license edit/MasterForm — reads it as
        the literal DB rows for CRUD).
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        data = serializer.data

        import_rows = data.get('import_license') if isinstance(data, dict) else None
        if import_rows:
            from apps.license.services.plan_enforcement import plan_status_for_items
            items_by_id = {it.id: it for it in instance.import_license.all()}
            status_by_id = plan_status_for_items(items_by_id.values())
            for row in import_rows:
                item = items_by_id.get(row.get('id'))
                if item is None:
                    continue
                plan_status = status_by_id.get(item.id)
                row['has_plan'] = plan_status is not None
                if plan_status is not None:
                    row['original_planned_quantity'] = str(plan_status['original_quantity'])
                    row['used_planned_quantity'] = str(plan_status['used_quantity'])
                    row['remaining_planned_quantity'] = str(plan_status['remaining_quantity'])
                    row['original_planned_cif_fc'] = str(plan_status['original_cif_fc'])
                    row['used_planned_cif_fc'] = str(plan_status['used_cif_fc'])
                    row['remaining_planned_cif_fc'] = str(plan_status['remaining_cif_fc'])

        from apps.license.services.plan_utilization import plan_utilization_rows
        from apps.license.services.license_plan_presentation import LicensePlanPresentationService
        from apps.license.serializers.license import LicensePlanPresentationSerializer

        _decimal_fields = (
            'available_quantity', 'total_quantity', 'balance_cif_fc',
            'original_quantity', 'used_quantity', 'remaining_quantity',
            'original_cif_fc', 'used_cif_fc', 'remaining_cif_fc',
            'unit_conversion', 'available_qty', 'planned_qty',
            'effective_available_quantity', 'effective_available_qty',
            'license_balance_cif', 'effective_license_balance_cif',
            'allocated_qty', 'consumed_qty', 'remaining_qty',
            'shortage_qty', 'excess_qty',
            'total_qty', 'total_utilized_qty', 'balance_qty',
            'over_utilized_qty', 'over_planned_qty',
        )
        data['plan_utilization'] = [
            {**row, **{f: str(row[f]) for f in _decimal_fields if f in row}}
            for row in plan_utilization_rows(instance)
        ]
        from apps.license.services.planning_tolerances import effective_planning_balance_cif
        # The licence's canonical available CIF is the one balance every planning figure starts from.
        from apps.license.services.licence_balance_report import build_licence_balance_reports
        canonical_available = build_licence_balance_reports([instance.pk], include_legacy=False)[instance.pk].summary_cif.get('available')
        raw_planning_balance = Decimal(canonical_available) if canonical_available is not None else Decimal('0')
        effective_planning_balance = effective_planning_balance_cif(raw_planning_balance)
        data['planning_balance_cif'] = {
            'raw_balance_cif': str(raw_planning_balance),
            'effective_balance_cif': str(effective_planning_balance),
            'balance_cif_ignored_by_tolerance': raw_planning_balance != effective_planning_balance,
        }
        # Canonical gross-entitlement reconciliation for every planning
        # consumer.  Never derive "available" by subtracting only plans: BOE
        # and unlinked allotment CIF are actual historical utilization.
        from apps.license.models import LicenseExportItemModel, LicenseItemPlan
        from apps.license.services.planning_usage_reconciliation import aggregate_license_usage
        usage = aggregate_license_usage(instance.pk)
        actual_boe_cif = sum((v['boe_used_cif'] for v in usage['mapped'].values()), Decimal('0'))
        actual_allotment_cif = sum((v['unlinked_allotment_cif'] for v in usage['mapped'].values()), Decimal('0'))
        actual_boe_cif += sum((r['cif_fc'] for r in usage['unmapped_usage'] if r['source'] == 'BOE'), Decimal('0'))
        actual_allotment_cif += sum((r['cif_fc'] for r in usage['unmapped_usage'] if r['source'] == 'ALLOTMENT'), Decimal('0'))
        gross_cif = sum((Decimal(v or 0) for v in LicenseExportItemModel.objects.filter(license=instance).values_list('cif_fc', flat=True)), Decimal('0'))
        # Leaf effective values are the one canonical planning aggregate.  A
        # percentage line can have a calculated CIF-cap adjustment without a
        # quantity change, so summing persisted candidate CIF is incorrect.
        from apps.license.services.planning_usage_reconciliation import reconcile_license_plans
        reconciliation = reconcile_license_plans(instance.pk)
        # Replaced/superseded plans are an audit trail, not current planning
        # capacity.  Match the active-plan predicate used by the plan list and
        # reconciliation so historical rows can never inflate this summary.
        plan_rows = LicenseItemPlan.objects.filter(
            license=instance,
            is_active=True,
            is_deleted=False,
            is_cancelled=False,
        ).values_list('id', 'planned_cif_fc')
        new_plan_cif = sum((
            Decimal(str(reconciliation['plans'].get(plan_id, {}).get('adjusted_planned_cif', planned_cif or 0)))
            for plan_id, planned_cif in plan_rows
        ), Decimal('0'))
        accounted_cif = actual_boe_cif + actual_allotment_cif + new_plan_cif
        # Canonical available CIF already deducts BOE and allotment utilisation, so the planning balance is the
        # canonical figure less only the new planned CIF. Subtracting BOE and allotment again would double count.
        actual_balance_cif = raw_planning_balance
        final_balance_cif = raw_planning_balance - new_plan_cif
        data['operational_reconciliation'] = {
            'cif_balance_basis': 'CANONICAL_AVAILABLE', 'license_total_cif': str(gross_cif),
            'actual_boe_cif': str(actual_boe_cif), 'actual_allotment_cif': str(actual_allotment_cif),
            'total_actual_cif': str(actual_boe_cif + actual_allotment_cif),
            # Opening pool for new planning; it deliberately excludes all
            # future/planned rows so actual CIF is never deducted twice.
            'actual_balance_cif': str(actual_balance_cif),
            'new_reconciled_planned_cif': str(new_plan_cif), 'new_planned_cif': str(new_plan_cif),
            'total_accounted_cif': str(accounted_cif), 'final_balance_cif': str(final_balance_cif),
            'balance_cif': str(final_balance_cif),
            'overdrawn_cif': str(max(-final_balance_cif, Decimal('0'))),
            'aggregation_level': 'leaf LicenseItemPlan rows; parent groups are not added again',
        }

        # Attach canonical license plan presentation (single source of truth)
        try:
            presentation = LicensePlanPresentationService.get_license_plan(instance.id)
            serializer = LicensePlanPresentationSerializer(presentation)
            data['license_plan_presentation'] = serializer.data
        except Exception as e:
            logger.warning(
                f"Failed to load license plan presentation for license {instance.id}: {e}",
                exc_info=True
            )
            # Gracefully degrade: omit the field if service fails
            data['license_plan_presentation'] = None

        return Response(data)

    @action(detail=True, methods=['get'], url_path='check-validity')
    def check_validity(self, request, pk=None):
        """Return the current, non-mutating validity state for a licence.

        The frontend's ``checkLicenseValidity`` client has always called this
        route.  Validity is intentionally calculated from today's date instead
        of trusting the denormalized ``flags.is_expired`` value, which may be
        refreshed asynchronously.
        """
        license_obj = self.get_object()
        today = timezone.localdate()
        expiry_date = license_obj.license_expiry_date
        is_expired = expiry_date is not None and expiry_date < today
        is_active = license_obj.is_active
        is_valid = is_active and not is_expired

        return Response({
            'license_id': license_obj.pk,
            'license_number': license_obj.license_number,
            'is_valid': is_valid,
            'is_active': is_active,
            'is_expired': is_expired,
            'license_expiry_date': expiry_date,
            'days_until_expiry': (expiry_date - today).days if expiry_date else None,
        })

    def get_object(self):
        """
        Override to support lookup by either pk (ID) or license_number.
        """
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        filter_kwargs = {self.lookup_field: self.kwargs[lookup_url_kwarg]}

        # Try to get by primary key first (if it's a number)
        lookup_value = self.kwargs[lookup_url_kwarg]
        try:
            # If lookup value is numeric, try ID first
            if lookup_value.isdigit():
                filter_kwargs = {'pk': int(lookup_value)}
                obj = self.get_queryset().get(**filter_kwargs)
            else:
                # Otherwise lookup by license number
                filter_kwargs = {'license_number': lookup_value}
                obj = self.get_queryset().get(**filter_kwargs)
        except (ValueError, self.queryset.model.DoesNotExist):
            # If ID lookup fails, try license_number
            try:
                filter_kwargs = {'license_number': lookup_value}
                obj = self.get_queryset().get(**filter_kwargs)
            except self.queryset.model.DoesNotExist:
                from django.http import Http404
                raise Http404(f"License with identifier '{lookup_value}' not found")

        # May raise a permission denied
        self.check_object_permissions(self.request, obj)
        return obj

    def update(self, request, *args, **kwargs):
        """Override to log incoming request data."""
        import logging
        logger = logging.getLogger(__name__)
        logger.info("=" * 50)
        logger.info("ViewSet.update called")
        logger.info("request.data type: %s", type(request.data))
        logger.info("request.data keys: %s", list(request.data.keys()) if hasattr(request.data, 'keys') else 'N/A')

        # Log license_documents from request.data
        if 'license_documents' in request.data:
            docs = request.data.getlist('license_documents') if hasattr(request.data, 'getlist') else request.data.get(
                'license_documents')
            logger.info("license_documents in request.data: %s", docs)
        else:
            logger.info("license_documents NOT in request.data")

        # Log all keys that contain 'license_documents'
        if hasattr(request.data, 'keys'):
            doc_keys = [k for k in request.data.keys() if 'license_documents' in k]
            logger.info("Keys containing 'license_documents': %s", doc_keys)
            for key in doc_keys[:5]:  # Log first 5
                logger.info("  %s = %s", key, request.data.get(key))

        return super().update(request, *args, **kwargs)

    def get_queryset(self):
        """
        Override to add performance optimizations with select_related and prefetch_related.
        For detail view (retrieve/update/partial_update), don't apply default filters so expired licenses can be edited.
        """
        # For detail view actions, skip default filters by temporarily clearing them
        # Detail actions must resolve a licence by its ID even when it is
        # expired or hidden from the default list view.  Their own services
        # preserve the status; clearing list filters here does not reactivate
        # a licence or relax any operational workflow's validation.
        skip_default_filters = self.action in [
            'retrieve', 'update', 'partial_update', 'destroy', 'nested_items',
            'item_usage', 'balance_ledger', 'balance_pdf', 'balance_excel', 'auto_plan',
            'overview_summary', 'overview_boes', 'overview_allotments',
            'overview_items', 'overview_invoice_ledger', 'plan_utilization',
            # Validity must report an expired or inactive licence's current
            # state.  Object permissions still apply after lookup.
            'check_validity',
            'hide_boe', 'restore_boe', 'hide_boe_bulk', 'restore_boe_bulk',
        ]

        if skip_default_filters:
            # Save original default filters
            original_default_filters = getattr(self, 'default_filters', {})
            # Temporarily clear default filters
            self.default_filters = {}

        qs = super().get_queryset()

        # Restore original default filters if they were cleared
        if skip_default_filters:
            self.default_filters = original_default_filters

        # Add select_related for ForeignKey fields to avoid N+1 queries.
        # current_owner now lives on LicenseOwnership sub-table; balance and flags
        # are also sub-tables we want pre-joined so the back-compat @property
        # accessors don't issue separate queries.
        qs = qs.select_related(
            'exporter', 'port', 'purchase_status',
            'balance', 'flags', 'ownership', 'ownership__current_owner', 'notes',
        )

        # Flag licenses that have a manual utilization plan (drives list colour) and
        # which document types they carry — annotated so the list serializer doesn't
        # fire an .exists() query per row (was 2 extra queries/row for has_tl/has_copy).
        from django.db.models import Exists, OuterRef
        from apps.license.models import LicenseItemPlan, LicenseDocumentModel
        qs = qs.annotate(
            _has_manual_plan=Exists(LicenseItemPlan.objects.filter(license=OuterRef('pk'))),
            _has_tl=Exists(LicenseDocumentModel.objects.filter(license=OuterRef('pk'), type='TRANSFER LETTER')),
            _has_copy=Exists(LicenseDocumentModel.objects.filter(license=OuterRef('pk'), type='LICENSE COPY')),
        )

        # Only prefetch deep nested items for detail view (single object).
        # For list view, those relations cause massive performance issues,
        # but license_documents is lightweight (0–3 rows per license) and
        # must be prefetched so the serializer can build the merge-link stub
        # without firing 2 extra queries per row (.exists() + .all()[:1]).
        if self.action == 'retrieve':
            # Prefetch nested relationships for detail view only
            qs = qs.prefetch_related(
                'export_license',
                'export_license__norm_class',
                'import_license',
                'import_license__hs_code',
                'import_license__items',
                'import_license__items__sion_norm_class',
                'import_license__allotment_details',
                'import_license__item_details',
                'license_documents',
            )
        else:
            # List view: prefetch only license_documents so the serializer can
            # read the prefetch cache (zero per-row queries) instead of calling
            # .exists() + .all()[:1] which fired 2 queries per row.
            qs = qs.prefetch_related('license_documents')
            if self.action == 'list':
                # The row serializer also reads each licence's export-line norm
                # classes (get_norm_class) and its transfers (latest_transfer,
                # which reads `transfers_for_list` in the same order when set).
                # Scoped to list: other actions reuse this queryset and their
                # query budgets are asserted elsewhere.
                from apps.license.models import LicenseTransferModel
                qs = qs.prefetch_related(
                    'export_license__norm_class',
                    Prefetch(
                        'transfers',
                        queryset=LicenseTransferModel.objects.order_by('-transfer_date', '-id'),
                        to_attr='transfers_for_list',
                    ),
                )

        return qs

    # Id-valued filters: one id, or a comma-separated list (also `name[]`).
    _ID_FILTER_PARAMS = frozenset({
        'exporter', 'exclude_exporter', 'port', 'exclude_port',
        'purchase_status', 'export_license__norm_class',
    })
    # Date bounds read by the generic date_range branch, in every spelling it accepts.
    _DATE_BOUND_PARAMS = frozenset(
        f'{field}{suffix}'
        for field in ('license_date', 'license_expiry_date')
        for suffix in ('_from', '_to', '_from[]', '_to[]', '__gte', '__lte')
    )
    # Live balance bounds, read in apply_advanced_filters below.
    _LIVE_BALANCE_PARAMS = frozenset({'balance__balance_cif_min', 'balance__balance_cif_max'})

    @staticmethod
    def _parse_finite_decimal(raw):
        """Decimal converter for the live balance bounds; NaN and Infinity are rejected."""
        try:
            value = Decimal(raw)
        except ArithmeticError:  # Decimal('abc') raises InvalidOperation
            raise DjangoValidationError('Enter a finite decimal number.')
        if not value.is_finite():
            raise DjangoValidationError('Enter a finite decimal number.')
        return value

    @staticmethod
    def _boolean_converter(field):
        """Accept the yes/no and 0/1 spellings the generic filter maps, else the field's own rule."""
        def convert(raw):
            if raw.lower() not in ('true', '1', 'yes', 'false', '0', 'no'):
                field.to_python(raw)
        return convert

    def _validate_filter_params(self, params):
        """Reject malformed id, date and balance query params with a field-level 400.

        Each value goes through the same Django converter the ORM would apply,
        so every value that filtered correctly before still does. Values the
        ORM could not convert (``exporter=abc``, ``license_date__gte=2026-13-45``,
        ``balance__balance_cif_min=abc``) used to surface as a 500 and are now
        reported under their own parameter name. Empty values are ignored, as
        the generic filters already ignore them.

        Splitting follows the generic filters: a comma splits a value, while an
        ``name[]`` array element is taken whole.
        """
        config_keys = set(self.filter_config)
        generic_fields = {
            f.name: f for f in LicenseDetailsModel._meta.concrete_fields
            if isinstance(f, (ForeignKey, IntegerField, DecimalField, DateField, BooleanField))
            and f.name not in config_keys
        }
        errors = {}
        for name, raw_values in params.lists():
            base = name[:-2] if name.endswith('[]') else name
            is_array = name != base
            if base in self._ID_FILTER_PARAMS:
                converter = IntegerField().to_python
            elif name in self._DATE_BOUND_PARAMS:
                converter = DateField().to_python
            elif name in self._LIVE_BALANCE_PARAMS:
                converter = self._parse_finite_decimal
            elif name in generic_fields:
                field = generic_fields[name]
                converter = (self._boolean_converter(field) if isinstance(field, BooleanField)
                             else field.to_python)
            else:
                continue

            for raw in raw_values:
                if is_array and base in self._ID_FILTER_PARAMS:
                    values = [raw]
                elif not raw:
                    continue
                elif ',' in raw and name not in self._DATE_BOUND_PARAMS and name not in self._LIVE_BALANCE_PARAMS:
                    values = [v.strip() for v in raw.split(',') if v.strip()]
                else:
                    values = [raw]
                for value in values:
                    try:
                        converter(value)
                    except DjangoValidationError as exc:
                        errors.setdefault(name, []).extend(exc.messages)

        if errors:
            raise ValidationError(errors)

    def apply_advanced_filters(self, qs, params, filter_config):
        """Override to add custom logic for is_expired and is_null with default values."""
        from datetime import date
        from decimal import Decimal
        from django.db.models import Q

        self._validate_filter_params(params)

        # Get default filters
        default_filters = getattr(self, "default_filters", {})

        # The current filter schema exposes the child-table paths
        # (``flags__is_expired`` / ``flags__is_null``); older callers use the
        # short aliases.  Both must use the live calculations below rather
        # than falling through to MasterViewSet's stale stored-flag filter.
        is_expired_value = params.get('is_expired', params.get('flags__is_expired'))

        # Special case: if user explicitly selects "all", don't apply any filter
        if is_expired_value and is_expired_value.lower() == "all":
            is_expired_value = None
        elif is_expired_value is None or is_expired_value == "":
            # Apply default if no value provided
            is_expired_value = default_filters.get('is_expired')

        if is_expired_value is not None and is_expired_value != "":
            today = date.today()
            if is_expired_value in ("True", "true", "1", True):
                # Show expired licenses: expiry_date < today
                qs = qs.filter(license_expiry_date__lt=today)
            elif is_expired_value in ("False", "false", "0", False):
                # Show non-expired licenses: expiry_date >= today OR null
                qs = qs.filter(Q(license_expiry_date__gte=today) | Q(license_expiry_date__isnull=True))

        # Handle is_null filter - apply default if not provided
        is_null_value = params.get('is_null', params.get('flags__is_null'))

        # Special case: if user explicitly selects "all", don't apply any filter
        if is_null_value and is_null_value.lower() == "all":
            is_null_value = None
        elif is_null_value is None or is_null_value == "":
            # Apply default if no value provided
            is_null_value = default_filters.get('is_null')

        if is_null_value is not None and is_null_value != "":
            # BL-LEDGER-02: `balance__balance_cif` is a denormalized cache
            # with no signal on reconciliation-allocation changes, so it can
            # be stale. Resolve against the LIVE, batched-computed balance
            # instead of filtering the DB column directly (same fix already
            # applied to active_dfia_report.py / license_report.py).
            from apps.license.services.balance_calculator import LicenseBalanceCalculator
            candidate_ids = list(qs.values_list('id', flat=True))
            live_balance_by_license = LicenseBalanceCalculator.calculate_financial_balance_for_licenses(candidate_ids)
            if is_null_value in ("True", "true", "1", True):
                # Show null licenses: live balance < 200
                matching_ids = [i for i in candidate_ids if live_balance_by_license.get(i, Decimal('0')) < 200]
                qs = qs.filter(id__in=matching_ids)
            elif is_null_value in ("False", "false", "0", False):
                # Show non-null licenses: live balance >= 200
                matching_ids = [i for i in candidate_ids if live_balance_by_license.get(i, Decimal('0')) >= 200]
                qs = qs.filter(id__in=matching_ids)

        # `is_active` is the administrative flag (`flags.is_active`). The
        # dashboard's Active link uses it. Absent or "all" applies no filter.
        is_active_value = params.get('is_active', '').lower()
        if is_active_value in ("true", "1"):
            qs = qs.filter(Q(flags__is_active=True) | Q(flags__isnull=True))
        elif is_active_value in ("false", "0"):
            qs = qs.filter(flags__is_active=False)

        # Handle is_planned filter - based on whether the license has a manual
        # utilization plan (i.e. at least one LicenseItemPlan row). This mirrors
        # the `is_manually_planned` flag surfaced in the serializer/list UI.
        # The `_has_manual_plan` annotation is added later in get_queryset (after
        # this method runs), so we filter with an Exists subquery here instead.
        is_planned_value = params.get('is_planned')

        # Special case: if user explicitly selects "all", don't apply any filter
        if is_planned_value and is_planned_value.lower() == "all":
            is_planned_value = None

        if is_planned_value is not None and is_planned_value != "":
            from django.db.models import Exists, OuterRef
            from apps.license.models import LicenseItemPlan
            has_manual_plan = Exists(LicenseItemPlan.objects.filter(license=OuterRef('pk')))
            if is_planned_value in ("True", "true", "1", True):
                # Show planned licenses: has at least one item plan
                qs = qs.filter(has_manual_plan)
            elif is_planned_value in ("False", "false", "0", False):
                # Show licenses that are not planned: no item plans
                qs = qs.filter(~has_manual_plan)

        # Handle the generic balance__balance_cif range filter (type "range"
        # in the base viewset config, params balance__balance_cif_min/_max)
        # live too — same stale-cache reasoning as is_null above. Resolved
        # here, before delegating to super(), so the parent's generic range
        # handler never sees these params and never filters the cached
        # column directly.
        balance_min = params.get('balance__balance_cif_min')
        balance_max = params.get('balance__balance_cif_max')
        if balance_min or balance_max:
            from apps.license.services.balance_calculator import LicenseBalanceCalculator
            candidate_ids = list(qs.values_list('id', flat=True))
            live_balance_by_license = LicenseBalanceCalculator.calculate_financial_balance_for_licenses(candidate_ids)
            matching_ids = candidate_ids
            if balance_min:
                min_dec = Decimal(str(balance_min))
                matching_ids = [i for i in matching_ids if live_balance_by_license.get(i, Decimal('0')) >= min_dec]
            if balance_max:
                max_dec = Decimal(str(balance_max))
                matching_ids = [i for i in matching_ids if live_balance_by_license.get(i, Decimal('0')) <= max_dec]
            qs = qs.filter(id__in=matching_ids)

        # Call parent method for remaining filters (exclude is_expired and is_null)
        # Create a new QueryDict-like object
        from django.http import QueryDict
        filtered_params = QueryDict(mutable=True)
        custom_filter_keys = (
            'is_expired', 'flags__is_expired', 'is_null', 'flags__is_null',
            'is_planned', 'balance__balance_cif_min', 'balance__balance_cif_max',
        )
        for key, value in params.items():
            if key not in custom_filter_keys:
                # Handle array format for purchase_status
                if key == 'purchase_status[]':
                    # Frontend sends purchase_status[] for multi-select
                    for val in params.getlist(key):
                        filtered_params.appendlist('purchase_status[]', val)
                else:
                    filtered_params[key] = value

        # Create a copy of filter_config without custom-handled fields
        filtered_config = {
            k: v for k, v in filter_config.items()
            if k not in ('is_expired', 'flags__is_expired', 'is_null', 'flags__is_null', 'is_planned')
        }

        # Call parent method with filtered params and config
        qs = super().apply_advanced_filters(qs, filtered_params, filtered_config)

        return qs

    @action(detail=True, methods=['get'])
    def nested_items(self, request, pk=None):
        """
        Fetch nested items for a specific license on demand.
        This endpoint is called lazily when user expands a license row.
        """
        license_obj = self.get_object()

        import_items = list(license_obj.import_license.all())
        # Batch the live available_value/balance_cif_fc for this licence's
        # items in one shot instead of falling back to the per-item live
        # property N times — see `available_value_bulk_map`'s docstring.
        from apps.license.services.condition_pool import available_value_bulk_map
        available_value_map = available_value_bulk_map(import_items)
        import_data = LicenseImportItemSerializer(
            import_items, many=True,
            context={'request': request, 'available_value_map': available_value_map}
        ).data

        # Attach each item's utilization-plan status (Original/Used/Remaining)
        # — the SAME `plan_status_for` the Allotment screen's Max-allotment
        # cap reads (see apps/allotment/views_actions.py::available_licenses),
        # so the Balance tab's "Plan" figures can never disagree with what's
        # actually enforced there. Absent (has_plan=False) for items with no
        # LicenseItemPlan rows — unconstrained, nothing to show.
        from apps.license.services.plan_enforcement import plan_status_for
        for row, item in zip(import_data, import_items):
            plan_status = plan_status_for(item)
            row['has_plan'] = plan_status is not None
            if plan_status is not None:
                row['original_planned_quantity'] = str(plan_status['original_quantity'])
                row['used_planned_quantity'] = str(plan_status['used_quantity'])
                row['remaining_planned_quantity'] = str(plan_status['remaining_quantity'])
                row['original_planned_cif_fc'] = str(plan_status['original_cif_fc'])
                row['used_planned_cif_fc'] = str(plan_status['used_cif_fc'])
                row['remaining_planned_cif_fc'] = str(plan_status['remaining_cif_fc'])

        return Response({
            'export_license': LicenseExportItemSerializer(license_obj.export_license.all(), many=True).data,
            'import_license': import_data,
            'license_documents': LicenseDocumentSerializer(license_obj.license_documents.all(), many=True).data
        })

    @action(detail=True, methods=['get'], url_path='item-usage')
    def item_usage(self, request, pk=None):
        """
        Get real-time usage details for a specific license item (export or import).
        Shows where the item is used in BOEs and Allotments.

        Query params:
        - item_id: ID of the export or import item
        - type: 'export' or 'import'
        """
        from apps.license.models import LicenseImportItemsModel
        from apps.license.services.item_usage import get_item_usage

        self.get_object()
        item_id = request.query_params.get('item_id')
        item_type = request.query_params.get('type')

        if not item_id or not item_type:
            return Response({'error': 'item_id and type parameters are required'}, status=400)

        boes = []
        allotments = []

        if item_type == 'import':
            try:
                import_item = LicenseImportItemsModel.objects.get(pk=item_id)
            except LicenseImportItemsModel.DoesNotExist:
                return Response({'boes': [], 'allotments': []})

            usage = get_item_usage(import_item)

            for detail in usage['boes']:
                boe = detail.bill_of_entry
                boes.append({
                    'id': boe.id if boe else None,
                    'bill_of_entry_number': boe.bill_of_entry_number if boe else None,
                    'date': boe.bill_of_entry_date if boe else None,
                    'port': boe.port.name if (boe and boe.port) else None,
                    'company': boe.company.name if (boe and boe.company) else None,
                    'quantity': float(detail.qty),
                    'cif_fc': float(detail.cif_fc),
                    'cif_inr': float(detail.cif_inr)
                })

            for item in usage['allotments']:
                allotment = item.allotment
                allotments.append({
                    'id': allotment.id if allotment else None,
                    'allotment_number': (allotment.invoice if allotment else None) or f"Allotment #{allotment.id if allotment else ''}",
                    'company': allotment.company.name if (allotment and allotment.company) else None,
                    'quantity': float(item.qty),
                    'cif_fc': float(item.cif_fc),
                    'cif_inr': float(item.cif_inr)
                })

        elif item_type == 'export':
            # For export items, check allotments (AllotmentItems might link to export items)
            # This depends on your data model structure
            pass

        return Response({
            'boes': boes,
            'allotments': allotments
        })

    @action(detail=True, methods=['get'], url_path='balance-pdf')
    def balance_pdf(self, request, pk=None):
        """Generate PDF report for license balance details with all BOEs and Allotments.

        `?show_hidden=true` matches the on-screen "show hidden BOE" toggle —
        see `LicenseBalanceLedgerBuilder.build_customs_ledger`'s docstring.
        """
        license_obj = self.get_object()
        show_hidden = request.query_params.get('show_hidden', '').lower() in ('1', 'true', 'yes')
        from apps.license.services.exporters.license_balance_pdf import build_balance_pdf_response

        try:
            return build_balance_pdf_response(license_obj, request, show_hidden=show_hidden)
        except Exception:
            logger.exception(
                "Balance PDF generation failed",
                extra={
                    "license_id": license_obj.id,
                    "license_number": license_obj.license_number,
                    "user_id": getattr(request.user, "id", None),
                    "operation": "balance_pdf_generation",
                },
            )
            return Response(
                {
                    "code": "balance_pdf_generation_failed",
                    "detail": "Unable to generate Balance PDF. Please try again.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=['post'], url_path='bulk-balance-excel')
    def bulk_balance_excel(self, request):
        """Generate a multi-sheet Excel with one sheet per license."""
        from apps.license.services.exporters.license_balance_excel import build_bulk_balance_excel
        return build_bulk_balance_excel(request)

    @action(detail=True, methods=['get'], url_path='balance-excel')
    def balance_excel(self, request, pk=None):
        """Generate Excel summary report (BOE & Allotments + Balance Quantity).

        `?show_hidden=true` matches the on-screen "show hidden BOE" toggle —
        see `LicenseBalanceLedgerBuilder.build_customs_ledger`'s docstring.
        """
        from apps.license.services.exporters.license_balance_excel import build_balance_excel
        license_obj = self.get_object()
        show_hidden = request.query_params.get('show_hidden', '').lower() in ('1', 'true', 'yes')
        return build_balance_excel(license_obj, show_hidden=show_hidden)

    @action(detail=True, methods=['get'], url_path='balance-excel-unused')
    def balance_excel_unused(self, request, pk=None):
        """Original full balance Excel — kept for reference, no longer exposed."""
        from apps.license.services.exporters.license_balance_excel import build_balance_excel_unused
        license_obj = self.get_object()
        return build_balance_excel_unused(license_obj)

    @action(detail=True, methods=['post'], url_path='auto-plan')
    def auto_plan(self, request, pk=None):
        """Synchronously and atomically replace this licence's generated plan.

        This is deliberately the one interactive planning endpoint that is
        synchronous.  The SION-wide and source-change replan routes keep
        their durable-worker semantics; a user pressing Auto Plan needs an
        authoritative committed result before the request returns.
        """
        # Keep the public field strict and backwards compatible.  Manual Auto
        # Plan has historically been forced regardless of the supplied value;
        # accepting ``false`` therefore does not turn this into a cache hit.
        force = request.data.get("force", True)
        if not isinstance(force, bool):
            return Response(
                {"force": ["Must be a boolean."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # get_object performs the viewset's existing object-level permission
        # checks.  Re-fetch it under a row lock before resolving SIONs, so two
        # simultaneous button clicks cannot interleave destructive REPLACE
        # writes.  The nested planner transactions become savepoints and the
        # whole operation rolls back on any unexpected failure.
        requested_license = self.get_object()
        from apps.license.services.sion_rule_engine import SionRulePlanningService
        from apps.license.views.sion_planning_rule import SionPlanningRuleViewSet
        with transaction.atomic():
            license_obj = LicenseDetailsModel.objects.select_for_update().get(pk=requested_license.pk)
            _, sion_ids = SionPlanningRuleViewSet._resolve_sions_for_license(license_obj.pk)
            results = [
                SionRulePlanningService.plan_sion(
                    sion_id,
                    license_ids=[license_obj.pk],
                    mode="ALL",
                    force_plan=True,
                )
                for sion_id in sion_ids
            ]
        return Response({
            "license_id": license_obj.pk,
            "license_number": license_obj.license_number,
            "planning_state": "COMPLETED",
            "force": True,
            "write_results": sum(len(result.get("write_results", [])) for result in results),
            "rules_executed": [rule for result in results for rule in result.get("rules_executed", [])],
            "message": "Licence planning has completed.",
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='merged-documents')
    def merged_documents(self, request, pk=None):
        """
        Merge all license documents (LICENSE COPY + TRANSFER LETTER) into one PDF.
        Converts images to PDF if needed.
        """
        from django.http import FileResponse, HttpResponse
        import io
        import os
        import logging

        logger = logging.getLogger(__name__)
        try:
            license_obj = LicenseDetailsModel.objects.get(pk=pk)
        except LicenseDetailsModel.DoesNotExist:
            from django.http import HttpResponse
            return HttpResponse("License not found", status=404)
        documents = license_obj.license_documents.all()

        if not documents.exists():
            return HttpResponse("No documents found for this license", status=404)

        # Check if required libraries are installed
        try:
            from pypdf import PdfWriter, PdfReader
            from PIL import Image
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.utils import ImageReader
        except ImportError as e:
            return HttpResponse(f"Missing required library: {str(e)}. Please install pypdf and Pillow.", status=500)

        try:
            writer = PdfWriter()

            # Sort documents: TRANSFER LETTER first, then LICENSE COPY, then OTHER
            type_order = {'TRANSFER LETTER': 0, 'LICENSE COPY': 1, 'OTHER': 2}
            sorted_documents = sorted(documents, key=lambda doc: type_order.get(doc.type, 3))

            for doc in sorted_documents:
                if not doc.file:
                    continue

                # Use Django storage API so this works for local, S3, or any backend
                storage = doc.file.storage
                file_name = doc.file.name

                if not storage.exists(file_name):
                    logger.warning(f"File not found in storage: {file_name}")
                    continue

                file_ext = os.path.splitext(file_name)[1].lower()

                if file_ext == '.pdf':
                    # Add PDF directly
                    with storage.open(file_name, 'rb') as f:
                        reader = PdfReader(f)
                        for page in reader.pages:
                            writer.add_page(page)
                    logger.info(f"Added PDF: {file_name}")
                elif file_ext in ['.doc', '.docx']:
                    # Convert DOCX/DOC to PDF
                    try:
                        from docx import Document
                        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
                        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                        from reportlab.lib.pagesizes import A4
                        from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT
                        import tempfile

                        # Read DOCX content using storage API
                        with storage.open(file_name, 'rb') as docx_f:
                            doc_bytes = io.BytesIO(docx_f.read())
                        doc = Document(doc_bytes)

                        # Create temporary PDF file
                        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_pdf:
                            tmp_pdf_path = tmp_pdf.name

                        # Create PDF
                        pdf = SimpleDocTemplate(tmp_pdf_path, pagesize=A4)
                        story = []
                        styles = getSampleStyleSheet()

                        # Add custom style
                        normal_style = ParagraphStyle(
                            'CustomNormal',
                            parent=styles['Normal'],
                            fontSize=10,
                            leading=14,
                            alignment=TA_LEFT
                        )

                        # Convert paragraphs to PDF
                        for paragraph in doc.paragraphs:
                            if paragraph.text.strip():
                                # Escape special characters for reportlab
                                text = paragraph.text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                                p = Paragraph(text, normal_style)
                                story.append(p)
                                story.append(Spacer(1, 6))

                        # Build PDF
                        pdf.build(story)

                        # Add converted PDF pages to writer
                        with open(tmp_pdf_path, 'rb') as tmp_f:
                            tmp_reader = PdfReader(tmp_f)
                            for page in tmp_reader.pages:
                                writer.add_page(page)
                        logger.info(f"Converted and added DOCX/DOC: {file_name}")

                        # Clean up temp file
                        try:
                            os.remove(tmp_pdf_path)
                        except OSError:
                            pass

                    except Exception as e:
                        logger.error(f"Error converting DOCX file {file_name}: {str(e)}")
                        continue
                elif file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
                    # Convert image to PDF
                    with storage.open(file_name, 'rb') as img_f:
                        img = Image.open(io.BytesIO(img_f.read()))

                    # Convert to RGB if necessary
                    if img.mode != 'RGB':
                        img = img.convert('RGB')

                    # Create PDF from image using ReportLab
                    img_buffer = io.BytesIO()
                    img_width, img_height = img.size

                    # Use A4 size for PDF
                    pdf_canvas = canvas.Canvas(img_buffer, pagesize=A4)
                    a4_width, a4_height = A4

                    # Calculate scaling to fit image on A4 page
                    scale = min(a4_width / img_width, a4_height / img_height)
                    new_width = img_width * scale
                    new_height = img_height * scale

                    # Center image on page
                    x = (a4_width - new_width) / 2
                    y = (a4_height - new_height) / 2

                    # Use ImageReader for PIL Image object
                    img_reader = ImageReader(img)
                    pdf_canvas.drawImage(img_reader, x, y, width=new_width, height=new_height)
                    pdf_canvas.save()

                    # Add image-converted PDF pages to writer
                    img_buffer.seek(0)
                    img_pdf_reader = PdfReader(img_buffer)
                    for page in img_pdf_reader.pages:
                        writer.add_page(page)
                    logger.info(f"Converted and added image: {file_name}")

            if len(writer.pages) == 0:
                return HttpResponse("Document files are missing from the server storage. The files may not have been synced to this environment.", status=404)

            # Write merged PDF to buffer
            output_buffer = io.BytesIO()
            writer.write(output_buffer)
            output_buffer.seek(0)

            # Return merged PDF
            import traceback as tb
            pdf_bytes = output_buffer.getvalue()
            response = HttpResponse(pdf_bytes, content_type='application/pdf')
            response['Content-Disposition'] = f'inline; filename="license_{license_obj.license_number}_documents.pdf"'
            return response

        except Exception as e:
            import traceback as tb
            full_trace = tb.format_exc()
            logger.error(f"Error merging documents: {full_trace}")
            return HttpResponse(f"Error: {str(e)}\n\n{full_trace}", status=500, content_type='text/plain')

    @action(detail=True, methods=['post'], url_path='documents')
    def documents(self, request, pk=None):
        """
        Upload and save license documents.
        POST /licenses/{id}/documents/

        Accepts multipart/form-data with:
        - file: The document file (PDF, image, etc.)
        - type: Document type (LICENSE COPY, TRANSFER LETTER, OTHER)
        """
        from apps.license.models import LicenseDocumentModel

        try:
            license_obj = LicenseDetailsModel.objects.get(pk=pk)
        except LicenseDetailsModel.DoesNotExist:
            return Response(
                {"error": "License not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Get uploaded file and document type
        uploaded_file = request.FILES.get('file')
        doc_type = request.data.get('type', 'OTHER')

        if not uploaded_file:
            return Response(
                {"error": "No file provided"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate document type
        valid_types = [choice[0] for choice in LicenseDocumentModel.DOCUMENT_TYPE_CHOICES]
        if doc_type not in valid_types:
            return Response(
                {"error": f"Invalid document type. Must be one of: {', '.join(valid_types)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Create document record
            document = LicenseDocumentModel(
                license=license_obj,
                type=doc_type,
                file=uploaded_file
            )
            document.save()

            logger.info(f"Document saved for license {license_obj.license_number}: {doc_type}")

            serializer = LicenseDocumentSerializer(document)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Error saving document for license {pk}: {str(e)}", exc_info=True)
            return Response(
                {"error": f"Failed to save document: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# Add license report actions to viewset
LicenseDetailsViewSet = add_license_report_action(LicenseDetailsViewSet)
LicenseDetailsViewSet = add_active_dfia_report_action(LicenseDetailsViewSet)
LicenseDetailsViewSet = add_license_balance_ledger_actions(LicenseDetailsViewSet)
LicenseDetailsViewSet = add_license_overview_actions(LicenseDetailsViewSet)
