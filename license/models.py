# models.py  — cleaned & optimized
# NOTE: No schema changes; safe drop-in. Focused on correctness & perf within one file.
# license/models.py

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Dict, Any, Optional

from django.core.validators import RegexValidator, MinValueValidator
from django.db import models
from django.db.models import IntegerField, Count, Sum
from django.db.models.functions import Coalesce
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from django.utils.functional import cached_property

from allotment.models import AllotmentItems
from bill_of_entry.models import RowDetails, ARO, Debit
from bill_of_entry.tasks import update_balance_values_task
from core.models import AuditModel  # your existing timestamp/made_by mixin
from core.models import AuditModel, InvoiceEntity  # your existing timestamp/made_by mixin
from core.models import ItemNameModel, PurchaseStatus, SchemeCode, NotificationNumber
from core.scripts.calculation import optimize_milk_distribution
from license.helper import round_down
from scripts.veg_oil_allocator import allocate_priority_oils_with_min_pomace
from setup.migrations_script import filter_list

# -----------------------------
# Constants / Choices
# -----------------------------

DFIA = "26"

SCHEME_CODE_CHOICES = (
    (DFIA, "26 - Duty Free Import Authorization"),
)

N2009 = "098/2009"
N2015 = "019/2015"
N2023 = "025/2023"

NOTIFICATION_NORM_CHOICES = (
    (N2015, "019/2015"),
    (N2009, "098/2009"),
    (N2023, "025/2023"),
)

GE = "GE"
MI = "NP"
IP = "IP"
SM = "SM"
OT = "OT"
CO = "CO"
RA = "RA"
LM = "LM"

LICENCE_PURCHASE = (
    (GE, "GE Purchase"),
    (MI, "GE Operating"),
    (IP, "GE Item Purchase"),
    (SM, "SM Purchase"),
    (OT, "OT Purchase"),
    (CO, "Conversion"),
    (RA, "Ravi Foods"),
    (LM, "LM Purchase"),
)

KG = "kg"
UNIT_CHOICES = ((KG, "kg"),)

USD = "usd"
EURO = "euro"
CURRENCY_CHOICES = ((USD, "usd"), (EURO, "euro"))


def license_path(instance, filename):
    """Upload path: <license_number>/<type>.pdf"""
    return f"{instance.license.license_number}/{instance.type}.pdf"


# -----------------------------
# License Header
# -----------------------------

