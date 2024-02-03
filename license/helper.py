from django.db.models import Sum

from allotment.models import AllotmentItems



def calculate(self):
    from license.models import LicenseExportItemModel
    from bill_of_entry.models import RowDetails
    from django.db.models import Sum
    from allotment.models import Debit
    if not self.cif_fc or self.cif_fc == 0:
        credit = LicenseExportItemModel.objects.filter(license=self.license).aggregate(Sum('cif_fc'))['cif_fc__sum']
        debit = RowDetails.objects.filter(sr_number__license=self.license).filter(transaction_type=Debit).aggregate(
            Sum('cif_fc'))[
            'cif_fc__sum']
    else:
        credit = self.cif_fc
        debit = RowDetails.objects.filter(sr_number=self).filter(transaction_type=Debit).aggregate(Sum('cif_fc'))[
            'cif_fc__sum']
    from allotment.models import AllotmentItems
    allotment = \
        AllotmentItems.objects.filter(item=self, allotment__bill_of_entry__bill_of_entry_number__isnull=True).aggregate(
            Sum('cif_fc'))['cif_fc__sum']
    t_debit = 0
    if debit:
        t_debit = t_debit + debit
    if allotment:
        t_debit = t_debit + allotment
    return credit, t_debit


def round_down(n, decimals=0):
    multiplier = 10 ** decimals
    import math
    return math.floor(n * multiplier) / multiplier


def check_license():
    from license.models import LicenseDetailsModel
    from license.models import GE
    for license in LicenseDetailsModel.objects.all():
        if license.get_balance_cif < 500:
            license.is_null = True
        if not license.purchase_status == GE:
            license.is_active = False
        elif license.is_expired or not license.purchase_status == GE or license.get_balance_cif < 500 or license.is_au:
            license.is_active = False
        else:
            license.is_active = True
        license.save()
    from django.db.models import Q
    LicenseDetailsModel.objects.filter(purchase_status=GE).filter(
        Q(license_expiry_date=None) | Q(file_number=None) | Q(notification_number=None) | Q(
            export_license__norm_class=None)).update(is_incomplete=True)
    from datetime import timedelta
    from django.utils import timezone
    expiry_date = (timezone.now() - timedelta(days=90)).date()
    LicenseDetailsModel.objects.filter(license_expiry_date__lte=expiry_date).update(is_expired=True)
    LicenseDetailsModel.objects.filter(import_license__item_details__cif_fc='.01').update(is_individual=True)


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
    dict_list = []
    dict_return = {}
    total_qty = 0
    total_cif = 0
    if item_name:
        data = AllotmentItems.objects.filter(allotment__item_name__icontains=item_name,allotment__bill_of_entry=None, item__item__head=item_head,
                                             item__license=dfia, is_boe=False).order_by('item__item__head',
                                                                                        'allotment__company')
    else:
        data = AllotmentItems.objects.filter(item__item__head=item_head,allotment__bill_of_entry=None,
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
    from core.management.commands.report_fetch import fetch_total
    if item_name:
        debiting, total_qty_debits, total_cif_debits = item_wise_debiting(dfia, import_item.head, item_name)
        allotment, total_qty_alloted, total_cif_alloted = item_wise_allotment(dfia, import_item.head, item_name)
    else:
        debiting, total_qty_debits, total_cif_debits = item_wise_debiting(dfia, import_item.head)
        allotment, total_qty_alloted, total_cif_alloted = item_wise_allotment(dfia, import_item.head)
    from license.models import LicenseImportItemsModel
    dict_data = {'name': import_item.name, 'hs_code': hs_code, 'debiting': debiting,
                 'allotment': allotment,
                 'total_debited_qty': total_qty_debits + total_qty_alloted,
                 'sum_total_cif_fc': total_cif_debits + total_cif_alloted,
                 'opening_balance': LicenseImportItemsModel.objects.filter(license=dfia,
                                                                           item__name__icontains=item_name).aggregate(
                     Sum('quantity')).get('quantity__sum', 0.00)
                 }
    dict_data['balance_qty'] = dict_data['opening_balance'] - dict_data['total_debited_qty']
    if dict_data['total_debited_qty']:
        dict_data['unit_price'] = dict_data['sum_total_cif_fc'] / dict_data['total_debited_qty']
    else:
        dict_data['unit_price'] = 0
    return dict_data
