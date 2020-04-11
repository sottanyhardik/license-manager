from django import template

from license.models import AllotmentItems

register = template.Library()


@register.simple_tag
def quantity_allotment(arg1, arg2):
    try:
        allotment = AllotmentItems.objects.get(item_id=arg1, allotment=arg2)
        return allotment.qty
    except:
        return 0


@register.simple_tag
def value_allotment(arg1, arg2):
    try:
        allotment = AllotmentItems.objects.get(item_id=arg1, allotment=arg2)
        return allotment.cif_fc
    except:
        return 0


@register.simple_tag
def get_table_html(table):
    from allotment.tables import AllottedItemsTable
    table = AllottedItemsTable(table)
    table.paginate(page=1, per_page=50)
    return table


@register.simple_tag
def get_total(queryset):
    total = 0
    for query in queryset:
        total = total + query.required_value
    return round(total,2)


@register.simple_tag
def get_boe_total_inr(queryset):
    total = 0
    for query in queryset:
        total = total + query.get_total_inr()
    return round(total,2)


@register.simple_tag
def get_boe_total_fc(queryset):
    total = 0
    for query in queryset:
        total = total + query.get_total_fc()
    return round(total,2)


@register.simple_tag
def get_boe_total_quantity(queryset):
    total = 0
    for query in queryset:
        total = total + query.get_total_quantity()
    return round(total,2)

@register.simple_tag
def get_total_quantity(queryset):
    total = 0
    for query in queryset:
        total = total + query.required_quantity
    return round(total,2)
