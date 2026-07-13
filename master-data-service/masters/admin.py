from django.contrib import admin

from .models import MASTER_REGISTRY, MasterChange

# Register every master with a simple admin (generated from the registry).
for _model, _nk, _endpoint in MASTER_REGISTRY:
    try:
        admin.site.register(_model)
    except admin.sites.AlreadyRegistered:
        pass


@admin.register(MasterChange)
class MasterChangeAdmin(admin.ModelAdmin):
    list_display = ("at", "op", "model_label", "natural_key")
    list_filter = ("op", "model_label")
    search_fields = ("natural_key",)
