import datetime

from django.db.models import Q, Sum

from . import models as license
from .models import N2009, N2015, LicenseDetailsModel
from .tables import LicenseItemReportTable


def all_queryset(query_dict, and_filter=None, or_filters=None, exclude_or_filters=None, and_or_filter=None,
                 minimun_qty=500, minimun_value=500):
    expiry_limit = datetime.datetime.today() - datetime.timedelta(days=60)
    query_dict['license__license_expiry_date__gte'] = expiry_limit
    query_dict['license__is_self'] = True
    query_dict['license__is_au'] = False
    query_dict['available_quantity__gte'] = minimun_qty
    query_dict['available_value__gte'] = minimun_value
    my_filter = Q()
    for item in query_dict:
        my_filter &= Q(**{item: query_dict[item]})
    if and_filter:
        for item in and_filter:
            my_filter &= Q(**{item: and_filter[item]})
    if or_filters:
        for item in or_filters:
            if 'list' in str(type(or_filters[item])) and '__icontains' in item:
                or_filter_text = Q()
                for value in or_filters[item]:
                    or_filter_text |= Q(**{item: value})
                my_filter &= or_filter_text
            else:
                my_filter = Q(**{item: or_filters[item]})
    if and_or_filter:
        and_filter = Q()
        for data in and_or_filter:
            or_filter_text = Q()
            for item in data:
                or_filter_text &= Q(**{item: data[item]})
            and_filter |= or_filter_text
        my_filter &= and_filter
    if exclude_or_filters:
        for item in exclude_or_filters:
            my_filter &= ~Q(**{item: exclude_or_filters[item]})
    query_set = license.LicenseImportItemsModel.objects.filter(my_filter).order_by(
        'license__license_expiry_date')
    for object in query_set:
        object.available_quantity = object.balance_quantity
        object.available_value = object.balance_cif_fc
        object.save()
    query_set = query_set.filter(Q(available_quantity__gte=minimun_qty) & Q(available_value__gte=minimun_value))
    return query_set.distinct()


def query_set_table(tables, query_set, label='License List'):
    table = LicenseItemReportTable(query_set)
    tables.append({'label': label, 'table': table,
                   'total': query_set.aggregate(Sum('available_quantity')).get('available_quantity__sum', 0.0)})
    return tables


def sugar_query():
    tables = []
    query_dict = {
        'item__head__name__icontains': 'sugar'
    }
    queryset = all_queryset(query_dict, minimun_qty=1000)
    tables = query_set_table(tables, queryset)
    return tables


def rbd_query():
    tables = []
    query_dict = {
        'item__head__name__icontains': 'RBD Palmolein Oil',
        'hs_code__hs_code__icontains': '15119020'
    }
    queryset = all_queryset(query_dict)
    tables = query_set_table(tables, queryset, 'RBD Palmolein Oil')
    query_dict = {
        'item__head__name__icontains': 'RBD Palmolein Oil',
        'hs_code__hs_code__icontains': '15119010'
    }
    queryset = all_queryset(query_dict)
    tables = query_set_table(tables, queryset, 'RBD Palm Oil')
    query_dict = {
        'item__head__name__icontains': 'RBD Palmolein Oil',
    }
    exclude_or_filters = {
        'hs_code__hs_code__in': ['15119010', '15119020']
    }
    queryset = all_queryset(query_dict, exclude_or_filters=exclude_or_filters)
    tables = query_set_table(tables, queryset, 'Need Amendment')
    return tables


def milk_query():
    tables = []
    query_dict = {
        'license__export_license__norm_class__norm_class': 'E5',
        'item__head__name__icontains': 'milk & milk products',
        'hs_code__hs_code__icontains': '04041020'
    }
    queryset = all_queryset(query_dict)
    tables = query_set_table(tables, queryset)
    return tables


def skimmed_milk_query():
    tables = []
    query_dict = {
        'license__export_license__norm_class__norm_class': 'E5',
        'item__head__name__icontains': 'milk & milk products',
    }
    or_filters = {
        'item__name__icontains': ['skim', 'skimmed'],

    }
    exclude_or_filters = {
        'hs_code__hs_code__icontains': '04041020'
    }
    queryset = all_queryset(query_dict, or_filters=or_filters, exclude_or_filters=exclude_or_filters)
    tables = query_set_table(tables, queryset)
    return tables


def wpc_query():
    tables = []
    query_dict = {
        'license__export_license__norm_class__norm_class': 'E5',
        'hs_code__hs_code__startswith': '35',
        'item__head__name__icontains': 'milk',
    }
    queryset = all_queryset(query_dict)
    tables = query_set_table(tables, queryset)
    return tables


def dietary_query():
    tables = []
    query_dict = {
        'license__export_license__norm_class__norm_class': 'E5',
        'item__head__name__icontains': 'dietary fibre',
        'hs_code__hs_code__startswith': '08'
    }
    and_or_filter = [{
        'license__export_license__old_quantity__gt': 1,
        'license__notification_number': N2015
    }, {
        'license__notification_number': N2009
    }]
    queryset = all_queryset(query_dict, and_or_filter=and_or_filter)
    tables = query_set_table(tables, queryset)
    query_dict = {
        'license__export_license__norm_class__norm_class': 'E5',
        'item__head__name__icontains': 'dietary fibre',
    }
    exclude_or_filters = {
        'hs_code__hs_code__startswith': '08'
    }
    queryset = all_queryset(query_dict, and_or_filter=and_or_filter, exclude_or_filters=exclude_or_filters)
    tables = query_set_table(tables, queryset, 'Need Amendment')
    return tables


