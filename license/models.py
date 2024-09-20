from decimal import Decimal

from django.db import models
from django.db.models import Sum, IntegerField
from django.db.models.functions import Coalesce
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.urls import reverse
from django.utils.functional import cached_property
from allotment.models import AllotmentItems, Debit
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
SM = 'SM'
OT = 'OT'

LICENCE_PURCHASE = (
    (GE, 'GE Purchase'),
    (MI, 'GE Operating'),
    (IP, 'GE Item Purchase'),
    (SM, 'SM Purchase'),
    (OT, 'OT Purchase'),
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
    billing_rate = models.FloatField(default=0)
    billing_amount = models.FloatField(default=0)
    admin_search_fields = ('license_number',)

    def __str__(self):
        return self.license_number

    class Meta:
        ordering = ('license_expiry_date',)

    def use_balance_cif(self, amount, available_cif):
        amount = float(amount)  # convert float 'amount' to Decimal
        if amount <= available_cif:
            available_cif -= amount
            return available_cif
        else:
            return 0

    @cached_property
    def get_norm_class(self):
        return ','.join([export.norm_class.norm_class for export in self.export_license.all() if export.norm_class])

    def get_absolute_url(self):
        return reverse('license-detail', kwargs={'license': self.license_number})

    @cached_property
    def opening_balance(self):
        result = self.export_license.all().aggregate(sum=Sum('cif_fc'))['sum'] or 0
        return result if result is not None else 0.0

    @cached_property
    def opening_fob(self):
        result = self.export_license.all().aggregate(sum=Sum('fob_inr'))['sum']
        return result if result is not None else 0.0

    def opening_cif_inr(self):
        result = self.export_license.all().aggregate(sum=Sum('cif_inr'))['sum']
        return result if result is not None else 0.0

    @property
    def get_total_debit(self):
        result = self.import_license.aggregate(total_debits=Sum('debited_value'))['total_debits']
        return result if result is not None else 0.0

    @property
    def get_total_allotment(self):
        result = self.import_license.aggregate(total_allotted=Sum('allotted_value'))[
            'total_allotted']
        return result if result is not None else 0.0

    @property
    def get_balance_cif(self):
        credit = float(self.opening_balance)
        debit = float(self.get_total_debit)
        allotment = float(self.get_total_allotment)
        t_debit = debit + allotment
        return round_down(credit - t_debit, 2)

    def get_party_name(self):
        return str(self.exporter)[:8]

    @cached_property
    def get_glass_formers(self):
        total_quantity = self.get_item_data('RUTILE').get('quantity_sum')
        available_quantity = self.get_item_data('RUTILE').get('available_quantity_sum')
        opening_balance = self.opening_balance
        avg = float(opening_balance) / float(total_quantity)
        if avg <= 3:
            borax_quantity = (total_quantity / Decimal('.62')) * Decimal('.1')
            debit = RowDetails.objects.filter(
                sr_number__license=self,
                bill_of_entry__company=567,
                transaction_type=Debit
            ).aggregate(Sum('qty')).get('qty__sum') or Decimal('0')
            allotment = AllotmentItems.objects.filter(
                item__license=self,
                allotment__company=567,
                allotment__bill_of_entry__bill_of_entry_number__isnull=True).aggregate(
                Sum('qty')).get('qty__sum') or Decimal('0')
            borax = min(Decimal(borax_quantity) - (Decimal(debit) + Decimal(allotment)), Decimal(available_quantity))
        else:
            borax = 0
        rutile = min(Decimal(available_quantity) - Decimal(borax), Decimal(available_quantity))
        return {'borax': borax, 'rutile': rutile, 'total': total_quantity,
                'description': self.get_item_data('RUTILE').get('description')}

    @cached_property
    def borax_quantity(self):
        return self.get_glass_formers.get('borax')

    @cached_property
    def rutile_quantity(self):
        return self.get_glass_formers.get('rutile')

    @cached_property
    def average_unit_price(self):
        return round(Decimal(self.cif_value_balance_glass.get('rutile')) / self.get_glass_formers.get('rutile'), 2)

    @cached_property
    def get_intermediates_namely(self):
        return self.get_item_data('ALUMINIUM OXIDE, ZINC OXIDE, ZIRCONIUM OXIDE')

    @cached_property
    def get_modifiers_namely(self):
        return self.get_item_data('SODA ASH')

    @cached_property
    def get_other_special_additives(self):
        return self.get_item_data('TITANIUM DIOXIDE')

    @cached_property
    def cif_value_balance_glass(self):
        available_value = self.get_balance_cif
        soda_ash_qty = self.get_modifiers_namely.get('available_quantity_sum')
        titanium_qty = self.get_other_special_additives.get('available_quantity_sum')
        borax_qty = self.get_glass_formers.get('borax')
        rutile_qty = self.get_glass_formers.get('rutile')
        borax_cif = soda_ash_cif = rutile_cif = titanium_cif = 0
        if borax_qty > 100:
            borax_cif = min(borax_qty * Decimal('.7'), available_value)
            available_value = self.use_balance_cif(borax_cif, available_value)
        if soda_ash_qty > 100:
            soda_ash_cif = min(soda_ash_qty * Decimal('.3'), available_value)
            available_value = self.use_balance_cif(soda_ash_cif, available_value)
        if rutile_qty > 100:
            rutile_cif = min(rutile_qty * Decimal('3.5'), available_value)
            available_value = self.use_balance_cif(rutile_cif, available_value)
        if titanium_qty > 100:
            titanium_cif = min(titanium_qty * Decimal('1.8'), available_value)
            available_value = self.use_balance_cif(titanium_cif, available_value)
        return {'borax': borax_cif, 'rutile': rutile_cif, 'soda_ash': soda_ash_cif, 'titanium': titanium_cif,
                'balance_cif': available_value}

    @cached_property
    def get_rfa(self):
        return self.get_item_data('FOOD FLAVOUR PICKLE')

    @cached_property
    def get_hot_rolled(self):
        return self.get_item_data('HOT ROLLED STEEL')

    @cached_property
    def get_bearing(self):
        return self.get_item_data('BEARING')

    @cached_property
    def get_battery(self):
        return self.get_item_data('AUTOMOTIVE BATTERY')

    @cached_property
    def get_alloy_steel_total(self):
        return self.get_item_data('ALLOY STEEL')

    @cached_property
    def import_license_grouped(self):
        return self.import_license.select_related('item').values('hs_code__hs_code', 'item__name', 'description',
                                                                 'item__unit_price') \
            .annotate(available_quantity_sum=Sum('available_quantity'),
                      quantity_sum=Sum('quantity')) \
            .order_by('item__name')

    def get_item_data(self, item_name):
        if item_name in ['JUICE', 'FOOD FLAVOUR BISCUITS', 'DIETARY FIBRE', 'LEAVENING AGENT', 'STARCH 1108',
                         'STARCH 3505', 'FRUIT/COCOA']:
            restricted_value = self.get_per_cif.get('tenRestriction')
            if restricted_value > 200:
                return next((item for item in self.import_license_grouped if item['item__name'] == item_name),
                            {'available_quantity_sum': 0, 'quantity_sum': 0})
            else:
                return {'available_quantity_sum': 0, 'quantity_sum': 0}

        else:
            return next((item for item in self.import_license_grouped if item['item__name'] == item_name),
                        {'available_quantity_sum': 0, 'quantity_sum': 0})

    @cached_property
    def import_license_head_grouped(self):
        return self.import_license.select_related('item', 'item__head').values('item__head__name', 'description',
                                                                               'item__unit_price', 'hs_code__hs_code') \
            .annotate(available_quantity_sum=Sum('available_quantity'),
                      quantity_sum=Sum('quantity')) \
            .order_by('item__name')

    def get_item_head_data(self, item_name):
        return next((item for item in self.import_license_head_grouped if item['item__head__name'] == item_name),
                    {'available_quantity_sum': 0, 'quantity_sum': 0})

    """
    Vegetable Oil Logics 
    """

    @cached_property
    def oil_queryset(self):
        return self.get_item_head_data('VEGETABLE OIL')

    @cached_property
    def get_rbd(self):
        return self.get_item_data('RBD PALMOLEIN OIL')

    @cached_property
    def get_pko(self):
        return self.get_item_data('PALM KERNEL OIL')

    @cached_property
    def get_veg_oil(self):
        return self.get_item_data('EDIBLE VEGETABLE OIL')

    @cached_property
    def get_food_flavour(self):
        return self.get_item_data('FOOD FLAVOUR BISCUITS')

    @cached_property
    def get_biscuit_juice(self):
        return self.get_item_data('JUICE')

    @cached_property
    def get_dietary_fibre(self):
        return self.get_item_data('DIETARY FIBRE')

    @cached_property
    def get_wheat_starch(self):
        return self.get_item_data('STARCH 1108')

    @cached_property
    def get_modified_starch(self):
        return self.get_item_data('STARCH 3505')

    @cached_property
    def get_leavening_agent(self):
        return self.get_item_data('LEAVENING AGENT')

    @cached_property
    def get_fruit(self):
        """
        Query Balance Cocoa Quantity
        @return: Total Balance Quantity of Cocoa
        """
        return self.get_item_data('FRUIT/COCOA')

    @cached_property
    def get_mnm_pd(self):
        return self.get_item_head_data('MILK & MILK Product')

    @cached_property
    def get_wpc(self):
        return self.get_item_data('WPC')

    @cached_property
    def get_swp(self):
        return self.get_item_data('SWP')

    @cached_property
    def get_cheese(self):
        return self.get_item_data('CHEESE')

    @cached_property
    def cif_value_balance_biscuits(self):
        available_value = self.get_balance_cif
        restricted_value = self.get_per_cif.get('tenRestriction')
        cif_juice = cif_swp = cif_cheese = f_f_cif = wheat_starch_cif = 0
        juice_quantity = self.get_biscuit_juice.get('available_quantity_sum')
        if juice_quantity > 50 and restricted_value > 200:
            cif_juice = min(juice_quantity * self.get_biscuit_juice.get('item__unit_price'), restricted_value)
            restrict_value = min(available_value, restricted_value)
            cif_juice = min(cif_juice, restrict_value)
            restricted_value = self.use_balance_cif(cif_juice, restricted_value)
            available_value = self.use_balance_cif(cif_juice, available_value)
        swp_quantity = self.get_swp.get('available_quantity_sum')
        if swp_quantity > 100:
            cif_swp = swp_quantity * self.get_swp.get('item__unit_price')
            cif_swp = min(cif_swp, available_value)
            available_value = self.use_balance_cif(cif_swp, available_value)
        cheese_quantity = self.get_cheese.get('available_quantity_sum')
        if cheese_quantity > 100:
            cif_cheese = cheese_quantity * self.get_cheese.get('item__unit_price')
            cif_cheese = min(cif_cheese, available_value)
            available_value = self.use_balance_cif(cif_cheese, available_value)
        pko_quantity = self.get_pko.get('available_quantity_sum')
        veg_oil_quantity = self.get_veg_oil.get('available_quantity_sum')
        rbd_quantity = self.get_rbd.get('available_quantity_sum')
        from core.scripts.calculation import optimize_product_distribution
        if pko_quantity > 100 and available_value < (pko_quantity * self.get_pko.get('item__unit_price', 1.340)):
            veg_oil_details = {
                'pko': {"quantity": Decimal(
                    Decimal(available_value) / Decimal(self.get_pko.get('item__unit_price', 1.340))),
                    "value": available_value},
                'veg_oil': {"quantity": 0, "value": 0},
                'get_rbd': {"quantity": 0, "value": 0}
            }
        elif pko_quantity > 100 and available_value:
            veg_oil_details = optimize_product_distribution(self.get_pko.get('item__unit_price', 1.340),
                                                            self.get_veg_oil.get('item__unit_price', 7), pko_quantity,
                                                            available_value, is_pko=True)
            pko = min(veg_oil_details.get('pko').get('value'), available_value)
            available_value = self.use_balance_cif(pko, available_value)
            veg_oil = min(veg_oil_details.get('veg_oil').get('value'), available_value)
            available_value = self.use_balance_cif(veg_oil, available_value)
        elif veg_oil_quantity > 100:
            veg_oil_details = optimize_product_distribution(0.985, 7, veg_oil_quantity, available_value, is_pko=False)
            rbd = min(veg_oil_details.get('get_rbd').get('value'), available_value)
            available_value = self.use_balance_cif(rbd, available_value)
            veg_oil = min(veg_oil_details.get('veg_oil').get('value'), available_value)
            available_value = self.use_balance_cif(veg_oil, available_value)
        elif rbd_quantity > 100:
            rbd_cif = rbd_quantity * self.get_rbd.get('item__unit_price')
            veg_oil_details = {
                'pko': {"quantity": 0, "value": 0 * 1},
                'veg_oil': {"quantity": 0, "value": 0},
                'get_rbd': {"quantity": rbd_quantity, "value": min(rbd_cif, available_value)}
            }
            available_value = self.use_balance_cif(min(rbd_cif, available_value), available_value)
        else:
            veg_oil_details = {
                'pko': {"quantity": 0, "value": 0 * 1},
                'veg_oil': {"quantity": 0, "value": 0},
                'get_rbd': {"quantity": 0, "value": 0}
            }
        wheat_starch_quantity = self.get_wheat_starch.get('available_quantity_sum')
        if wheat_starch_quantity > 100:
            wheat_starch_cif = wheat_starch_quantity * self.get_wheat_starch.get('item__unit_price')
            restrict_value = min(available_value, restricted_value)
            wheat_starch_cif = min(wheat_starch_cif, restrict_value)
            restricted_value = self.use_balance_cif(wheat_starch_cif, restricted_value)
            available_value = self.use_balance_cif(wheat_starch_cif, available_value)
        cocoa_quantity = self.get_fruit.get('available_quantity_sum')
        if cocoa_quantity > 100:
            f_f_cif = cocoa_quantity * self.get_fruit.get('item__unit_price')
            restrict_value = min(available_value, restricted_value)
            f_f_cif = min(f_f_cif, restrict_value)
            restricted_value = self.use_balance_cif(f_f_cif, restricted_value)
            available_value = self.use_balance_cif(f_f_cif, available_value)
        return {'cif_juice': cif_juice, 'restricted_value': restricted_value, 'cif_swp': cif_swp,
                'cif_cheese': cif_cheese, 'veg_oil': veg_oil_details, 'f_f_cif': f_f_cif,
                'wheat_starch_cif': wheat_starch_cif, 'available_value': available_value}

    @cached_property
    def get_pp(self):
        return self.get_item_data('PP')

    @cached_property
    def get_aluminium(self):
        return self.get_item_data('ALUMINIUM FOIL')

    @cached_property
    def get_paper_and_paper(self):
        return self.get_item_data('PAPER & PAPER')

    @cached_property
    def get_cmc(self):
        return self.get_item_data('RELEVANT ADDITIVES DESCRIPTION')

    @cached_property
    def get_chickpeas(self):
        return self.get_item_data('CEREALS FLAKES')

    @cached_property
    def get_food_flavour_namkeen(self):
        return self.get_item_data('FOOD FLAVOUR NAMKEEN')

    @cached_property
    def get_juice(self):
        return self.get_item_data('FRUIT JUICE')

    @cached_property
    def get_tartaric_acid(self):
        return self.get_item_data('CITRIC ACID / TARTARIC ACID')

    @cached_property
    def get_essential_oil(self):
        return self.get_item_data('ESSENTIAL OIL')

    @cached_property
    def get_food_flavour_confectionery(self):
        return self.get_item_data('FOOD FLAVOUR CONFECTIONERY')

    def get_other_confectionery(self):
        return self.get_item_data('OTHER CONFECTIONERY INGREDIENTS')

    def get_starch_confectionery(self):
        return self.get_item_data('EMULSIFIER')

    @cached_property
    def get_per_cif(self):
        available_value = self.get_balance_cif
        lic = self.export_license.all().values('norm_class__norm_class')
        credit = self.opening_balance
        if 'E132' in str(lic.first().get('norm_class__norm_class')):
            credit_3 = credit * .03
            result = self.import_license.filter(item__head__name='NAMKEEN 3% Restriction').aggregate(
                total_debited_value=Coalesce(Sum('debited_value'), 0, output_field=IntegerField()),
                total_allotted_value=Coalesce(Sum('allotted_value'), 0, output_field=IntegerField())
            )
            conf_3 = result['total_debited_value'] + result['total_allotted_value']
            credit_5 = credit * .05
            result = self.import_license.filter(item__head__name='NAMKEEN 5% Restriction').aggregate(
                total_debited_value=Coalesce(Sum('debited_value'), 0, output_field=IntegerField()),
                total_allotted_value=Coalesce(Sum('allotted_value'), 0, output_field=IntegerField())
            )
            conf_5 = result['total_debited_value'] + result['total_allotted_value']
            return {'threeRestriction': min(available_value, max(round_down(credit_3 - conf_3), 0)),
                    'fiveRestriction': min(available_value, max(round_down(credit_5 - conf_5), 0))}
        elif 'E126' in str(lic.first().get('norm_class__norm_class')):
            credit_3 = credit * .03
            result = self.import_license.filter(item__head__name='PICKLE 3% Restriction').aggregate(
                total_debited_value=Coalesce(Sum('debited_value'), 0, output_field=IntegerField()),
                total_allotted_value=Coalesce(Sum('allotted_value'), 0, output_field=IntegerField())
            )
            conf_3 = result['total_debited_value'] + result['total_allotted_value']
            return {'threeRestriction': min(available_value, max(round_down(credit_3 - conf_3), 0))}
        elif 'E1' in str(lic.first().get('norm_class__norm_class')):
            credit_2 = credit * .02
            result = self.import_license.filter(item__head__name='CONFECTIONERY 2% Restriction').aggregate(
                total_debited_value=Coalesce(Sum('debited_value'), 0, output_field=IntegerField()),
                total_allotted_value=Coalesce(Sum('allotted_value'), 0, output_field=IntegerField())
            )
            conf_2 = result['total_debited_value'] + result['total_allotted_value']
            credit_3 = credit * .03
            result = self.import_license.filter(item__head__name='CONFECTIONERY 3% Restriction').aggregate(
                total_debited_value=Coalesce(Sum('debited_value'), 0, output_field=IntegerField()),
                total_allotted_value=Coalesce(Sum('allotted_value'), 0, output_field=IntegerField())
            )
            conf_3 = result['total_debited_value'] + result['total_allotted_value']
            credit_5 = credit * .05
            result = self.import_license.filter(item__head__name='CONFECTIONERY 5% Restriction').aggregate(
                total_debited_value=Coalesce(Sum('debited_value'), 0, output_field=IntegerField()),
                total_allotted_value=Coalesce(Sum('allotted_value'), 0, output_field=IntegerField())
            )
            conf_5 = result['total_debited_value'] + result['total_allotted_value']
            return {'twoRestriction': min(available_value, max(round_down(credit_2 - conf_2), 0)),
                    'threeRestriction': min(available_value, max(round_down(credit_3 - conf_3), 0)),
                    'fiveRestriction': min(available_value, max(round_down(credit_5 - conf_5), 0))}
        elif 'E5' in str(lic.first().get('norm_class__norm_class')):
            credit = credit * .1
            result = self.import_license.filter(item__head__name='BISCUIT 10% Restriction').aggregate(
                total_debited_value=Coalesce(Sum('debited_value'), 0, output_field=IntegerField()),
                total_allotted_value=Coalesce(Sum('allotted_value'), 0, output_field=IntegerField())
            )
            total_value = result['total_debited_value'] + result['total_allotted_value']
            return {'tenRestriction': min(max(round_down(credit - total_value), 0), available_value)}


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
        credit = LicenseExportItemModel.objects.filter(license=self.license).aggregate(Sum('cif_fc'))[
                     'cif_fc__sum'] or 0
        debit = RowDetails.objects.filter(sr_number__license=self.license).filter(transaction_type=Debit).aggregate(
            Sum('cif_fc'))[
                    'cif_fc__sum'] or 0
        allotment = AllotmentItems.objects.filter(item__license=self.license,
                                                  allotment__bill_of_entry__bill_of_entry_number__isnull=True).aggregate(
            Sum('cif_fc'))['cif_fc__sum'] or 0
        return credit - (debit + allotment)


class LicenseImportItemsModel(models.Model):
    serial_number = models.IntegerField(default=0)
    license = models.ForeignKey('license.LicenseDetailsModel', on_delete=models.CASCADE, related_name='import_license')
    hs_code = models.ForeignKey('core.HSCodeModel', on_delete=models.CASCADE, blank=True, related_name='import_item',
                                null=True)
    item = models.ForeignKey('core.ItemNameModel', related_name='license_items', on_delete=models.CASCADE, blank=True,
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
        unique_together = (('license', 'serial_number'),)

    def __str__(self):
        return "{0}-{1}".format(str(self.license), str(self.serial_number))

    @cached_property
    def required_cif(self):
        if self.available_quantity > 100:
            required = self.available_quantity * self.item.head.unit_rate
            return required
        else:
            return 0

    @cached_property
    def balance_quantity(self):
        from core.scripts.calculate_balance import calculate_available_quantity
        return calculate_available_quantity(self)

    @cached_property
    def balance_cif_fc(self):
        if not self.cif_fc or int(self.cif_fc) == 0 or self.cif_fc == 0.1:
            credit = LicenseExportItemModel.objects.filter(license=self.license).aggregate(Sum('cif_fc'))['cif_fc__sum']
        else:
            credit = self.cif_fc
        if not self.cif_fc or self.cif_fc == 0.01:
            debit = RowDetails.objects.filter(sr_number__license=self.license).filter(transaction_type=Debit).aggregate(
                Sum('cif_fc'))[
                        'cif_fc__sum'] or 0
            allotment = AllotmentItems.objects.filter(item__license=self.license,
                                                      allotment__bill_of_entry__bill_of_entry_number__isnull=True).aggregate(
                Sum('cif_fc'))['cif_fc__sum'] or 0
        else:
            debit = RowDetails.objects.filter(sr_number=self).filter(transaction_type=Debit).aggregate(
                Sum('cif_fc'))[
                        'cif_fc__sum'] or 0
            allotment = AllotmentItems.objects.filter(item=self,
                                                      allotment__bill_of_entry__bill_of_entry_number__isnull=True).aggregate(
                Sum('cif_fc'))['cif_fc__sum'] or 0
        return float(credit) - float(debit) - float(allotment)

    @cached_property
    def license_expiry(self):
        return self.license.license_expiry_date

    @cached_property
    def license_date(self):
        return self.license.license_date

    @cached_property
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

    @cached_property
    def total_debited_qty(self):
        return self.item_details.filter(transaction_type='D').aggregate(Sum('qty')).get('qty__sum', 0.00)

    @cached_property
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

    @cached_property
    def total_debited_cif_inr(self):
        return self.item_details.filter(transaction_type='D').aggregate(Sum('cif_inr')).get('cif_inr__sum', 0.00)

    @cached_property
    def opening_balance(self):
        return self.item_details.filter(transaction_type='C').aggregate(Sum('qty')).get('qty__sum', 0.00)

    @cached_property
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

    @cached_property
    def ge_file_number(self):
        return self.license.ge_file_number


@receiver(post_save, sender=LicenseImportItemsModel, dispatch_uid="update_balance")
def update_balance(sender, instance, **kwargs):
    item = instance
    from bill_of_entry.tasks import update_balance_values_task
    update_balance_values_task(item.id)
    from migrations_script import filter_list
    items_and_filters = filter_list()
    for item_name, query_filter in items_and_filters:
        from core.models import ItemNameModel
        nItem = ItemNameModel.objects.get(name=item_name)
        LicenseImportItemsModel.objects.filter(license=instance.license).filter(query_filter).update(item=nItem)
