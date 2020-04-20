import datetime

from django.db.models import Q, Sum

from . import models as license
from .models import N2009, N2015, LicenseDetailsModel
from .tables import LicenseItemReportTable


def all_queryset(query_dict, and_filter=None, or_filters=None, exclude_or_filters=None, and_or_filter=None,
                 minimun_qty=500, minimun_value=500, date_range=None):
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


def sugar_query(date_range=None):
    tables = []
    query_dict = {
        'item__head__name__icontains': 'sugar'
    }
    queryset = all_queryset(query_dict, minimun_qty=1000, date_range=date_range)
    tables = query_set_table(tables, queryset)
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
    queryset = all_queryset(query_dict, date_range=date_range)
    tables = query_set_table(tables, queryset)
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
        'license__export_license__old_quantity__gt': 1,
        'license__notification_number': N2015
    }, {
        'license__notification_number': N2009
    }]
    queryset = all_queryset(query_dict, date_range=date_range, and_or_filter=and_or_filter)
    tables = query_set_table(tables, queryset)
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
        'license__export_license__old_quantity__gt': 1,
        'license__notification_number': N2015
    }, {
        'license__notification_number': N2009
    }]
    queryset = all_queryset(query_dict, date_range=date_range, and_or_filter=and_or_filter)
    tables = query_set_table(tables, queryset)
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
    and_or_filter = [{
        'license__export_license__norm_class__norm_class': 'E1',
    }, {
        'license__export_license__old_quantity__lte': 1,
        'license__export_license__norm_class__norm_class': 'E5',
        'license__notification_number': N2015
    }]
    queryset = all_queryset(query_dict, date_range=date_range, and_or_filter=and_or_filter)
    tables = query_set_table(tables, queryset)
    return tables


def oci_query(date_range=None):
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
    queryset = all_queryset(query_dict, date_range=date_range, and_or_filter=and_or_filter)
    tables = query_set_table(tables, queryset)
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
        'hs_code__hs_code__startswith': '08',
    }
    and_or_filter = [{
        'license__export_license__old_quantity__gt': 1,
        'license__notification_number': N2015
    }, {
        'license__notification_number': N2009
    }]
    queryset = all_queryset(query_dict, and_or_filter=and_or_filter, date_range=date_range)
    tables = query_set_table(tables, queryset)
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
        expiry_limit = datetime.datetime.today() - datetime.timedelta(days=60)
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


def conversion_other(date_range=None):
    tables = []
    from license.tables import LicenseBiscuitReportTable, LicenseConfectineryReportTable
    from license.models import N2015
    query_dict = {
        'export_license__norm_class__norm_class': 'E5',
        'notification_number': N2015
    }
    exclude_and_filters = {
        'exporter__name__icontains': ['rama', 'rani', 'VANILA', 'parle']
    }
    exclude_or_filters = {
        'export_license__old_quantity': 0
    }
    queryset = get_table_query(query_dict, date_range=date_range, exclude_and_filters=exclude_and_filters,
                               exclude_or_filters=exclude_or_filters)
    table = LicenseBiscuitReportTable(queryset)
    tables.append({'label': 'Viva, V A global, Vipul Kumar Biscuits', 'table': table})
    query_dict = {
        'export_license__norm_class__norm_class': 'E1',
        'notification_number': N2015
    }
    queryset = get_table_query(query_dict, date_range=date_range, exclude_and_filters=exclude_and_filters,
                               exclude_or_filters=exclude_or_filters)
    table = LicenseConfectineryReportTable(queryset)
    tables.append({'label': 'Viva, V A global, Vipul Kumar Confectinery', 'table': table})
    or_filters = {
        'exporter__name__icontains': ['parle']
    }
    queryset = get_table_query(query_dict, date_range=date_range, or_filters=or_filters,
                               exclude_or_filters=exclude_or_filters)
    table = LicenseConfectineryReportTable(queryset)
    tables.append({'label': 'Parle Confectinery', 'table': table})
    return tables


def conversion_main(date_range=None):
    tables = []
    from license.tables import LicenseBiscuitReportTable, LicenseConfectineryReportTable
    from license.models import N2015
    query_dict = {
        'export_license__norm_class__norm_class': 'E5',
        'notification_number': N2015
    }
    or_filters = {
        'exporter__name__icontains': ['rama', 'rani', 'VANILA']
    }
    exclude_or_filters = {
        'export_license__old_quantity': 0
    }
    queryset = get_table_query(query_dict, date_range=date_range, or_filters=or_filters, exclude_or_filters=exclude_or_filters)
    table = LicenseBiscuitReportTable(queryset)
    tables.append({'label': 'RAMA RANI VANNILA Biscuits', 'table': table})
    query_dict = {
        'export_license__norm_class__norm_class': 'E1',
        'notification_number': N2015
    }
    or_filters = {
        'exporter__name__icontains': ['rama', 'rani', 'VANILA']
    }
    exclude_or_filters = {
        'export_license__old_quantity': 0
    }
    queryset = get_table_query(query_dict, date_range=date_range, or_filters=or_filters, exclude_or_filters=exclude_or_filters)
    table = LicenseConfectineryReportTable(queryset)
    tables.append({'label': 'RAMA RANI VANNILA Confectinery', 'table': table})
    query_dict = {
        'export_license__norm_class__norm_class': 'E5',
        'notification_number': N2015
    }
    or_filters = {
        'exporter__name__icontains': ['Parle']
    }
    exclude_or_filters = {
        'export_license__old_quantity': 0
    }
    queryset = get_table_query(query_dict, date_range=date_range, or_filters=or_filters, exclude_or_filters=exclude_or_filters)
    table = LicenseBiscuitReportTable(queryset)
    tables.append({'label': 'Parle Biscuits', 'table': table})
    return tables


