from decimal import Decimal

from django.db import models
from django.db.models import Sum, IntegerField
from django.db.models.functions import Coalesce
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from django.utils.functional import cached_property

from allotment.models import AllotmentItems, Debit
from bill_of_entry.models import RowDetails, ARO
from core.models import ItemNameModel
from core.scripts.calculation import optimize_milk_distribution
from license.helper import round_down
from setup.migrations_script import filter_list
from veg_oil_allocator import allocate_priority_oils_with_min_pomace

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
CO = 'CO'
RA = 'RA'
LM = 'LM'

LICENCE_PURCHASE = (
    (GE, 'GE Purchase'),
    (MI, 'GE Operating'),
    (IP, 'GE Item Purchase'),
    (SM, 'SM Purchase'),
    (OT, 'OT Purchase'),
    (CO, 'Conversion'),
    (RA, 'Ravi Foods'),
    (LM, 'LM Purchase'),
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
    condition_sheet = models.TextField(null=True, blank=True)
    user_restrictions = models.TextField(null=True, blank=True)
    ledger_date = models.DateField(null=True, blank=True)
    is_audit = models.BooleanField(default=False)
    is_mnm = models.BooleanField(default=False)
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
    current_owner = models.ForeignKey('core.CompanyModel', on_delete=models.PROTECT, null=True, blank=True,
                                      related_name='online_data')
    file_transfer_status = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.license_number

    class Meta:
        ordering = ('license_expiry_date',)

    def use_balance_cif(self, amount, available_cif):
        amount = float(amount)  # convert float 'amount' to Decimal
        available_cif = float(available_cif)  # convert float 'amount' to Decimal
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
        credit = LicenseExportItemModel.objects.filter(license=self).aggregate(Sum('cif_fc'))[
                     'cif_fc__sum'] or 0
        debit = RowDetails.objects.filter(sr_number__license=self).filter(transaction_type=Debit).aggregate(
            Sum('cif_fc'))[
                    'cif_fc__sum'] or 0
        allotment = AllotmentItems.objects.filter(item__license=self,
                                                  allotment__bill_of_entry__bill_of_entry_number__isnull=True).aggregate(
            Sum('cif_fc'))['cif_fc__sum'] or 0
        return round_down(credit - (debit + allotment),2)

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
    def get_radiator(self):
        return self.get_item_data('RADIATOR')

    @cached_property
    def get_clutch(self):
        return self.get_item_data('CLUTCH ASSEMBLY')

    @cached_property
    def get_wiring(self):
        return self.get_item_data('WIRING HANRNESS')

    @cached_property
    def get_brake(self):
        return self.get_item_data('BRAKE ASSEMBLY')

    @cached_property
    def get_alternator(self):
        return self.get_item_data('ALTERNATOR')

    @cached_property
    def get_fuel_filter(self):
        return self.get_item_data('FUEL FILTER')

    @cached_property
    def import_license_grouped(self):
        return self.import_license.select_related('item').values('hs_code__hs_code', 'item__name', 'description',
                                                                 'item__unit_price') \
            .annotate(available_quantity_sum=Sum('available_quantity'),
                      quantity_sum=Sum('quantity')) \
            .order_by('item__name')

    def get_item_data(self, item_name):
        """
        Fetches consolidated data for a specific item, summing up quantities across all matching entries.
        """

        def fetch_item(item_name):
            normalized_name = item_name.strip().lower()
            # Filter all matching entries for the specified item_name
            matching_items = [
                item for item in self.import_license_grouped
                if item['item__name'] and item['item__name'].strip().lower() == normalized_name
            ]

            if matching_items:
                # Consolidate data
                available_quantity_sum = sum(item['available_quantity_sum'] for item in matching_items)
                quantity_sum = sum(item['quantity_sum'] for item in matching_items)
                # Use the first entry for static fields like 'hs_code__hs_code' and 'description'
                first_entry = matching_items[0]
                return {
                    'hs_code__hs_code': first_entry['hs_code__hs_code'],
                    'item__name': first_entry['item__name'],
                    'description': first_entry['description'],
                    'item__unit_price': first_entry['item__unit_price'],
                    'available_quantity_sum': available_quantity_sum,
                    'quantity_sum': quantity_sum
                }
            return {'available_quantity_sum': 0, 'quantity_sum': 0}

        restricted_items = ['JUICE', 'FOOD FLAVOUR BISCUITS', 'DIETARY FIBRE',
                            'LEAVENING AGENT', 'STARCH 1108', 'STARCH 3505', 'FRUIT/COCOA']

        if item_name in restricted_items:
            restricted_value = self.get_per_cif.get('tenRestriction', 0)
            if restricted_value > 200:
                return fetch_item(item_name)
            else:
                return {'available_quantity_sum': 0, 'quantity_sum': 0}

        return fetch_item(item_name)

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

    @cached_property
    def sugar_quantity(self):
        return self.get_item_data('SUGAR')

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

        if available_value <= 100:
            return {
                'cif_juice': 0, 'restricted_value': 0, 'qty_swp': 0, 'cif_swp': 0,
                'qty_cheese': 0, 'cif_cheese': 0, 'qty_wpc': 0, 'cif_wpc': 0,
                'veg_oil': 0, 'available_value': 0
            }

        restricted_value = self.get_per_cif.get('tenRestriction', 0)
        biscuit_juice = self.get_biscuit_juice
        juice_quantity = biscuit_juice.get('available_quantity_sum', 0)
        juice_unit_price = biscuit_juice.get('item__unit_price', 0)

        # Initialize CIF values
        cif_juice = cif_swp = cif_cheese = wpc_cif = 0

        # Juice CIF Calculation
        if juice_quantity > 50 and restricted_value > 200:
            cif_juice = min(juice_quantity * juice_unit_price, restricted_value, available_value)
            restricted_value = self.use_balance_cif(cif_juice, restricted_value)
            available_value = self.use_balance_cif(cif_juice, available_value)

        # SWP, Cheese, and WPC Calculations
        # Initialize a dictionary to store CIF values
        cif_values = {
            "cif_swp": 0,
            "cif_cheese": 0
        }

        # SWP, Cheese, and WPC Calculations
        for item_type, threshold, cif_var in [
            (self.get_swp, 100, "cif_swp"),
        ]:
            quantity = item_type.get("available_quantity_sum", 0)
            if quantity > threshold:
                unit_price = item_type.get("item__unit_price", 0)
                cif_value = min(quantity * unit_price, available_value)
                available_value = self.use_balance_cif(cif_value, available_value)

                # Store the CIF value in the dictionary
                cif_values[cif_var] = cif_value

        # Access the values like this:
        cif_swp = cif_values["cif_swp"]
        cif_cheese = cif_values["cif_cheese"]

        # Oil Distribution Logic
        oil_info = self.oil_queryset
        total_oil_available = oil_info.get('available_quantity_sum', 0)
        oil_hsn = oil_info.get('hs_code__hs_code', '')
        oil_pd = oil_info.get('description', '')

        oil_types = {
            'pko_oil': ('15132110', 1.2, False),
            'olive_oil': ('1500', 4.75, False),
            'pomace_oil': ('1500', 3, False),
            'rbd_oil': ('15119020', 1.1, False)
        }

        for key, (hs_code, price, used) in oil_types.items():
            if hs_code in oil_hsn or hs_code in oil_pd:
                oil_types[key] = (hs_code, price, True)

        if not oil_types['olive_oil'][2]:
            olive_cif = 0
        else:
            olive_cif = oil_types['olive_oil'][1]
        if not oil_types['pko_oil'][2]:
            pko_cif = 0
        else:
            pko_cif = oil_types['pko_oil'][1]
        if not oil_types['pomace_oil'][2]:
            pomace_cif = 0
        else:
            pomace_cif = oil_types['pomace_oil'][1]
        if not oil_types['rbd_oil'][2]:
            rbd_cif = 0
        else:
            rbd_cif = oil_types['rbd_oil'][1]
        oil_data = allocate_priority_oils_with_min_pomace(total_oil_available,available_value,
                                             olive_cif=olive_cif,
                                             rbd_cif=rbd_cif,
                                             pomace_cif=pomace_cif,
                                             pko_cif=pko_cif)
        # Ensure oil CIF values are calculated correctly
        if oil_data.get('Total_CIF'):
            available_value = self.use_balance_cif(oil_data.get('Total_CIF'), available_value)
            oil_data['rbd_oil'] = oil_data.get('RBD QTY', 0)
            oil_data['cif_rbd_oil'] = min(oil_data.get('rbd_oil', 0) * float(rbd_cif),
                                          oil_data.get('Total_CIF'))
            oil_data['pko_oil'] = oil_data.get('PKO QTY', 0)
            oil_data['cif_pko_oil'] = min(oil_data.get('pko_oil', 0) * float(pko_cif),
                                          oil_data.get('Total_CIF'))
            oil_data['olive_oil'] = oil_data.get('Olive QTY', 0)
            oil_data['cif_olive_oil'] = min(oil_data.get('olive_oil', 0) * float(olive_cif),
                                            oil_data.get('Total_CIF'))
            oil_data['pomace_oil'] = oil_data.get('Pomace QTY', 0)
            oil_data['cif_pomace_oil'] = min(oil_data.get('pomace_oil', 0) * float(pomace_cif),
                                             oil_data.get('Total_CIF'))
        elif olive_cif:
            oil_data['olive_oil'] = total_oil_available
            oil_data['cif_olive_oil'] = float(olive_cif) * float(total_oil_available)
            if pko_cif and oil_data['cif_olive_oil'] > float(available_value):
                oil_data['pko_oil'] = total_oil_available
                oil_data['cif_pko_oil'] = min(float(pko_cif) * float(total_oil_available),oil_data.get('Total_CIF'))
                if oil_data['cif_pko_oil'] <= 0:
                    oil_data['pko_oil'] = 0
                oil_data['olive_oil'] = 0
                oil_data['cif_olive_oil'] = 0
                available_value = self.use_balance_cif(oil_data['cif_pko_oil'], available_value)
            elif rbd_cif and oil_data['cif_olive_oil'] > float(available_value):
                oil_data['rbd_oil'] = total_oil_available
                oil_data['cif_rbd_oil'] = min(float(rbd_cif) * float(total_oil_available),oil_data.get('Total_CIF'))
                if oil_data['cif_rbd_oil'] <= 0:
                    oil_data['rbd_oil'] = 0
                available_value = self.use_balance_cif(oil_data['cif_rbd_oil'], available_value)
                oil_data['olive_oil'] = 0
                oil_data['cif_olive_oil'] = 0
            available_value = self.use_balance_cif(oil_data['cif_olive_oil'], available_value)
        elif pko_cif:
            oil_data['pko_oil'] = total_oil_available
            oil_data['cif_pko_oil'] = float(pko_cif) * float(total_oil_available)
            available_value = self.use_balance_cif(oil_data['cif_pko_oil'], available_value)
        elif rbd_cif:
            oil_data['rbd_oil'] = total_oil_available
            oil_data['cif_rbd_oil'] = float(rbd_cif) * float(total_oil_available)
            available_value = self.use_balance_cif(oil_data['cif_rbd_oil'], available_value)
        # Milk Product Distribution
        total_milk = self.get_mnm_pd.get('available_quantity_sum', 0)
        total_milk_cif = Decimal(available_value) + Decimal(cif_swp) + Decimal(cif_cheese)

        if total_milk_cif >= 200 and total_milk >= 100:
            unit_prices = {
                'swp': float(self.get_swp.get('item__unit_price', 1)),
                'cheese': float(self.get_cheese.get('item__unit_price', 5.5)),
                'wpc': float(self.get_wpc.get('item__unit_price', 15))
            }
            milk_data = optimize_milk_distribution(
                unit_prices['swp'], unit_prices['cheese'], unit_prices['wpc'],
                total_milk_cif, total_milk,
                True, True, True
            )

            cif_swp = min(milk_data.get('SWP', 0) * unit_prices['swp'], total_milk_cif)
            total_milk_cif = self.use_balance_cif(cif_swp, total_milk_cif)
            cif_cheese = min(milk_data.get('CHEESE', 0) * unit_prices['cheese'], total_milk_cif)
            total_milk_cif = self.use_balance_cif(cif_cheese, total_milk_cif)
            wpc_cif = min(milk_data.get('WPC', 0) * unit_prices['wpc'], total_milk_cif)
            total_milk_cif = self.use_balance_cif(wpc_cif, total_milk_cif)
            available_value = total_milk_cif
        else:
            milk_data = {'SWP': 0, 'CHEESE': 0, 'WPC': 0, 'total_value_used': 0}
        return {
            'cif_juice': cif_juice,
            'restricted_value': restricted_value,
            'qty_swp': milk_data.get('SWP', 0),
            'cif_swp': cif_swp,
            'qty_cheese': milk_data.get('CHEESE', 0),
            'cif_cheese': cif_cheese,
            'qty_wpc': milk_data.get('WPC', 0),
            'cif_wpc': wpc_cif,
            'veg_oil': oil_data,
            'available_value': available_value
        }

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

    @cached_property
    def latest_transfer(self):
        if self.transfers.order_by('-transfer_date', '-id'):
            return self.transfers.order_by('-transfer_date', '-id').first()
        elif self.current_owner:
            return "Current Owner is {}".format(self.current_owner.name)
        else:
            return "Data Not Found"

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
    license = models.ForeignKey('license.LicenseDetailsModel', on_delete=models.CASCADE, related_name='import_license',
                                db_index=True)
    hs_code = models.ForeignKey('core.HSCodeModel', on_delete=models.CASCADE, blank=True, related_name='import_item',
                                null=True, db_index=True)
    item = models.ForeignKey('core.ItemNameModel', related_name='license_items', on_delete=models.CASCADE, blank=True,
                             null=True, db_index=True)
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
        indexes = [
            models.Index(fields=['license']),  # âœ… Optimized indexing
            models.Index(fields=['hs_code']),  # âœ… Optimized indexing
            models.Index(fields=['item']),  # âœ… Optimized indexing
        ]

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
    def sorted_allotment_list(self):
        dict_list = []
        dict_return = {}
        data = self.allotment_details.filter(is_boe=False).order_by('allotment__company',
                                          'allotment__modified_on')
        company_data = list(set([c['allotment__company__name'] for c in
                                 self.allotment_details.filter(is_boe=False).order_by('allotment__company',
                                                            'allotment__modified_on','allotment__unit_value_per_unit').values(
                                     'allotment__company__name')]))
        for company in company_data:
            if company:
                if not company in list(dict_return.keys()):
                    dict_return[company] = {}
                dict_return[company]['company'] = company
                dict_return[company]['data_list'] = data.filter(allotment__company__name=company,is_boe=False)
                dict_return[company]['sum_total_qty'] = data.filter(allotment__company__name=company,is_boe=False).aggregate(
                    Sum('qty')).get('qty__sum', 0.00)
                dict_return[company]['sum_total_cif_fc'] = data.filter(allotment__company__name=company,is_boe=False).aggregate(
                    Sum('cif_fc')).get('cif_fc__sum', 0.00)
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


@receiver(post_save, sender=LicenseImportItemsModel)
def update_balance(sender, instance, **kwargs):
    item = instance
    from bill_of_entry.tasks import update_balance_values_task
    update_balance_values_task(item.id)
    items_and_filters = filter_list()
    for item_name, query_filter in items_and_filters:
        from core.models import ItemNameModel
        nItem = ItemNameModel.objects.get(name=item_name)
        LicenseImportItemsModel.objects.filter(license=instance.license).filter(query_filter).update(item=nItem)


class LicenseTransferModel(models.Model):
    license = models.ForeignKey(LicenseDetailsModel, on_delete=models.CASCADE, related_name="transfers")

    transfer_date = models.DateField(null=True, blank=True)

    from_company = models.ForeignKey('core.CompanyModel', on_delete=models.SET_NULL, null=True, blank=True, related_name='transfers_from')
    to_company = models.ForeignKey('core.CompanyModel', on_delete=models.SET_NULL, null=True, blank=True, related_name='transfers_to')

    transfer_status = models.CharField(max_length=50)
    transfer_initiation_date = models.DateTimeField(null=True, blank=True)
    transfer_acceptance_date = models.DateTimeField(null=True, blank=True)

    cbic_status = models.CharField(max_length=100, null=True, blank=True)
    cbic_response_date = models.DateTimeField(null=True, blank=True)

    user_id_transfer_initiation = models.CharField(max_length=100, null=True, blank=True)
    user_id_acceptance = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        if self.transfer_date:
            return f"{self.transfer_status} from {self.from_company.name if self.from_company else 'N/A'} to {self.to_company.name if self.to_company else 'N/A'} on {self.transfer_date}"
        else:
            return f"{self.transfer_status} from {self.from_company.name if self.from_company else 'N/A'} to {self.to_company.name if self.to_company else 'N/A'} on {self.transfer_initiation_date.date()}"

    def from_company_name(self):
        return self.from_company.name if self.from_company else "-"

    from_company_name.short_description = "From Company"

    def to_company_name(self):
        return self.to_company.name if self.to_company else "-"

    to_company_name.short_description = "To Company"