class LicenseDetailsModel(AuditModel):
    purchase_status = models.CharField(choices=LICENCE_PURCHASE, max_length=2, default=GE)
    scheme_code = models.CharField(choices=SCHEME_CODE_CHOICES, max_length=10, default=DFIA)
    notification_number = models.CharField(choices=NOTIFICATION_NORM_CHOICES, max_length=10, default=N2023)

    license_number = models.CharField(max_length=50, unique=True)
    license_date = models.DateField(null=True, blank=True)
    license_expiry_date = models.DateField(null=True, blank=True)
    file_number = models.CharField(max_length=30, null=True, blank=True)

    exporter = models.ForeignKey("core.CompanyModel", on_delete=models.CASCADE, null=True, blank=True)
    port = models.ForeignKey("core.PortModel", on_delete=models.CASCADE, null=True, blank=True)

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
    is_au = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    balance_cif = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )

    export_item = models.CharField(max_length=255, null=True, blank=True)
    is_incomplete = models.BooleanField(default=False)
    is_expired = models.BooleanField(default=False)
    is_individual = models.BooleanField(default=False)

    ge_file_number = models.IntegerField(default=0)

    fob = models.IntegerField(default=0, null=True, blank=True)

    billing_rate = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    billing_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )

    admin_search_fields = ("license_number",)

    current_owner = models.ForeignKey(
        "core.CompanyModel", on_delete=models.PROTECT, null=True, blank=True, related_name="online_data"
    )
    file_transfer_status = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ("license_expiry_date",)

    def __str__(self) -> str:
        return self.license_number

    def get_absolute_url(self) -> str:
        return reverse("license-detail", kwargs={"license": self.license_number})

    # ---------- helpers / balances ----------

    def use_balance_cif(self, amount: float, available_cif: float) -> float:
        """
        Consume `amount` from `available_cif` (both coerced to float), not below 0.
        """
        amt = float(amount or 0)
        avail = float(available_cif or 0)
        if amt <= avail:
            return avail - amt
        return 0.0

    @cached_property
    def get_norm_class(self) -> str:
        """CSV of all SION norm codes on export lines."""
        return ",".join([e.norm_class.norm_class for e in self.export_license.all() if e.norm_class])

    @cached_property
    def opening_balance(self) -> float:
        return self.export_license.all().aggregate(sum=Sum("cif_fc"))["sum"] or 0.0

    @cached_property
    def opening_fob(self) -> float:
        return self.export_license.all().aggregate(sum=Sum("fob_inr"))["sum"] or 0.0

    def opening_cif_inr(self) -> float:
        return self.export_license.all().aggregate(sum=Sum("cif_inr"))["sum"] or 0.0

    @property
    def get_total_debit(self) -> float:
        return self.import_license.aggregate(total=Sum("debited_value"))["total"] or 0.0

    @property
    def get_total_allotment(self) -> float:
        return self.import_license.aggregate(total=Sum("allotted_value"))["total"] or 0.0

    @property
    def get_balance_cif(self) -> float:
        """
        Authoritative live balance:
        SUM(Export.cif_fc) - (SUM(BOE debit cif_fc for license) + SUM(allotments cif_fc (unattached BOE))).
        """
        credit = (
                LicenseExportItemModel.objects.filter(license=self).aggregate(Sum("cif_fc"))["cif_fc__sum"] or 0
        )
        debit = (
                RowDetails.objects.filter(sr_number__license=self, transaction_type=Debit)
                .aggregate(Sum("cif_fc"))["cif_fc__sum"]
                or 0
        )
        allotment = (
                AllotmentItems.objects.filter(
                    item__license=self, allotment__bill_of_entry__bill_of_entry_number__isnull=True
                ).aggregate(Sum("cif_fc"))["cif_fc__sum"]
                or 0
        )
        return round_down(float(credit) - (float(debit) + float(allotment)), 2)

    def get_party_name(self) -> str:
        return str(self.exporter)[:8]

    # ---------- grouped import summaries ----------

    @cached_property
    def import_license_grouped(self):
        """
        Group import rows to consolidate quantities by item name/HSN.
        NOTE: Kept keys compatible with existing code ('item__name' etc.).
        """
        return (
            self.import_license.select_related("hs_code")
            .values("hs_code__hs_code", "items__name", "description", "items__unit_price")
            .annotate(
                available_quantity_sum=Sum("available_quantity"),
                quantity_sum=Sum("quantity"),
            )
            .order_by("items__name")
        )

    @cached_property
    def _import_group_by_name_map(self) -> Dict[str, Dict[str, Any]]:
        """
        Speed map for get_item_data: lower(item_name) -> consolidated dict.
        Uses `items__name` (M2M).
        """
        m: Dict[str, Dict[str, Any]] = {}
        for row in self.import_license_grouped:
            name = row.get("items__name")
            if not name:
                continue
            key = str(name).strip().lower()
            if key not in m:
                m[key] = {
                    "hs_code__hs_code": row.get("hs_code__hs_code"),
                    "items__name": name,
                    "description": row.get("description"),
                    "items__unit_price": row.get("items__unit_price"),
                    "available_quantity_sum": 0,
                    "quantity_sum": 0,
                }
            m[key]["available_quantity_sum"] += row.get("available_quantity_sum") or 0
            m[key]["quantity_sum"] += row.get("quantity_sum") or 0
        return m

    def get_item_data(self, item_name: str) -> Dict[str, Any]:
        """
        Consolidated data for a specific item by name (case-insensitive).
        Certain items are gated by 10% restriction (see restricted_items).
        """
        # Restriction gate
        restricted_items = {
            "JUICE",
            "FOOD FLAVOUR BISCUITS",
            "DIETARY FIBRE",
            "LEAVENING AGENT",
            "STARCH 1108",
            "STARCH 3505",
            "FRUIT/COCOA",
        }
        normalized = (item_name or "").strip().upper()

        if normalized in restricted_items:
            if (self.get_per_cif or {}).get("tenRestriction", 0) <= 200:
                return {"available_quantity_sum": 0, "quantity_sum": 0}

        key = normalized.lower()
        hit = self._import_group_by_name_map.get(key)
        if hit:
            return hit
        return {"available_quantity_sum": 0, "quantity_sum": 0}

    @cached_property
    def import_license_head_grouped(self):
        return (
            self.import_license.select_related("hs_code")
            .values("items__head__name", "description", "items__unit_price", "hs_code__hs_code", 'items__name')
            .annotate(
                available_quantity_sum=Sum("available_quantity"),
                quantity_sum=Sum("quantity"),
            )
            .order_by("items__name")
        )

    def get_item_head_data(self, item_name: str) -> Dict[str, Any]:
        return next(
            (
                row
                for row in self.import_license_head_grouped
                if (row.get("items__head__name") == item_name)
            ),
            {"available_quantity_sum": 0, "quantity_sum": 0},
        )

    # ---------- domain convenience lookups ----------

    @cached_property
    def get_glass_formers(self) -> Dict[str, Any]:
        total_quantity = self.get_item_data("RUTILE").get("quantity_sum") or 0
        available_quantity = self.get_item_data("RUTILE").get("available_quantity_sum") or 0
        opening_balance = self.opening_balance or 0

        if not total_quantity:
            return {"borax": 0, "rutile": 0, "total": 0, "description": self.get_item_data("RUTILE").get("description")}

        avg = float(opening_balance) / float(total_quantity)
        if avg <= 3:
            borax_quantity = (total_quantity / Decimal(".62")) * Decimal(".1")
            debit = (
                    RowDetails.objects.filter(
                        sr_number__license=self, bill_of_entry__company=567, transaction_type=Debit
                    ).aggregate(Sum("qty"))["qty__sum"]
                    or Decimal("0")
            )
            allotment = (
                    AllotmentItems.objects.filter(
                        item__license=self,
                        allotment__company=567,
                        allotment__bill_of_entry__bill_of_entry_number__isnull=True,
                    ).aggregate(Sum("qty"))["qty__sum"]
                    or Decimal("0")
            )
            borax = min(Decimal(borax_quantity) - (Decimal(debit) + Decimal(allotment)), Decimal(available_quantity))
        else:
            borax = 0
        rutile = min(Decimal(available_quantity) - Decimal(borax), Decimal(available_quantity))
        return {
            "borax": borax,
            "rutile": rutile,
            "total": total_quantity,
            "description": self.get_item_data("RUTILE").get("description"),
        }

    @cached_property
    def borax_quantity(self):
        return self.get_glass_formers.get("borax")

    @cached_property
    def rutile_quantity(self):
        return self.get_glass_formers.get("rutile")

    @cached_property
    def average_unit_price(self):
        # Guard against division by zero
        rutile_qty = (self.get_glass_formers.get("rutile") or 0) or Decimal("0")
        if not rutile_qty:
            return Decimal("0.00")
        return round(
            Decimal(self.cif_value_balance_glass.get("rutile") or 0) / Decimal(rutile_qty), 2
        )

    # ---- many thin wrappers for items/heads ----
    # (kept as-is for compatibility; see original file for the full set)

    @cached_property
    def get_intermediates_namely(self):
        return self.get_item_data("ALUMINIUM OXIDE, ZINC OXIDE, ZIRCONIUM OXIDE")

    @cached_property
    def get_modifiers_namely(self):
        return self.get_item_data("SODA ASH")

    @cached_property
    def get_other_special_additives(self):
        return self.get_item_data("TITANIUM DIOXIDE")

    @cached_property
    def cif_value_balance_glass(self):
        available_value = self.get_balance_cif
        soda_ash_qty = self.get_modifiers_namely.get("available_quantity_sum") or 0
        titanium_qty = self.get_other_special_additives.get("available_quantity_sum") or 0
        borax_qty = self.get_glass_formers.get("borax") or 0
        rutile_qty = self.get_glass_formers.get("rutile") or 0

        borax_cif = soda_ash_cif = rutile_cif = titanium_cif = 0
        if borax_qty > 100:
            borax_cif = min(borax_qty * Decimal(".7"), available_value)
            available_value = self.use_balance_cif(borax_cif, available_value)
        if soda_ash_qty > 100:
            soda_ash_cif = min(soda_ash_qty * Decimal(".3"), available_value)
            available_value = self.use_balance_cif(soda_ash_cif, available_value)
        if rutile_qty > 100:
            rutile_cif = min(rutile_qty * Decimal("3.5"), available_value)
            available_value = self.use_balance_cif(rutile_cif, available_value)
        if titanium_qty > 100:
            titanium_cif = min(titanium_qty * Decimal("1.8"), available_value)
            available_value = self.use_balance_cif(titanium_cif, available_value)
        return {
            "borax": borax_cif,
            "rutile": rutile_cif,
            "soda_ash": soda_ash_cif,
            "titanium": titanium_cif,
            "balance_cif": available_value,
        }

    # ---- Biscuits domain block (unchanged externally; internal perf tuned) ----

    @cached_property
    def oil_queryset(self):
        return self.get_item_head_data("VEGETABLE OIL")

    @cached_property
    def get_rbd(self):
        return self.get_item_data("RBD PALMOLEIN OIL")

    @cached_property
    def get_pko(self):
        return self.get_item_data("PALM KERNEL OIL")

    @cached_property
    def get_veg_oil(self):
        return self.get_item_data("EDIBLE VEGETABLE OIL")

    @cached_property
    def get_food_flavour(self):
        return self.get_item_data("FOOD FLAVOUR BISCUITS")

    @cached_property
    def get_biscuit_juice(self):
        return self.get_item_data("JUICE")

    @cached_property
    def get_dietary_fibre(self):
        return self.get_item_data("DIETARY FIBRE")

    @cached_property
    def get_wheat_starch(self):
        return self.get_item_data("STARCH 1108")

    @cached_property
    def get_modified_starch(self):
        return self.get_item_data("STARCH 3505")

    @cached_property
    def get_leavening_agent(self):
        return self.get_item_data("LEAVENING AGENT")

    @cached_property
    def get_fruit(self):
        """Balance Cocoa quantity proxy."""
        return self.get_item_data("FRUIT/COCOA")

    @cached_property
    def get_mnm_pd(self):
        return self.get_item_head_data("MILK & MILK Product")

    @cached_property
    def get_wpc(self):
        return self.get_item_data("WPC")

    @cached_property
    def get_swp(self):
        return self.get_item_data("SWP")

    @cached_property
    def get_cheese(self):
        return self.get_item_data("CHEESE")

    @cached_property
    def cif_value_balance_biscuits(self):
        """
        Allocation engine: restricted value + dairy + oils; uses use_balance_cif to consume budget.
        """
        available_value = self.get_balance_cif
        if available_value <= 100:
            return {
                "cif_juice": 0,
                "restricted_value": 0,
                "qty_swp": 0,
                "cif_swp": 0,
                "qty_cheese": 0,
                "cif_cheese": 0,
                "qty_wpc": 0,
                "cif_wpc": 0,
                "veg_oil": {'rbd_oil': 0, 'cif_rbd_oil': 0,
                            'pko_oil': 0, 'cif_pko_oil': 0,
                            'olive_oil': 0, 'cif_olive_oil': 0,
                            'pomace_oil': 0, 'cif_pomace_oil': 0},
                "available_value": 0,
            }

        restricted_value = (self.get_per_cif or {}).get("tenRestriction", 0)

        # Juice
        biscuit_juice = self.get_biscuit_juice
        juice_quantity = biscuit_juice.get("available_quantity_sum", 0) or 0
        juice_unit_price = biscuit_juice.get("items__unit_price", 0) or 0
        cif_juice = 0
        if juice_quantity > 50 and restricted_value > 200:
            cif_juice = min(juice_quantity * juice_unit_price, restricted_value, available_value)
            restricted_value = self.use_balance_cif(cif_juice, restricted_value)
            available_value = self.use_balance_cif(cif_juice, available_value)

        # Dairy base
        cif_swp = cif_cheese = wpc_cif = 0

        # Oils
        oil_info = self.oil_queryset
        total_oil_available = oil_info.get("available_quantity_sum", 0) or 0
        oil_hsn = oil_info.get("hs_code__hs_code", "") or ""
        oil_pd = oil_info.get("description", "") or ""

        oil_types = {
            "pko_oil": ("15132110", 1.2, False),
            "olive_oil": ("1500", 4.75, False),
            "pomace_oil": ("1500", 3, False),
            "rbd_oil": ("15119020", 1.1, False),
        }
        for key, (hs_code, price, used) in list(oil_types.items()):
            oil_types[key] = (hs_code, price, (hs_code in oil_hsn) or (hs_code in oil_pd))

        olive_cif = oil_types["olive_oil"][1] if oil_types["olive_oil"][2] else 0
        pko_cif = oil_types["pko_oil"][1] if oil_types["pko_oil"][2] else 0
        pomace_cif = oil_types["pomace_oil"][1] if oil_types["pomace_oil"][2] else 0
        rbd_cif = oil_types["rbd_oil"][1] if oil_types["rbd_oil"][2] else 0

        oil_data = allocate_priority_oils_with_min_pomace(
            total_oil_available,
            available_value,
            olive_cif=olive_cif,
            rbd_cif=rbd_cif,
            pomace_cif=pomace_cif,
            pko_cif=pko_cif,
        )

        if oil_data.get("Total_CIF"):
            available_value = self.use_balance_cif(oil_data.get("Total_CIF"), available_value)
            oil_data["rbd_oil"] = oil_data.get("RBD QTY", 0)
            oil_data["cif_rbd_oil"] = min(oil_data.get("rbd_oil", 0) * float(rbd_cif), oil_data.get("Total_CIF"))
            oil_data["pko_oil"] = oil_data.get("PKO QTY", 0)
            oil_data["cif_pko_oil"] = min(oil_data.get("pko_oil", 0) * float(pko_cif), oil_data.get("Total_CIF"))
            oil_data["olive_oil"] = oil_data.get("Olive QTY", 0)
            oil_data["cif_olive_oil"] = min(oil_data.get("olive_oil", 0) * float(olive_cif), oil_data.get("Total_CIF"))
            oil_data["pomace_oil"] = oil_data.get("Pomace QTY", 0)
            oil_data["cif_pomace_oil"] = min(oil_data.get("pomace_oil", 0) * float(pomace_cif),
                                             oil_data.get("Total_CIF"))
        elif olive_cif:
            oil_data["olive_oil"] = total_oil_available
            oil_data["cif_olive_oil"] = float(olive_cif) * float(total_oil_available)
            if pko_cif and oil_data["cif_olive_oil"] > float(available_value):
                oil_data["pko_oil"] = total_oil_available
                oil_data["cif_pko_oil"] = min(float(pko_cif) * float(total_oil_available), oil_data.get("Total_CIF"))
                if oil_data["cif_pko_oil"] <= 0:
                    oil_data["pko_oil"] = 0
                oil_data["olive_oil"] = 0
                oil_data["cif_olive_oil"] = 0
                available_value = self.use_balance_cif(oil_data["cif_pko_oil"], available_value)
            elif rbd_cif and oil_data["cif_olive_oil"] > float(available_value):
                oil_data["rbd_oil"] = total_oil_available
                oil_data["cif_rbd_oil"] = min(float(rbd_cif) * float(total_oil_available), oil_data.get("Total_CIF"))
                if oil_data["cif_rbd_oil"] <= 0:
                    oil_data["rbd_oil"] = 0
                available_value = self.use_balance_cif(oil_data["cif_rbd_oil"], available_value)
                oil_data["olive_oil"] = 0
                oil_data["cif_olive_oil"] = 0
            available_value = self.use_balance_cif(oil_data["cif_olive_oil"], available_value)
        elif pko_cif:
            oil_data["pko_oil"] = total_oil_available
            oil_data["cif_pko_oil"] = float(pko_cif) * float(total_oil_available)
            available_value = self.use_balance_cif(oil_data["cif_pko_oil"], available_value)
        elif rbd_cif:
            oil_data["rbd_oil"] = total_oil_available
            oil_data["cif_rbd_oil"] = float(rbd_cif) * float(total_oil_available)
            available_value = self.use_balance_cif(oil_data["cif_rbd_oil"], available_value)

        # Milk Product Distribution
        total_milk = self.get_mnm_pd.get("available_quantity_sum", 0) or 0
        total_milk_cif = Decimal(available_value) + Decimal(cif_swp or 0) + Decimal(cif_cheese or 0)

        if total_milk_cif >= 200 and total_milk >= 100:
            unit_prices = {
                "swp": float(self.get_swp.get("items__unit_price", 1) or 1),
                "cheese": float(self.get_cheese.get("items__unit_price", 5.5) or 5.5),
                "wpc": float(self.get_wpc.get("items__unit_price", 15) or 15),
            }

            # check which items actually have quantity > 0
            use_swp = (self.get_swp.get("quantity_sum") or 0) > 0
            use_cheese = (self.get_cheese.get("quantity_sum") or 0) > 0
            use_wpc = (self.get_wpc.get("quantity_sum") or 0) > 0

            # call optimizer with only valid flags
            milk_data = optimize_milk_distribution(
                unit_prices["swp"],
                unit_prices["cheese"],
                unit_prices["wpc"],
                total_milk_cif,
                total_milk,
                use_swp,
                use_cheese,
                use_wpc,
            )
            cif_swp = min(milk_data.get("SWP", 0) * unit_prices["swp"], total_milk_cif)
            total_milk_cif = self.use_balance_cif(cif_swp, total_milk_cif)
            cif_cheese = min(milk_data.get("CHEESE", 0) * unit_prices["cheese"], total_milk_cif)
            total_milk_cif = self.use_balance_cif(cif_cheese, total_milk_cif)
            wpc_cif = min(milk_data.get("WPC", 0) * unit_prices["wpc"], total_milk_cif)
            total_milk_cif = self.use_balance_cif(wpc_cif, total_milk_cif)
            available_value = total_milk_cif
        else:
            milk_data = {"SWP": 0, "CHEESE": 0, "WPC": 0, "total_value_used": 0}

        return {
            "cif_juice": cif_juice,
            "restricted_value": restricted_value,
            "qty_swp": milk_data.get("SWP", 0),
            "cif_swp": cif_swp,
            "qty_cheese": milk_data.get("CHEESE", 0),
            "cif_cheese": cif_cheese,
            "qty_wpc": milk_data.get("WPC", 0),
            "cif_wpc": wpc_cif,
            "veg_oil": oil_data,
            "available_value": available_value,
        }

    # ---- other domain getters (kept) ----

    @cached_property
    def get_pp(self):
        return self.get_item_data("PP")

    @cached_property
    def get_aluminium(self):
        return self.get_item_data("ALUMINIUM FOIL")

    @cached_property
    def get_paper_and_paper(self):
        return self.get_item_data("PAPER & PAPER")

    @cached_property
    def get_cmc(self):
        return self.get_item_data("RELEVANT ADDITIVES DESCRIPTION")

    @cached_property
    def get_chickpeas(self):
        return self.get_item_data("CEREALS FLAKES")

    @cached_property
    def get_food_flavour_namkeen(self):
        return self.get_item_data("FOOD FLAVOUR NAMKEEN")

    @cached_property
    def get_juice(self):
        return self.get_item_data("FRUIT JUICE")

    @cached_property
    def get_tartaric_acid(self):
        return self.get_item_data("CITRIC ACID / TARTARIC ACID")

    @cached_property
    def get_essential_oil(self):
        return self.get_item_data("ESSENTIAL OIL")

    @cached_property
    def get_food_flavour_confectionery(self):
        return self.get_item_data("FOOD FLAVOUR CONFECTIONERY")

    def get_other_confectionery(self):
        return self.get_item_data("OTHER CONFECTIONERY INGREDIENTS")

    def get_starch_confectionery(self):
        return self.get_item_data("EMULSIFIER")

    @cached_property
    def get_per_cif(self) -> Optional[Dict[str, float]]:
        """
        Compute % restriction budgets based on norm class (E132/E126/E1/E5).
        Uses filtered aggregates to reduce query count.
        Returns dict like {'tenRestriction': x} or {'twoRestriction': x, ...}
        """
        available_value = self.get_balance_cif
        credit = self.opening_balance or 0

        first_norm = self.export_license.all().values_list("norm_class__norm_class", flat=True).first()
        if not first_norm:
            return None

        def _sum_for_head(name: str) -> float:
            vals = self.import_license.filter(items__head__name=name).aggregate(
                dv=Coalesce(Sum("debited_value"), 0, output_field=IntegerField()),
                av=Coalesce(Sum("allotted_value"), 0, output_field=IntegerField()),
            )
            return float(vals["dv"] + vals["av"])

        if "E132" in str(first_norm):
            credit_3 = credit * 0.03
            conf_3 = _sum_for_head("NAMKEEN 3% Restriction")
            credit_5 = credit * 0.05
            conf_5 = _sum_for_head("NAMKEEN 5% Restriction")
            return {
                "threeRestriction": min(available_value, max(round_down(credit_3 - conf_3), 0)),
                "fiveRestriction": min(available_value, max(round_down(credit_5 - conf_5), 0)),
            }

        if "E126" in str(first_norm):
            credit_3 = credit * 0.03
            conf_3 = _sum_for_head("PICKLE 3% Restriction")
            return {"threeRestriction": min(available_value, max(round_down(credit_3 - conf_3), 0))}

        if "E1" in str(first_norm):
            credit_2 = credit * 0.02
            conf_2 = _sum_for_head("CONFECTIONERY 2% Restriction")
            credit_3 = credit * 0.03
            conf_3 = _sum_for_head("CONFECTIONERY 3% Restriction")
            credit_5 = credit * 0.05
            conf_5 = _sum_for_head("CONFECTIONERY 5% Restriction")
            return {
                "twoRestriction": min(available_value, max(round_down(credit_2 - conf_2), 0)),
                "threeRestriction": min(available_value, max(round_down(credit_3 - conf_3), 0)),
                "fiveRestriction": min(available_value, max(round_down(credit_5 - conf_5), 0)),
            }

        if "E5" in str(first_norm):
            credit_10 = credit * 0.10
            total_value = _sum_for_head("BISCUIT 10% Restriction")
            return {"tenRestriction": min(max(round_down(credit_10 - total_value), 0), available_value)}

        return None

    @cached_property
    def latest_transfer(self):
        qs = self.transfers.order_by("-transfer_date", "-id")
        if qs.exists():
            return qs.first()
        if self.current_owner:
            return f"Current Owner is {self.current_owner.name}"
        return "Data Not Found"


