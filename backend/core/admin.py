from django.contrib import admin

# Register your models here.
from django.contrib import admin
from django.apps import apps

from core.models import HSCodeModel, ExchangeRateModel

app = apps.get_app_config('core')
for model_name, model in app.models.items():
    try:
        if model_name not in ['hscodemodel', 'exchangeratemodel']:
            model_admin = type(model_name + "Admin", (admin.ModelAdmin,), {})
            model_admin.list_display = model.admin_list_display if hasattr(model, 'admin_list_display') else tuple(
                [field.name for field in model._meta.fields])
            model_admin.list_display_links = model.admin_list_display_links if hasattr(model,
                                                                                       'admin_list_display_links') else ()
            model_admin.list_editable = model.admin_list_editable if hasattr(model, 'admin_list_editable') else ()
            model_admin.search_fields = model.admin_search_fields if hasattr(model, 'admin_search_fields') else ()
            model_admin.list_filter = model.list_filter if hasattr(model, 'list_filter') else ()
            admin.site.register(model, model_admin)
    except:
        pass


@admin.register(HSCodeModel)
class HSCodeDutyAdmin(admin.ModelAdmin):
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
class ExchangeRateAdmin(admin.ModelAdmin):
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



