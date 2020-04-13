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
    for license in LicenseDetailsModel.objects.all():
        if license.get_balance_cif() < 500:
            license.is_null = True
        if not license.is_self:
            license.is_active = False
        elif license.is_expired or not license.is_self or license.get_balance_cif() < 500 or license.is_au:
            license.is_active = False
        else:
            license.is_active = True
        license.save()
    from django.db.models import Q
    LicenseDetailsModel.objects.filter(is_self=True).filter(Q(license_expiry_date=None)|Q(file_number=None)|Q(notification_number=None)|Q(export_license__norm_class=None)).update(is_incomplete=True)
    from datetime import timedelta
    from django.utils import timezone
    expiry_date = (timezone.now() - timedelta(days=90)).date()
    LicenseDetailsModel.objects.filter(license_expiry_date__lte=expiry_date).update(is_expired=True)
    LicenseDetailsModel.objects.filter(import_license__item_details__cif_fc='.01').update(is_individual=True)