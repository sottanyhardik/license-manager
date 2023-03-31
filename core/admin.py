from django.contrib import admin

# Register your models here.
from django.contrib import admin
from django.apps import apps

from core.models import HSCodeDutyModel

app = apps.get_app_config('core')
for model_name, model in app.models.items():
    try:
        if not model_name == 'hscodedutymodel':
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


@admin.register(HSCodeDutyModel)
class HSCodeDutyAdmin(admin.ModelAdmin):
    actions = ['download_csv']
    list_display = (
        'id', 'hs_code', 'product_description', 'basic_custom_duty', 'additional_duty_of_customs', 'custom_health_CESS',
        'social_welfare_surcharge', 'additional_CVD', 'IGST_levy', 'compensation_cess', 'total_duty', 'sample_on_lakh')
    list_filter = ('is_fetch','is_fetch_xls')
    search_fields = ('hs_code',)

    def download_csv(self, request, queryset):
        import csv
        from django.http import HttpResponse
        from io import StringIO
        f = StringIO()
        writer = csv.writer(f)
        writer.writerow(['id', 'hs_code', 'product_description', 'basic_custom_duty', 'additional_duty_of_customs',
                         'custom_health_CESS', 'social_welfare_surcharge', 'additional_CVD', 'IGST_levy',
                         'compensation_cess', 'total_duty', 'sample_on_lakh'])
        for s in queryset:
            writer.writerow(
                [s.id, "'" + s.hs_code, s.product_description, s.basic_custom_duty, s.additional_duty_of_customs,
                 s.custom_health_CESS, s.social_welfare_surcharge, s.additional_CVD, s.IGST_levy,
                 s.compensation_cess, s.total_duty, s.sample_on_lakh])
        f.seek(0)
        response = HttpResponse(f, content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename=stat-info.csv'
        return response

    download_csv.short_description = "Download CSV file for selected stats."


