import datetime

from django.db.models import Q, Sum

from license import models as license
from license.models import N2009, N2015, LicenseDetailsModel
from license.tables import LicenseItemReportTable, LicenseBiscuitReportTable, LicenseConfectineryReportTable, \
    LicenseBiscuitNewReportTable
from datetime import date
from dateutil.relativedelta import relativedelta


def all_queryset(query_dict, and_filter=None, or_filters=None, exclude_or_filters=None, and_or_filter=None,
                 minimun_qty=500, minimun_value=500, date_range=None, notification_number=False, maximum_qty=None):
    if date_range:
        start = date_range.get('start')
        end = date_range.get('end')
        if start:
            start_object = datetime.datetime.strptime(start, '%Y-%m-%d')
            query_dict['license__license_expiry_date__gte'] = start_object
        if end:
            start_object = datetime.datetime.strptime(end, '%Y-%m-%d')
            query_dict['license__license_expiry_date__lte'] = start_object
    else:
        expiry_limit = datetime.datetime.today() - datetime.timedelta(days=150)
        query_dict['license__license_expiry_date__gte'] = expiry_limit
    if notification_number:
        query_dict['license__notification_number'] = notification_number
    query_dict['license__is_self'] = True
    query_dict['license__is_au'] = False
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
        if object.cif_fc == 0.01:
            if object.comment and not 'individual' in object.comment.lower():
                object.comment = object.comment + ' individual value error'
            else:
                object.comment = 'individual value error'
        expiry = date.today() + relativedelta(months=-2)
        if object.license_expiry < expiry:
            if object.comment and not 'expired' in object.comment.lower():
                object.comment = object.comment + ' expired'
            else:
                object.comment = 'expired'
        else:
            if object.comment:
                object.comment = object.comment.replace('expired', '')
        object.available_value = object.balance_cif_fc
        object.save()
    if maximum_qty:
        query_set = query_set.filter(
            Q(available_quantity__gte=minimun_qty) & Q(available_value__gte=minimun_value) & Q(is_restrict=False) & Q(
                available_quantity__lte=maximum_qty))
    else:
        query_set = query_set.filter(
            Q(available_quantity__gte=minimun_qty) & Q(available_value__gte=minimun_value) & Q(is_restrict=False))
    return query_set.distinct()


def query_set_table(tables, query_set, label='License List'):
    table = LicenseItemReportTable(query_set)
    tables.append({'label': label, 'table': table,
                   'total': query_set.aggregate(Sum('available_quantity')).get('available_quantity__sum', 0.0)})
    return tables


def sugar_query(date_range=None):
    tables = []
    query_dict = {
        'item__head__name__icontains': 'sugar'
    }
    queryset = all_queryset(query_dict, minimun_qty=1000, date_range=date_range, maximum_qty=25000)
    tables = query_set_table(tables, queryset, label="Below 25 MTS")
    queryset = all_queryset(query_dict, minimun_qty=25001, date_range=date_range)
    tables = query_set_table(tables, queryset, label="Above 25 MTS")
    return tables


def rbd_query(date_range=None):
    tables = []
    query_dict = {
        'item__head__name__icontains': 'RBD Palmolein Oil',
        'hs_code__hs_code__icontains': '15119020'
    }
    queryset = all_queryset(query_dict, date_range=date_range)
    tables = query_set_table(tables, queryset, 'RBD Palmolein Oil')
    query_dict = {
        'item__head__name__icontains': 'RBD Palmolein Oil',
        'hs_code__hs_code__icontains': '15119010'
    }
    queryset = all_queryset(query_dict, date_range=date_range)
    tables = query_set_table(tables, queryset, 'RBD Palm Oil')
    query_dict = {
        'item__head__name__icontains': 'RBD Palmolein Oil',
    }
    exclude_or_filters = {
        'hs_code__hs_code__in': ['15119010', '15119020']
    }
    queryset = all_queryset(query_dict, exclude_or_filters=exclude_or_filters, date_range=date_range)
    tables = query_set_table(tables, queryset, 'Need Amendment')
    return tables