# -----------------------------
# Export Items
# -----------------------------

class LicenseExportItemModel(models.Model):
    license = models.ForeignKey("license.LicenseDetailsModel", on_delete=models.CASCADE, related_name="export_license")
    description = models.CharField(max_length=255, blank=True, db_index=True, null=True)
    item = models.ForeignKey(
        "core.ItemNameModel", related_name="export_licenses", on_delete=models.CASCADE, null=True, blank=True
    )
    norm_class = models.ForeignKey(
        "core.SionNormClassModel", null=True, blank=True, on_delete=models.CASCADE, related_name="export_item"
    )

    duty_type = models.CharField(max_length=255, default="Basic")
    net_quantity = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    old_quantity = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default=KG)

    fob_fc = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    fob_inr = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    fob_exchange_rate = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    currency = models.CharField(choices=CURRENCY_CHOICES, default=USD, max_length=5)
    value_addition = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    cif_fc = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    cif_inr = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )

    def __str__(self) -> str:
        return getattr(self.item, "name", "") or ""

    def balance_cif_fc(self) -> float:
        credit = (
                LicenseExportItemModel.objects.filter(license=self.license).aggregate(Sum("cif_fc"))["cif_fc__sum"] or 0
        )
        debit = (
                RowDetails.objects.filter(sr_number__license=self.license, transaction_type=Debit)
                .aggregate(Sum("cif_fc"))["cif_fc__sum"]
                or 0
        )
        allotment = (
                AllotmentItems.objects.filter(
                    item__license=self.license, allotment__bill_of_entry__bill_of_entry_number__isnull=True
                ).aggregate(Sum("cif_fc"))["cif_fc__sum"]
                or 0
        )
        return float(credit) - float(debit + allotment)


