from django.db import models

# Create your models here.
from django.db.models import Sum, Q
from django.urls import reverse
from django.utils import timezone

from allotment.models import AllotmentItems, Debit, ALLOTMENT
from bill_of_entry.models import RowDetails, ARO
from license.helper import round_down

DFIA = "26"

SCHEME_CODE_CHOICES = (
    (DFIA, '26 - Duty Free Import Authorization'),
)

N2009 = '098/2009'
N2015 = '019/2015'
N2023 = '025/2023'

NOTIFICATION_NORM_CHOICES = (
    (N2015, '019/2015'),
    (N2009, '098/2009'),
    (N2023, '025/2023')
)

GE = 'GE'
MI = 'NP'
IP = 'IP'

LICENCE_PURCHASE = (
    (GE, 'GE Purchase'),
    (MI, 'GE Operating'),
    (IP, 'GE Item Purchase')
)


def license_path(instance, filename):
    return '{0}/{1}'.format(instance.license.license_number, "{0}.pdf".format(instance.type))


class LicenseDetailsModel(models.Model):
    scheme_code = models.CharField(choices=SCHEME_CODE_CHOICES, max_length=10, default=DFIA)
    notification_number = models.CharField(choices=NOTIFICATION_NORM_CHOICES, max_length=10, default=N2023)
    license_number = models.CharField(max_length=50, unique=True)
    license_date = models.DateField(null=True, blank=True)
    license_expiry_date = models.DateField(null=True, blank=True)
    file_number = models.CharField(max_length=30, null=True, blank=True)
    exporter = models.ForeignKey('core.CompanyModel', on_delete=models.CASCADE, null=True, blank=True)
    port = models.ForeignKey('core.PortModel', on_delete=models.CASCADE, null=True, blank=True)
    registration_number = models.CharField(max_length=10, null=True, blank=True)
    registration_date = models.DateField(null=True, blank=True)
    user_comment = models.TextField(null=True, blank=True)
    user_restrictions = models.TextField(null=True, blank=True)
    ledger_date = models.DateField(null=True, blank=True)
    is_audit = models.BooleanField(default=False)
    is_not_registered = models.BooleanField(default=False)
    is_null = models.BooleanField(default=False)
    purchase_status = models.CharField(choices=LICENCE_PURCHASE, max_length=2, default=GE)
    is_au = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    balance_cif = models.FloatField(default=0.0)
    export_item = models.CharField(max_length=255, null=True, blank=True)
    is_incomplete = models.BooleanField(default=False)
    is_expired = models.BooleanField(default=False)
    is_individual = models.BooleanField(default=False)
    ge_file_number = models.IntegerField(default=0)
    fob = models.IntegerField(default=0, null=True, blank=True)
    created_on = models.DateField(auto_created=True, null=True, blank=True)
    created_by = models.ForeignKey('auth.User', on_delete=models.PROTECT, null=True, blank=True,
                                   related_name='dfia_created')
    modified_on = models.DateField(auto_now=True)
    modified_by = models.ForeignKey('auth.User', on_delete=models.PROTECT, null=True, blank=True,
                                    related_name='dfia_updated')
    cheese_unit = models.FloatField(default=0)
    juice_unit = models.FloatField(default=0)
    wpc_unit = models.FloatField(default=0)
    yeast_unit = models.FloatField(default=0)
    gluten_unit = models.FloatField(default=0)
    palmolein_unit = models.FloatField(default=0)
    billing_rate = models.FloatField(default=0)
    billing_amount = models.FloatField(default=0)
    is_item = models.CharField(default="gluten,palmolein,yeast,juice,milk,Packing Material", max_length=255)
    admin_search_fields = ('license_number',)

    def __str__(self):
        return self.license_number

    class Meta:
        ordering = ('license_expiry_date',)

    @property
    def get_norm_class(self):
        return ','.join([export.norm_class.norm_class for export in self.export_license.all() if export.norm_class])

    def get_absolute_url(self):
        return reverse('license-detail', kwargs={'license': self.license_number})

    @property
    def get_total_debit(self):
        alloted = AllotmentItems.objects.filter(item__license=self, allotment__type=ARO,
                                                allotment__bill_of_entry__bill_of_entry_number__isnull=True).aggregate(
            Sum('cif_fc'))['cif_fc__sum']
        debited = \
            RowDetails.objects.filter(sr_number__license=self).filter(transaction_type=Debit).aggregate(Sum('cif_fc'))[
                'cif_fc__sum']
        if debited and alloted:
            total = debited + alloted
        elif alloted:
            total = alloted
        elif debited:
            total = debited
        else:
            total = 0
        return round(total, 0)

    @property
    def get_total_allotment(self):
        total = AllotmentItems.objects.filter(item__license=self, allotment__type=ALLOTMENT,
                                              allotment__bill_of_entry__bill_of_entry_number__isnull=True).aggregate(
            Sum('cif_fc'))['cif_fc__sum']
        if total:
            return total
        else:
            return 0

    @property
    def get_balance_cif(self):
        credit = LicenseExportItemModel.objects.filter(license=self).aggregate(Sum('cif_fc'))['cif_fc__sum']
        debit = \
            RowDetails.objects.filter(sr_number__license=self).filter(transaction_type=Debit).aggregate(Sum('cif_fc'))[
                'cif_fc__sum']
        allotment = AllotmentItems.objects.filter(item__license=self,
                                                  allotment__bill_of_entry__bill_of_entry_number__isnull=True).aggregate(
            Sum('cif_fc'))['cif_fc__sum']
        t_debit = 0
        if debit:
            t_debit = t_debit + debit
        if allotment:
            t_debit = t_debit + allotment
        if credit and t_debit:
            value = round(credit - t_debit, 0)
        elif credit:
            value = round(credit, 0)
        else:
            value = 0
        if value > 0:
            return value
        else:
            return 0

    @property
    def opening_balance(self):
        return self.export_license.all().aggregate(sum=Sum('cif_fc'))['sum']

    @property
    def opening_fob(self):
        return self.export_license.all().aggregate(sum=Sum('fob_inr'))['sum']

    def opening_cif_inr(self):
        return self.export_license.all().aggregate(sum=Sum('cif_inr'))['sum']

    @property
    def get_chickpeas_obj(self):
        return self.import_license.filter(
            Q(item__name__icontains='Chickpeas') | Q(item__name__icontains='Green Peas') | Q(
                item__name__icontains='Lentils'))

    @property
    def get_glass_formers(self):
        object = self.import_license.filter(item__name__icontains='Glass Formers')
        if object.first():
            return object.first()
        else:
            return None

    @property
    def get_intermediates_namely(self):
        object = self.import_license.filter(
            Q(item__name__icontains='Intermediates namely') | Q(item__name__icontains='Aluminium Oxide'))
        if object.first():
            return object.first()
        else:
            return None

    @property
    def get_other_special_additives(self):
        object = self.import_license.filter(item__name__icontains='Other Special Additives')
        if object.first():
            return object.first()
        else:
            return None

    @property
    def get_hot_rolled(self):
        object = self.import_license.filter(item__name__icontains='HOT ROLLED')
        if object.first():
            return object.first()
        else:
            return None

    @property
    def get_bearing(self):
        object = self.import_license.filter(item__name__icontains='Bearing')
        if object.first():
            return object.first()
        else:
            return None

    @property
    def get_modifiers_namely(self):
        object = self.import_license.filter(item__name__icontains='Modifiers namely')
        if object.first():
            return object.first()
        else:
            return None

    @property
    def get_pickle_oil(self):
        object = self.import_license.filter(
            Q(item__name__icontains='Fats and Oils') | Q(item__name__icontains='Oils and Fats') | Q(
                item__name__icontains='Salad Oil'))
        if object.first():
            return object.first()
        else:
            return None

    @property
    def get_rfa(self):
        object = self.import_license.filter(
            Q(item__name__icontains='Food Additives') | Q(item__name__icontains='Food Additive') | Q(
                item__name__icontains='0908'))
        if object.first():
            return object.first()
        else:
            return None

    @property
    def get_chickpeas(self):
        all = self.get_chickpeas_obj
        sum1 = 0
        for d in all:
            sum1 += d.balance_quantity
        return sum1

    @property
    def get_hs_steel(self):
        all = self.import_license.all()
        return all

    @property
    def get_battery_obj(self):
        return self.import_license.filter(item__name__icontains='battery')

    @property
    def get_alloy_steel_obj(self):
        return self.import_license.filter(item__name__icontains='alloy steel')

    @property
    def get_hot_rolled_obj(self):
        return self.import_license.filter(item__name__icontains='HOT ROLLED')

    @property
    def get_bearing_obj(self):
        return self.import_license.filter(item__name__icontains='Bearing')

    @property
    def get_battery_total(self):
        items = self.get_battery_obj
        return sum(item.quantity for item in items)

    @property
    def get_battery_balance(self):
        items = self.get_battery_obj
        return sum(item.balance_quantity for item in items)

    @property
    def get_alloy_steel_total(self):
        items = self.get_alloy_steel_obj
        return sum(item.quantity for item in items)

    @property
    def get_alloy_steel_balance(self):
        items = self.get_alloy_steel_obj
        return sum(item.balance_quantity for item in items)

    @property
    def get_hot_rolled_total(self):
        items = self.get_hot_rolled_obj
        return sum(item.quantity for item in items)

    @property
    def get_hot_rolled_balance(self):
        items = self.get_hot_rolled_obj
        return sum(item.balance_quantity for item in items)

    @property
    def get_bearing_total(self):
        items = self.get_bearing_obj
        return sum(item.quantity for item in items)

    @property
    def get_bearing_balance(self):
        items = self.get_bearing_obj
        return sum(item.balance_quantity for item in items)

    def wheat(self):
        return self.import_license.filter(item__head__name__icontains='wheat').first()

    def get_sugar(self):
        all = self.import_license.filter(item__head__name__icontains='sugar')
        sum1 = 0
        for d in all:
            sum1 += d.balance_quantity
        return sum1

    def sugar(self):
        return self.import_license.filter(item__head__name__icontains='sugar').first()

    @property
    def get_rbd(self):
        all = self.import_license.filter(Q(item__name__icontains='rbd')).exclude(
            Q(item__name__icontains='1513') | Q(item__name__icontains='1509') | Q(
                item__name__icontains='Edible Vegtable') | Q(
                item__name__icontains='150000') | Q(item__name__icontains='Edible Vegetable Oil /') | Q(
                item__name__icontains='Edible Vegetable Oil/'))
        sum1 = 0
        for d in all:
            sum1 += d.balance_quantity
        return sum1

    @property
    def oil_queryset(self):
        rbd = self.import_license.filter(Q(item__name__icontains='rbd') | Q(item__name__icontains='1513') | Q(
            item__name__icontains='Edible Vegtable Oil') | Q(item__name__icontains='Edible Vegetable Oi')).distinct()
        return rbd

    @property
    def rbd_pd(self):
        rbd = self.oil_queryset
        if rbd:
            return rbd.first().item.name
        else:
            return "Missing"

    @property
    def oil_queryset_total(self):
        all = self.oil_queryset
        sum1 = 0
        for d in all:
            sum1 += d.balance_quantity
        return sum1

    @property
    def get_rbd_cif(self):
        qty = self.get_rbd
        if qty and qty > 100:
            required_cif = self.get_rbd * 1
            balance_cif = self.get_balance_cif - self.get_wpc_cif - self.get_total_quantity_of_ff_df_cif
            if required_cif <= balance_cif:
                return required_cif
            else:
                if balance_cif > 0:
                    return balance_cif
                else:
                    return 0
        else:
            return 0

    @property
    def get_pko(self):
        all = self.import_license.filter(
            Q(item__name__icontains='1513') | Q(item__name__icontains="Vegetable Oil")).exclude(
            Q(item__name__icontains='1509') | Q(item__name__icontains='1509') | Q(
                item__name__icontains='Edible Vegtable') | Q(
                item__name__icontains='150000') | Q(item__name__icontains='Edible Vegetable Oil /') | Q(
                item__name__icontains='Edible Vegetable Oil/'))
        sum1 = 0
        for d in all:
            sum1 += d.balance_quantity
        return sum1

    @property
    def get_veg_oil(self):
        all = self.import_license.filter(
            Q(item__name__icontains='1509') | Q(item__name__icontains='Edible Vegtable') | Q(
                item__name__icontains='150000') | Q(item__name__icontains='Edible Vegetable Oil /') | Q(
                item__name__icontains='Edible Vegetable Oil/') | Q(item__name__icontains='Edible Vegetable Oil'))
        sum1 = 0
        for d in all:
            sum1 += d.balance_quantity
        return sum1

    @property
    def get_pko_cif(self):
        qty = self.get_pko
        if qty and qty > 100:
            balance_cif = self.get_balance_cif - self.get_cheese_cif - self.get_total_quantity_of_ff_df_cif - self.get_swp_cif
            required_cif = qty * 1
            if required_cif <= balance_cif:
                return required_cif
            else:
                if balance_cif > 0:
                    return balance_cif
                else:
                    return 0
        else:
            return 0

    @property
    def get_veg_oil_cif(self):
        qty = self.get_veg_oil
        if qty and qty > 100:
            balance_cif = self.get_balance_cif - self.get_cheese_cif - self.get_total_quantity_of_ff_df_cif - self.get_swp_cif
            if balance_cif > 0:
                return balance_cif
            else:
                return 0
        else:
            return 0

    @property
    def get_cmc_obj(self):
        return self.import_license.filter(
            Q(item__name__icontains='Additives'))

    @property
    def get_cmc(self):
        sum1 = 0
        all = self.get_cmc_obj
        for d in all:
            sum1 += d.balance_quantity
        return sum1

    @property
    def get_food_flavour_namkeen_obj(self):
        return self.import_license.filter(
            Q(item__name__icontains='pepper') | Q(item__name__icontains='food flavour') | Q(
                item__name__icontains='Cardamom') | Q(
                item__name__icontains='Cardamon')).distinct()

    @property
    def get_food_flavour_confectionery_obj(self):
        return self.import_license.filter(Q(item__name__icontains='Flavour') |
                                          Q(item__name__icontains='Fruit Flavour') | Q(
            item__name__icontains='food flavour')).distinct()

    @property
    def get_food_flavour_confectionery_obj_qty(self):
        sum1 = 0
        all = self.get_food_flavour_confectionery_obj
        for d in all:
            sum1 += d.balance_quantity
        return sum1

    @property
    def get_food_flavour_confectionery_hsn(self):
        food_flavour_confectionery_obj = self.get_food_flavour_confectionery_obj
        first_item = food_flavour_confectionery_obj.first()
        return str(first_item.hs_code) if first_item else 'Missing'

    @property
    def get_food_flavour_confectionery_pd(self):
        food_flavour_confectionery_obj = self.get_food_flavour_confectionery_obj
        first_item = food_flavour_confectionery_obj.first()
        return str(first_item.item.name) if first_item else 'Missing'

    @property
    def get_food_flavour_namkeen(self):
        sum1 = 0
        all = self.get_food_flavour_namkeen_obj
        for d in all:
            sum1 += d.balance_quantity
        return sum1

    @property
    def get_food_flavour_qs(self):
        all = self.import_license.filter(Q(item__name__icontains='flavour'))
        return all

    @property
    def get_food_flavour_pd(self):
        sum1 = 0
        all = self.get_food_flavour_qs
        if all.first():
            return all.first().item.name
        else:
            return "Missing"

    @property
    def get_food_flavour_tq(self):
        sum1 = 0
        all = self.get_food_flavour_qs
        for d in all:
            sum1 += d.balance_quantity
        return sum1

    @property
    def get_food_flavour(self):
        sum1 = 0
        all = self.import_license.filter(
            Q(item__name__icontains='0802') & Q(item__name__icontains='food flavour')).exclude(
            Q(hs_code__hs_code__istartswith='2009') | Q(item__name__icontains='2009'))
        for d in all:
            sum1 += d.balance_quantity
        return sum1

    @property
    def get_food_flavour_juice(self):
        sum1 = 0
        all = self.import_license.filter(Q(item__name__icontains='juice') | Q(item__name__icontains='2009') | Q(
            hs_code__hs_code__istartswith='2009'))
        for d in all:
            sum1 += d.balance_quantity
        return sum1

    @property
    def get_dietary_fibre(self):
        sum1 = 0
        all = self.import_license.filter(
            Q(item__name__icontains='0802') & Q(item__name__icontains='dietary fibre')).exclude(
            item__name__icontains='juice')
        for d in all:
            sum1 += d.balance_quantity
        return sum1

    @property
    def get_total_quantity_of_ff_df_cif(self):
        balance_cif = self.get_balance_cif
        per_cif = self.get_per_cif
        if balance_cif < per_cif:
            per_cif = balance_cif
        product_description = self.get_food_flavour_pd
        if 'Missing' in product_description:
            return 0
        elif '0908' in product_description:
            required = self.get_food_flavour * 6.22
        elif '2009' in product_description:
            required = self.get_food_flavour_juice * 2.5
        else:
            required = 0
        required = required + self.get_fruit * 2.5
        if required > per_cif:
            return per_cif
        else:
            return required
        # qty = self.get_total_quantity_of_ff_df
        # if qty and qty > 100:
        #     balance_cif = self.get_balance_cif
        #     required_cif = qty * 2
        #     if required_cif <= balance_cif:
        #         return required_cif
        #     else:
        #         if balance_cif > 0:
        #             return balance_cif
        #         else:
        #             return 0
        # else:
        #     return 0

    @property
    def get_wheat_starch(self):
        sum1 = 0
        all = self.import_license.filter(
            Q(item__head__name__icontains='starch') & Q(hs_code__hs_code__istartswith='11'))
        for d in all:
            sum1 += d.balance_quantity
        return sum1

    @property
    def get_modified_starch(self):
        sum1 = 0
        all = self.import_license.filter(
            Q(item__head__name__icontains='starch') & Q(hs_code__hs_code__istartswith='35'))
        for d in all:
            sum1 += d.balance_quantity
        return sum1

    @property
    def get_starch_cif(self):
        qty = self.get_wheat_starch + self.get_modified_starch
        if qty and qty > 100:
            required_cif = qty * 1
            balance_cif = self.get_balance_cif - self.get_pko_cif - self.get_total_quantity_of_ff_df_cif
            if required_cif <= balance_cif:
                return required_cif
            else:
                if balance_cif > 0:
                    return balance_cif
                else:
                    return 0
        else:
            return 0

    @property
    def get_leavening_agent(self):
        sum1 = 0
        all = self.import_license.filter(Q(item__name__icontains='Leavening Agent'))
        for d in all:
            sum1 += d.balance_quantity
        return sum1

    @property
    def get_fruit(self):
        """
        Query Balance Cocoa Quantity
        @return: Total Balance Quantity of Cocoa
        """
        return sum(
            [item.balance_quantity for item in self.import_license.filter(Q(hs_code__hs_code__istartswith='18050000'))])

    @property
    def get_mnm_qs(self):
        """
        Query Balance Cheese Quantity
        @return: Total Balance Quantity of Cheese
        """
        return self.import_license.filter(Q(item__name__icontains='milk'))

    @property
    def get_mnm_pd(self):
        """
        Query Balance Cheese Quantity
        @return: Total Balance Quantity of Cheese
        """
        all = self.get_mnm_qs
        if all.first():
            return all.first().item.name
        else:
            return 0

    @property
    def get_mnm_tq(self):
        """
        Query Balance Cheese Quantity
        @return: Total Balance Quantity of Cheese
        """
        all = self.get_mnm_qs
        return sum([item.balance_quantity for item in all])

    @property
    def get_cheese(self):
        """
        Query Balance Cheese Quantity
        @return: Total Balance Quantity of Cheese
        """
        return sum([item.balance_quantity for item in
                    self.import_license.filter(Q(item__name__icontains='0406') & Q(item__name__icontains='milk'))])

    @property
    def get_cheese_cif(self):
        qty = self.get_cheese
        if qty and qty > 100:
            balance_cif = self.get_balance_cif
            required_cif = qty * 6.8
            if required_cif <= balance_cif:
                return required_cif
            else:
                if balance_cif > 0:
                    return balance_cif
                else:
                    return 0
        else:
            return 0

    @property
    def get_wpc(self):
        """
                Query Balance WPC Quantity
                @return: Total Balance Quantity of WPC
        """
        return sum([item.balance_quantity for item in
                    self.import_license.filter(item__name__icontains='milk').exclude(
                        Q(item__name__icontains='0406') | Q(item__name__icontains='0404'))])

    @property
    def get_swp(self):
        """
                Query Balance WPC Quantity
                @return: Total Balance Quantity of WPC
        """
        return sum([item.balance_quantity for item in
                    self.import_license.filter(item__name__icontains='0404').exclude(item__name__icontains='0406')])

    @property
    def get_wpc_cif(self):
        qty = self.get_wpc
        if qty and qty > 100:
            required_cif = qty * 5.5
            balance_cif = self.get_balance_cif - self.get_pko_cif - self.get_total_quantity_of_ff_df_cif - self.get_starch_cif
            if required_cif <= balance_cif:
                return required_cif
            else:
                if balance_cif > 0:
                    return balance_cif
                else:
                    return 0
        else:
            return 0

    @property
    def get_swp_cif(self):
        qty = self.get_swp
        if qty and qty > 100:
            required_cif = qty * 1
            balance_cif = self.get_balance_cif - self.get_total_quantity_of_ff_df_cif
            if required_cif <= balance_cif:
                return required_cif
            else:
                if balance_cif > 0:
                    return balance_cif
                else:
                    return 0
        else:
            return 0

    @property
    def cif_value_balance(self):
        balance_cif = self.get_balance_cif - self.get_pko_cif - self.get_cheese_cif - self.get_wpc_cif - self.get_total_quantity_of_ff_df_cif - self.get_rbd_cif - self.get_veg_oil_cif - self.get_swp_cif
        if balance_cif >= 0:
            return balance_cif
        else:
            return -1

    @property
    def get_pp_pd(self):
        all = self.import_license.filter(
            item__head__name__icontains='pp'
        )
        if all.first():
            return all.first().item.name
        else:
            return 'Missing'

    @property
    def get_pp(self):
        all_imports = self.import_license.filter(
            item__head__name__icontains='pp'
        ).exclude(
            item__name__icontains='aluminium'
        )
        total_quantity = sum(entry.balance_quantity for entry in all_imports)
        return total_quantity

    @property
    def get_aluminium(self):
        all_entries = self.import_license.filter(Q(item__name__icontains='Aluminium') | Q(item__name__icontains='7607'))
        total_quantity = sum(entry.balance_quantity for entry in all_entries)
        return total_quantity

    @property
    def get_paper_and_paper_qs(self):
        all = self.import_license.filter(Q(item__name__icontains='paper')).exclude(item__name__icontains='7607')
        return all

    @property
    def get_paper_and_paper_pd(self):
        all = self.get_paper_and_paper_qs
        if all.first():
            return all.first().item.name
        else:
            return 'Missing'

    @property
    def get_paper_and_paper_hsn(self):
        all = self.get_paper_and_paper_qs
        if all.first():
            return str(all.first().hs_code)
        else:
            return 'Missing'

    @property
    def get_pp_qs(self):
        all = self.import_license.filter(Q(hs_code__hs_code__istartswith='3902'))
        return all

    @property
    def get_pp_pd(self):
        all = self.get_pp_qs
        if all.first():
            return all.first().item.name
        else:
            return 'Missing'

    @property
    def get_pp_hsn(self):
        all = self.get_pp_qs
        if all.first():
            return str(all.first().hs_code)
        else:
            return 'Missing'

    @property
    def get_paper_and_paper(self):
        sum1 = 0
        all = self.get_paper_and_paper_qs
        for d in all:
            sum1 += d.balance_quantity
        return sum1

    @property
    def get_juice(self):
        sum1 = 0
        all = self.import_license.filter(Q(item__name__icontains='Relevant Fruit') | Q(item__name__icontains='juice'))
        for d in all:
            sum1 += d.balance_quantity
        return sum1

    @property
    def get_tartaric_acid(self):
        sum1 = 0
        all = self.import_license.filter(item__head__name__icontains='acid')
        for d in all:
            sum1 += d.balance_quantity
        return sum1

    @property
    def get_orange_essential_pd(self):
        all = self.import_license.filter(
            Q(item__head__name__icontains='Essential oil'))
        if all.first():
            return all.first().item.name
        else:
            return 'Missing'

    @property
    def get_orange_essential_total(self):
        sum1 = 0
        all = self.import_license.filter(
            Q(item__head__name__icontains='Essential oil'))
        for d in all:
            if d:
                sum1 += d.balance_quantity
        return sum1

    @property
    def get_orange_essential_oil(self):
        sum1 = 0
        all = self.import_license.filter(
            Q(item__head__name__icontains='Essential oil')).exclude(
            Q(item__name__icontains='lemon') & Q(item__name__icontains='pippermint'))
        for d in all:
            if d:
                sum1 += d.balance_quantity
        return sum1

    @property
    def get_lemon_essential_oil(self):
        sum1 = 0
        all = self.import_license.filter(
            Q(item__head__name__icontains='Essential Oil') & Q(item__name__icontains='lemon'))
        for d in all:
            if d:
                sum1 += d.balance_quantity
        return sum1

    @property
    def get_pippermint_essential_oil(self):
        sum1 = 0
        all = self.import_license.filter(
            Q(item__head__name__icontains='essential oil') & Q(item__name__icontains='pippermint'))
        for d in all:
            if d:
                sum1 += d.balance_quantity
        return sum1

    def get_other_confectionery(self):
        sum1 = 0
        all = self.import_license.filter(item__head__name__icontains='other confectionery')
        for d in all:
            sum1 += d.balance_quantity
        return sum1

    def get_other_confectionery_pd(self):
        all = self.import_license.filter(item__head__name__icontains='other confectionery')
        if all.first():
            return all.first().item.name
        else:
            return 'Missing'

    def get_starch_confectionery(self):
        from django.db.models import Q
        return self.import_license.filter(Q(item__head__name__icontains='starch') | Q(
            item__head__name__icontains='emulsifier')).first().balance_quantity

    def get_party_name(self):
        return str(self.exporter)[:8]

    def get_required_sugar_value(self):
        return round(self.get_sugar() * 0.330, 0)

    def get_required_rbd_value(self):
        return round(self.get_rbd() * 0.800, 0)

    def get_required_mnm_value(self):
        return round(self.get_m_n_m() * 5, 0)

    @property
    def get_per_cif(self):
        lic = LicenseExportItemModel.objects.filter(license=self)
        credit = LicenseExportItemModel.objects.filter(license=self).aggregate(Sum('cif_fc'))['cif_fc__sum']
        if 'E1' in str(lic[0].norm_class):
            credit = credit * .02
            imports = LicenseImportItemsModel.objects.filter(license=self).filter(
                Q(item__head__name__icontains='other'))
        else:
            credit = credit * .1
            imports = LicenseImportItemsModel.objects.filter(license=self).filter(
                Q(item__head__name__icontains='flavour') | Q(item__head__name__icontains='fruit') | Q(
                    item__head__name__icontains='dietary') | Q(
                    item__head__name__icontains='Leavening') | Q(
                    item__head__name__icontains='starch') | Q(
                    item__head__name__icontains='Coco'))
        for dimport in imports:
            if dimport.alloted_value:
                credit = credit - dimport.debited_value - int(dimport.alloted_value)
            else:
                credit = credit - dimport.debited_value
        if credit > 0:
            return round_down(credit)
        else:
            return 0

    @property
    def get_per_essential_oil(self):
        lic = LicenseExportItemModel.objects.filter(license=self)
        credit = LicenseExportItemModel.objects.filter(license=self).aggregate(Sum('cif_fc'))['cif_fc__sum']
        if 'E1' in str(lic[0].norm_class):
            credit = credit * .05
            imports = LicenseImportItemsModel.objects.filter(license=self).filter(
                Q(item__name__icontains='essential oil') | Q(item__head__name__icontains='food flavour') | Q(
                    item__name__icontains='Flavour') |
                Q(item__name__icontains='Fruit Flavour') | Q(item__name__icontains='food flavour'))
        else:
            imports = []
        for dimport in imports:
            if dimport.alloted_value:
                credit = credit - dimport.debited_value - int(dimport.alloted_value)
            else:
                credit = credit - dimport.debited_value
        if credit > 0:
            return round_down(credit)
        else:
            return 0

    @property
    def get_per_black_pepper_cif(self):
        lic = LicenseExportItemModel.objects.filter(license=self)
        credit = LicenseExportItemModel.objects.filter(license=self).aggregate(Sum('cif_fc'))['cif_fc__sum']
        if 'E132' in str(lic[0].norm_class):
            credit = credit * .03
            imports = LicenseImportItemsModel.objects.filter(license=self).filter(
                Q(item__name__icontains='pepper'))
        else:
            imports = []
        for dimport in imports:
            if dimport.alloted_value:
                credit = credit - dimport.debited_value - int(dimport.alloted_value)
            else:
                credit = credit - dimport.debited_value
        if credit > 0:
            return round_down(credit)
        else:
            return 0

    @property
    def get_cmc_cif(self):
        lic = LicenseExportItemModel.objects.filter(license=self)
        credit = LicenseExportItemModel.objects.filter(license=self).aggregate(Sum('cif_fc'))['cif_fc__sum']
        if 'E132' in str(lic[0].norm_class):
            credit = credit * .05
            imports = LicenseImportItemsModel.objects.filter(license=self).filter(
                Q(item__name__icontains='Additives'))
        else:
            imports = []
        for dimport in imports:
            if dimport.alloted_value:
                credit = credit - dimport.debited_value - int(dimport.alloted_value)
            else:
                credit = credit - dimport.debited_value
        if credit > 0:
            return round_down(credit)
        else:
            return 0

    def get_balance_value(self):
        if self.get_norm_class == 'E5':
            return round(
                self.get_balance_cif - self.get_required_sugar_value() - self.get_required_rbd_value() - self.get_required_mnm_value(),
                0)
        else:
            return round(self.get_balance_cif - self.get_required_sugar_value(), 0)