def milk_query(date_range=None):
    tables = []
    query_dict = {
        'license__export_license__norm_class__norm_class': 'E5',
        'item__head__name__icontains': 'milk & milk products',
        'hs_code__hs_code__icontains': '04041020'
    }
    exclude_or_filters = {
        'license__license_number': '0310832494'
    }
    queryset = all_queryset(query_dict, date_range=date_range, exclude_or_filters=exclude_or_filters)
    tables = query_set_table(tables, queryset, 'Whey Powder')
    query_dict['license__license_number'] = '0310832494'
    queryset = all_queryset(query_dict, date_range=date_range)
    tables = query_set_table(tables, queryset, 'CHEESE')
    return tables


def skimmed_milk_query(date_range=None):
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
    queryset = all_queryset(query_dict, date_range=date_range, or_filters=or_filters,
                            exclude_or_filters=exclude_or_filters)
    tables = query_set_table(tables, queryset)
    return tables


def wpc_query(date_range=None):
    tables = []
    query_dict = {
        'license__export_license__norm_class__norm_class': 'E5',
        'hs_code__hs_code__startswith': '35',
        'item__head__name__icontains': 'milk',
    }
    queryset = all_queryset(query_dict, date_range=date_range)
    tables = query_set_table(tables, queryset)
    return tables


def dietary_query(date_range=None):
    tables = []
    query_dict = {
        'license__export_license__norm_class__norm_class': 'E5',
        'item__head__name__icontains': 'dietary fibre',
        'hs_code__hs_code__startswith': '08'
    }

    and_or_filter = [{
        'license__notification_number': N2009
    }]
    queryset = all_queryset(query_dict, date_range=date_range, and_or_filter=and_or_filter)
    tables = query_set_table(tables, queryset, 'OLD Notification')
    and_or_filter = [{
        'license__export_license__old_quantity__gt': 1,
        'license__notification_number': N2015
    }]
    queryset = all_queryset(query_dict, date_range=date_range, and_or_filter=and_or_filter)
    tables = query_set_table(tables, queryset, 'New Notification')
    query_dict = {
        'license__export_license__norm_class__norm_class': 'E5',
        'item__head__name__icontains': 'dietary fibre',
    }
    exclude_or_filters = {
        'hs_code__hs_code__startswith': '08'
    }
    queryset = all_queryset(query_dict, date_range=date_range, and_or_filter=and_or_filter,
                            exclude_or_filters=exclude_or_filters)
    tables = query_set_table(tables, queryset, 'Need Amendment')
    return tables


def food_query(date_range=None):
    tables = []
    query_dict = {
        'license__export_license__norm_class__norm_class': 'E5',
        'item__head__name__icontains': 'food flavour',
    }
    and_or_filter = [{
        'license__notification_number': N2009
    }]
    queryset = all_queryset(query_dict, date_range=date_range, and_or_filter=and_or_filter)
    tables = query_set_table(tables, queryset, 'OLD Notification')
    and_or_filter = [{
        'license__export_license__old_quantity__gt': 1,
        'license__notification_number': N2015
    }]
    queryset = all_queryset(query_dict, date_range=date_range, and_or_filter=and_or_filter)
    tables = query_set_table(tables, queryset, 'New Notification')
    return tables


def juice_query(date_range=None):
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
    queryset = all_queryset(query_dict, date_range=date_range, and_or_filter=and_or_filter)
    tables = query_set_table(tables, queryset)
    query_dict = {
        'license__export_license__norm_class__norm_class': 'E1',
        'item__head__name__icontains': 'juice',
    }
    exclude_or_filters = {
        'hs_code__hs_code__startswith': '2009'
    }
    queryset = all_queryset(query_dict, date_range=date_range, and_or_filter=and_or_filter,
                            exclude_or_filters=exclude_or_filters)
    tables = query_set_table(tables, queryset, 'Need Amendment')
    return tables


