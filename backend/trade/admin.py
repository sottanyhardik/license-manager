# trade/admin.py

from django.contrib import admin
from .models import (
    LicenseTrade, LicenseTradeLine, LicenseTradePayment,
    ChartOfAccounts, BankAccount, JournalEntry, JournalEntryLine,
    CommissionAgent, Commission, CommissionSlab
)


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


# =============================================================================
# LEDGER MODULE ADMIN
# =============================================================================

@admin.register(ChartOfAccounts)
class ChartOfAccountsAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'account_type', 'parent', 'linked_company', 'is_active', 'balance']
    list_filter = ['account_type', 'is_active']
    search_fields = ['code', 'name', 'description', 'linked_company__name']
    readonly_fields = ['balance', 'created_on', 'modified_on']

    fieldsets = (
        ('Account Information', {
            'fields': ('code', 'name', 'account_type', 'parent')
        }),
        ('Party Ledger', {
            'fields': ('linked_company',),
            'description': 'Link to company for party-wise ledgers (Sundry Debtors/Creditors)'
        }),
        ('Details', {
            'fields': ('description', 'is_active', 'balance')
        }),
        ('Timestamps', {
            'fields': ('created_on', 'modified_on'),
            'classes': ('collapse',)
        })
    )

    def balance(self, obj):
        return f"₹{obj.balance:,.2f}"
    balance.short_description = 'Current Balance'


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ['account_name', 'bank_name', 'account_number', 'ifsc_code', 'current_balance', 'is_active']
    list_filter = ['bank_name', 'is_active']
    search_fields = ['account_name', 'bank_name', 'account_number', 'ifsc_code']
    readonly_fields = ['current_balance', 'created_on', 'modified_on']

    fieldsets = (
        ('Bank Information', {
            'fields': ('account_name', 'bank_name', 'account_number', 'ifsc_code', 'branch')
        }),
        ('Ledger Link', {
            'fields': ('ledger_account',)
        }),
        ('Opening Balance', {
            'fields': ('opening_balance', 'opening_balance_date')
        }),
        ('Status', {
            'fields': ('is_active', 'current_balance')
        }),
        ('Timestamps', {
            'fields': ('created_on', 'modified_on'),
            'classes': ('collapse',)
        })
    )

    def current_balance(self, obj):
        return f"₹{obj.current_balance:,.2f}"
    current_balance.short_description = 'Current Balance'


