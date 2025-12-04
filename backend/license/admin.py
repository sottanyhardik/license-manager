# Register your models here.
from django.apps import apps
from django.contrib import admin

from license.models import LicenseTransferModel


@admin.register(LicenseTransferModel)
class LicenseTransferAdmin(admin.ModelAdmin):
    list_display = (
        'dfia_number',
        'transfer_initiation_date',
        'from_company_name',
        'to_company_name',
        'transfer_date',
        'transfer_status',
    )

    search_fields = (
        'license__license_number',
        'from_company__name',
        'to_company__name',
    )

    list_filter = (
        'transfer_status',
        'transfer_date',
    )

    def dfia_number(self, obj):
        return obj.license.license_number
    dfia_number.short_description = 'DFIA No'


app = apps.get_app_config('license')
for model_name, model in app.models.items():
    model_admin = type(model_name + "Admin", (admin.ModelAdmin,), {})

    model_admin.list_display = model.admin_list_display if hasattr(model, 'admin_list_display') else tuple(
        [field.name for field in model._meta.fields])
    model_admin.list_display_links = model.admin_list_display_links if hasattr(model,
                                                                               'admin_list_display_links') else ()
    model_admin.list_editable = model.admin_list_editable if hasattr(model, 'admin_list_editable') else ()
    model_admin.search_fields = model.admin_search_fields if hasattr(model, 'admin_search_fields') else ()
    model_admin.list_filter = model.list_filter if hasattr(model, 'list_filter') else ()
    try:
        admin.site.register(model, model_admin)
    except:
        print("Already registered")