def packing_query(date_range=None):
    tables = []
    query_dict = {
        'item__head__name__icontains': 'Packing Material',
    }
    query_dict['is_restrict'] = False
    query_dict['available_quantity__lte'] = 10000
    queryset = all_queryset(query_dict, date_range=date_range)
    tables = query_set_table(tables, queryset, 'Less than 10000 Kg')

    query_dict['available_quantity__gte'] = 10001
    query_dict['available_quantity__lte'] = 25000
    queryset = all_queryset(query_dict, date_range=date_range)
    tables = query_set_table(tables, queryset, 'Between 10001 to 25000 Kg')

    query_dict['available_quantity__gte'] = 25001
    query_dict['available_quantity__lte'] = 50000
    queryset = all_queryset(query_dict, date_range=date_range)
    tables = query_set_table(tables, queryset, 'Between 25001 to 50000 Kg')

    query_dict['available_quantity__gte'] = 50001
    query_dict['available_quantity__lte'] = 100000
    queryset = all_queryset(query_dict, date_range=date_range)
    tables = query_set_table(tables, queryset, 'Between 50001 to 100000 Kg')

    query_dict['available_quantity__gte'] = 100000
    del query_dict['available_quantity__lte']
    queryset = all_queryset(query_dict, date_range=date_range)
    tables = query_set_table(tables, queryset, 'Above 100001 Kg')

    return tables


def oci_query(date_range=None):
    tables = []
    query_dict = {
        'license__export_license__norm_class__norm_class': 'E1',
        'item__head__name__icontains': 'other confectionery',
        'hs_code__hs_code__startswith': '08',
    }
    and_or_filter = [{
        'license__notification_number': N2009
    }]
    queryset = all_queryset(query_dict, date_range=date_range, and_or_filter=and_or_filter)
    tables = query_set_table(tables, queryset, 'Old Notification')
    and_or_filter = [{
        'license__export_license__old_quantity__gt': 1,
        'license__notification_number': N2015
    }]
    queryset = all_queryset(query_dict, date_range=date_range, and_or_filter=and_or_filter)
    tables = query_set_table(tables, queryset, 'New Notification')

    query_dict = {
        'license__export_license__norm_class__norm_class': 'E1',
        'item__head__name__icontains': 'other confectionery',
    }
    exclude_or_filters = {
        'hs_code__hs_code__startswith': '08'
    }
    queryset = all_queryset(query_dict, date_range=date_range, and_or_filter=and_or_filter,
                            exclude_or_filters=exclude_or_filters)
    tables = query_set_table(tables, queryset, 'Need Amendment')
    return tables


def fruit_query(date_range=None):
    tables = []
    query_dict = {
        'license__export_license__norm_class__norm_class': 'E5',
        'item__head__name__icontains': 'fruit',
    }
    and_or_filter = [{
        'license__notification_number': N2009
    }]
    queryset = all_queryset(query_dict, and_or_filter=and_or_filter, date_range=date_range)
    tables = query_set_table(tables, queryset, 'Old Notification')
    and_or_filter = [{
        'license__export_license__old_quantity__gt': 1,
        'license__notification_number': N2015
    }]
    queryset = all_queryset(query_dict, and_or_filter=and_or_filter, date_range=date_range)
    tables = query_set_table(tables, queryset, 'New Notification')
    query_dict = {
        'license__export_license__norm_class__norm_class': 'E5',
        'item__head__name__icontains': 'fruit',
    }
    exclude_or_filters = {
        'hs_code__hs_code__startswith': '08'
    }
    queryset = all_queryset(query_dict, date_range=date_range, and_or_filter=and_or_filter,
                            exclude_or_filters=exclude_or_filters)
    tables = query_set_table(tables, queryset, 'Need Amendment')
    return tables