# -----------------------------
# Import Items
# -----------------------------

class LicenseImportItemsModel(models.Model):
    serial_number = models.IntegerField(default=0)
    license = models.ForeignKey(
        "license.LicenseDetailsModel", on_delete=models.CASCADE, related_name="import_license", db_index=True
    )
    hs_code = models.ForeignKey(
        "core.HSCodeModel", on_delete=models.CASCADE, blank=True, related_name="import_item", null=True, db_index=True
    )
    items = models.ManyToManyField(ItemNameModel, blank=True, related_name="license_import_item")

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

    admin_search_fields = ("license__license_number",)

    class Meta:
        ordering = ["license__license_expiry_date", "serial_number"]
        unique_together = (("license", "serial_number"),)
        indexes = [
            models.Index(fields=["license"]),
            models.Index(fields=["hs_code"]),
        ]

    def __str__(self) -> str:
        return f"{self.license}-{self.serial_number}"

    @cached_property
    def required_cif(self):
        """
        If available quantity > 100, use the first linked item's head.unit_rate as the multiplier.
        (Original code referenced self.item.head, but this model uses M2M `items`.)
        """
        if self.available_quantity and float(self.available_quantity) > 100:
            first_item = self.items.first()
            unit_rate = getattr(getattr(first_item, "head", None), "unit_rate", None)
            if unit_rate:
                return self.available_quantity * unit_rate
        return 0

    @cached_property
    def balance_quantity(self):
        from core.scripts.calculate_balance import calculate_available_quantity

        return calculate_available_quantity(self)

    @cached_property
    def balance_cif_fc(self) -> float:
        """
        Row-level balance. For special rows (0 / 0.01 / 0.1), fall back to license-level debits/allotments.
        """
        if not self.cif_fc or float(self.cif_fc) in (0, 0.1, 0.01):
            credit = (
                    LicenseExportItemModel.objects.filter(license=self.license).aggregate(Sum("cif_fc"))[
                        "cif_fc__sum"] or 0
            )
            debit = (
                    RowDetails.objects.filter(sr_number__license=self.license, transaction_type=Debit)
                    .aggregate(Sum("cif_fc"))["cif_fc__sum"]
                    or 0
            )
            allotment = (
                    AllotmentItems.objects.filter(
                        item__license=self.license, allotment__bill_of_entry__bill_of_entry_number__isnull=True
                    ).aggregate(Sum("cif_fc"))["cif_fc__sum"]
                    or 0
            )
        else:
            credit = self.cif_fc or 0
            debit = (
                    RowDetails.objects.filter(sr_number=self, transaction_type=Debit)
                    .aggregate(Sum("cif_fc"))["cif_fc__sum"]
                    or 0
            )
            allotment = (
                    AllotmentItems.objects.filter(
                        item=self, allotment__bill_of_entry__bill_of_entry_number__isnull=True
                    ).aggregate(Sum("cif_fc"))["cif_fc__sum"]
                    or 0
            )
        return float(credit) - float(debit) - float(allotment)

    @cached_property
    def license_expiry(self):
        return self.license.license_expiry_date

    @cached_property
    def license_date(self):
        return self.license.license_date

    @cached_property
    def sorted_item_list(self):
        """
        Company-grouped BOE details with sums.
        (Kept compatible; optimized a bit for readability.)
        """
        dict_list = []
        dict_return = {}
        data = self.item_details.order_by("transaction_type", "bill_of_entry__company",
                                          "bill_of_entry__bill_of_entry_date")
        company_names = (
            self.item_details.order_by("transaction_type", "bill_of_entry__company",
                                       "bill_of_entry__bill_of_entry_date")
            .values_list("bill_of_entry__company__name", flat=True)
            .distinct()
        )
        for company in company_names:
            if company:
                dict_return.setdefault(company, {})
                dict_return[company]["company"] = company
                dict_return[company]["data_list"] = data.filter(bill_of_entry__company__name=company)
                dict_return[company]["sum_total_qty"] = (
                    data.filter(bill_of_entry__company__name=company).aggregate(Sum("qty")).get("qty__sum", 0.00)
                )
                dict_return[company]["sum_total_cif_fc"] = (
                    data.filter(bill_of_entry__company__name=company).aggregate(Sum("cif_fc")).get("cif_fc__sum", 0.00)
                )
                dict_return[company]["sum_total_cif_inr"] = (
                    data.filter(bill_of_entry__company__name=company).aggregate(Sum("cif_inr")).get("cif_inr__sum",
                                                                                                    0.00)
                )
                dict_list.append(dict_return[company])
        dict_return["item_details"] = dict_list
        return dict_return

    @cached_property
    def sorted_allotment_list(self):
        dict_list = []
        dict_return = {}
        data = self.allotment_details.filter(is_boe=False).order_by("allotment__company", "allotment__modified_on")
        company_names = (
            self.allotment_details.filter(is_boe=False)
            .order_by("allotment__company", "allotment__modified_on", "allotment__unit_value_per_unit")
            .values_list("allotment__company__name", flat=True)
            .distinct()
        )
        for company in company_names:
            if company:
                dict_return.setdefault(company, {})
                dict_return[company]["company"] = company
                dict_return[company]["data_list"] = data.filter(allotment__company__name=company, is_boe=False)
                dict_return[company]["sum_total_qty"] = (
                    data.filter(allotment__company__name=company, is_boe=False).aggregate(Sum("qty")).get("qty__sum",
                                                                                                          0.00)
                )
                dict_return[company]["sum_total_cif_fc"] = (
                    data.filter(allotment__company__name=company, is_boe=False)
                    .aggregate(Sum("cif_fc"))
                    .get("cif_fc__sum", 0.00)
                )
                dict_list.append(dict_return[company])
        dict_return["item_details"] = dict_list
        return dict_return

    @cached_property
    def total_debited_qty(self):
        return self.item_details.filter(transaction_type="D").aggregate(Sum("qty")).get("qty__sum", 0.00)

    @cached_property
    def total_debited_cif_fc(self):
        debited = self.item_details.filter(transaction_type="D").aggregate(Sum("cif_fc")).get("cif_fc__sum", 0.00)
        alloted = (
                self.allotment_details.filter(
                    allotment__bill_of_entry__bill_of_entry_number__isnull=True,
                    allotment__type=ARO,
                ).aggregate(Sum("cif_fc"))["cif_fc__sum"]
                or 0
        )
        total = (debited or 0) + (alloted or 0)
        return round(total or 0, 0)

    @cached_property
    def total_debited_cif_inr(self):
        return self.item_details.filter(transaction_type="D").aggregate(Sum("cif_inr")).get("cif_inr__sum", 0.00)

    @cached_property
    def opening_balance(self):
        return self.item_details.filter(transaction_type="C").aggregate(Sum("qty")).get("qty__sum", 0.00)

    @cached_property
    def usable(self):
        if hasattr(self, "item") and getattr(self, "item", None) and getattr(self.item, "head", None):
            if self.license.notification_number == N2015 and self.items.head.is_restricted:
                return self.old_quantity
        value = self.item_details.filter(transaction_type="C").aggregate(Sum("qty")).get("qty__sum", 0.00)
        return round(value or 0, 0)