KG = 'kg'

UNIT_CHOICES = (
    (KG, 'kg'),
)

USD = 'usd'
EURO = 'euro'

CURRENCY_CHOICES = (
    (USD, 'usd'),
    (EURO, 'euro'),
)


class LicenseExportItemModel(models.Model):
    license = models.ForeignKey('license.LicenseDetailsModel', on_delete=models.CASCADE,
                                related_name='export_license')
    item = models.ForeignKey('core.ItemNameModel', related_name='export_licenses', on_delete=models.CASCADE, null=True,
                             blank=True)
    norm_class = models.ForeignKey('core.SionNormClassModel', null=True, blank=True, on_delete=models.CASCADE,
                                   related_name='export_item')
    duty_type = models.CharField(max_length=255, default='Basic')
    net_quantity = models.FloatField(default=0)
    old_quantity = models.FloatField(default=0)
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default=KG)
    fob_fc = models.FloatField(default=0)
    fob_inr = models.FloatField(default=0)
    fob_exchange_rate = models.FloatField(default=0)
    currency = models.CharField(choices=CURRENCY_CHOICES, default=USD, max_length=5)
    value_addition = models.FloatField(default=15)
    cif_fc = models.FloatField(default=0)
    cif_inr = models.FloatField(default=0)

    def __str__(self):
        try:
            return str(self.item.name)
        except:
            return ''

    def balance_cif_fc(self):
        if not self.cif_fc or self.cif_fc == 0:
            credit = LicenseExportItemModel.objects.filter(license=self.license).aggregate(Sum('cif_fc'))['cif_fc__sum']
        else:
            credit = self.cif_fc
        debit = RowDetails.objects.filter(sr_number__license=self.license).filter(transaction_type=Debit).aggregate(
            Sum('cif_fc'))[
            'cif_fc__sum']
        allotment = AllotmentItems.objects.filter(item__license=self.license,
                                                  allotment__bill_of_entry__bill_of_entry_number__isnull=True).aggregate(
            Sum('cif_fc'))['cif_fc__sum']
        t_debit = 0
        if debit:
            t_debit = t_debit + debit
        if allotment:
            t_debit = t_debit + allotment
        if self.cif_fc:
            return int(credit - t_debit)
        else:
            "Error"


