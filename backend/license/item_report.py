import datetime
from datetime import date

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.db.models import Q, Sum

from core.constants import N2023, GE, MI
from core.models import ItemNameModel
from license import models as license
from license.models import LicenseDetailsModel, LicenseImportItemsModel
from license.tables import LicenseItemReportTable, RutileLicenseItemReportTable


def all_queryset(query_dict, and_filter=None, or_filters=None, exclude_or_filters=None, and_or_filter=None,
                 minimun_qty=500, minimun_value=500, date_range=None, notification_number=False, maximum_qty=None,
                 item_name=None, purchase_status=GE):
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
        expiry_limit = datetime.datetime.today() - datetime.timedelta(days=15)
        query_dict['license__license_expiry_date__gte'] = expiry_limit
    if notification_number:
        query_dict['license__notification_number'] = notification_number
    query_dict['license__purchase_status'] = purchase_status
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
        if item_name and item_name == 'DF':
            object.available_value = object.license.get_per_cif.get('tenRestriction') or 0
        else:
            object.available_value = object.license.opening_balance
        if object.cif_fc == 0.01:
            if object.comment and not 'individual' in object.comment.lower():
                object.comment = object.comment + ' individual value error'
            else:
                object.comment = 'individual value error'
        expiry = date.today() + relativedelta(months=-6)
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
            Q(available_quantity__gte=minimun_qty) & Q(available_value__gte=minimun_value) & Q(is_restricted=False) & Q(
                available_quantity__lte=maximum_qty))
    else:
        query_set = query_set.filter(
            Q(available_quantity__gte=minimun_qty) & Q(available_value__gte=minimun_value) & Q(is_restricted=False))
    return query_set.distinct()


def query_set_table(tables, query_set, label='License List'):
    table = LicenseItemReportTable(query_set)
    tables.append({'label': label, 'table': table,
                   'total': query_set.aggregate(Sum('available_quantity')).get('available_quantity__sum', 0.0)})
    return tables


def get_table_query(query_dict, date_range=None, or_filters=None, exclude_or_filters=None, exclude_and_filters=None,
                    is_au=False, is_expired=False, purchase_status=GE):
    my_filter = Q()
    if date_range:
        start = date_range.get('start', None)
        end = date_range.get('end', None)
    else:
        start = None
        end = None
    if is_expired:
        expiry_limit = datetime.datetime.today() - datetime.timedelta(days=settings.EXPIRY_DAY)
        START = datetime.datetime.today() - datetime.timedelta(days=60)
        query_dict['license_expiry_date__gte'] = START
        query_dict['license_expiry_date__lte'] = expiry_limit
    else:
        expiry_limit = datetime.datetime.today() - datetime.timedelta(days=settings.EXPIRY_DAY)
        query_dict['license_expiry_date__gte'] = expiry_limit
    query_dict['purchase_status'] = purchase_status
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
    query_set = LicenseDetailsModel.objects.filter(my_filter).order_by('license_expiry_date', 'license_date')
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


def biscuit_conversion(date_range=None, party=None, exclude_party=None, is_expired=False, purchase_status=GE):
    query_dict = {
        'export_license__norm_class__norm_class': 'E5',
        'purchase_status': purchase_status,
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
    }
    return get_table_query(query_dict, date_range=date_range, or_filters=or_filters,
                           exclude_or_filters=exclude_or_filters, exclude_and_filters=exclude_and_filters,
                           is_expired=is_expired, purchase_status=purchase_status)