# -----------------------------
# Documents
# -----------------------------

class LicenseDocumentModel(models.Model):
    license = models.ForeignKey("license.LicenseDetailsModel", on_delete=models.CASCADE,
                                related_name="license_documents")
    type = models.CharField(max_length=255)
    file = models.FileField(upload_to=license_path)


# -----------------------------
# Status / Workflow
# -----------------------------

class StatusModel(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self) -> str:
        return self.name


class OfficeModel(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self) -> str:
        return self.name


class AlongWithModel(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self) -> str:
        return self.name


class DateModel(models.Model):
    date = models.DateField()

    def __str__(self) -> str:
        return str(self.date)


class LicenseInwardOutwardModel(models.Model):
    date = models.ForeignKey("license.DateModel", on_delete=models.CASCADE, related_name="license_status")
    license = models.ForeignKey(
        "license.LicenseDetailsModel", on_delete=models.CASCADE, related_name="license_status", null=True, blank=True
    )
    status = models.ForeignKey("license.StatusModel", on_delete=models.CASCADE, related_name="license_status")
    office = models.ForeignKey("license.OfficeModel", on_delete=models.CASCADE, related_name="license_status")

    description = models.TextField(null=True, blank=True)
    amd_sheets_number = models.CharField(max_length=100, null=True, blank=True)
    copy = models.BooleanField(default=False)
    annexure = models.BooleanField(default=False)
    tl = models.BooleanField(default=False)
    aro = models.BooleanField(default=False)
    along_with = models.ForeignKey(
        "license.AlongWithModel", on_delete=models.CASCADE, related_name="license_status", null=True, blank=True
    )

    def __str__(self) -> str:
        """
        Human readable trail of an inward/outward record.
        """
        parts = []
        if self.license:
            parts.append(str(self.license))
        if self.copy:
            parts.append("copy")
        if self.amd_sheets_number:
            parts.append(f"amendment sheet: {self.amd_sheets_number}")
        if self.annexure:
            parts.append("& annexure")
        if self.status:
            parts.append(f"has been {self.status.name}")
        if self.office:
            parts.append(f"sent to {self.office.name}")
        if self.description:
            parts.append(f"for {self.description}")
        if self.along_with:
            parts.append(f"along with {self.along_with.name}")
        return " ".join(parts)

    @cached_property
    def ge_file_number(self):
        return self.license.ge_file_number