def food_query():
    tables = []
    query_dict = {
        'license__export_license__norm_class__norm_class': 'E5',
        'item__head__name__icontains': 'food flavour',
    }
    and_or_filter = [{
        'license__export_license__old_quantity__gt': 1,
        'license__notification_number': N2015
    }, {
        'license__notification_number': N2009
    }]
    queryset = all_queryset(query_dict, and_or_filter=and_or_filter)
    tables = query_set_table(tables, queryset)
    return tables


def juice_query():
    tables = []
    query_dict = {
        'license__export_license__norm_class__norm_class': 'E1',
        'item__head__name__icontains': 'juice',
        'hs_code__hs_code__startswith': '2009',
    }
    and_or_filter = [{
        'license__export_license__old_quantity__gt': 1,
        'license__notification_number': N2015
    }, {
        'license__notification_number': N2009
    }]
    queryset = all_queryset(query_dict, and_or_filter=and_or_filter)
    tables = query_set_table(tables, queryset)
    query_dict = {
        'license__export_license__norm_class__norm_class': 'E1',
        'item__head__name__icontains': 'juice',
    }
    exclude_or_filters = {
        'hs_code__hs_code__startswith': '2009'
    }
    queryset = all_queryset(query_dict, and_or_filter=and_or_filter,exclude_or_filters=exclude_or_filters)
    tables = query_set_table(tables, queryset, 'Need Amendment')
    return tables


def packing_query():
    tables = []
    query_dict = {
        'item__head__name__icontains': 'Packing Material',
    }
    and_or_filter = [{
        'license__export_license__norm_class__norm_class': 'E1',
    }, {
        'license__export_license__old_quantity__lte': 1,
        'license__export_license__norm_class__norm_class': 'E5',
        'license__notification_number': N2015
    }]
    queryset = all_queryset(query_dict, and_or_filter=and_or_filter)
    tables = query_set_table(tables, queryset)
    return tables


def oci_query():
    tables = []
    query_dict = {
        'license__export_license__norm_class__norm_class': 'E1',
        'item__head__name__icontains': 'other confectionery',
        'hs_code__hs_code__startswith': '08',
    }
    and_or_filter = [{
        'license__export_license__old_quantity__gt': 1,
        'license__notification_number': N2015
    }, {
        'license__notification_number': N2009
    }]
    queryset = all_queryset(query_dict, and_or_filter=and_or_filter)
    tables = query_set_table(tables, queryset)
    query_dict = {
        'license__export_license__norm_class__norm_class': 'E1',
        'item__head__name__icontains': 'other confectionery',
    }
    exclude_or_filters = {
        'hs_code__hs_code__startswith': '08'
    }
    queryset = all_queryset(query_dict, and_or_filter=and_or_filter, exclude_or_filters=exclude_or_filters)
    tables = query_set_table(tables, queryset, 'Need Amendment')
    return tables


def fruit_query():
    tables = []
    query_dict = {
        'license__export_license__norm_class__norm_class': 'E5',
        'item__head__name__icontains': 'fruit',
        'hs_code__hs_code__startswith': '08',
    }
    and_or_filter = [{
        'license__export_license__old_quantity__gt': 1,
        'license__notification_number': N2015
    }, {
        'license__notification_number': N2009
    }]
    queryset = all_queryset(query_dict, and_or_filter=and_or_filter)
    tables = query_set_table(tables, queryset)
    query_dict = {
        'license__export_license__norm_class__norm_class': 'E5',
        'item__head__name__icontains': 'fruit',
    }
    exclude_or_filters = {
        'hs_code__hs_code__startswith': '08'
    }
    queryset = all_queryset(query_dict, and_or_filter=and_or_filter, exclude_or_filters=exclude_or_filters)
    tables = query_set_table(tables, queryset, 'Need Amendment')
    return tables



def get_table_query(query_dict, or_filters=None,exclude_or_filters=None, is_self=True, is_au=False, is_expired=False):
    my_filter = Q()
    if is_expired:
        expiry_limit = datetime.datetime.today() - datetime.timedelta(days=30)
        query_dict['license_expiry_date__lte'] = expiry_limit
    else:
        expiry_limit = datetime.datetime.today() - datetime.timedelta(days=60)
        query_dict['license_expiry_date__gte'] = expiry_limit
    query_dict['is_self'] = is_self
    query_dict['is_au'] = is_au
    for item in query_dict:
        my_filter &= Q(**{item: query_dict[item]})
    # if or_filters:
    #     for item in or_filters:
    #         if 'list' in str(type(or_filters[item])) and '__icontains' in item:
    #             or_filter_text = Q()
    #             for value in or_filters[item]:
    #                 or_filter_text |= Q(**{item: value})
    #             my_filter &= or_filter_text
    #         else:
    #             my_filter = Q(**{item: or_filters[item]})
    if exclude_or_filters:
        for item in exclude_or_filters:
            my_filter &= ~Q(**{item: exclude_or_filters[item]})
    query_set = LicenseDetailsModel.objects.filter(my_filter)
    return query_set.distinct()