def confectionery_conversion(date_range=None, party=None, exclude_party=None):
    query_dict = {
        'export_license__norm_class__norm_class': 'E1',
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


def biscuit_dfia(date_range=None, status=False, party=GE):
    if status == 'expired':
        is_expired = True
    else:
        is_expired = False
    if is_expired:
        limit = 20000
    else:
        limit = 1000
    empty_list = []
    parle_dfia = []
    other_dfia = []
    tables = []
    if party == 'parle':
        parle_dfia_qs = biscuit_conversion(date_range, party=['Parle'], is_expired=is_expired, purchase_status=GE)
        for dfia in parle_dfia_qs:
            if dfia.get_balance_cif > limit:
                parle_dfia.append(dfia)
            else:
                empty_list.append(dfia)
        tables.append({'label': 'Parle Biscuits', 'table': parle_dfia})
    elif party == 'mi':
        other_dfia_qs = biscuit_conversion(date_range, is_expired=is_expired,
                                           purchase_status=MI)
        for dfia in other_dfia_qs:
            if dfia.get_balance_cif > limit:
                other_dfia.append(dfia)
            else:
                empty_list.append(dfia)
        tables.append({'label': 'Nilesh Sir DFIA', 'table': other_dfia})
    else:
        other_dfia_qs = biscuit_conversion(date_range, exclude_party=['Parle'], is_expired=is_expired,
                                           purchase_status=GE)
        for dfia in other_dfia_qs:
            if dfia.get_balance_cif > limit:
                other_dfia.append(dfia)
            else:
                empty_list.append(dfia)
        tables.append({'label': 'GE DFIA', 'table': other_dfia})
    return tables


def confectionery_query(date_range=None, party=None, exclude_party=None, is_expired=False):
    tables = []
    query_dict = {
        'export_license__norm_class__norm_class': 'E1',
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
                               exclude_and_filters=exclude_and_filters, is_expired=is_expired)
    return queryset


def confectionery_dfia(date_range=None, status=None):
    if status == 'expired':
        is_expired = True
    else:
        is_expired = False
    empty_list = []
    dfia_list = []
    if is_expired:
        limit = 20000
    else:
        limit = 1000
    dfia_qs = confectionery_query(date_range, party=[], is_expired=is_expired)
    for dfia in dfia_qs:
        if dfia.get_balance_cif > limit:
            dfia_list.append(dfia)
        else:
            empty_list.append(dfia)
    tables = [
        {'label': 'All DFIA',
         'table': dfia_list},
        {'label': 'NULL DFIA',
         'table': empty_list}
    ]
    return tables


def namkeen_query(date_range=None, party=None, exclude_party=None, is_expired=False):
    tables = []
    query_dict = {
        'export_license__norm_class__norm_class': 'E132',
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
                               exclude_and_filters=exclude_and_filters, is_expired=is_expired)
    return queryset


def tractor_query(date_range=None, party=None, exclude_party=None, is_expired=False, notification_number=N2023):
    tables = []
    query_dict = {
        'export_license__norm_class__norm_class': 'C969',
        'notification_number': notification_number
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
                               exclude_and_filters=exclude_and_filters, is_expired=is_expired)
    return queryset


def steel_query(date_range=None, party=None, exclude_party=None, is_expired=False, notification_number=N2023):
    tables = []
    query_dict = {
        'export_license__norm_class__norm_class__in': ['C471', 'C969', 'C473'],
        'notification_number': notification_number
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
                               exclude_and_filters=exclude_and_filters, is_expired=is_expired)
    return queryset


def namkeen_dfia(date_range=None, status=None):
    if status == 'expired':
        is_expired = True
    else:
        is_expired = False
    empty_list = []
    dfia_list = []
    if is_expired:
        limit = 20000
    else:
        limit = 1000
    dfia_qs = namkeen_query(date_range, party=[], is_expired=is_expired)
    for dfia in dfia_qs:
        if dfia.get_balance_cif > limit:
            dfia_list.append(dfia)
        else:
            empty_list.append(dfia)
    tables = [
        {'label': 'All DFIA',
         'table': dfia_list},
    ]
    if empty_list:
        tables.append({'label': 'NULL DFIA',
                       'table': empty_list})
    return tables


def tractor_dfia(date_range=None, status=None):
    if status == 'expired':
        is_expired = True
    else:
        is_expired = False
    empty_list = []
    dfia_list = []
    if is_expired:
        limit = 50000
    else:
        limit = 999
    dfia_qs = tractor_query(date_range, party=[], is_expired=is_expired)
    for dfia in dfia_qs:
        if dfia.get_balance_cif > limit:
            dfia_list.append(dfia)
        else:
            empty_list.append(dfia)
    tables = [
        {'label': 'All DFIA',
         'table': dfia_list},
    ]
    if empty_list:
        tables.append({'label': 'NULL DFIA',
                       'table': empty_list})
    return tables


def steel_dfia(date_range=None, status=None):
    if status == 'expired':
        is_expired = True
    else:
        is_expired = False
    empty_list = []
    dfia_list = []
    if is_expired:
        limit = 8000
    else:
        limit = 999
    dfia_qs = steel_query(date_range, party=['Grip', 'posco'], is_expired=is_expired)
    for dfia in dfia_qs:
        if dfia.get_balance_cif > limit:
            dfia_list.append(dfia)
        else:
            empty_list.append(dfia)
    tables = [
        {'label': 'All DFIA',
         'table': dfia_list},
    ]
    if empty_list:
        tables.append({'label': 'NULL DFIA',
                       'table': empty_list})
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
    total_dict['balance']['cif'] = round(total_dict['balance']['cif'] + object.get_balance_cif, 2)
    balance = round(object.get_balance_cif, 0)
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


def glass_dfia(date_range=None, status=None):
    if status == 'expired':
        is_expired = True
    else:
        is_expired = False
    empty_list = []
    dfia_list = []
    if is_expired:
        limit = 8000
    else:
        limit = 200
    dfia_qs = glass_query(date_range, party=[], is_expired=is_expired)
    for dfia in dfia_qs:
        if dfia.get_balance_cif > limit:
            dfia_list.append(dfia)
        else:
            empty_list.append(dfia)
    tables = [
        {'label': 'All DFIA',
         'table': dfia_list},
    ]
    if empty_list:
        tables.append({'label': 'NULL DFIA',
                       'table': empty_list})
    return tables


def glass_query(date_range=None, party=None, exclude_party=None, is_expired=False, notification_number=N2023):
    tables = []
    query_dict = {
        'export_license__norm_class__norm_class': 'A3627',
        'notification_number': notification_number
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
                               exclude_and_filters=exclude_and_filters, is_expired=is_expired)
    return queryset


def pickle_dfia(date_range=None, status=None):
    if status == 'expired':
        is_expired = True
    else:
        is_expired = False
    empty_list = []
    dfia_list = []
    if is_expired:
        limit = 8000
    else:
        limit = 500
    dfia_qs = pickle_query(date_range, party=[], is_expired=is_expired)
    for dfia in dfia_qs:
        if dfia.get_balance_cif > limit:
            dfia_list.append(dfia)
        else:
            empty_list.append(dfia)
    tables = [
        {'label': 'All DFIA',
         'table': dfia_list},
    ]
    if empty_list:
        tables.append({'label': 'NULL DFIA',
                       'table': empty_list})
    return tables


def pickle_query(date_range=None, party=None, exclude_party=None, is_expired=False, notification_number=N2023):
    tables = []
    query_dict = {
        'export_license__norm_class__norm_class': 'E126',
        'notification_number': notification_number
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
                               exclude_and_filters=exclude_and_filters, is_expired=is_expired)
    return queryset


def item_filter(date_range=None, item=None):
    tables = []
    item_details = ItemNameModel.objects.get(id=item)
    expiry_limit = datetime.datetime.today() - datetime.timedelta(days=15)
    if item_details.head.name in ['PACKING MATERIAL']:
        queryset = LicenseImportItemsModel.objects.filter(
            Q(item_id=item) & Q(license__license_expiry_date__gte=expiry_limit) & Q(available_quantity__gte=250) & Q(
                available_value__gte=500) & ~Q(license__export_license__norm_class__norm_class='E5'))
        tables.append({'label': item_details.name.title(), 'table': LicenseItemReportTable(queryset),
                       'total': queryset.aggregate(Sum('available_quantity')).get('available_quantity__sum', 0.0)})
    if item_details.head.name in ['MILK & MILK Product']:
        queryset = LicenseImportItemsModel.objects.filter(
            Q(item_id=item) & Q(license__license_expiry_date__gte=expiry_limit) & Q(available_quantity__gte=250) & Q(
                available_value__gte=500) & Q(license__export_license__norm_class__norm_class='E5'))
        tables.append({'label': item_details.name.title(), 'table': LicenseItemReportTable(queryset),
                       'total': queryset.aggregate(Sum('available_quantity')).get('available_quantity__sum', 0.0)})
    elif item_details.name in ['RUTILE']:
        queryset = LicenseImportItemsModel.objects.filter(
            Q(item_id=item) & Q(license__license_expiry_date__gte=expiry_limit) & Q(available_quantity__gte=50) & Q(
                available_value__gte=100))
        tables.append({'label': item_details.name.title(), 'table': RutileLicenseItemReportTable(queryset),
                       'total': queryset.aggregate(Sum('available_quantity')).get('available_quantity__sum', 0.0)})
    else:
        queryset = LicenseImportItemsModel.objects.filter(
            Q(item_id=item) & Q(license__license_expiry_date__gte=expiry_limit) & Q(available_quantity__gte=250) & Q(
                available_value__gte=500))
        tables.append({'label': item_details.name.title(), 'table': LicenseItemReportTable(queryset),
                       'total': queryset.aggregate(Sum('available_quantity')).get('available_quantity__sum', 0.0)})
    return tables
