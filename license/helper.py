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