class LicenseImportItemsModel(models.Model):
    serial_number = models.IntegerField(default=0)
    license = models.ForeignKey('license.LicenseDetailsModel', on_delete=models.CASCADE, related_name='import_license')
    hs_code = models.ForeignKey('core.HSCodeModel', on_delete=models.CASCADE, null=True, blank=True,
                                related_name='import_item')
    item = models.ForeignKey('core.ItemNameModel', related_name='license_items', on_delete=models.CASCADE, null=True,
                             blank=True)
    duty_type = models.CharField(max_length=255, default='Basic')
    quantity = models.FloatField(default=0)
    old_quantity = models.FloatField(default=0)
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default=KG)
    cif_fc = models.FloatField(null=True, blank=True)
    cif_inr = models.FloatField(default=0)
    restricted_value_in_percentage = models.FloatField(default=0)
    restricted_value_per_unit = models.FloatField(default=0)
    blocked_value = models.FloatField(default=0.00)
    blocked_quantity = models.FloatField(default=0.00)
    available_quantity = models.FloatField(default=0.00)
    available_value = models.FloatField(default=0.00)
    is_restrict = models.BooleanField(default=False)
    comment = models.TextField(null=True, blank=True)
    admin_search_fields = ('license__license_number',)

    class Meta:
        ordering = ['license__license_expiry_date', 'serial_number']

    def __str__(self):
        return "{0}-{1}".format(str(self.license), str(self.serial_number))

    @property
    def debited_quantity(self):
        debited = self.item_details.filter(transaction_type='D').aggregate(Sum('qty'))['qty__sum']
        alloted = self.allotment_details.filter(allotment__type=ARO).aggregate(Sum('qty'))['qty__sum']
        if debited and alloted:
            total = debited + alloted
        elif alloted:
            total = alloted
        elif debited:
            total = debited
        else:
            total = 0
        return round(total, 0)

    @property
    def alloted_quantity(self):
        alloted = self.allotment_details.filter(allotment__bill_of_entry__bill_of_entry_number__isnull=True,
                                                allotment__type=ALLOTMENT).aggregate(
            Sum('qty'))['qty__sum']
        if alloted:
            return alloted
        else:
            return 0

    @property
    def required_cif(self):
        if self.balance_quantity > 100:
            required = round(self.balance_quantity * self.item.head.unit_rate, 0) + 10
            return required
        else:
            return 0

    @property
    def balance_quantity(self):
        if self.item and self.item.head and self.item.head.is_restricted and self.old_quantity:
            credit = self.old_quantity
        elif self.item and self.item.head and self.item.head.is_restricted and self.license.notification_number == N2015:
            credit = self.quantity
        else:
            credit = self.quantity
        debit = self.debited_quantity
        alloted = self.alloted_quantity
        if debit and alloted:
            value = round_down(credit - debit - alloted, 0)
        elif debit:
            value = round_down(credit - debit, 0)
        elif alloted:
            value = round_down((credit - alloted), 0)
        else:
            value = round_down(credit, 0)
        if value > 0:
            return value
        else:
            return 0

    @property
    def debited_value(self):
        debited = self.item_details.filter(transaction_type='D').aggregate(Sum('cif_fc'))['cif_fc__sum']
        alloted = self.allotment_details.filter(allotment__type=ARO).aggregate(Sum('cif_fc'))['cif_fc__sum']
        if debited and alloted:
            total = debited + alloted
        elif alloted:
            total = alloted
        elif debited:
            total = debited
        else:
            total = 0
        return round(total, 0)

    @property
    def alloted_value(self):
        return self.allotment_details.filter(allotment__bill_of_entry__bill_of_entry_number__isnull=True,
                                             allotment__type=ALLOTMENT).aggregate(
            Sum('cif_fc'))['cif_fc__sum']

    @property
    def balance_cif_fc(self):
        if not self.cif_fc or int(self.cif_fc) == 0 or self.cif_fc == 0.1:
            credit = LicenseExportItemModel.objects.filter(license=self.license).aggregate(Sum('cif_fc'))['cif_fc__sum']
        else:
            credit = self.cif_fc
        if not self.cif_fc or self.cif_fc == 0.01:
            debit = RowDetails.objects.filter(sr_number__license=self.license).filter(transaction_type=Debit).aggregate(
                Sum('cif_fc'))[
                'cif_fc__sum']
            allotment = AllotmentItems.objects.filter(item__license=self.license,
                                                      allotment__bill_of_entry__bill_of_entry_number__isnull=True).aggregate(
                Sum('cif_fc'))['cif_fc__sum']
        else:
            debit = RowDetails.objects.filter(sr_number=self).filter(transaction_type=Debit).aggregate(
                Sum('cif_fc'))[
                'cif_fc__sum']
            allotment = AllotmentItems.objects.filter(item=self,
                                                      allotment__bill_of_entry__bill_of_entry_number__isnull=True).aggregate(
                Sum('cif_fc'))['cif_fc__sum']
        t_debit = 0
        if debit:
            t_debit = t_debit + debit
        if allotment:
            t_debit = t_debit + allotment
        return int(credit - t_debit)

    @property
    def license_expiry(self):
        return self.license.license_expiry_date

    @property
    def license_date(self):
        return self.license.license_date

    @property
    def sorted_item_list(self):
        dict_list = []
        dict_return = {}
        data = self.item_details.order_by('transaction_type', 'bill_of_entry__company',
                                          'bill_of_entry__bill_of_entry_date')
        company_data = list(set([c['bill_of_entry__company__name'] for c in
                                 self.item_details.order_by('transaction_type', 'bill_of_entry__company',
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
                dict_return[company]['sum_total_cif_inr'] = data.filter(bill_of_entry__company__name=company).aggregate(
                    Sum('cif_inr')).get('cif_inr__sum', 0.00)
        for company in company_data:
            if company:
                dict_list.append(dict_return[company])
        dict_return['item_details'] = dict_list
        return dict_return

    @property
    def total_debited_qty(self):
        return self.item_details.filter(transaction_type='D').aggregate(Sum('qty')).get('qty__sum', 0.00)

    @property
    def total_debited_cif_fc(self):
        debited = self.item_details.filter(transaction_type='D').aggregate(Sum('cif_fc')).get('cif_fc__sum', 0.00)
        alloted = self.allotment_details.filter(allotment__bill_of_entry__bill_of_entry_number__isnull=True,
                                                allotment__type=ARO).aggregate(Sum('cif_fc'))['cif_fc__sum']
        if debited and alloted:
            total = debited + alloted
        elif alloted:
            total = alloted
        elif debited:
            total = debited
        else:
            total = 0
        return round(total, 0)

    @property
    def total_debited_cif_inr(self):
        return self.item_details.filter(transaction_type='D').aggregate(Sum('cif_inr')).get('cif_inr__sum', 0.00)

    @property
    def opening_balance(self):
        return self.item_details.filter(transaction_type='C').aggregate(Sum('qty')).get('qty__sum', 0.00)

    @property
    def usable(self):
        if self.item.head:
            if self.license.notification_number == N2015 and self.item.head.is_restricted:
                return self.old_quantity
        value = self.item_details.filter(transaction_type='C').aggregate(Sum('qty')).get('qty__sum', 0.00)
        if value:
            return round(value, 0)
        else:
            return 0


class LicenseDocumentModel(models.Model):
    license = models.ForeignKey('license.LicenseDetailsModel', on_delete=models.CASCADE,
                                related_name='license_documents')
    type = models.CharField(max_length=255)
    file = models.FileField(upload_to=license_path)


class StatusModel(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class OfficeModel(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class AlongWithModel(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class DateModel(models.Model):
    date = models.DateField()

    def __str__(self):
        return str(self.date)


class LicenseInwardOutwardModel(models.Model):
    date = models.ForeignKey('license.DateModel', on_delete=models.CASCADE,
                             related_name='license_status')
    license = models.ForeignKey('license.LicenseDetailsModel', on_delete=models.CASCADE,
                                related_name='license_status', null=True, blank=True)
    status = models.ForeignKey('license.StatusModel', on_delete=models.CASCADE,
                               related_name='license_status')
    office = models.ForeignKey('license.OfficeModel', on_delete=models.CASCADE,
                               related_name='license_status')
    description = models.TextField(null=True, blank=True)
    amd_sheets_number = models.CharField(max_length=100, null=True, blank=True)
    copy = models.BooleanField(default=False)
    annexure = models.BooleanField(default=False)
    tl = models.BooleanField(default=False)
    aro = models.BooleanField(default=False)
    along_with = models.ForeignKey('license.AlongWithModel', on_delete=models.CASCADE,
                                   related_name='license_status', null=True, blank=True)

    def __str__(self):
        text = ''
        if self.license:
            text = text + str(self.license) + ' '
        if self.copy:
            text = text + 'copy '
        if self.amd_sheets_number:
            text = text + 'amendment sheet:- ' + str(self.amd_sheets_number) + ' '
        if self.annexure:
            text = text + '& annexure '
        if self.status:
            text = text + 'has been {0} '.format(self.status.name)
        if self.office:
            text = text + 'send to '.format(self.office.name)
        if self.description:
            text = text + 'for ' + str(self.description) + ' '
        if self.along_with:
            text = text + 'along with ' + str(self.along_with.name)
        return text

    @property
    def ge_file_number(self):
        return self.license.ge_file_number
