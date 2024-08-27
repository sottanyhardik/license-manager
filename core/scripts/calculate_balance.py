from django.db.models import Sum

from license.helper import round_down


def calculate_available_quantity(instance):
    from license.models import N2015
    credit = float(instance.quantity)
    if instance.item and instance.item.head and instance.item.head.is_restricted:
        if instance.old_quantity or instance.license.notification_number == N2015:
            credit = instance.old_quantity or instance.quantity
    value = round_down(float(credit) - calculate_debited_quantity(instance) - calculate_allotted_quantity(instance), 0)
    return max(round(value, 2), 0)


def calculate_debited_quantity(instance):
    debited = instance.item_details.filter(transaction_type='D').aggregate(sum=Sum('qty'))['sum'] or 0
    allotted = instance.allotment_details.filter(allotment__type='ARO').aggregate(sum=Sum('qty'))['sum'] or 0
    return round(debited + allotted, 2)


def calculate_allotted_quantity(instance):
    allotted = instance.allotment_details.filter(
        allotment__bill_of_entry__bill_of_entry_number__isnull=True,
        allotment__type='AT'
    ).aggregate(Sum('qty'))['qty__sum'] or 0
    return round(allotted, 2) or 0


def calculate_debited_value(instance):
    debited = instance.item_details.filter(transaction_type='D').aggregate(sum=Sum('cif_fc'))['sum'] or 0
    allotted = instance.allotment_details.filter(allotment__type='ARO').aggregate(sum=Sum('cif_fc'))['sum'] or 0
    return round(debited + allotted, 2)


def calculate_allotted_value(instance):
    value = instance.allotment_details.filter(allotment__bill_of_entry__bill_of_entry_number__isnull=True,
                                              allotment__type='AT').aggregate(
        Sum('cif_fc'))['cif_fc__sum'] or 0
    return round(value, 2)


def calculate_available_value(instance):
    available_value = instance.license.get_balance_cif
    balance_value = available_value
    if instance.item:
        head = instance.item.head
    else:
        head = None
    if instance.license and instance.license.get_per_cif and head and head.is_restricted:
        balance_value = instance.license.get_per_cif.get(head.dict_key, available_value)
    value = min(available_value, balance_value)
    return round(value, 2)


def update_balance_values(item):
    values = {
        'available_quantity': calculate_available_quantity(item),
        'debited_quantity': calculate_debited_quantity(item),
        'allotted_quantity': calculate_allotted_quantity(item),
        'allotted_value': calculate_allotted_value(item),
        'debited_value': calculate_debited_value(item),
        'available_value': calculate_available_value(item),
    }

    # Flags if a value has changed
    is_changed = False

    # Iterate over each item in the dictionary
    for attr, value in values.items():
        # If the item's current value is different from the new value, update it
        if float(getattr(item, attr)) != float(value):
            setattr(item, attr, value)
            is_changed = True

    # If any values have been changed, save the item
    if is_changed:
        item.save()