def biscuit_2019(date_range=None):
    tables = []
    from license.tables import LicenseBiscuitReportTable
    from license.models import N2015
    query_dict = {
        'export_license__norm_class__norm_class': 'E5',
        'notification_number': N2015,
        'export_license__old_quantity': 0
    }
    or_filters = {
        'exporter__name__icontains': ['rama', 'rani', 'VANILA']
    }
    queryset = get_table_query(query_dict, date_range=date_range, or_filters=or_filters)
    table = LicenseBiscuitReportTable(queryset)
    tables.append({'label': 'RAMA RANI Other Biscuits', 'table': table})
    or_filters = {
        'exporter__name__icontains': ['parle']
    }
    queryset = get_table_query(query_dict, date_range=date_range, or_filters=or_filters)
    table = LicenseBiscuitReportTable(queryset)
    tables.append({'label': 'Parle Other Biscuits', 'table': table})
    return tables


def biscuit_2009(date_range=None):
    tables = []
    from license.models import N2009
    from license.tables import LicenseBiscuitReportTable
    query_dict = {
        'export_license__norm_class__norm_class': 'E5',
        'notification_number': N2009
    }
    exclude_and_filters = {
        'exporter__name__icontains': ['rama', 'rani', 'VANILA']
    }
    queryset = get_table_query(query_dict, date_range=date_range, exclude_and_filters=exclude_and_filters)
    table = LicenseBiscuitReportTable(queryset)
    tables.append({'label': 'Biscuits 098/2019 Notification [ No Rama & Rani]', 'table': table})
    or_filters = {
        'exporter__name__icontains': ['rama', 'rani', 'VANILA']
    }
    queryset = get_table_query(query_dict, date_range=date_range, or_filters=or_filters)
    table = LicenseBiscuitReportTable(queryset)
    tables.append({'label': 'Rama Rani Biscuits 098/2019 Notification', 'table': table})
    return tables


def biscuit_2019_other(date_range=None):
    tables = []
    from license.tables import LicenseBiscuitReportTable
    from license.models import N2015
    query_dict = {
        'export_license__norm_class__norm_class': 'E5',
        'notification_number': N2015,
        'export_license__old_quantity': 0
    }
    exclude_and_filters = {
        'exporter__name__icontains': ['rama', 'rani', 'VANILA', 'parle']
    }
    queryset = get_table_query(query_dict, date_range=date_range, exclude_and_filters=exclude_and_filters)
    table = LicenseBiscuitReportTable(queryset)
    tables.append({'label': 'Biscuits Remaning 019/2015 Notification', 'table': table})
    return tables


def confectinery_2009(date_range=None):
    tables = []
    from license.tables import LicenseConfectineryReportTable
    from license.models import N2009
    query_dict = {
        'export_license__norm_class__norm_class': 'E1',
        'notification_number': N2009
    }
    exclude_and_filters = {
        'exporter__name__icontains': ['rama', 'rani', 'VANILA']
    }
    queryset = get_table_query(query_dict, date_range=date_range, exclude_and_filters=exclude_and_filters)
    table = LicenseConfectineryReportTable(queryset)
    tables.append({'label': 'Confectinery 098/2019 Notification [ No Rama & Rani]', 'table': table})
    or_filters = {
        'exporter__name__icontains': ['rama', 'rani', 'VANILA']
    }
    queryset = get_table_query(query_dict, date_range=date_range, or_filters=or_filters)
    table = LicenseConfectineryReportTable(queryset)
    tables.append({'label': 'Rama & Rani Confectinery 098/2019 Notification', 'table': table})
    return tables


def confectinery_2019(date_range=None):
    tables = []
    from license.tables import LicenseConfectineryReportTable
    from license.models import N2015
    query_dict = {
        'export_license__norm_class__norm_class': 'E1',
        'notification_number': N2015,
        'export_license__old_quantity': 0
    }
    or_filters = {
        'exporter__name__icontains': ['rama', 'rani', 'VANILA']
    }
    queryset = get_table_query(query_dict, date_range=date_range, or_filters=or_filters)
    table = LicenseConfectineryReportTable(queryset)
    tables.append({'label': 'RAMA RANI VANNILA Other Confectinery', 'table': table})
    or_filters = {
        'exporter__name__icontains': ['Parle']
    }
    queryset = get_table_query(query_dict, date_range=date_range, or_filters=or_filters)
    table = LicenseConfectineryReportTable(queryset)
    tables.append({'label': 'Parle Other Confectinery', 'table': table})
    return tables


def confectinery_2019_other(date_range=None):
    tables = []
    from license.tables import LicenseConfectineryReportTable
    from license.models import N2015
    query_dict = {
        'export_license__norm_class__norm_class': 'E1',
        'notification_number': N2015,
        'export_license__old_quantity': 0
    }
    exclude_and_filters = {
        'exporter__name__icontains': ['rama', 'rani', 'VANILA', 'parle']
    }
    queryset = get_table_query(query_dict, date_range=date_range, exclude_and_filters=exclude_and_filters)
    table = LicenseConfectineryReportTable(queryset)
    tables.append({'label': 'Confectinery Remaning 019/2015 Notification', 'table': table})
    return tables
