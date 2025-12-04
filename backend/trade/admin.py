# trade/admin.py

from django.contrib import admin
from .models import LicenseTrade, LicenseTradeLine, LicenseTradePayment


class LicenseTradeLineInline(admin.TabularInline):
    model = LicenseTradeLine
    extra = 1
    fields = ('sr_number', 'mode', 'qty_kg', 'rate_inr_per_kg', 'cif_inr', 'fob_inr', 'pct', 'amount_inr')
    readonly_fields = ('amount_inr',)


class LicenseTradePaymentInline(admin.TabularInline):
    model = LicenseTradePayment
    extra = 1
    fields = ('date', 'amount', 'note')


@admin.register(LicenseTrade)
class LicenseTradeAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'direction',
        'invoice_number',
        'invoice_date',
        'from_company',
        'to_company',
        'subtotal_amount',
        'total_amount',
        'paid_or_received',
        'due_amount'
    ]
    list_filter = ['direction', 'invoice_date', 'created_on']
    search_fields = ['invoice_number', 'from_company__name', 'to_company__name', 'remarks']
    date_hierarchy = 'invoice_date'
    readonly_fields = ['subtotal_amount', 'roundoff', 'total_amount', 'paid_or_received', 'due_amount', 'created_on', 'modified_on']

    fieldsets = (
        ('Trade Information', {
            'fields': ('direction', 'invoice_number', 'invoice_date', 'boe')
        }),
        ('Parties', {
            'fields': (
                'from_company', 'to_company',
                'from_pan', 'from_gst', 'from_addr_line_1', 'from_addr_line_2',
                'to_pan', 'to_gst', 'to_addr_line_1', 'to_addr_line_2'
            )
        }),
        ('Amounts', {
            'fields': ('subtotal_amount', 'roundoff', 'total_amount', 'paid_or_received', 'due_amount')
        }),
        ('Additional Information', {
            'fields': ('remarks', 'purchase_invoice_copy'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_on', 'modified_on'),
            'classes': ('collapse',)
        })
    )

    inlines = [LicenseTradeLineInline, LicenseTradePaymentInline]

    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        qs = super().get_queryset(request)
        return qs.select_related('from_company', 'to_company', 'boe')


@admin.register(LicenseTradeLine)
class LicenseTradeLineAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'trade',
        'sr_number',
        'mode',
        'qty_kg',
        'rate_inr_per_kg',
        'amount_inr'
    ]
    list_filter = ['mode', 'created_on']
    search_fields = ['trade__invoice_number', 'description']
    readonly_fields = ['amount_inr', 'created_on', 'modified_on']

    fieldsets = (
        ('Trade Information', {
            'fields': ('trade', 'sr_number', 'description', 'mode')
        }),
        ('Quantity Mode', {
            'fields': ('qty_kg', 'rate_inr_per_kg'),
            'classes': ('collapse',)
        }),
        ('CIF/FOB Mode', {
            'fields': ('cif_fc', 'exc_rate', 'cif_inr', 'fob_inr', 'pct'),
            'classes': ('collapse',)
        }),
        ('Result', {
            'fields': ('amount_inr',)
        }),
        ('Timestamps', {
            'fields': ('created_on', 'modified_on'),
            'classes': ('collapse',)
        })
    )

    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        qs = super().get_queryset(request)
        return qs.select_related('trade', 'sr_number')


@admin.register(LicenseTradePayment)
class LicenseTradePaymentAdmin(admin.ModelAdmin):
    list_display = ['id', 'trade', 'date', 'amount', 'note']
    list_filter = ['date']
    search_fields = ['trade__invoice_number', 'note']
    date_hierarchy = 'date'

    fieldsets = (
        ('Payment Information', {
            'fields': ('trade', 'date', 'amount', 'note')
        }),
    )

    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        qs = super().get_queryset(request)
        return qs.select_related('trade')