def get_table_query(query_dict, date_range=None, or_filters=None, exclude_or_filters=None, exclude_and_filters=None,
                    is_self=True, is_au=False,
                    is_expired=False):
    my_filter = Q()
    if date_range:
        start = date_range.get('start', None)
        end = date_range.get('end', None)
    else:
        start = None
        end = None
    if start:
        start_object = datetime.datetime.strptime(start, '%Y-%m-%d')
        query_dict['license_expiry_date__gte'] = start_object
    else:
        expiry_limit = datetime.datetime.strptime('2020-02-01', '%Y-%m-%d')
        query_dict['license_expiry_date__gte'] = expiry_limit
    if end:
        end_object = datetime.datetime.strptime(end, '%Y-%m-%d')
        query_dict['license_expiry_date__lte'] = end_object
    elif is_expired:
        expiry_limit = datetime.datetime.today() - datetime.timedelta(days=30)
        query_dict['license_expiry_date__lte'] = expiry_limit
    query_dict['is_self'] = is_self
    query_dict['is_au'] = is_au
    for item in query_dict:
        my_filter &= Q(**{item: query_dict[item]})
    if or_filters:
        for item in or_filters:
            if 'list' in str(type(or_filters[item])) and '__icontains' in item:
                or_filter_text = Q()
                for value in or_filters[item]:
                    or_filter_text |= Q(**{item: value})
                my_filter &= or_filter_text
            else:
                my_filter = Q(**{item: or_filters[item]})
    if exclude_or_filters:
        for item in exclude_or_filters:
            if 'list' in str(type(exclude_or_filters[item])) and '__icontains' in item:
                or_filter_text = Q()
                for value in exclude_or_filters[item]:
                    or_filter_text |= ~Q(**{item: value})
                my_filter &= or_filter_text
            else:
                my_filter &= ~Q(**{item: exclude_or_filters[item]})
    if exclude_and_filters:
        for item in exclude_and_filters:
            if 'list' in str(type(exclude_and_filters[item])) and '__icontains' in item:
                or_filter_text = Q()
                for value in exclude_and_filters[item]:
                    or_filter_text &= ~Q(**{item: value})
                my_filter &= or_filter_text
            else:
                my_filter &= ~Q(**{item: exclude_and_filters[item]})
    query_set = LicenseDetailsModel.objects.filter(my_filter).order_by('license_expiry_date')
    return query_set.distinct()


def report_dict_generate(tables, title, total_quantity=None):
    if total_quantity == 0:
        for table in tables:
            if table['total']:
                total_quantity = total_quantity + table['total']
        data_dict = {'page_title': title, 'tables': tables, 'total_quantity': total_quantity,
                     'today': datetime.datetime.now().date(), 'template_name': 'license/report_pdf_ITEM.html'}
    else:
        data_dict = {'page_title': title, 'tables': tables, 'total_quantity': total_quantity,
                     'today': datetime.datetime.now().date(), 'template_name': 'license/report_pdf.html'}
    return data_dict


def generate_table(queryset, table):
    table = table(queryset)
    return table


def biscuit_conversion(date_range=None, party=None, exclude_party=None):
    query_dict = {
        'export_license__norm_class__norm_class': 'E5',
        'notification_number': N2015
    }
    if party:
        or_filters = {
            'exporter__name__icontains': party
        }
    else:
        or_filters = {}
    if exclude_party:
        exclude_and_filters = {
            'exporter__name__icontains': exclude_party
        }
    else:
        exclude_and_filters = {}
    exclude_or_filters = {
        'export_license__old_quantity': 0
    }
    return get_table_query(query_dict, date_range=date_range, or_filters=or_filters,
                           exclude_or_filters=exclude_or_filters, exclude_and_filters=exclude_and_filters)


