from django.contrib import admin

from django.apps import apps
from django.conf import settings

from apps.core.models import HSCodeModel, ExchangeRateModel, PurchaseStatus

# --- MDS write-cutover admin safety (ADR-001 Phase 6) ----------------------
# When MDS_ENABLED, the 17 masters are centrally written via the API cutover, so
# the Django admin must NOT be a bypass write path — it becomes read-only for
# those models. When MDS is disabled (default), admin behavior is unchanged.
#
# The set of MDS-managed local model_labels comes from the SAME registry the
# cutover uses (mds_client's DEFAULT_MDS_MODELS), so admin and the API agree on
# exactly which models are centrally managed. Import is tolerant: without the
# client package there is nothing to lock down.
try:  # pragma: no cover - both installed/uninstalled envs exercised elsewhere
    from mds_client.model_map import DEFAULT_MDS_MODELS as _MDS_MODELS
except ImportError:  # pragma: no cover
    _MDS_MODELS = {}

_MDS_MANAGED_LABELS = frozenset(_MDS_MODELS.keys())


def _is_mds_managed(model) -> bool:
    label = f"{model._meta.app_label}.{model.__name__}"
    return label in _MDS_MANAGED_LABELS


class _MDSReadOnlyAdminMixin:
    """Make an admin read-only for MDS-managed masters while MDS_ENABLED.

    Falls through to the default permissions when MDS is off or the model isn't
    centrally managed, so the local-only admin experience is byte-for-byte
    unchanged by default."""

    def _mds_locked(self) -> bool:
        return bool(getattr(settings, "MDS_ENABLED", False)) and _is_mds_managed(self.model)

    def has_add_permission(self, request):
        if self._mds_locked():
            return False
        return super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        if self._mds_locked():
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if self._mds_locked():
            return False
        return super().has_delete_permission(request, obj)


app = apps.get_app_config('core')
for model_name, model in app.models.items():
    try:
        if model_name not in ['hscodemodel', 'exchangeratemodel', 'purchasestatus']:
            model_admin = type(
                model_name + "Admin",
                (_MDSReadOnlyAdminMixin, admin.ModelAdmin),
                {},
            )
            model_admin.list_display = model.admin_list_display if hasattr(model, 'admin_list_display') else tuple(
                [field.name for field in model._meta.fields])
            model_admin.list_display_links = model.admin_list_display_links if hasattr(model,
                                                                                       'admin_list_display_links') else ()
            model_admin.list_editable = model.admin_list_editable if hasattr(model, 'admin_list_editable') else ()
            model_admin.search_fields = model.admin_search_fields if hasattr(model, 'admin_search_fields') else ()
            model_admin.list_filter = model.list_filter if hasattr(model, 'list_filter') else ()
            admin.site.register(model, model_admin)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Admin registration failed for %s: %s", model, e)


@admin.register(PurchaseStatus)
class PurchaseStatusAdmin(admin.ModelAdmin):
    list_display = ('code', 'label', 'display_order', 'is_active')
    list_display_links = ('code', 'label')
    search_fields = ('code', 'label')
    list_filter = ('is_active',)
    ordering = ('display_order', 'label')


@admin.register(HSCodeModel)
class HSCodeDutyAdmin(_MDSReadOnlyAdminMixin, admin.ModelAdmin):
    actions = ['download_csv']
    list_display = (
        'id', 'hs_code', 'product_description', 'basic_duty', 'unit_price')
    search_fields = ('hs_code',)

    @admin.action(
        description="Download CSV file for selected stats."
    )
    def download_csv(self, request, queryset):
        import csv
        from django.http import HttpResponse
        from io import StringIO
        f = StringIO()
        writer = csv.writer(f)
        writer.writerow(['id', 'hs_code', 'product_description', 'basic_duty', 'unit_price', 'unit'])
        for s in queryset:
            writer.writerow(
                [s.id, "'" + s.hs_code, s.product_description, s.basic_duty, s.unit_price, s.unit])
        f.seek(0)
        response = HttpResponse(f, content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename=stat-info.csv'
        return response


@admin.register(ExchangeRateModel)
class ExchangeRateAdmin(_MDSReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ('date', 'usd', 'euro', 'pound_sterling', 'chinese_yuan', 'is_active', 'created_on', 'created_by')
    list_filter = ('date', 'created_on')
    search_fields = ('date',)
    ordering = ('-date',)
    readonly_fields = ('created_on', 'created_by', 'modified_on', 'modified_by')

    fieldsets = (
        ('Exchange Rate Date', {
            'fields': ('date',)
        }),
        ('Currency Rates (to INR)', {
            'fields': ('usd', 'euro', 'pound_sterling', 'chinese_yuan')
        }),
        ('Audit Information', {
            'fields': ('created_on', 'created_by', 'modified_on', 'modified_by'),
            'classes': ('collapse',)
        })
    )

    def is_active(self, obj):
        """Display if this is the active (latest) exchange rate"""
        active_rate = ExchangeRateModel.get_active_rate()
        return obj.id == active_rate.id if active_rate else False

    is_active.boolean = True
    is_active.short_description = 'Active Rate'