# -----------------------------
# Signals
# -----------------------------

@receiver(post_save, sender=LicenseImportItemsModel)
def update_balance(sender, instance, **kwargs):
    # async task
    update_balance_values_task(instance.id)

    # Auto-tag blank items using the predefined filter list
    items_and_filters = filter_list()  # e.g. [("Item1", Q(description__icontains="Item1")), ...]
    for item_name, query_filter in items_and_filters:
        try:
            nItem = ItemNameModel.objects.get(name=item_name)
        except ItemNameModel.DoesNotExist:
            continue

        matching_items = (
            LicenseImportItemsModel.objects.filter(license=instance.license)
            .filter(query_filter)
            .annotate(item_count=Count("items"))
            .filter(item_count=0)  # only rows where items is empty
        )
        for import_item in matching_items:
            import_item.items.add(nItem)


# -----------------------------
# Transfers
# -----------------------------

class LicenseTransferModel(models.Model):
    license = models.ForeignKey(LicenseDetailsModel, on_delete=models.CASCADE, related_name="transfers")
    transfer_date = models.DateField(null=True, blank=True)

    from_company = models.ForeignKey(
        "core.CompanyModel", on_delete=models.SET_NULL, null=True, blank=True, related_name="transfers_from"
    )
    to_company = models.ForeignKey(
        "core.CompanyModel", on_delete=models.SET_NULL, null=True, blank=True, related_name="transfers_to"
    )

    transfer_status = models.CharField(max_length=50)
    transfer_initiation_date = models.DateTimeField(null=True, blank=True)
    transfer_acceptance_date = models.DateTimeField(null=True, blank=True)

    cbic_status = models.CharField(max_length=100, null=True, blank=True)
    cbic_response_date = models.DateTimeField(null=True, blank=True)

    user_id_transfer_initiation = models.CharField(max_length=100, null=True, blank=True)
    user_id_acceptance = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self) -> str:
        if self.transfer_date:
            fd = self.transfer_date
        else:
            fd = getattr(self.transfer_initiation_date, "date", lambda: None)()
        fd_str = str(fd) if fd else "N/A"
        return (
            f"{self.transfer_status} from "
            f"{self.from_company.name if self.from_company else 'N/A'} to "
            f"{self.to_company.name if self.to_company else 'N/A'} on {fd_str}"
        )

    def from_company_name(self):
        return self.from_company.name if self.from_company else "-"

    from_company_name.short_description = "From Company"

    def to_company_name(self):
        return self.to_company.name if self.to_company else "-"

    to_company_name.short_description = "To Company"