def confectionery_conversion(date_range=None, party=None, exclude_party=None):
    query_dict = {
        'export_license__norm_class__norm_class': 'E1',
        'notification_number': N2015
    }
    if party:
        or_filters = {
            'exporter__name__icontains': party
        }
    else:
        or_filters = {}
    if exclude_party:
        exclude_and_filters = {
            'exporter__name__icontains': exclude_party
        }
    else:
        exclude_and_filters = {}
    exclude_or_filters = {
        'export_license__old_quantity': 0
    }
    return get_table_query(query_dict, date_range=date_range, or_filters=or_filters,
                           exclude_or_filters=exclude_or_filters, exclude_and_filters=exclude_and_filters)


def biscuit_2019(date_range=None, party=None, exclude_party=None):
    query_dict = {
        'export_license__norm_class__norm_class': 'E5',
        'notification_number': N2015,
        'export_license__old_quantity': 0
    }
    if party:
        or_filters = {
            'exporter__name__icontains': party
        }
    else:
        or_filters = {}
    if exclude_party:
        exclude_and_filters = {
            'exporter__name__icontains': exclude_party
        }
    else:
        exclude_and_filters = {}
    queryset = get_table_query(query_dict, date_range=date_range, or_filters=or_filters,
                               exclude_and_filters=exclude_and_filters)
    return queryset


def biscuit_2019_rama_rani(date_range=None):
    tables = [{'label': 'RAMA RANI New Biscuits',
               'table': generate_table(biscuit_2019(party=['rama', 'rani']),
                                       LicenseBiscuitNewReportTable)}, {'label': 'Parle New Biscuits',
                                                                     'table': generate_table(
                                                                         biscuit_2019(party=['Parle']),
                                                                         LicenseBiscuitNewReportTable)}]

    return tables


def conversion_other(date_range=None):
    tables = []
    from license.tables import LicenseBiscuitReportTable, LicenseConfectineryReportTable
    tables.append({'label': 'Viva, V A global, Vipul Kumar Biscuits',
                   'table': generate_table(
                       biscuit_conversion(date_range, exclude_party=['rama', 'rani', 'vanila', 'parle']),
                       LicenseBiscuitReportTable)})
    tables.append({'label': 'Viva, V A global, Vipul Kumar Confectioney',
                   'table': generate_table(
                       confectionery_conversion(date_range, exclude_party=['rama', 'rani', 'vanila', 'parle']),
                       LicenseConfectineryReportTable)})
    tables.append({'label': 'Parle Confectinery',
                   'table': generate_table(
                       confectionery_conversion(date_range, party=['parle']),
                       LicenseConfectineryReportTable)})
    return tables


def conversion_main(date_range=None):
    tables = [{'label': 'RAMA RANI Biscuits',
               'table': generate_table(biscuit_conversion(date_range, party=['rama', 'rani']),
                                       LicenseBiscuitReportTable)},
              {'label': 'RAMA RANI & VANILLA Confectionery',
               'table': generate_table(
                   confectionery_conversion(date_range, party=['rama', 'rani', 'VANILA', 'VANILLA']),
                   LicenseConfectineryReportTable)},
              {'label': 'Parle Biscuits',
               'table': generate_table(biscuit_conversion(date_range, party=['Parle']),
                                       LicenseBiscuitReportTable)}]
    return tables


def biscuit_2009(date_range=None, party=None, exclude_party=None):
    from license.models import N2009
    query_dict = {
        'export_license__norm_class__norm_class': 'E5',
        'notification_number': N2009
    }
    if party:
        or_filters = {
            'exporter__name__icontains': party
        }
    else:
        or_filters = {}
    if exclude_party:
        exclude_and_filters = {
            'exporter__name__icontains': exclude_party
        }
    else:
        exclude_and_filters = {}
    queryset = get_table_query(query_dict, date_range=date_range, exclude_and_filters=exclude_and_filters,
                               or_filters=or_filters)
    return queryset


def biscuit_2019_other(date_range=None):
    tables = [{'label': 'Biscuits New Remaning [019/2015]',
               'table': generate_table(biscuit_2019(date_range, exclude_party=['rama', 'rani', 'VANILA', 'parle']),
                                       LicenseBiscuitNewReportTable)}]
    return tables


