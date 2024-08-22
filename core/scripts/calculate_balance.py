from django.db.models import Sum

from license.helper import round_down


def calculate_available_quantity(instance):
    from license.models import N2015
    credit = float(instance.quantity)
    if instance.item and instance.item.head and instance.item.head.is_restricted:
        if instance.old_quantity or instance.license.notification_number == N2015:
            credit = instance.old_quantity or instance.quantity
    value = round_down(float(credit) - calculate_debited_quantity(instance) - calculate_allotted_quantity(instance), 0)
    return max(value, 0)


def calculate_debited_quantity(instance):
    debited = instance.item_details.filter(transaction_type='D').aggregate(sum=Sum('qty'))['sum'] or 0
    allotted = instance.allotment_details.filter(allotment__type='ARO').aggregate(sum=Sum('qty'))['sum'] or 0
    total = round(debited + allotted, 0)
    return total


def calculate_allotted_quantity(instance):
    allotted = instance.allotment_details.filter(
        allotment__bill_of_entry__bill_of_entry_number__isnull=True,
        allotment__type='AT'
    ).aggregate(Sum('qty'))['qty__sum']
    return allotted or 0


def calculate_debited_value(instance):
    debited = instance.item_details.filter(transaction_type='D').aggregate(sum=Sum('cif_fc'))['sum'] or 0
    allotted = instance.allotment_details.filter(allotment__type='ARO').aggregate(sum=Sum('cif_fc'))['sum'] or 0
    total = round(debited + allotted, 0)
    return total


def calculate_allotted_value(instance):
    return instance.allotment_details.filter(allotment__bill_of_entry__bill_of_entry_number__isnull=True,
                                             allotment__type='AT').aggregate(
        Sum('cif_fc'))['cif_fc__sum'] or 0


def calculate_available_value(instance):
    available_value = instance.license.get_balance_cif
    balance_value = available_value
    if instance.item:
        head = instance.item.head
    else:
        head = None
    if instance.license and instance.license.get_per_cif and head and head.is_restricted:
        balance_value = instance.license.get_per_cif.get(head.dict_key, available_value)
    total = min(available_value, balance_value)
    return total


def update_balance_values(item):
    available_quantity = calculate_available_quantity(item)
    debited_quantity = calculate_debited_quantity(item)
    allotted_quantity = calculate_allotted_quantity(item)
    allotted_value = calculate_allotted_value(item)
    debited_value = calculate_debited_value(item)
    available_value = calculate_available_value(item)

    is_changed = False

    if item.available_quantity != available_quantity:
        item.available_quantity = available_quantity
        is_changed = True

    if item.debited_quantity != debited_quantity:
        item.debited_quantity = debited_quantity
        is_changed = True

    if item.allotted_quantity != allotted_quantity:
        item.allotted_quantity = allotted_quantity
        is_changed = True

    if item.allotted_value != allotted_value:
        item.allotted_value = allotted_value
        is_changed = True

    if item.debited_value != debited_value:
        item.debited_value = debited_value
        is_changed = True

    if item.available_value != available_value:
        item.available_value = available_value
        is_changed = True

    if is_changed:
        item.save()