class LicensePurchase(AuditModel):
    MODE_AMOUNT = "AMOUNT"
    MODE_QTY = "QTY"
    MODE_CHOICES = (
        (MODE_AMOUNT, "Amount-based"),
        (MODE_QTY, "Quantity-based"),
    )

    SRC_FOB_INR = "FOB_INR"
    SRC_CIF_INR = "CIF_INR"
    SRC_CIF_USD = "CIF_USD"
    AMOUNT_SOURCE_CHOICES = (
        (SRC_FOB_INR, "FOB (INR)"),
        (SRC_CIF_INR, "CIF (INR)"),
        (SRC_CIF_USD, "CIF (USD)"),
    )

    # relations
    license = models.ForeignKey("license.LicenseDetailsModel", on_delete=models.CASCADE, related_name="purchases")
    purchasing_entity = models.ForeignKey("core.CompanyModel", null=True, blank=True,
                                          on_delete=models.SET_NULL, related_name="entity_purchases")
    supplier = models.ForeignKey("core.CompanyModel", null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name="supplier_purchases")

    # supplier snapshot
    supplier_pan = models.CharField(max_length=32, null=True, blank=True)
    supplier_gst = models.CharField(max_length=32, null=True, blank=True)

    # invoice
    invoice_number = models.CharField(max_length=128, null=True, blank=True)
    invoice_date = models.DateField(null=True, blank=True)
    invoice_copy = models.FileField(upload_to="license_purchases/invoices/", null=True, blank=True)

    # mode & source
    mode = models.CharField(max_length=10, choices=MODE_CHOICES, default=MODE_AMOUNT)

    # amount-based fields
    amount_source = models.CharField(max_length=10, choices=AMOUNT_SOURCE_CHOICES, default=SRC_FOB_INR)
    fob_inr = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )  # optional
    cif_inr = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )  # optional
    cif_usd = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )  # optional
    exchange_rate = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )  # used with CIF_USD
    markup_pct = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )  # ❌ no discounts, only markup %

    # quantity-based (single product)
    product_name = models.CharField(max_length=255, null=True, blank=True)
    quantity_kg = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    rate_inr = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )

    # result
    amount_inr = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )

    class Meta:
        ordering = ["-created_on"]

    def __str__(self):
        base = f"{self.amount_source}" if self.mode == self.MODE_AMOUNT else f"{self.product_name or 'QTY'}"
        return f"Purchase[{self.id}] L#{self.license_id} {base} ₹{self.amount_inr:.2f}"

    # ---------- helpers ----------
    def _source_amount(self) -> float:
        """
        The selected source amount for bill calculation (no FX on USD).
        - FOB_INR  -> FOB (₹)
        - CIF_INR  -> CIF (₹)
        - CIF_USD  -> CIF ($)  [AS-IS, do NOT multiply by exchange rate]
        """
        try:
            if self.amount_source == self.SRC_FOB_INR:
                return float(self.fob_inr or 0)
            if self.amount_source == self.SRC_CIF_INR:
                return float(self.cif_inr or 0)
            if self.amount_source == self.SRC_CIF_USD:
                return float(self.cif_usd or 0)
        except (TypeError, ValueError):
            return 0.0
        return 0.0

    # Backwards compatibility for any old callers
    def _amount_base_inr(self) -> float:
        """
        DEPRECATED: kept for compatibility. Previously did FX multiply and (1+%) logic.
        Now just returns the same value as _source_amount().
        """
        return self._source_amount()

    # ---------- computations ----------
    def compute_amount_inr(self) -> float:
        """
        Amount mode  : bill = source × (markup_pct / 100)  (no “+1×base”)
        Quantity mode: bill = qty × rate
        Always returns a 2 d.p. rounded number.
        """
        try:
            if self.mode == self.MODE_AMOUNT:
                source = float(self._source_amount() or 0)
                pct = float(self.markup_pct or 0)
                bill = source * (pct / 100.0)
                return round(bill, 2)

            # MODE_QTY
            q = float(self.quantity_kg or 0)
            r = float(self.rate_inr or 0)
            return round(q * r, 2)
        except (TypeError, ValueError):
            return 0.0

    def save(self, *args, **kwargs):
        # Snapshot PAN/GST from supplier if missing
        if self.supplier and not self.supplier_pan:
            try:
                self.supplier_pan = self.supplier.pan or self.supplier_pan
            except Exception:
                pass
        if self.supplier and not self.supplier_gst:
            try:
                self.supplier_gst = getattr(self.supplier, "gst_number", None) or self.supplier_gst
            except Exception:
                pass

        # Auto-calc exchange rate only for convenience (not used in bill math)
        # If absent/zero and both CIF ₹ and CIF $ present -> ER = round(CIF_INR / CIF_USD, 3)
        try:
            er = float(self.exchange_rate or 0)
        except (TypeError, ValueError):
            er = 0.0

        try:
            usd = float(self.cif_usd or 0)
            inr = float(self.cif_inr or 0)
        except (TypeError, ValueError):
            usd = inr = 0.0

        if (er <= 0.0) and (usd > 0.0) and (inr > 0.0):
            self.exchange_rate = round(inr / usd, 3)

        # Clamp markup % to max 3 decimals
        try:
            if self.markup_pct not in (None, ""):
                self.markup_pct = round(float(self.markup_pct), 3)
        except (TypeError, ValueError):
            self.markup_pct = 0.0

        # Final amount (bill) always computed server-side
        self.amount_inr = self.compute_amount_inr()
        super().save(*args, **kwargs)