def confectinery_2019(date_range=None, party=None, exclude_party=None):
    tables = []
    from license.tables import LicenseConfectineryReportTable
    from license.models import N2015
    query_dict = {
        'export_license__norm_class__norm_class': 'E1',
        'notification_number': N2015,
        'export_license__old_quantity': 0
    }
    if party:
        or_filters = {
            'exporter__name__icontains': party
        }
    else:
        or_filters = {}
    if exclude_party:
        exclude_and_filters = {
            'exporter__name__icontains': exclude_party
        }
    else:
        exclude_and_filters = {}
    queryset = get_table_query(query_dict, date_range=date_range, or_filters=or_filters,
                               exclude_and_filters=exclude_and_filters)
    return queryset


def confectinery_2019_rama_rani(date_range=None):
    tables = [{'label': 'RAMA RANI New Confectinery',
               'table': generate_table(confectinery_2019(date_range, party=['rama', 'rani', 'vanila']),
                                       LicenseConfectineryReportTable)}, {'label': 'Parle New Confectinery',
                                                                          'table': generate_table(
                                                                              confectinery_2019(date_range,
                                                                                                party=['Parle']),
                                                                              LicenseConfectineryReportTable)}]

    return tables


def confectinery_2019_other(date_range=None):
    tables = [{'label': 'Confectinery New Remaning [019/2015]',
               'table': generate_table(confectinery_2019(date_range, exclude_party=['rama', 'rani', 'VANILA', 'parle']),
                                       LicenseConfectineryReportTable)}]
    return tables


def confectinery_2009(date_range=None, party=None, exclude_party=None):
    query_dict = {
        'export_license__norm_class__norm_class': 'E1',
        'notification_number': N2009
    }
    if party:
        or_filters = {
            'exporter__name__icontains': party
        }
    else:
        or_filters = {}
    if exclude_party:
        exclude_and_filters = {
            'exporter__name__icontains': exclude_party
        }
    else:
        exclude_and_filters = {}
    return get_table_query(query_dict, date_range=date_range, exclude_and_filters=exclude_and_filters,
                           or_filters=or_filters)


def confectinery_2009_all(date_range=None):
    from license.tables import LicenseConfectineryReportTable
    tables = [{'label': 'Confectinery 098/2019 Notification',
               'table': generate_table(confectinery_2009(date_range, exclude_party=['rama', 'rani', 'VANILA']),
                                       LicenseConfectineryReportTable)},
              {'label': 'Confectinery 098/2019 Notification [Rama & Rani]',
               'table': generate_table(
                   confectinery_2009(date_range,
                                     party=['rama', 'rani', 'VANILA']),
                   LicenseConfectineryReportTable)}]
    return tables


def biscuits_2009_all(date_range=None):
    from license.tables import LicenseBiscuitReportTable
    tables = [{'label': 'Biscuits 098/2019 Notification',
               'table': generate_table(biscuit_2009(date_range, exclude_party=['rama', 'rani', 'VANILA']),
                                       LicenseBiscuitReportTable)},
              {'label': 'Biscuits 098/2019 Notification [Rama & Rani]',
               'table': generate_table(biscuit_2009(date_range, party=['rama', 'rani', 'VANILA']),
                                       LicenseBiscuitReportTable)}]
    return tables