class JournalEntryLineInline(admin.TabularInline):
    model = JournalEntryLine
    extra = 2
    fields = ('account', 'debit_amount', 'credit_amount', 'description')


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ['entry_number', 'entry_date', 'entry_type', 'total_debit', 'total_credit', 'is_balanced', 'is_posted', 'is_auto_generated']
    list_filter = ['entry_type', 'is_posted', 'is_auto_generated', 'entry_date']
    search_fields = ['entry_number', 'narration', 'reference_number', 'linked_trade__invoice_number']
    date_hierarchy = 'entry_date'
    readonly_fields = ['total_debit', 'total_credit', 'is_balanced', 'created_on', 'modified_on']

    fieldsets = (
        ('Entry Information', {
            'fields': ('entry_number', 'entry_date', 'entry_type')
        }),
        ('Details', {
            'fields': ('narration', 'reference_number')
        }),
        ('Links', {
            'fields': ('linked_trade', 'linked_payment'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_posted', 'is_auto_generated')
        }),
        ('Totals', {
            'fields': ('total_debit', 'total_credit', 'is_balanced')
        }),
        ('Timestamps', {
            'fields': ('created_by', 'created_on', 'modified_on'),
            'classes': ('collapse',)
        })
    )

    inlines = [JournalEntryLineInline]

    def total_debit(self, obj):
        return f"₹{obj.total_debit:,.2f}"
    total_debit.short_description = 'Total Debit'

    def total_credit(self, obj):
        return f"₹{obj.total_credit:,.2f}"
    total_credit.short_description = 'Total Credit'

    def is_balanced(self, obj):
        return "✓" if obj.is_balanced else "✗"
    is_balanced.short_description = 'Balanced'
    is_balanced.boolean = True

    actions = ['post_entries', 'unpost_entries']

    def post_entries(self, request, queryset):
        count = 0
        for entry in queryset:
            try:
                entry.post()
                count += 1
            except ValueError as e:
                self.message_user(request, f"Error posting {entry.entry_number}: {e}", level='error')
        self.message_user(request, f"Successfully posted {count} journal entries.")
    post_entries.short_description = "Post selected journal entries"

    def unpost_entries(self, request, queryset):
        count = 0
        for entry in queryset:
            try:
                entry.unpost()
                count += 1
            except ValueError as e:
                self.message_user(request, f"Error unposting {entry.entry_number}: {e}", level='error')
        self.message_user(request, f"Successfully unposted {count} journal entries.")
    unpost_entries.short_description = "Unpost selected journal entries"


@admin.register(JournalEntryLine)
class JournalEntryLineAdmin(admin.ModelAdmin):
    list_display = ['id', 'journal_entry', 'account', 'debit_amount', 'credit_amount']
    list_filter = ['journal_entry__entry_type', 'journal_entry__entry_date']
    search_fields = ['journal_entry__entry_number', 'account__name', 'description']

    fieldsets = (
        ('Entry Information', {
            'fields': ('journal_entry', 'account')
        }),
        ('Amounts', {
            'fields': ('debit_amount', 'credit_amount')
        }),
        ('Description', {
            'fields': ('description',)
        })
    )


# =============================================================================
# COMMISSION MODULE ADMIN
# =============================================================================

class CommissionSlabInline(admin.TabularInline):
    model = CommissionSlab
    extra = 1
    fields = ('direction', 'min_amount', 'max_amount', 'commission_rate', 'is_active')


@admin.register(CommissionAgent)
class CommissionAgentAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'email', 'phone', 'default_purchase_rate', 'default_sale_rate', 'total_commission_earned', 'total_commission_paid', 'outstanding_commission', 'is_active']
    list_filter = ['is_active']
    search_fields = ['code', 'name', 'email', 'phone', 'pan']
    readonly_fields = ['total_commission_earned', 'total_commission_paid', 'outstanding_commission', 'created_on', 'modified_on']

    fieldsets = (
        ('Basic Information', {
            'fields': ('code', 'name', 'is_active')
        }),
        ('Contact Details', {
            'fields': ('email', 'phone', 'address')
        }),
        ('Banking Details', {
            'fields': ('pan', 'bank_name', 'account_number', 'ifsc_code')
        }),
        ('Default Commission Rates', {
            'fields': ('default_purchase_rate', 'default_sale_rate')
        }),
        ('Commission Summary', {
            'fields': ('total_commission_earned', 'total_commission_paid', 'outstanding_commission')
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
        ('Timestamps', {
            'fields': ('created_on', 'modified_on'),
            'classes': ('collapse',)
        })
    )

    inlines = [CommissionSlabInline]

    def total_commission_earned(self, obj):
        return f"₹{obj.total_commission_earned:,.2f}"
    total_commission_earned.short_description = 'Total Earned'

    def total_commission_paid(self, obj):
        return f"₹{obj.total_commission_paid:,.2f}"
    total_commission_paid.short_description = 'Total Paid'

    def outstanding_commission(self, obj):
        return f"₹{obj.outstanding_commission:,.2f}"
    outstanding_commission.short_description = 'Outstanding'


@admin.register(Commission)
class CommissionAdmin(admin.ModelAdmin):
    list_display = ['id', 'trade', 'agent', 'commission_rate', 'base_amount', 'commission_amount', 'is_paid', 'payment_date']
    list_filter = ['is_paid', 'agent', 'trade__direction', 'created_on']
    search_fields = ['trade__invoice_number', 'agent__name', 'agent__code', 'payment_reference']
    date_hierarchy = 'created_on'
    readonly_fields = ['commission_amount', 'created_on', 'modified_on']

    fieldsets = (
        ('Trade Information', {
            'fields': ('trade', 'agent')
        }),
        ('Commission Calculation', {
            'fields': ('commission_rate', 'base_amount', 'commission_amount')
        }),
        ('Payment Information', {
            'fields': ('is_paid', 'payment_date', 'payment_reference', 'payment_note', 'payment_journal_entry')
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
        ('Timestamps', {
            'fields': ('created_by', 'created_on', 'modified_on'),
            'classes': ('collapse',)
        })
    )

    actions = ['mark_as_paid', 'mark_as_unpaid']

    def mark_as_paid(self, request, queryset):
        from django.utils import timezone
        count = 0
        for commission in queryset:
            if not commission.is_paid:
                commission.mark_paid()
                count += 1
        self.message_user(request, f"Marked {count} commissions as paid.")
    mark_as_paid.short_description = "Mark selected commissions as paid"

    def mark_as_unpaid(self, request, queryset):
        count = queryset.filter(is_paid=True).update(
            is_paid=False,
            payment_date=None,
            payment_reference='',
            payment_note=''
        )
        self.message_user(request, f"Marked {count} commissions as unpaid.")
    mark_as_unpaid.short_description = "Mark selected commissions as unpaid"


@admin.register(CommissionSlab)
class CommissionSlabAdmin(admin.ModelAdmin):
    list_display = ['agent', 'direction', 'min_amount', 'max_amount', 'commission_rate', 'is_active']
    list_filter = ['direction', 'is_active', 'agent']
    search_fields = ['agent__name', 'agent__code']

    fieldsets = (
        ('Agent', {
            'fields': ('agent',)
        }),
        ('Slab Configuration', {
            'fields': ('direction', 'min_amount', 'max_amount', 'commission_rate', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_on', 'modified_on'),
            'classes': ('collapse',)
        })
    )