class Invoice(models.Model):
    bills_of_entry = models.ForeignKey('bill_of_entry.BillOfEntryModel', related_name='invoices', blank=True,
                                       null=True, on_delete=models.CASCADE)
    from_entity = models.ForeignKey(InvoiceEntity, on_delete=models.CASCADE)
    to_company_name = models.CharField(max_length=255)
    to_company_pan = models.CharField(
        max_length=15,
        null=True,
        blank=True,
        validators=[
            RegexValidator(regex=r'^[A-Z]{5}[0-9]{4}[A-Z]$', message="Enter a valid PAN number.")
        ]
    )
    to_company_gst_number = models.CharField(
        max_length=15,
        null=True,
        blank=True,
        validators=[
            RegexValidator(regex=r'^\d{2}[A-Z]{5}\d{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$',
                           message="Enter a valid GST number.")
        ]
    )
    to_company_address_line_1 = models.TextField()
    to_company_address_line_2 = models.TextField(blank=True)
    invoice_number = models.CharField(max_length=50, unique=True)
    invoice_date = models.DateField(default=date.today)
    BILLING_MODE_CHOICES = [
        ('kg', 'KG'),
        ('cif', 'CIF %'),
        ('fob', 'FOB %'),
    ]

    billing_mode = models.CharField(max_length=10, choices=BILLING_MODE_CHOICES)
    total_qty = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    total_cif_fc = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_cif_inr = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_fob_inr = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_amount_in_words = models.TextField(null=True, blank=True)

    sale_type = models.CharField(  # NEW (optional, but matches your UI)
        max_length=10,
        choices=[('item', 'Item'), ('full', 'Full')],
        default='item'
    )


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, related_name='items', on_delete=models.CASCADE)
    sr_number = models.ForeignKey(
        'license.LicenseImportItemsModel',
        on_delete=models.CASCADE,
        related_name='invoice_items'
    )
    license_no = models.CharField(max_length=50)  # for quick display, filled from sr_number.license.license_number
    hsn_code = models.CharField(max_length=10, default='490700')
    qty = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    cif_fc = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    cif_inr = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    fob_inr = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)  # NEW

    rate = models.DecimalField(max_digits=12, decimal_places=2)
    amount = models.DecimalField(max_digits=15, decimal_places=2)

    def save(self, *args, **kwargs):
        # Auto-fill license_no from sr_number on save
        if self.sr_number and not self.license_no:
            self.license_no = self.sr_number.license.license_number
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.license_no} - {self.amount}"