def generate_dict(object, total_dict, new=False):
    dicts = {'license_number': object.license_number, 'license_date': object.license_date,
             'license_expiry': object.license_expiry_date, 'exporter': object.exporter}
    balance_dict = {
        'opening_balance': object.opening_balance,
        'usable_balance': '--',
        'balance': object.get_balance_cif,
        'usable_cif': '--'
    }
    dicts['balance'] = balance_dict
    total_dict['balance']['cif'] = round(total_dict['balance']['cif'] + object.get_balance_cif(), 2)
    balance = round(object.get_balance_cif(), 0)
    cif_required = object.sugar().required_cif
    if balance < cif_required:
        cif_required = balance
    balance = round(balance - cif_required, 0)
    balance_dict = {
        'opening_balance': object.sugar().quantity,
        'usable_balance': object.sugar().usable,
        'balance': object.get_sugar(),
        'usable_cif': cif_required
    }
    dicts['sugar'] = balance_dict
    total_dict['sugar']['cif'] = total_dict['sugar']['cif'] + cif_required
    total_dict['sugar']['quantity'] = total_dict['sugar']['quantity'] + round(
        cif_required / object.sugar().item.head.unit_rate, 0)

    cif_required = object.rbd().required_cif
    if balance < cif_required:
        cif_required = balance
    balance = round(balance - cif_required, 0)
    balance_dict = {
        'opening_balance': object.rbd().quantity,
        'usable_balance': object.rbd().usable,
        'balance': object.get_rbd(),
        'usable_cif': cif_required
    }
    dicts['rbd'] = balance_dict
    total_dict['rbd']['cif'] = total_dict['rbd']['cif'] + cif_required
    total_dict['rbd']['quantity'] = total_dict['rbd']['quantity'] + round(
        cif_required / object.rbd().item.head.unit_rate, 0)

    if not new:
        cif_required = object.dietary_fibre().required_cif
        if balance < cif_required:
            cif_required = balance
        balance = round(balance - cif_required, 0)
        balance_dict = {
            'opening_balance': object.dietary_fibre().quantity,
            'usable_balance': object.dietary_fibre().usable,
            'balance': object.get_dietary_fibre(),
            'usable_cif': cif_required
        }
        dicts['dietary_fibre'] = balance_dict
        total_dict['dietary_fibre']['cif'] = total_dict['dietary_fibre']['cif'] + cif_required
        total_dict['dietary_fibre']['quantity'] = total_dict['dietary_fibre']['quantity'] + round(
            cif_required / object.dietary_fibre().item.head.unit_rate, 0)
    if not new:
        cif_required = object.food_flavour().required_cif
        if balance < cif_required:
            cif_required = balance
        balance = round(balance - cif_required, 0)
        balance_dict = {
            'opening_balance': object.food_flavour().quantity,
            'usable_balance': object.food_flavour().usable,
            'balance': object.get_food_flavour(),
            'usable_cif': cif_required
        }
        dicts['food_flavour'] = balance_dict
        total_dict['food_flavour']['cif'] = total_dict['food_flavour']['cif'] + cif_required
        total_dict['food_flavour']['quantity'] = total_dict['food_flavour']['quantity'] + round(
            cif_required / object.food_flavour().item.head.unit_rate, 0)

    if not new:
        cif_required = object.fruit().required_cif
        if balance < cif_required:
            cif_required = balance
        balance = round(balance - cif_required, 0)
        balance_dict = {
            'opening_balance': object.fruit().quantity,
            'usable_balance': object.fruit().usable,
            'balance': object.get_fruit(),
            'usable_cif': cif_required
        }
        dicts['fruit'] = balance_dict
        total_dict['fruit']['cif'] = total_dict['fruit']['cif'] + cif_required
        total_dict['fruit']['quantity'] = total_dict['fruit']['quantity'] + round(
            cif_required / object.fruit().item.head.unit_rate, 0)

    cif_required = object.m_n_m().required_cif
    if balance < cif_required:
        cif_required = balance
    balance = round(balance - cif_required, 0)
    balance_dict = {
        'opening_balance': object.m_n_m().quantity,
        'usable_balance': object.m_n_m().usable,
        'balance': object.get_m_n_m(),
        'usable_cif': cif_required
    }
    dicts['m_n_m'] = balance_dict
    total_dict['m_n_m']['cif'] = total_dict['m_n_m']['cif'] + cif_required
    total_dict['m_n_m']['quantity'] = total_dict['m_n_m']['quantity'] + round(
        cif_required / object.m_n_m().item.head.unit_rate, 0)

    if not new:
        cif_required = object.wheat().required_cif
        if balance < cif_required:
            cif_required = balance
        balance = round(balance - cif_required, 0)
        balance_dict = {
            'opening_balance': object.wheat().quantity,
            'usable_balance': object.wheat().usable,
            'balance': object.get_wheat(),
            'usable_cif': cif_required
        }
        dicts['wheat'] = balance_dict
        total_dict['wheat']['cif'] = total_dict['wheat']['cif'] + cif_required
        total_dict['wheat']['quantity'] = total_dict['wheat']['quantity'] + round(
            cif_required / object.wheat().item.head.unit_rate, 0)

    if not new:
        cif_required = object.leavening_agent().required_cif
        if balance < cif_required:
            cif_required = balance
        balance = round(balance - cif_required, 0)
        balance_dict = {
            'opening_balance': object.leavening_agent().quantity,
            'usable_balance': object.leavening_agent().usable,
            'balance': object.get_leavening_agent(),
            'usable_cif': cif_required
        }
        dicts['leavening_agent'] = balance_dict
        total_dict['leavening_agent']['cif'] = total_dict['leavening_agent']['cif'] + cif_required
        total_dict['leavening_agent']['quantity'] = total_dict['leavening_agent']['quantity'] + round(
            cif_required / object.leavening_agent().item.head.unit_rate, 0)

    if object.pp():
        cif_required = object.pp().required_cif
        if balance < cif_required:
            cif_required = balance
        balance = round(balance - cif_required, 0)
        balance_dict = {
            'opening_balance': object.pp().quantity,
            'usable_balance': object.pp().usable,
            'balance': object.get_pp(),
            'usable_cif': cif_required
        }
        dicts['pp'] = balance_dict
        total_dict['pp']['cif'] = total_dict['pp']['cif'] + cif_required
        total_dict['pp']['quantity'] = total_dict['pp']['quantity'] + round(
            cif_required / object.pp().item.head.unit_rate, 0)
    balance_dict = {
        'opening_balance': '',
        'usable_balance': '',
        'balance': '',
        'usable_cif': balance
    }
    return dicts, total_dict


