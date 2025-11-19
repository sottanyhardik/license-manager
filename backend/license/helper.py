from django.db.models import Sum

from core.constants import DEBIT


def calculate(self):
    """
    DEPRECATED: Use ItemBalanceCalculator.calculate_item_credit_debit() instead.
    This function is kept for backward compatibility.
    """
    from license.services.balance_calculator import ItemBalanceCalculator
    return ItemBalanceCalculator.calculate_item_credit_debit(self)


def round_down(n, decimals=0):
    """
    DEPRECATED: Use round_decimal_down() from core.utils.decimal_utils instead.
    This function is kept for backward compatibility.
    """
    from core.utils.decimal_utils import round_decimal_down
    return round_decimal_down(n, decimals)


def check_license():
    """
    DEPRECATED: Use LicenseValidationService.update_license_flags() instead.
    This function is kept for backward compatibility but updated to use services.
    """
    from license.models import LicenseDetailsModel
    from license.services.validation_service import LicenseValidationService

    for license in LicenseDetailsModel.objects.all():
        # Use service to update flags
        flags = LicenseValidationService.update_license_flags(license)

        # Apply flags to model
        for flag_name, flag_value in flags.items():
            setattr(license, flag_name, flag_value)

        license.save()


def item_wise_debiting(dfia, item_head, item_name=None):
    dict_list = []
    dict_return = {}
    total_qty = 0
    total_cif = 0
    from bill_of_entry.models import RowDetails
    if item_name:
        data = RowDetails.objects.filter(bill_of_entry__product_name__icontains=item_name, transaction_type='D',
                                         sr_number__item__head=item_head,
                                         sr_number__license=dfia).order_by('transaction_type', 'sr_number__item__head',
                                                                           'bill_of_entry__company')
    else:
        data = RowDetails.objects.filter(transaction_type='D',
                                         sr_number__item__head=item_head,
                                         sr_number__license=dfia).order_by('transaction_type', 'sr_number__item__head',
                                                                           'bill_of_entry__company')
    company_data = list(set([c['bill_of_entry__company__name'] for c in
                             data.order_by('transaction_type', 'bill_of_entry__company',
                                           'bill_of_entry__bill_of_entry_date').values(
                                 'bill_of_entry__company__name')]))
    for company in company_data:
        if company:
            if not company in list(dict_return.keys()):
                dict_return[company] = {}
            dict_return[company]['company'] = company
            dict_return[company]['data_list'] = data.filter(bill_of_entry__company__name=company)
            dict_return[company]['sum_total_qty'] = data.filter(bill_of_entry__company__name=company).aggregate(
                Sum('qty')).get('qty__sum', 0.00)
            dict_return[company]['sum_total_cif_fc'] = data.filter(bill_of_entry__company__name=company).aggregate(
                Sum('cif_fc')).get('cif_fc__sum', 0.00)
            dict_return[company]['unit_price'] = round(
                dict_return[company]['sum_total_cif_fc'] / dict_return[company]['sum_total_qty'], 2)
    for company in company_data:
        if company:
            total_qty = total_qty + dict_return[company]['sum_total_qty']
            total_cif = total_cif + dict_return[company]['sum_total_cif_fc']
            dict_list.append(dict_return[company])
    dict_return['item_details'] = dict_list
    return dict_list, total_qty, total_cif


def item_wise_allotment(dfia, item_head, item_name=None):
    from allotment.models import AllotmentItems
    dict_list = []
    dict_return = {}
    total_qty = 0
    total_cif = 0
    if item_name:
        data = AllotmentItems.objects.filter(allotment__item_name__icontains=item_name, allotment__bill_of_entry=None,
                                             item__item__head=item_head,
                                             item__license=dfia, is_boe=False).order_by('item__item__head',
                                                                                        'allotment__company')
    else:
        data = AllotmentItems.objects.filter(item__item__head=item_head, allotment__bill_of_entry=None,
                                             item__license=dfia, is_boe=False).order_by('item__item__head',
                                                                                        'allotment__company')
    company_data = list(set([c['allotment__company__name'] for c in
                             data.order_by('allotment__company').values(
                                 'allotment__company__name')]))
    for company in company_data:
        if company:
            if not company in list(dict_return.keys()):
                dict_return[company] = {}
            dict_return[company]['company'] = company
            dict_return[company]['data_list'] = data.filter(allotment__company__name=company).values()
            dict_return[company]['sum_total_qty'] = data.filter(allotment__company__name=company).aggregate(
                Sum('qty')).get('qty__sum', 0.00)
            dict_return[company]['sum_total_cif_fc'] = data.filter(allotment__company__name=company).aggregate(
                Sum('cif_fc')).get('cif_fc__sum', 0.00)
            dict_return[company]['unit_price'] = round(
                dict_return[company]['sum_total_cif_fc'] / dict_return[company]['sum_total_qty'], 2)

    for company in company_data:
        if company:
            total_qty = total_qty + dict_return[company]['sum_total_qty']
            total_cif = total_cif + dict_return[company]['sum_total_cif_fc']
            dict_list.append(dict_return[company])
    dict_return['item_details'] = dict_list
    return dict_list, total_qty, total_cif


def fetch_item_details(import_item, hs_code, dfia, item_name=None):
    if item_name:
        debiting, total_qty_debits, total_cif_debits = item_wise_debiting(dfia, import_item.head, item_name)
        allotment, total_qty_alloted, total_cif_alloted = item_wise_allotment(dfia, import_item.head, item_name)
    else:
        debiting, total_qty_debits, total_cif_debits = item_wise_debiting(dfia, import_item.head)
        allotment, total_qty_alloted, total_cif_alloted = item_wise_allotment(dfia, import_item.head)
    from license.models import LicenseImportItemsModel
    import_description = ''
    dict_data = {'name': import_description, 'hs_code': hs_code, 'debiting': debiting,
                 'allotment': allotment,
                 'total_debited_qty': total_qty_debits + total_qty_alloted,
                 'sum_total_cif_fc': total_cif_debits + total_cif_alloted,
                 'opening_balance': LicenseImportItemsModel.objects.filter(license=dfia,
                                                                           description__icontains=item_name).aggregate(
                     Sum('quantity')).get('quantity__sum', 0.00)
                 }
    dict_data['balance_qty'] = dict_data['opening_balance'] - dict_data['total_debited_qty']
    if dict_data['total_debited_qty']:
        dict_data['unit_price'] = dict_data['sum_total_cif_fc'] / dict_data['total_debited_qty']
    else:
        dict_data['unit_price'] = 0
    return dict_data
