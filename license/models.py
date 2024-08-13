from decimal import Decimal

from django.db import models
# Create your models here.
from django.db.models import Sum, Q, IntegerField
from django.db.models.functions import Coalesce
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse

from allotment.models import AllotmentItems, Debit
from bill_of_entry.models import RowDetails, ARO
from core.scripts.calculate_balance import calculate_available_quantity
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
    def opening_balance(self):
        if not hasattr(self, "_opening_balance"):
            self._opening_balance = self.export_license.all().aggregate(sum=Sum('cif_fc'))['sum']
        return self._opening_balance

    @property
    def opening_fob(self):
        result = self.export_license.all().aggregate(sum=Sum('fob_inr'))['sum']
        return result if result is not None else 0.0

    def opening_cif_inr(self):
        result = self.export_license.all().aggregate(sum=Sum('cif_inr'))['sum']
        return result if result is not None else 0.0

    @property
    def get_total_debit(self):
        if not hasattr(self, "_get_total_debit"):
            self._get_total_debit = self.import_license.aggregate(total_debits=Sum('debited_value'))['total_debits']
        return self._get_total_debit

    @property
    def get_total_allotment(self):
        if not hasattr(self, "_get_total_allotment"):
            self._get_total_allotment = self.import_license.aggregate(total_allotted=Sum('allotted_value'))[
                'total_allotted']
        return self._get_total_allotment

    @property
    def get_balance_cif(self):
        credit = float(self.opening_balance)
        debit = float(self.get_total_debit)
        allotment = float(self.get_total_allotment)
        t_debit = debit + allotment
        return round_down(credit - t_debit, 2)

    @property
    def get_chickpeas_obj(self):
        return self.import_license.filter(
            Q(description__icontains='Chickpeas') | Q(description__icontains='Green Peas') | Q(
                description__icontains='Lentils'))

    @property
    def get_glass_formers(self):
        object = self.import_license.filter(description__icontains='Glass Formers')
        if object.first():
            return object.first()
        else:
            return None

    @property
    def get_intermediates_namely(self):
        object = self.import_license.filter(
            Q(description__icontains='Intermediates namely') | Q(description__icontains='Aluminium Oxide'))
        if object.first():
            return object.first()
        else:
            return None

    @property
    def get_other_special_additives(self):
        object = self.import_license.filter(description__icontains='Other Special Additives')
        if object.first():
            return object.first()
        else:
            return None

    @property
    def get_hot_rolled(self):
        object = self.import_license.filter(description__icontains='HOT ROLLED')
        if object.first():
            return object.first()
        else:
            return None

    @property
    def get_bearing(self):
        object = self.import_license.filter(description__icontains='Bearing')
        if object.first():
            return object.first()
        else:
            return None

    @property
    def get_modifiers_namely(self):
        object = self.import_license.filter(description__icontains='Modifiers namely')
        if object.first():
            return object.first()
        else:
            return None

    @property
    def get_pickle_oil(self):
        object = self.import_license.filter(
            Q(description__icontains='Fats and Oils') | Q(description__icontains='Oils and Fats') | Q(
                description__icontains='Salad Oil'))
        if object.first():
            return object.first()
        else:
            return None

    @property
    def get_rfa(self):
        object = self.import_license.filter(
            Q(description__icontains='Food Additives') | Q(description__icontains='Food Additive') | Q(
                description__icontains='0908'))
        if object.first():
            return object.first()
        else:
            return None

    @property
    def get_chickpeas(self):
        return self.get_chickpeas_obj.aggregate(Sum('available_quantity'))['available_quantity__sum'] or 0

    @property
    def get_hs_steel(self):
        all = self.import_license.all()
        return all

    @property
    def get_battery_obj(self):
        return self.import_license.filter(description__icontains='battery')

    @property
    def get_alloy_steel_obj(self):
        return self.import_license.filter(description__icontains='alloy steel')

    @property
    def get_hot_rolled_obj(self):
        return self.import_license.filter(description__icontains='HOT ROLLED')

    @property
    def get_bearing_obj(self):
        return self.import_license.filter(description__icontains='Bearing')

    @property
    def get_battery_total(self):
        items = self.get_battery_obj
        return sum(item.quantity for item in items)

    @property
    def get_battery_balance(self):
        return self.get_battery_obj.aggregate(Sum('available_quantity'))['available_quantity__sum'] or 0

    @property
    def get_alloy_steel_total(self):
        items = self.get_alloy_steel_obj
        return sum(item.quantity for item in items)

    @property
    def get_alloy_steel_balance(self):
        return self.get_alloy_steel_obj.aggregate(Sum('available_quantity'))['available_quantity__sum'] or 0

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
        return self.get_bearing_obj.aggregate(Sum('available_quantity'))['available_quantity__sum'] or 0

    def wheat(self):
        return self.import_license.filter(item__head__name__icontains='wheat').first()

    def get_sugar(self):
        return self.import_license.filter(item__head__name__icontains='sugar').aggregate(Sum('available_quantity'))[
            'available_quantity__sum'] or 0

    def sugar(self):
        return self.import_license.filter(item__head__name__icontains='sugar').first()

    """
    Vegetable Oil Logics 
    """

    @property
    def oil_queryset(self):
        rbd = self.import_license.filter(Q(description__icontains='rbd') | Q(description__icontains='1513') | Q(
            description__icontains='Edible Vegtable Oil') | Q(description__icontains='Edible Vegetable Oi') | Q(
            description__icontains='Edible Vegetable Oi')).distinct()
        return rbd

    @property
    def get_rbd(self):
        return self.import_license.filter(Q(description__icontains='rbd')).exclude(
            Q(description__icontains='1513') | Q(description__icontains='1509') | Q(
                description__icontains='Edible Vegtable') | Q(
                description__icontains='150000') | Q(description__icontains='Edible Vegetable Oil /') | Q(
                description__icontains='Edible Vegetable Oil/')).aggregate(Sum('available_quantity'))[
            'available_quantity__sum'] or 0

    @property
    def rbd_pd(self):
        rbd = self.oil_queryset
        if rbd:
            return rbd.first().description
        else:
            return "Missing"

    @property
    def oil_queryset_total(self):
        return self.oil_queryset.aggregate(Sum('available_quantity'))['available_quantity__sum'] or 0

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
        return self.import_license.filter(
            Q(description__icontains='1513') | Q(description__icontains="Vegetable Oil")).exclude(
            Q(description__icontains='1509') | Q(description__icontains='1509') | Q(
                description__icontains='Edible Vegtable') | Q(
                description__icontains='150000') | Q(description__icontains='Edible Vegetable Oil /') | Q(
                description__icontains='Edible Vegetable Oil/')).aggregate(Sum('available_quantity'))[
            'available_quantity__sum'] or 0

    @property
    def get_veg_oil(self):
        return self.import_license.filter(
            Q(description__icontains='1509') | Q(description__icontains='Edible Vegtable') | Q(
                description__icontains='150000') | Q(description__icontains='Edible Vegetable Oil /') | Q(
                description__icontains='Edible Vegetable Oil/') | Q(
                description__icontains='Edible Vegetable Oil')).aggregate(Sum('available_quantity'))[
            'available_quantity__sum'] or 0

    @property
    def get_pko_cif(self):
        cif = 0
        qty = self.get_pko
        if qty and qty > 100:
            balance_cif = self.get_balance_cif - self.get_cheese_cif - self.get_total_quantity_of_ff_df_cif - self.get_swp_cif
            if balance_cif > 0:
                required_cif = qty
                cif = min(required_cif, balance_cif)
        return cif

    @property
    def get_veg_oil_cif(self):
        qty = self.get_veg_oil
        if qty and qty > 100:
            balance_cif = (Decimal(self.get_balance_cif) - Decimal(self.get_cheese_cif) -
                           Decimal(self.get_total_quantity_of_ff_df_cif) - Decimal(self.get_swp_cif))
            if balance_cif > 0:
                return balance_cif
            else:
                return 0
        else:
            return 0

    @property
    def get_cmc_obj(self):
        return self.import_license.filter(
            Q(description__icontains='Additives')).values('description', 'available_quantity', 'debited_quantity',
                                                          'allotted_quantity', 'debited_value', 'allotted_value')

    @property
    def get_cmc(self):
        return self.get_cmc_obj.aggregate(Sum('available_quantity'))['available_quantity__sum'] or 0

    @property
    def get_food_flavour_namkeen_obj(self):
        return self.import_license.filter(
            Q(description__icontains='pepper') | Q(description__icontains='food flavour') | Q(
                description__icontains='Cardamom') | Q(
                description__icontains='Cardamon')).distinct()

    @property
    def get_food_flavour_confectionery_obj(self):
        return self.import_license.filter(Q(description__icontains='Flavour') |
                                          Q(description__icontains='Fruit Flavour') | Q(
            description__icontains='food flavour')).distinct()

    @property
    def get_food_flavour_confectionery_obj_qty(self):
        return self.get_food_flavour_confectionery_obj.aggregate(Sum('available_quantity'))[
            'available_quantity__sum'] or 0

    @property
    def get_food_flavour_confectionery_hsn(self):
        food_flavour_confectionery_obj = self.get_food_flavour_confectionery_obj
        first_item = food_flavour_confectionery_obj.first()
        return str(first_item.hs_code) if first_item else 'Missing'

    @property
    def get_food_flavour_confectionery_pd(self):
        food_flavour_confectionery_obj = self.get_food_flavour_confectionery_obj
        first_item = food_flavour_confectionery_obj.first()
        return str(first_item.description) if first_item else 'Missing'

    @property
    def get_food_flavour_namkeen(self):
        return self.get_food_flavour_namkeen_obj.aggregate(Sum('available_quantity'))['available_quantity__sum'] or 0

    @property
    def get_food_flavour_qs(self):
        all = self.import_license.filter(Q(description__icontains='flavour'))
        return all

    @property
    def get_food_flavour_pd(self):
        sum1 = 0
        all = self.get_food_flavour_qs
        if all.first():
            return all.first().description
        else:
            return "Missing"

    @property
    def get_food_flavour_tq(self):
        return self.get_food_flavour_qs.aggregate(Sum('available_quantity'))['available_quantity__sum'] or 0

    @property
    def get_food_flavour(self):
        return self.import_license.filter(
            Q(description__icontains='0802') & Q(description__icontains='food flavour')).exclude(
            Q(hs_code__hs_code__istartswith='2009') | Q(description__icontains='2009')).aggregate(
            Sum('available_quantity'))['available_quantity__sum'] or 0

    @property
    def get_food_flavour_juice(self):
        return self.import_license.filter(Q(description__icontains='juice') | Q(description__icontains='2009') | Q(
            hs_code__hs_code__istartswith='2009')).aggregate(Sum('available_quantity'))['available_quantity__sum'] or 0

    @property
    def get_dietary_fibre(self):
        return self.import_license.filter(
            Q(description__icontains='0802') & Q(description__icontains='dietary fibre')).exclude(
            description__icontains='juice').aggregate(Sum('available_quantity'))['available_quantity__sum'] or 0

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
            required = float(self.get_food_flavour) * 6.22
        elif '2009' in product_description:
            required = float(self.get_food_flavour_juice) * 2.5
        else:
            required = 0
        required = float(required) + float(self.get_fruit) * 2.5
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
        return self.import_license.filter(
            Q(item__head__name__icontains='starch') & Q(hs_code__hs_code__istartswith='11')).aggregate(
            Sum('available_quantity'))['available_quantity__sum'] or 0

    @property
    def get_modified_starch(self):
        return self.import_license.filter(
            Q(item__head__name__icontains='starch') & Q(hs_code__hs_code__istartswith='35')).aggregate(
            Sum('available_quantity'))['available_quantity__sum'] or 0

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
        return \
                self.import_license.filter(Q(description__icontains='Leavening Agent')).aggregate(
                    Sum('available_quantity'))[
                    'available_quantity__sum'] or 0

    @property
    def get_fruit(self):
        """
        Query Balance Cocoa Quantity
        @return: Total Balance Quantity of Cocoa
        """
        return self.import_license.filter(Q(hs_code__hs_code__istartswith='18050000')).aggregate(
            Sum('available_quantity'))['available_quantity__sum'] or 0

    @property
    def get_mnm_qs(self):
        """
        Query Balance Cheese Quantity
        @return: Total Balance Quantity of Cheese
        """
        return self.import_license.filter(Q(description__icontains='milk'))

    @property
    def get_mnm_pd(self):
        """
        Query Balance Cheese Quantity
        @return: Total Balance Quantity of Cheese
        """
        all = self.get_mnm_qs
        if all.first():
            return all.first().description
        else:
            return 0

    @property
    def get_mnm_tq(self):
        """
        Query Balance Cheese Quantity
        @return: Total Balance Quantity of Cheese
        """
        return self.get_mnm_qs.aggregate(Sum('available_quantity'))['available_quantity__sum'] or 0

    _product_quantities = None

    from django.db.models import Q, Sum

    @property
    def product_quantities(self):
        if self._product_quantities is None:
            self._product_quantities = {}
            all_entries = self.import_license.values_list('description', 'hs_code__hs_code', 'available_quantity')
            description_dict = {
                "cheese": '0406',
                "swp": '0404',
                "wpc": '3502'
            }
            for item, desc in description_dict.items():
                self._product_quantities[item] = 0
            for entry in all_entries:
                for item, description in description_dict.items():
                    if ((description in entry[0]) or (entry[1].startswith(description))):
                        self._product_quantities[item] += entry[2]
                        break
                if self._product_quantities["cheese"] != 0:
                    self._product_quantities["swp"] = 0
                    self._product_quantities["wpc"] = 0
                elif self._product_quantities["swp"] != 0:
                    self._product_quantities["wpc"] = 0
        return self._product_quantities

    @property
    def get_wpc(self):
        return self.product_quantities.get('wpc', 0)

    @property
    def get_swp(self):
        return self.product_quantities.get('swp', 0)

    @property
    def get_cheese(self):
        return self.product_quantities.get('cheese', 0)

    @property
    def get_cheese_cif(self):
        qty = self.get_cheese
        if qty and qty > 100:
            required_cif = float(qty) * 6.8
            balance_cif = self.get_balance_cif - self.get_total_quantity_of_ff_df_cif
            return max(0, min(required_cif, balance_cif))
        return 0

    @property
    def get_wpc_cif(self):
        qty = self.get_wpc
        if qty and qty > 100:
            required_cif = Decimal(qty) * Decimal(5.5)  # convert the float to a Decimal
            balance_cif = (Decimal(self.get_balance_cif) - Decimal(self.get_pko_cif) -
                           Decimal(self.get_total_quantity_of_ff_df_cif) - Decimal(self.get_starch_cif))
            # Easier readability by using max function to get the maximum between 0 and balance_cif
            return max(0, min(required_cif, balance_cif))
        return 0

    @property
    def get_swp_cif(self):
        qty = self.get_swp
        if qty and qty > 100:
            required_cif = qty * 1
            balance_cif = self.get_balance_cif - self.get_total_quantity_of_ff_df_cif
            return max(0, min(required_cif, balance_cif))
        return 0

    from decimal import Decimal

    @property
    def cif_value_balance(self):
        balance_cif = (Decimal(self.get_balance_cif) - Decimal(self.get_pko_cif) -
                       Decimal(self.get_cheese_cif) - Decimal(self.get_wpc_cif) -
                       Decimal(self.get_total_quantity_of_ff_df_cif) -
                       Decimal(self.get_rbd_cif) - Decimal(self.get_veg_oil_cif) -
                       Decimal(self.get_swp_cif))

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
            return all.first().description
        else:
            return 'Missing'

    @property
    def get_pp(self):
        return self.import_license.filter(
            item__head__name__icontains='pp'
        ).exclude(
            Q(description__icontains='Aluminium') | Q(description__icontains='7607')
        ).aggregate(Sum('available_quantity'))['available_quantity__sum'] or 0

    @property
    def get_pp_total(self):
        all_imports = self.import_license.filter(
            item__head__name__icontains='pp'
        ).exclude(
            description__icontains='7607'
        )
        total_quantity = sum(entry.quantity for entry in all_imports)
        return total_quantity

    @property
    def get_aluminium(self):
        return self.import_license.filter(
            Q(description__icontains='Aluminium') | Q(description__icontains='7607')).aggregate(
            Sum('available_quantity'))['available_quantity__sum'] or 0

    @property
    def get_paper_and_paper_qs(self):
        all = self.import_license.filter(Q(description__icontains='paper')).exclude(
            Q(description__icontains='Aluminium') | Q(description__icontains='7607'))
        return all

    @property
    def get_paper_and_paper_pd(self):
        all = self.get_paper_and_paper_qs
        if all.first():
            return all.first().description
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
            return all.first().description
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
        return self.get_paper_and_paper_qs.aggregate(Sum('available_quantity'))['available_quantity__sum'] or 0

    @property
    def get_juice(self):
        return self.import_license.filter(
            Q(description__icontains='Relevant Fruit') | Q(description__icontains='juice')).aggregate(
            Sum('available_quantity'))['available_quantity__sum'] or 0

    @property
    def get_tartaric_acid(self):
        return self.import_license.filter(item__head__name__icontains='acid').aggregate(Sum('available_quantity'))[
            'available_quantity__sum'] or 0

    @property
    def get_orange_essential_pd(self):
        all = self.import_license.filter(
            Q(item__head__name__icontains='Essential oil'))
        if all.first():
            return all.first().description
        else:
            return 'Missing'

    @property
    def get_orange_essential_total(self):
        return self.import_license.filter(
            Q(item__head__name__icontains='Essential oil')).aggregate(Sum('available_quantity'))[
            'available_quantity__sum'] or 0

    @property
    def get_orange_essential_oil(self):
        return self.import_license.filter(
            Q(item__head__name__icontains='Essential oil')).exclude(
            Q(description__icontains='lemon') & Q(description__icontains='pippermint')).aggregate(
            Sum('available_quantity'))['available_quantity__sum'] or 0

    @property
    def get_lemon_essential_oil(self):
        return self.import_license.filter(
            Q(item__head__name__icontains='Essential Oil') & Q(description__icontains='lemon')).aggregate(
            Sum('available_quantity'))['available_quantity__sum'] or 0

    @property
    def get_pippermint_essential_oil(self):
        return self.import_license.filter(
            Q(item__head__name__icontains='essential oil') & Q(description__icontains='pippermint')).aggregate(
            Sum('available_quantity'))['available_quantity__sum'] or 0

    def get_other_confectionery(self):
        return self.import_license.filter(item__head__name__icontains='other confectionery').aggregate(
            Sum('available_quantity'))['available_quantity__sum'] or 0

    def get_other_confectionery_pd(self):
        all = self.import_license.filter(item__head__name__icontains='other confectionery')
        if all.first():
            return all.first().description
        else:
            return 'Missing'

    def get_starch_confectionery_qs(self):
        from django.db.models import Q
        return self.import_license.filter(Q(item__head__name__icontains='starch') | Q(
            item__head__name__icontains='emulsifier'))

    def get_starch_confectionery(self):
        return self.get_starch_confectionery_qs().aggregate(Sum('available_quantity'))['available_quantity__sum'] or 0

    def get_starch_confectionery_pd(self):
        all = self.get_starch_confectionery_qs()
        if all.first():
            return all.first().description
        else:
            return 'Missing'

    def get_starch_confectionery_hsn(self):
        all = self.get_starch_confectionery_qs()
        if all.first():
            return str(all.first().hs_code)
        else:
            return 'Missing'

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
        lic = self.export_license.all().values('norm_class__norm_class')
        credit = self.opening_balance
        if 'E1' in str(lic.first().get('norm_class__norm_class')):
            credit = credit * .02
            result = self.import_license.filter(
                Q(item__head__name__icontains='other')).aggregate(
                total_debited_value=Coalesce(Sum('debited_value'), 0, output_field=IntegerField()),
                total_allotted_value=Coalesce(Sum('allotted_value'), 0, output_field=IntegerField())
            )
            total_value = result['total_debited_value'] + result['total_allotted_value']
        else:
            credit = credit * .1
            result = LicenseImportItemsModel.objects.filter(license=self).filter(
                Q(item__head__name__icontains='flavour') | Q(item__head__name__icontains='fruit') | Q(
                    item__head__name__icontains='dietary') | Q(
                    item__head__name__icontains='Leavening') | Q(
                    item__head__name__icontains='starch') | Q(
                    item__head__name__icontains='Coco')).aggregate(
                total_debited_value=Coalesce(Sum('debited_value'), 0, output_field=IntegerField()),
                total_allotted_value=Coalesce(Sum('allotted_value'), 0, output_field=IntegerField())
            )
            total_value = result['total_debited_value'] + result['total_allotted_value']
        return max(round_down(credit - total_value), 0)

    @property
    def get_per_essential_oil(self):
        lic = self.export_license.all().values('norm_class__norm_class')
        credit = self.opening_balance
        if 'E1' in str(lic.first().get('norm_class__norm_class')):
            credit = credit * .05
            result = LicenseImportItemsModel.objects.filter(license=self).filter(
                Q(description__icontains='essential oil') | Q(item__head__name__icontains='food flavour') | Q(
                    description__icontains='Flavour') |
                Q(description__icontains='Fruit Flavour') | Q(description__icontains='food flavour')).aggregate(
                total_debited_value=Coalesce(Sum('debited_value'), 0, output_field=IntegerField()),
                total_allotted_value=Coalesce(Sum('allotted_value'), 0, output_field=IntegerField())
            )
            total_value = result['total_debited_value'] + result['total_allotted_value']
            return max(round_down(credit - total_value), 0)

    @property
    def get_per_black_pepper_cif(self):
        lic = self.export_license.all().values('norm_class__norm_class')
        credit = self.opening_balance
        if 'E132' in str(lic.first().get('norm_class__norm_class')):
            credit = credit * .03
            imports = LicenseImportItemsModel.objects.filter(license=self).filter(
                Q(description__icontains='pepper'))
        else:
            imports = []
        for dimport in imports:
            if dimport.allotted_value:
                credit = credit - dimport.debited_value - int(dimport.allotted_value)
            else:
                credit = float(credit) - float(dimport.debited_value)
        if credit > 0:
            return round_down(credit)
        else:
            return 0

    @property
    def get_starch_per_cif(self):
        lic = self.export_license.all().values('norm_class__norm_class')
        credit = self.opening_balance
        if 'E1' in str(lic.first().get('norm_class__norm_class')):
            credit = credit * .05
            result = LicenseImportItemsModel.objects.filter(license=self).filter(
                Q(description__icontains='emulsifier')).aggregate(
                total_debited_value=Coalesce(Sum('debited_value'), 0, output_field=IntegerField()),
                total_allotted_value=Coalesce(Sum('allotted_value'), 0, output_field=IntegerField())
            )
            total_value = result['total_debited_value'] + result['total_allotted_value']
            return max(round_down(credit - total_value), 0)

    @property
    def get_cmc_cif(self):
        lic = self.export_license.first()
        credit = float(self.opening_balance)
        if 'E132' in str(lic.norm_class):
            credit *= .05
            result = self.get_cmc_obj.aggregate(
                total_debited_value=Coalesce(Sum('debited_value'), 0, output_field=IntegerField()),
                total_allotted_value=Coalesce(Sum('allotted_value'), 0, output_field=IntegerField())
            )
            total_value = result['total_debited_value'] + result['total_allotted_value']
        else:
            total_value = 0
        return max(round_down(credit - total_value), 0)

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
    description = models.CharField(max_length=255, blank=True, db_index=True, null=True)
    item = models.ForeignKey('core.ItemNameModel', related_name='export_licenses', on_delete=models.SET_NULL, null=True,
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
    hs_code = models.ForeignKey('core.HSCodeModel', on_delete=models.CASCADE, blank=True, related_name='import_item',
                                null=True)
    item = models.ForeignKey('core.ItemNameModel', related_name='license_items', on_delete=models.SET, blank=True,
                             null=True)
    description = models.CharField(max_length=255, blank=True, db_index=True, null=True)
    duty_type = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    old_quantity = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default=KG)
    cif_fc = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    cif_inr = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    available_quantity = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    available_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    debited_quantity = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    debited_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    allotted_quantity = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    allotted_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    is_restrict = models.BooleanField(default=False)
    comment = models.TextField(blank=True, null=True)
    admin_search_fields = ('license__license_number',)

    class Meta:
        ordering = ['license__license_expiry_date', 'serial_number']

    def __str__(self):
        return "{0}-{1}".format(str(self.license), str(self.serial_number))

    @property
    def required_cif(self):
        if self.available_quantity > 100:
            required = self.available_quantity * self.item.head.unit_rate
            return required
        else:
            return 0

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
        if self.item and self.item.head:
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


@receiver(post_save, sender=LicenseImportItemsModel, dispatch_uid="update_balance")
def update_balance(sender, instance, **kwargs):
    if not instance.available_quantity == calculate_available_quantity(instance):
        instance.available_quantity = calculate_available_quantity(instance)
        instance.save()
