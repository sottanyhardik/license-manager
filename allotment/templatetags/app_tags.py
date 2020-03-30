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
    from allotment.tables import AllotedItemsTable
    table = AllotedItemsTable(table)
    table.paginate(page=1, per_page=50)
    return table
