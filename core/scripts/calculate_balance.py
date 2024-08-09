from django.db.models import Sum

from license.helper import round_down


def calculate_available_quantity(instance):
    from license.models import N2015
    credit = float(instance.quantity)
    if instance.item and instance.item.head and instance.item.head.is_restricted:
        if instance.old_quantity or instance.license.notification_number == N2015:
            credit = instance.old_quantity or instance.quantity
    value = round_down(float(credit) - float(instance.debited_quantity) - float(instance.allotted_quantity), 0)
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
        Sum('cif_fc'))['cif_fc__sum']