def tartaric_query(date_range=None):
    tables = []
    query_dict = {
        'license__export_license__norm_class__norm_class': 'E1',
        'item__head__name__icontains': 'citric',
    }
    and_or_filter = [{
        'license__notification_number': N2009
    }]
    queryset = all_queryset(query_dict, date_range=date_range, and_or_filter=and_or_filter)
    tables = query_set_table(tables, queryset, 'Old Notification')
    and_or_filter = [{
        'license__export_license__old_quantity__gt': 1,
        'license__notification_number': N2015
    }]
    queryset = all_queryset(query_dict, date_range=date_range, and_or_filter=and_or_filter)
    tables = query_set_table(tables, queryset, 'New Notification')
    return tables


def essential_oil_query(date_range=None):
    tables = []
    query_dict = {
        'license__export_license__norm_class__norm_class': 'E1',
        'item__head__name__icontains': 'essential oil',
    }
    and_or_filter = [{
        'license__notification_number': N2009
    }]
    queryset = all_queryset(query_dict, date_range=date_range, and_or_filter=and_or_filter)
    tables = query_set_table(tables, queryset, 'Old Notification')
    and_or_filter = [{
        'license__export_license__old_quantity__gt': 1,
        'license__notification_number': N2015
    }]
    queryset = all_queryset(query_dict, date_range=date_range, and_or_filter=and_or_filter)
    tables = query_set_table(tables, queryset, 'New Notification')

    query_dict = {
        'license__export_license__norm_class__norm_class': 'E1',
        'item__head__name__icontains': 'other confectionery',
    }
    exclude_or_filters = {
        'hs_code__hs_code__startswith': '08'
    }
    queryset = all_queryset(query_dict, date_range=date_range, and_or_filter=and_or_filter,
                            exclude_or_filters=exclude_or_filters)
    tables = query_set_table(tables, queryset, 'Need Amendment')
    return tables
