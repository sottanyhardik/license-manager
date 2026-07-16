# license/models.py  — cleaned, Decimal-safe, imports shared constants from core.constants

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, Optional

from django.conf import settings
from django.core.validators import RegexValidator, MinValueValidator
from django.db import models, transaction
from django.db.models import Count, Sum, DecimalField, Value
from django.db.models.functions import Coalesce
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from django.utils.functional import cached_property

from apps.allotment.models import AllotmentItems
from apps.bill_of_entry.models import RowDetails
# Removed: from bill_of_entry.tasks import update_balance_values_task
# Now using direct synchronous balance updates for better performance
from apps.core.constants import (
    DEC_0,
    DEC_000,
    UNIT_CHOICES,
    CURRENCY_CHOICES,
    SCHEME_CODE_CHOICES,
    NOTIFICATION_NORM_CHOICES,
    LICENCE_PURCHASE_CHOICES,
    GE,
    KG,
    USD,
    ARO,
    DEBIT,
)
# Local imports — keep lightweight at module import time
from apps.core.models import AuditModel, InvoiceEntity, ItemNameModel
from apps.core.models import PurchaseStatus, SchemeCode, NotificationNumber  # kept for compatibility
# -----------------------------
# Import centralized utilities
# -----------------------------
from apps.core.utils.decimal_utils import to_decimal as _to_decimal, round_decimal_down as round_down

_D = Decimal  # shorthand


def license_path(instance, filename):
    """
    Upload path with naming convention:
    - LICENSE COPY -> licenses/<license_number>/<license_number> Copy.ext
    - TRANSFER LETTER -> licenses/<license_number>/<license_number> TL.ext
    - OTHER -> licenses/<license_number>/<license_number> Other.ext
    """
    import os
    import logging
    logger = logging.getLogger(__name__)

    # Safely get license number with fallback
    try:
        if not instance.license:
            logger.error(f"license_path called with instance.license=None, filename={filename}")
            license_number = 'temp'
        else:
            license_number = instance.license.license_number or 'unknown'
    except Exception as e:
        logger.error(f"Error in license_path: {e}, instance={instance}, filename={filename}")
        license_number = 'temp'

    file_ext = os.path.splitext(filename)[1]  # Get original extension

    # Map document type to suffix
    type_suffix_map = {
        'LICENSE COPY': 'Copy',
        'TRANSFER LETTER': 'TL',
        'OTHER': 'Other',
    }

    # Safely get type with fallback
    doc_type = getattr(instance, 'type', 'OTHER')
    suffix = type_suffix_map.get(doc_type, 'Document')

    return f"licenses/{license_number}/{license_number} {suffix}{file_ext}"


# -----------------------------
# License Header
# -----------------------------
class LicenseDetailsModel(AuditModel):
    purchase_status = models.ForeignKey(
        'core.PurchaseStatus',
        on_delete=models.PROTECT,
        related_name='licenses',
        help_text='Purchase status for this license',
        null=True,
        blank=True
    )
    scheme_code = models.ForeignKey(
        "core.SchemeCode",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="licenses",
    )
    notification_number = models.ForeignKey(
        "core.NotificationNumber",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="licenses",
    )

    license_number = models.CharField(max_length=50, unique=True)
    license_date = models.DateField(null=True, blank=True)
    license_expiry_date = models.DateField(null=True, blank=True)
    file_number = models.CharField(max_length=30, null=True, blank=True)

    exporter = models.ForeignKey(
        "core.CompanyModel",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    # Snapshot of the exporter's name at the time it was deleted, so historical
    # licenses still show a meaningful exporter even after the company is gone.
    archived_exporter_name = models.CharField(max_length=255, blank=True, default="")
    port = models.ForeignKey("core.PortModel", on_delete=models.CASCADE, null=True, blank=True)

    registration_number = models.CharField(max_length=10, null=True, blank=True)
    registration_date = models.DateField(null=True, blank=True)

    ge_file_number = models.IntegerField(default=0)

    admin_search_fields = ("license_number",)

    # NOTE: user_comment / condition_sheet / user_restrictions / balance_report_notes
    #       live on LicenseNotes (OneToOne) — see below.
    # NOTE: is_audit / is_mnm / is_not_registered / is_null / is_au / is_active /
    #       is_incomplete / is_expired / is_individual live on LicenseFlags.
    # NOTE: balance_cif / ledger_date live on LicenseBalance.
    # NOTE: current_owner / file_transfer_status / last_ownership_fetch live on LicenseOwnership.
    # Read-only @property accessors below preserve the old `license.<field>` read API.

    class Meta:
        ordering = ("license_expiry_date", "license_date")
        indexes = [
            models.Index(fields=['license_number']),
            models.Index(fields=['file_number']),
            models.Index(fields=['exporter', 'license_date']),
            models.Index(fields=['port', 'license_date']),
            models.Index(fields=['license_date']),
            models.Index(fields=['license_expiry_date']),
            # Indexes for moved fields now live on the child tables.
        ]

    def __str__(self) -> str:
        return self.license_number

    def get_absolute_url(self) -> str:
        return reverse("license:licenses-detail", kwargs={"pk": self.pk})

    # Backward-compat shims for templates that previously used Django's auto-generated
    # `get_<field>_display()` (only present on CharField(choices=...)). After the FK
    # conversion these methods don't exist, so we provide them by hand.
    def get_scheme_code_display(self) -> str:
        return self.scheme_code.label if self.scheme_code_id else ""

    def get_notification_number_display(self) -> str:
        return self.notification_number.label if self.notification_number_id else ""

    # ------------------------------------------------------------------
    # Back-compat read accessors for fields moved to OneToOne sub-tables.
    # See LicenseNotes / LicenseBalance / LicenseFlags / LicenseOwnership.
    # Sub-rows are auto-created via the post_save signal at the bottom of
    # this module, so these accessors normally hit a present row. The
    # try/except defends against partial state right after license create
    # inside a transaction that hasn't committed yet.
    # WRITES must go through the sub-table directly (e.g.
    # `license.flags.is_active = X; license.flags.save()`).
    # ------------------------------------------------------------------
    def _sub(self, related_name, default_field, default_value):
        try:
            return getattr(getattr(self, related_name), default_field)
        except Exception:
            return default_value

    # -- LicenseBalance --
    @property
    def balance_cif(self):
        return self._sub("balance", "balance_cif", DEC_0)

    @property
    def ledger_date(self):
        return self._sub("balance", "ledger_date", None)

    # -- LicenseFlags --
    @property
    def is_active(self):
        return self._sub("flags", "is_active", True)

    @property
    def is_audit(self):
        return self._sub("flags", "is_audit", False)

    @property
    def is_mnm(self):
        return self._sub("flags", "is_mnm", False)

    @property
    def is_not_registered(self):
        return self._sub("flags", "is_not_registered", False)

    @property
    def is_null(self):
        return self._sub("flags", "is_null", False)

    @property
    def is_au(self):
        return self._sub("flags", "is_au", False)

    @property
    def is_incomplete(self):
        return self._sub("flags", "is_incomplete", False)

    @property
    def is_expired(self):
        return self._sub("flags", "is_expired", False)

    @property
    def is_individual(self):
        return self._sub("flags", "is_individual", False)

    # -- LicenseOwnership --
    @property
    def current_owner(self):
        return self._sub("ownership", "current_owner", None)

    @property
    def file_transfer_status(self):
        return self._sub("ownership", "file_transfer_status", None)

    @property
    def last_ownership_fetch(self):
        return self._sub("ownership", "last_ownership_fetch", None)

    # -- LicenseNotes --
    @property
    def user_comment(self):
        return self._sub("notes", "user_comment", None)

    @property
    def condition_sheet(self):
        return self._sub("notes", "condition_sheet", None)

    @property
    def user_restrictions(self):
        return self._sub("notes", "user_restrictions", None)

    @property
    def balance_report_notes(self):
        return self._sub("notes", "balance_report_notes", None)

    # ---------- helpers / balances ----------
    def use_balance_cif(self, amount: Decimal | float | int | str,
                        available_cif: Decimal | float | int | str) -> Decimal:
        """
        Consume `amount` from `available_cif` using Decimal arithmetic.
        Returns remaining available (never negative).
        """
        amt = _to_decimal(amount, DEC_0)
        avail = _to_decimal(available_cif, DEC_0)
        remaining = avail - amt
        return remaining if remaining >= DEC_0 else DEC_0

    @cached_property
    def get_norm_class(self) -> str:
        """CSV of all SION norm codes on export lines."""
        return ",".join([e.norm_class.norm_class for e in self.export_license.all() if e.norm_class])

    @cached_property
    def opening_balance(self) -> Decimal:
        """Total export CIF (credit). Uses centralized service."""
        return self._calculate_license_credit()

    @cached_property
    def opening_fob(self) -> Decimal:
        total = \
            self.export_license.aggregate(total=Coalesce(Sum("fob_inr"), Value(DEC_0), output_field=DecimalField()))[
                "total"]
        return _to_decimal(total, DEC_0)

    @property
    def get_total_debit(self) -> Decimal:
        """Total BOE debit. Uses centralized service."""
        return self._calculate_license_debit()

    @property
    def get_total_allotment(self) -> Decimal:
        """Total allotment (no BOE). Uses centralized service."""
        return self._calculate_license_allotment()

    def _calculate_license_credit(self) -> Decimal:
        """Calculate total credit using centralized service"""
        from apps.license.services.balance_calculator import LicenseBalanceCalculator
        return LicenseBalanceCalculator.calculate_credit(self)

    def _calculate_license_debit(self) -> Decimal:
        """Calculate total debit using centralized service"""
        from apps.license.services.balance_calculator import LicenseBalanceCalculator
        return LicenseBalanceCalculator.calculate_debit(self)

    def _calculate_license_allotment(self) -> Decimal:
        """Calculate total allotment using centralized service"""
        from apps.license.services.balance_calculator import LicenseBalanceCalculator
        return LicenseBalanceCalculator.calculate_allotment(self)

    @property
    def get_balance_cif(self) -> Decimal:
        """
        Authoritative live balance at license level using centralized service.
        SUM(Export.cif_fc) - (SUM(BOE debit cif_fc for license) + SUM(allotments cif_fc (unattached BOE))).
        All sums returned as Decimal.
        """
        from apps.license.services.balance_calculator import LicenseBalanceCalculator
        return LicenseBalanceCalculator.calculate_balance(self)

    def get_restriction_balances(self) -> Dict[str, Decimal]:
        """
        Per-condition_type remaining pool balances for this licence.

        Returns: {condition_type ("2%" / "3%" / "5%" / "10%"): remaining_balance}
        Delegates to the new `condition_pool.compute_condition_pools` helper.
        """
        from apps.license.services.condition_pool import compute_condition_pools
        return compute_condition_pools(self)

    # ---------- grouped import summaries ----------
    @cached_property
    def import_license_grouped(self):
        """
        Group import rows to consolidate quantities by item name/HSN.
        Keeps compatibility keys used elsewhere.
        """
        return (
            self.import_license.select_related("hs_code")
            .values("hs_code__hs_code", "items__name", "description", "items__unit_price")
            .annotate(
                available_quantity_sum=Coalesce(Sum("available_quantity"), Value(DEC_000), output_field=DecimalField()),
                quantity_sum=Coalesce(Sum("quantity"), Value(DEC_000), output_field=DecimalField()),
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
                    "items__unit_price": _to_decimal(row.get("items__unit_price") or DEC_0),
                    "available_quantity_sum": _to_decimal(row.get("available_quantity_sum") or DEC_000, DEC_000),
                    "quantity_sum": _to_decimal(row.get("quantity_sum") or DEC_000, DEC_000),
                }
            else:
                m[key]["available_quantity_sum"] += _to_decimal(row.get("available_quantity_sum") or DEC_000, DEC_000)
                m[key]["quantity_sum"] += _to_decimal(row.get("quantity_sum") or DEC_000, DEC_000)
        return m

    def get_item_data(self, item_name: str) -> Dict[str, Any]:
        """
        Consolidated data for a specific item by name (case-insensitive).
        Returns Decimal totals where applicable.
        """
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
                return {"available_quantity_sum": DEC_000, "quantity_sum": DEC_000}

        key = normalized.lower()
        hit = self._import_group_by_name_map.get(key)
        if hit:
            return hit
        return {"available_quantity_sum": DEC_000, "quantity_sum": DEC_000}

    @cached_property
    def import_license_group_grouped(self):
        return (
            self.import_license.select_related("hs_code")
            .values("items__group__name", "description", "hs_code__hs_code", "items__name")
            .annotate(
                available_quantity_sum=Coalesce(Sum("available_quantity"), Value(DEC_000), output_field=DecimalField()),
                quantity_sum=Coalesce(Sum("quantity"), Value(DEC_000), output_field=DecimalField()),
            )
            .order_by("items__name")
        )

    # Deprecated: Use import_license_group_grouped instead
    @property
    def import_license_head_grouped(self):
        return self.import_license_group_grouped

    def get_item_group_data(self, item_name: str) -> Dict[str, Any]:
        matching_rows = [
            row
            for row in self.import_license_group_grouped
            if row.get("items__group__name") == item_name
        ]
        if not matching_rows:
            return {"available_quantity_sum": DEC_000, "quantity_sum": DEC_000}

        total_available = sum(
            _to_decimal(row.get("available_quantity_sum") or DEC_000, DEC_000)
            for row in matching_rows
        )
        total_quantity = sum(
            _to_decimal(row.get("quantity_sum") or DEC_000, DEC_000)
            for row in matching_rows
        )

        return {
            "available_quantity_sum": total_available,
            "quantity_sum": total_quantity,
        }

    # Deprecated: Use get_item_group_data instead
    def get_item_head_data(self, item_name: str) -> Dict[str, Any]:
        return self.get_item_group_data(item_name)

    # ---------- domain convenience lookups ----------
    @cached_property
    def get_glass_formers(self) -> Dict[str, Any]:
        total_quantity = _to_decimal(self.get_item_data("RUTILE").get("quantity_sum") or DEC_000, DEC_000)
        available_quantity = _to_decimal(self.get_item_data("RUTILE").get("available_quantity_sum") or DEC_000, DEC_000)
        opening_balance = _to_decimal(self.opening_balance or DEC_0, DEC_0)

        if total_quantity == DEC_000:
            return {"borax": DEC_000, "rutile": DEC_000, "total": DEC_000,
                    "description": self.get_item_data("RUTILE").get("description")}

        avg = (opening_balance / total_quantity) if total_quantity and total_quantity != DEC_000 else DEC_0
        borax = DEC_000
        if avg <= _to_decimal("3"):
            from django.conf import settings
            biscuit_company_id = settings.BISCUIT_COMPANY_ID
            borax_quantity = (total_quantity / _to_decimal("0.62")) * _to_decimal("0.1")
            debit = _to_decimal(
                RowDetails.objects.filter(sr_number__license=self, bill_of_entry__company=biscuit_company_id, transaction_type=DEBIT)
                .aggregate(total=Coalesce(Sum("qty"), Value(DEC_000), output_field=DecimalField()))["total"],
                DEC_000,
            )
            allotment = _to_decimal(
                AllotmentItems.objects.filter(
                    item__license=self,
                    allotment__company=biscuit_company_id,
                    allotment__bill_of_entry__isnull=True,
                ).aggregate(total=Coalesce(Sum("qty"), Value(DEC_000), output_field=DecimalField()))["total"],
                DEC_000,
            )
            borax = min(borax_quantity - (debit + allotment), available_quantity)
            if borax < DEC_000:
                borax = DEC_000
        rutile = min(max(available_quantity - borax, DEC_000), available_quantity)
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
        rutile_qty = _to_decimal(self.get_glass_formers.get("rutile") or DEC_000, DEC_000)
        if rutile_qty == DEC_000:
            return DEC_0
        cif_rutile = _to_decimal(self.cif_value_balance_glass.get("rutile") or DEC_0, DEC_0)
        return (cif_rutile / rutile_qty).quantize(DEC_0, rounding=ROUND_HALF_UP)

    # ---- wrappers for item getters ----
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
        soda_ash_qty = _to_decimal(self.get_modifiers_namely.get("available_quantity_sum") or DEC_000, DEC_000)
        titanium_qty = _to_decimal(self.get_other_special_additives.get("available_quantity_sum") or DEC_000, DEC_000)
        borax_qty = _to_decimal(self.get_glass_formers.get("borax") or DEC_000, DEC_000)
        rutile_qty = _to_decimal(self.get_glass_formers.get("rutile") or DEC_000, DEC_000)

        borax_cif = soda_ash_cif = rutile_cif = titanium_cif = DEC_0
        if borax_qty > _to_decimal("100"):
            borax_cif = min(borax_qty * _to_decimal("0.7"), available_value)
            available_value = self.use_balance_cif(borax_cif, available_value)
        if soda_ash_qty > _to_decimal("100"):
            soda_ash_cif = min(soda_ash_qty * _to_decimal("0.3"), available_value)
            available_value = self.use_balance_cif(soda_ash_cif, available_value)
        if rutile_qty > _to_decimal("100"):
            rutile_cif = min(rutile_qty * _to_decimal("3.5"), available_value)
            available_value = self.use_balance_cif(rutile_cif, available_value)
        if titanium_qty > _to_decimal("100"):
            titanium_cif = min(titanium_qty * _to_decimal("1.8"), available_value)
            available_value = self.use_balance_cif(titanium_cif, available_value)

        return {
            "borax": borax_cif,
            "rutile": rutile_cif,
            "soda_ash": soda_ash_cif,
            "titanium": titanium_cif,
            "balance_cif": available_value,
        }

    # ---- Biscuits domain block ----
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
        Allocation engine using Decimal arithmetic.
        """
        available_value = self.get_balance_cif
        if available_value <= _to_decimal("100"):
            return {
                "cif_juice": DEC_0,
                "restricted_value": DEC_0,
                "qty_swp": DEC_0,
                "cif_swp": DEC_0,
                "qty_cheese": DEC_0,
                "cif_cheese": DEC_0,
                "qty_wpc": DEC_0,
                "cif_wpc": DEC_0,
                "veg_oil": {"rbd_oil": DEC_0, "cif_rbd_oil": DEC_0, "pko_oil": DEC_0, "cif_pko_oil": DEC_0,
                            "olive_oil": DEC_0, "cif_olive_oil": DEC_0, "pomace_oil": DEC_0, "cif_pomace_oil": DEC_0},
                "available_value": DEC_0,
            }

        restricted_value = _to_decimal((self.get_per_cif or {}).get("tenRestriction", DEC_0), DEC_0)

        # Juice
        biscuit_juice = self.get_biscuit_juice
        juice_quantity = _to_decimal(biscuit_juice.get("available_quantity_sum") or DEC_000, DEC_000)
        juice_unit_price = _to_decimal(biscuit_juice.get("items__unit_price") or DEC_0, DEC_0)
        cif_juice = DEC_0
        if juice_quantity > _to_decimal("50") and restricted_value > _to_decimal("200"):
            cif_juice = min(juice_quantity * juice_unit_price, restricted_value, available_value)
            restricted_value = self.use_balance_cif(cif_juice, restricted_value)
            available_value = self.use_balance_cif(cif_juice, available_value)

        cif_swp = cif_cheese = wpc_cif = DEC_0

        # heuristics omitted for brevity; preserve Decimal conversions as before
        oil_data = {"Total_CIF": DEC_0, "rbd_oil": DEC_000, "cif_rbd_oil": DEC_0, "pko_oil": DEC_000,
                    "cif_pko_oil": DEC_0, "olive_oil": DEC_000, "cif_olive_oil": DEC_0, "pomace_oil": DEC_000,
                    "cif_pomace_oil": DEC_0}

        try:
            from apps.core.scripts.calculation import optimize_milk_distribution
        except Exception:
            optimize_milk_distribution = None

        total_milk = _to_decimal(self.get_mnm_pd.get("available_quantity_sum") or DEC_000, DEC_000)
        total_milk_cif = available_value + cif_swp + cif_cheese

        if optimize_milk_distribution and total_milk_cif >= _to_decimal("200") and total_milk >= _to_decimal("100"):
            unit_prices = {
                "swp": float(_to_decimal(self.get_swp.get("items__unit_price") or DEC_0)),
                "cheese": float(_to_decimal(self.get_cheese.get("items__unit_price") or DEC_0)),
                "wpc": float(_to_decimal(self.get_wpc.get("items__unit_price") or DEC_0)),
            }
            use_swp = (_to_decimal(self.get_swp.get("quantity_sum") or DEC_000) > DEC_000)
            use_cheese = (_to_decimal(self.get_cheese.get("quantity_sum") or DEC_000) > DEC_000)
            use_wpc = (_to_decimal(self.get_wpc.get("quantity_sum") or DEC_000) > DEC_000)

            milk_data = optimize_milk_distribution(
                unit_prices["swp"],
                unit_prices["cheese"],
                unit_prices["wpc"],
                float(total_milk_cif),
                float(total_milk),
                use_swp,
                use_cheese,
                use_wpc,
            )
            cif_swp = min(_to_decimal(milk_data.get("SWP") or DEC_000) * _to_decimal(unit_prices["swp"]),
                          total_milk_cif)
            total_milk_cif = self.use_balance_cif(cif_swp, total_milk_cif)
            cif_cheese = min(_to_decimal(milk_data.get("CHEESE") or DEC_000) * _to_decimal(unit_prices["cheese"]),
                             total_milk_cif)
            total_milk_cif = self.use_balance_cif(cif_cheese, total_milk_cif)
            wpc_cif = min(_to_decimal(milk_data.get("WPC") or DEC_000) * _to_decimal(unit_prices["wpc"]),
                          total_milk_cif)
            total_milk_cif = self.use_balance_cif(wpc_cif, total_milk_cif)
            available_value = total_milk_cif
        else:
            milk_data = {"SWP": 0, "CHEESE": 0, "WPC": 0, "total_value_used": 0}

        return {
            "cif_juice": cif_juice,
            "restricted_value": restricted_value,
            "qty_swp": _to_decimal(milk_data.get("SWP") or DEC_000, DEC_000),
            "cif_swp": cif_swp,
            "qty_cheese": _to_decimal(milk_data.get("CHEESE") or DEC_000, DEC_000),
            "cif_cheese": cif_cheese,
            "qty_wpc": _to_decimal(milk_data.get("WPC") or DEC_000, DEC_000),
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

    def get_per_cif(self) -> Optional[Dict[str, Decimal]]:
        """
        Compute restriction budgets based on export norm class.
        Returns decimals in the dict values.
        NOTE: Removed @cached_property to ensure fresh calculation after updates.
        """
        available_value = self.get_balance_cif
        # Use total export CIF as credit for restriction calculations
        credit = _to_decimal(self._calculate_license_credit() or DEC_0, DEC_0)

        first_norm = self.export_license.all().values_list("norm_class__norm_class", flat=True).first()
        if not first_norm:
            return None

        def _sum_for_group(name: str) -> Decimal:
            vals = self.import_license.filter(items__group__name=name).aggregate(
                dv=Coalesce(Sum("debited_value"), Value(DEC_0), output_field=DecimalField()),
                av=Coalesce(Sum("allotted_value"), Value(DEC_0), output_field=DecimalField()),
            )
            return _to_decimal(vals["dv"] or DEC_0, DEC_0) + _to_decimal(vals["av"] or DEC_0, DEC_0)

        # Deprecated alias
        def _sum_for_head(name: str) -> Decimal:
            return _sum_for_group(name)

        if "E132" in str(first_norm):
            credit_3 = credit * _to_decimal("0.03")
            conf_3 = _sum_for_head("NAMKEEN 3% Restriction")
            credit_5 = credit * _to_decimal("0.05")
            conf_5 = _sum_for_head("NAMKEEN 5% Restriction")
            return {
                "threeRestriction": min(available_value, max(round_down(credit_3 - conf_3), DEC_0)),
                "fiveRestriction": min(available_value, max(round_down(credit_5 - conf_5), DEC_0)),
            }

        if "E126" in str(first_norm):
            credit_3 = credit * _to_decimal("0.03")
            conf_3 = _sum_for_head("PICKLE 3% Restriction")
            return {"threeRestriction": min(available_value, max(round_down(credit_3 - conf_3), DEC_0))}

        if "E1" in str(first_norm):
            credit_2 = credit * _to_decimal("0.02")
            conf_2 = _sum_for_head("CONFECTIONERY 2% Restriction")
            credit_3 = credit * _to_decimal("0.03")
            conf_3 = _sum_for_head("CONFECTIONERY 3% Restriction")
            credit_5 = credit * _to_decimal("0.05")
            conf_5 = _sum_for_head("CONFECTIONERY 5% Restriction")
            return {
                "twoRestriction": min(available_value, max(round_down(credit_2 - conf_2), DEC_0)),
                "threeRestriction": min(available_value, max(round_down(credit_3 - conf_3), DEC_0)),
                "fiveRestriction": min(available_value, max(round_down(credit_5 - conf_5), DEC_0)),
            }

        if "E5" in str(first_norm):
            credit_10 = credit * _to_decimal("0.10")
            total_value = _sum_for_head("BISCUIT 10% Restriction")
            return {"tenRestriction": min(max(round_down(credit_10 - total_value), DEC_0), available_value)}

        return None

    @cached_property
    def latest_transfer(self):
        qs = self.transfers.order_by("-transfer_date", "-id")
        if qs.exists():
            return qs.first()
        if self.current_owner:
            return f"Current Owner is {self.current_owner.name}"
        return "Data Not Found"

    @property
    def purchase_status_label(self):
        return self.purchase_status.label if self.purchase_status else None


# -----------------------------
# Export Items
# -----------------------------
class LicenseExportItemModel(models.Model):
    license = models.ForeignKey("license.LicenseDetailsModel", on_delete=models.CASCADE,
                                related_name="export_license")
    description = models.CharField(max_length=2000, blank=True, db_index=True, null=True)
    item = models.ForeignKey("core.ItemNameModel", related_name="export_licenses", on_delete=models.CASCADE, null=True,
                             blank=True)
    norm_class = models.ForeignKey("core.SionNormClassModel", null=True, blank=True, on_delete=models.CASCADE,
                                   related_name="export_item")

    duty_type = models.CharField(max_length=255, default="Basic")
    net_quantity = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0,
                                       validators=[MinValueValidator(DEC_0)])
    old_quantity = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0,
                                       validators=[MinValueValidator(DEC_0)])
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default=KG)

    fob_fc = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0, validators=[MinValueValidator(DEC_0)])
    fob_inr = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0, validators=[MinValueValidator(DEC_0)])
    fob_exchange_rate = models.DecimalField(max_digits=15, decimal_places=6, default=DEC_0,
                                            validators=[MinValueValidator(DEC_0)])
    currency = models.CharField(choices=CURRENCY_CHOICES, default=USD, max_length=5)
    value_addition = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0,
                                         validators=[MinValueValidator(DEC_0)])
    cif_fc = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0, validators=[MinValueValidator(DEC_0)])
    cif_inr = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0, validators=[MinValueValidator(DEC_0)])

    def __str__(self) -> str:
        return getattr(self.item, "name", "") or f"ExportItem#{self.pk}"

    def balance_cif_fc(self) -> Decimal:
        """
        Export item balance - delegates to license's centralized calculation.
        Returns the same as license.get_balance_cif for consistency.
        """
        if self.license:
            return self.license.get_balance_cif
        return DEC_0


# -----------------------------
# Import Items
# -----------------------------
class LicenseImportItemsModel(models.Model):
    serial_number = models.IntegerField(default=0)
    license = models.ForeignKey("license.LicenseDetailsModel", on_delete=models.CASCADE,
                                related_name="import_license",
                                db_index=True)
    hs_code = models.ForeignKey("core.HSCodeModel", on_delete=models.CASCADE, blank=True, related_name="import_item",
                                null=True, db_index=True)
    items = models.ManyToManyField(ItemNameModel, blank=True, related_name="license_import_item")

    description = models.CharField(max_length=2000, blank=True, db_index=True, null=True)
    quantity = models.DecimalField(max_digits=15, decimal_places=3, default=DEC_000)
    old_quantity = models.DecimalField(max_digits=15, decimal_places=3, default=DEC_000)
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default=KG)

    cif_fc = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0)
    cif_inr = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0)

    available_quantity = models.DecimalField(max_digits=15, decimal_places=3, default=DEC_000)
    available_value = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0)

    debited_quantity = models.DecimalField(max_digits=15, decimal_places=3, default=DEC_000)
    debited_value = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0)

    allotted_quantity = models.DecimalField(max_digits=15, decimal_places=3, default=DEC_000)
    allotted_value = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0)

    is_restricted = models.BooleanField(default=False,
                                        help_text="If True, uses restriction-based calculation (2%, 3%, 5%, 10% etc.). If False, uses license balance.")
    condition_type = models.CharField(
        max_length=8,
        blank=True,
        default="",
        help_text="Per-item licence condition extracted from the condition sheet: 'AU', '2%', '3%', '5%', '10%' etc. Drives the colour badge in the UI. Empty means no special condition.",
    )
    comment = models.TextField(blank=True, null=True)

    admin_search_fields = ("license__license_number",)

    class Meta:
        ordering = ["license__license_expiry_date", "serial_number"]
        unique_together = (("license", "serial_number"),)
        indexes = [
            models.Index(fields=["license"]),
            models.Index(fields=["hs_code"]),
            models.Index(fields=["available_quantity"]),  # Optimize queries filtering by available_quantity > 0
            models.Index(fields=["available_value"]),  # Optimize queries filtering by available_value
        ]

    def __str__(self) -> str:
        return f"{self.license}-{self.serial_number}"

    def save(self, *args, **kwargs):
        # `is_restricted` is now a DERIVED flag — true iff a licence condition
        # (AU / N%) applies to this item. The new restriction model lives in
        # `condition_type` + `license.services.condition_pool`; the boolean is
        # kept purely as a fast filter/index for existing queries.
        self.is_restricted = bool((self.condition_type or "").strip())
        super().save(*args, **kwargs)

    @cached_property
    def required_cif(self) -> Decimal:
        """
        If available quantity > 100, use first linked item's head.unit_rate as multiplier.
        """
        if self.available_quantity and self.available_quantity > _to_decimal("100"):
            first_item = self.items.first()
            unit_rate = _to_decimal(getattr(getattr(first_item, "head", None), "unit_rate", DEC_0), DEC_0)
            if unit_rate and unit_rate > DEC_0:
                return self.available_quantity * unit_rate
        return DEC_0

    @cached_property
    def balance_quantity(self) -> Decimal:
        """
        Delegates to core script calculate_balance if present; otherwise compute here.
        """
        try:
            from apps.core.scripts.calculate_balance import calculate_available_quantity as calc  # lazy import
            return _to_decimal(calc(self), DEC_000)
        except Exception:
            # Fallback: quantity - debited - allotted (un-BOE)
            total = _to_decimal(self.quantity or DEC_000, DEC_000)
            debited = _to_decimal(self.item_details.filter(transaction_type=DEBIT).aggregate(
                total=Coalesce(Sum("qty"), Value(DEC_000), output_field=DecimalField()))["total"], DEC_000)
            allotted = _to_decimal(
                self.allotment_details.filter(allotment__bill_of_entry__isnull=True).aggregate(
                    total=Coalesce(Sum("qty"), Value(DEC_000), output_field=DecimalField()))["total"], DEC_000)
            avail = total - (debited + allotted)
            return avail if avail >= DEC_000 else DEC_000

    def _calculate_item_debit(self) -> Decimal:
        """Calculate total debit for this specific import item"""
        return _to_decimal(
            RowDetails.objects.filter(sr_number=self, transaction_type=DEBIT).aggregate(
                total=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=DecimalField()))["total"],
            DEC_0,
        )

    def _calculate_item_allotment(self) -> Decimal:
        """Calculate total allotment for this specific import item"""
        return _to_decimal(
            AllotmentItems.objects.filter(
                item=self,
                allotment__bill_of_entry__isnull=True
            ).aggregate(total=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=DecimalField()))["total"],
            DEC_0,
        )

    @property
    def balance_cif_fc(self) -> Decimal:
        """
        Row-level balance under the new condition_type model.

        - condition_type ending in "%": pool-based shared limit (delegated to
          `condition_pool.remaining_for_condition`), capped at the licence
          balance.
        - condition_type "AU" or empty: tracks the licence balance.

        Always calculated fresh from database (no caching) — see
        `available_value_calculated` for the same logic used by the cached
        `available_value` field. Prefer the stored field when reading in bulk.
        """
        if not self.license:
            return DEC_0
        license_balance = self.license.balance_cif or DEC_0
        cond = (self.condition_type or "").strip()
        if cond.endswith("%"):
            from apps.license.services.condition_pool import remaining_for_condition
            remaining = remaining_for_condition(self.license, cond)
            if remaining is None:
                return license_balance
            return min(remaining, license_balance)
        return license_balance

    @property
    def available_value_calculated(self) -> Decimal:
        """
        CENTRALIZED available_value calculation — SINGLE SOURCE OF TRUTH.

        NEW model (driven by `condition_type` on the import item):

        1. If cif_inr / cif_fc == 0.01: return 0.01 (special marker value).
        2. If condition_type ends with "%" (e.g. "10%"):
              Collective pool = N% × license total CIF.
              All items on this licence sharing the same condition_type share
              that pool. available_value = min(pool_remaining, license_balance).
              (Computed via `license.services.condition_pool`.)
        3. If condition_type == "AU": item is non-transferable; available_value
              still tracks license_balance (the restriction is on transfer of
              the licence, not on use of the item).
        4. Otherwise (empty condition_type / "open"): available_value = license_balance.

        For BULK contexts (many items on the same licence) prefer
        `condition_pool.compute_condition_pools(license)` once and reuse the
        returned dict, rather than calling this property per-item — see
        `_update_all_import_items_available_value` in license.signals.
        """
        if not self.license:
            return DEC_0

        # Special marker value
        if self.cif_inr == Decimal("0.01") or self.cif_fc == Decimal("0.01"):
            return Decimal("0.01")

        license_balance = self.license.balance_cif or DEC_0
        cond = (self.condition_type or "").strip()

        # Percentage condition — pool-based shared limit.
        if cond.endswith("%"):
            from apps.license.services.condition_pool import remaining_for_condition
            remaining = remaining_for_condition(self.license, cond)
            if remaining is None:
                return license_balance
            return min(remaining, license_balance)

        # "AU" or open: track licence balance directly.
        return license_balance

    @cached_property
    def license_expiry(self) -> Optional[date]:
        return self.license.license_expiry_date

    @cached_property
    def license_date(self) -> Optional[date]:
        return self.license.license_date

    @cached_property
    def sorted_item_list(self) -> Dict[str, Any]:
        """
        Company-grouped BOE details with sums.
        """
        dict_list = []
        data = self.item_details.order_by("transaction_type", "bill_of_entry__company",
                                          "bill_of_entry__bill_of_entry_date")
        company_names = data.values_list("bill_of_entry__company__name", flat=True).distinct()
        for company in company_names:
            if not company:
                continue
            company_data = data.filter(bill_of_entry__company__name=company)
            dict_list.append({
                "company": company,
                "data_list": company_data,
                "sum_total_qty": _to_decimal(
                    company_data.aggregate(total=Coalesce(Sum("qty"), Value(DEC_000), output_field=DecimalField()))[
                        "total"], DEC_000),
                "sum_total_cif_fc": _to_decimal(
                    company_data.aggregate(total=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=DecimalField()))[
                        "total"], DEC_0),
                "sum_total_cif_inr": _to_decimal(
                    company_data.aggregate(total=Coalesce(Sum("cif_inr"), Value(DEC_0), output_field=DecimalField()))[
                        "total"], DEC_0),
            })
        return {"item_details": dict_list}

    @cached_property
    def sorted_allotment_list(self) -> Dict[str, Any]:
        dict_list = []
        data = self.allotment_details.filter(allotment__bill_of_entry__isnull=True).order_by("allotment__company", "allotment__modified_on")
        company_names = data.order_by("allotment__company", "allotment__modified_on",
                                      "allotment__unit_value_per_unit").values_list("allotment__company__name",
                                                                                    flat=True).distinct()
        for company in company_names:
            if not company:
                continue
            company_data = data.filter(allotment__company__name=company)
            dict_list.append({
                "company": company,
                "data_list": company_data,
                "sum_total_qty": _to_decimal(
                    company_data.aggregate(total=Coalesce(Sum("qty"), Value(DEC_000), output_field=DecimalField()))[
                        "total"], DEC_000),
                "sum_total_cif_fc": _to_decimal(
                    company_data.aggregate(total=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=DecimalField()))[
                        "total"], DEC_0),
            })
        return {"item_details": dict_list}

    @cached_property
    def total_debited_qty(self) -> Decimal:
        return _to_decimal(self.item_details.filter(transaction_type=DEBIT).aggregate(
            total=Coalesce(Sum("qty"), Value(DEC_000), output_field=DecimalField()))["total"], DEC_000)

    @cached_property
    def total_debited_cif_fc(self) -> Decimal:
        debited = _to_decimal(self.item_details.filter(transaction_type=DEBIT).aggregate(
            total=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=DecimalField()))["total"], DEC_0)
        alloted = _to_decimal(self.allotment_details.filter(allotment__bill_of_entry__isnull=True,
                                                            allotment__type=ARO).aggregate(
            total=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=DecimalField()))["total"], DEC_0)
        total = debited + alloted
        return total.quantize(Decimal("1"), rounding=ROUND_HALF_UP)

    @cached_property
    def total_debited_cif_inr(self) -> Decimal:
        return _to_decimal(self.item_details.filter(transaction_type=DEBIT).aggregate(
            total=Coalesce(Sum("cif_inr"), Value(DEC_0), output_field=DecimalField()))["total"], DEC_0)

    @cached_property
    def opening_balance(self) -> Decimal:
        return _to_decimal(self.item_details.filter(transaction_type="C").aggregate(
            total=Coalesce(Sum("qty"), Value(DEC_000), output_field=DecimalField()))["total"], DEC_000)

    @cached_property
    def usable(self) -> Decimal:
        try:
            if hasattr(self, "item") and getattr(self, "item", None) and getattr(self.item, "head", None):
                first_item = self.items.first()
                notif_code = self.license.notification_number.code if self.license.notification_number_id else None
                if (notif_code == NOTIFICATION_NORM_CHOICES[1][0] and
                        first_item and first_item.sion_norm_class and first_item.restriction_percentage > 0):
                    return _to_decimal(self.old_quantity or DEC_000, DEC_000)
        except Exception:
            pass
        value = _to_decimal(self.item_details.filter(transaction_type="C").aggregate(
            total=Coalesce(Sum("qty"), Value(DEC_000), output_field=DecimalField()))["total"], DEC_000)
        return round_down(value or DEC_000)


# -----------------------------
# Utilization Planning
# -----------------------------
class LicenseItemPlan(AuditModel):
    """
    User-authored utilization plan line for an import item.

    An import item's total quantity can be SPLIT into several plan lines, each
    optionally tagged with an item name (e.g. milk → WPC / SWP / DWP) and priced
    with a unit price. Each line records planned quantity, unit price and CIF-FC.

    At allotment time (`allocate_items`) the SUM of an item's plan lines acts as
    a CAP: cumulative allotment for the item may not exceed the total planned
    quantity / CIF-FC. Items without any plan line keep the default
    availability-based behavior.

    This is distinct from the norm-derived "planned CIF" produced by the
    E1/E5 waterfall (`services/e1_plan.py` / `e5_plan.py`), which is read-only.
    """
    import_item = models.ForeignKey(
        "license.LicenseImportItemsModel",
        on_delete=models.CASCADE,
        related_name="utilization_plans",
        db_index=True,
    )
    # Optional split label — one of the item's attached item names.
    item_name = models.ForeignKey(
        "core.ItemNameModel",
        on_delete=models.SET_NULL,
        related_name="plan_lines",
        null=True,
        blank=True,
    )
    # Denormalized for fast per-license querying and shared-pool validation.
    license = models.ForeignKey(
        "license.LicenseDetailsModel",
        on_delete=models.CASCADE,
        related_name="item_plans",
        null=True,
        blank=True,
        db_index=True,
    )
    planned_quantity = models.DecimalField(
        max_digits=15, decimal_places=3, default=DEC_000,
        validators=[MinValueValidator(DEC_000)],
    )
    unit_price = models.DecimalField(
        max_digits=15, decimal_places=2, default=DEC_0,
        validators=[MinValueValidator(DEC_0)],
    )
    planned_cif_fc = models.DecimalField(
        max_digits=15, decimal_places=2, default=DEC_0,
        validators=[MinValueValidator(DEC_0)],
    )
    planned_cif_inr = models.DecimalField(
        max_digits=15, decimal_places=2, default=DEC_0, null=True, blank=True,
    )
    note = models.CharField(max_length=500, blank=True, null=True)

    class Meta:
        indexes = [models.Index(fields=["license"]), models.Index(fields=["import_item"])]

    def save(self, *args, **kwargs):
        # Keep the denormalized license in sync with the item's license.
        if self.import_item_id and not self.license_id:
            self.license_id = self.import_item.license_id
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"Plan item={self.import_item_id}: qty={self.planned_quantity} cif_fc={self.planned_cif_fc}"


# -----------------------------
# Documents
# -----------------------------
class LicenseDocumentModel(models.Model):
    DOCUMENT_TYPE_CHOICES = [
        ('LICENSE COPY', 'LICENSE COPY'),
        ('TRANSFER LETTER', 'TRANSFER LETTER'),
        ('OTHER', 'OTHER'),
    ]

    license = models.ForeignKey("license.LicenseDetailsModel", on_delete=models.CASCADE,
                                related_name="license_documents")
    type = models.CharField(max_length=255, choices=DOCUMENT_TYPE_CHOICES)
    file = models.FileField(upload_to=license_path)

    def __str__(self) -> str:
        return f"{self.type} - {getattr(self.license, 'license_number', 'N/A')}"


# -----------------------------
# Status / Workflow Models
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
    license = models.ForeignKey("license.LicenseDetailsModel", on_delete=models.CASCADE,
                                related_name="license_status",
                                null=True, blank=True)
    status = models.ForeignKey("license.StatusModel", on_delete=models.CASCADE, related_name="license_status")
    office = models.ForeignKey("license.OfficeModel", on_delete=models.CASCADE, related_name="license_status")

    description = models.TextField(null=True, blank=True)
    amd_sheets_number = models.CharField(max_length=100, null=True, blank=True)
    copy = models.BooleanField(default=False)
    annexure = models.BooleanField(default=False)
    tl = models.BooleanField(default=False)
    aro = models.BooleanField(default=False)
    along_with = models.ForeignKey("license.AlongWithModel", on_delete=models.CASCADE,
                                   related_name="license_status",
                                   null=True, blank=True)

    def __str__(self) -> str:
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
        return self.license.ge_file_number if self.license else 0


# -----------------------------
# Signals
# -----------------------------
@receiver(post_save, sender=LicenseImportItemsModel)
def update_balance(sender, instance, **kwargs):
    """
    After an import item is saved, update derived balances synchronously.
    Use transaction.on_commit so the update sees committed DB state.

    Guards against infinite recursion by checking if balance fields changed.
    Also honours the per-thread suspend flag used by bulk serializer save
    operations — `_update_all_import_items_available_value` will run once at
    the end of the bulk save instead of 38 times per item via this on_commit.
    """
    from apps.core.scripts.calculate_balance import update_balance_values
    from apps.license.signals import _flags_suspended

    # Bulk serializer operation in progress — skip the per-item on_commit
    # rebalance, the serializer's final flush handles it once.
    if _flags_suspended():
        return

    # Prevent infinite recursion: only update if non-balance fields changed
    update_fields = kwargs.get('update_fields')
    if update_fields is not None:
        balance_fields = {
            'available_quantity', 'debited_quantity', 'allotted_quantity',
            'allotted_value', 'debited_value', 'available_value'
        }
        # If ONLY balance fields were updated, skip to prevent recursion
        if set(update_fields).issubset(balance_fields):
            return

    def _job():
        try:
            update_balance_values(instance)
        except Exception:
            pass

    try:
        transaction.on_commit(_job)
    except Exception:
        _job()

    # Auto-tag blank items using a predefined filter list (lazy import)
    try:
        from backend.setup.migrations_script import filter_list
    except Exception:
        filter_list = lambda: []

    items_and_filters = filter_list()
    for item_name, query_filter in items_and_filters:
        try:
            nItem = ItemNameModel.objects.get(name=item_name)
        except ItemNameModel.DoesNotExist:
            continue

        matching_items = (
            LicenseImportItemsModel.objects.filter(license=instance.license)
            .filter(query_filter)
            .annotate(item_count=Count("items"))
            .filter(item_count=0)
        )
        for import_item in matching_items:
            import_item.items.add(nItem)


# -----------------------------
# Transfers
# -----------------------------
class LicenseTransferModel(models.Model):
    license = models.ForeignKey("license.LicenseDetailsModel", on_delete=models.CASCADE,
                                related_name="transfers")
    transfer_date = models.DateField(null=True, blank=True)

    from_company = models.ForeignKey("core.CompanyModel", on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name="transfers_from")
    to_company = models.ForeignKey("core.CompanyModel", on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="transfers_to")

    transfer_status = models.CharField(max_length=50)
    transfer_initiation_date = models.DateTimeField(null=True, blank=True)
    transfer_acceptance_date = models.DateTimeField(null=True, blank=True)

    cbic_status = models.CharField(max_length=100, null=True, blank=True)
    cbic_response_date = models.DateTimeField(null=True, blank=True)

    user_id_transfer_initiation = models.CharField(max_length=100, null=True, blank=True)
    user_id_acceptance = models.CharField(max_length=100, null=True, blank=True)

    # Expand phase: proper FK columns replacing the CharField ID copies above.
    # Backfilled by data migration 0XXX_backfill_transfer_user_fks.
    transfer_initiation_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='transfer_initiations',
    )
    acceptance_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='transfer_acceptances',
    )

    def __str__(self) -> str:
        fd = self.transfer_date or (self.transfer_initiation_date.date() if self.transfer_initiation_date else None)
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


# -----------------------------
# Incentive License (RODTEP/ROSTL/MEIS)
# -----------------------------
class IncentiveLicense(AuditModel):
    """
    Model for incentive-based licenses: RODTEP, ROSTL, MEIS
    These licenses have a standard 2-year validity from license date.
    """
    LICENSE_TYPE_CHOICES = (
        ('RODTEP', 'RODTEP'),
        ('ROSTL', 'ROSTL'),
        ('MEIS', 'MEIS'),
    )

    SOLD_STATUS_CHOICES = (
        ('NO', 'Not Sold'),
        ('PARTIAL', 'Partially Sold'),
        ('YES', 'Fully Sold'),
    )

    license_type = models.CharField(max_length=10, choices=LICENSE_TYPE_CHOICES, db_index=True)
    license_number = models.CharField(max_length=50, unique=True, db_index=True)
    license_date = models.DateField()
    license_expiry_date = models.DateField(help_text="Auto-calculated as 2 years from license date")

    exporter = models.ForeignKey("core.CompanyModel", on_delete=models.CASCADE, related_name="incentive_licenses")
    port_code = models.ForeignKey("core.PortModel", on_delete=models.CASCADE, related_name="incentive_licenses")

    license_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=DEC_0,
        validators=[MinValueValidator(DEC_0)],
        help_text="Total license value in INR"
    )

    sold_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=DEC_0,
        validators=[MinValueValidator(DEC_0)],
        help_text="Total sold value in INR (auto-calculated)"
    )

    balance_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=DEC_0,
        help_text="Remaining balance in INR (auto-calculated)"
    )

    sold_status = models.CharField(
        max_length=10,
        choices=SOLD_STATUS_CHOICES,
        default='NO',
        db_index=True,
        help_text="Sold status (auto-calculated)"
    )

    # Additional fields for tracking
    is_active = models.BooleanField(default=True)
    notes = models.TextField(null=True, blank=True)

    admin_search_fields = ("license_number", "exporter__name")

    class Meta:
        ordering = ("-license_date", "license_number")
        indexes = [
            models.Index(fields=['license_number']),
            models.Index(fields=['license_type']),
            models.Index(fields=['exporter', 'license_date']),
            models.Index(fields=['license_date']),
            models.Index(fields=['license_expiry_date']),
            models.Index(fields=['is_active']),
            models.Index(fields=['sold_status']),
        ]
        verbose_name = "Incentive License"
        verbose_name_plural = "Incentive Licenses"

    def __str__(self) -> str:
        return f"{self.license_type} - {self.license_number}"

    def save(self, *args, **kwargs):
        """Auto-calculate expiry date as 2 years from license date"""
        if self.license_date and not self.license_expiry_date:
            from dateutil.relativedelta import relativedelta
            self.license_expiry_date = self.license_date + relativedelta(years=2)

        # Calculate balance if license_value changed
        if self.license_value is not None:
            self.balance_value = self.license_value - self.sold_value

        super().save(*args, **kwargs)

    def update_sold_status(self):
        """
        Update sold_value, balance_value, and sold_status based on related trades.
        Call this method after trade changes.
        """
        from django.db.models import Sum
        from decimal import Decimal

        # Calculate sold value from SALE trades
        sold = self.trade_lines.filter(
            trade__direction='SALE'
        ).aggregate(
            total=Sum('license_value')
        )['total'] or Decimal('0.00')

        self.sold_value = sold
        self.balance_value = self.license_value - self.sold_value

        # Determine sold status
        if self.sold_value == Decimal('0.00'):
            self.sold_status = 'NO'
        elif self.balance_value <= Decimal('0.00'):
            self.sold_status = 'YES'
        else:
            self.sold_status = 'PARTIAL'

        # Use update() to avoid triggering signals
        IncentiveLicense.objects.filter(pk=self.pk).update(
            sold_value=self.sold_value,
            balance_value=self.balance_value,
            sold_status=self.sold_status
        )

    def get_sold_value(self):
        """Get cached sold value (deprecated - use sold_value field directly)"""
        return self.sold_value

    def get_balance_value(self):
        """Get cached balance value (deprecated - use balance_value field directly)"""
        return self.balance_value


# -----------------------------
# License Purchase (unchanged but Decimal-safe)
# -----------------------------
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
    license = models.ForeignKey("license.LicenseDetailsModel", on_delete=models.CASCADE,
                                related_name="purchases")
    purchasing_entity = models.ForeignKey("core.CompanyModel", null=True, blank=True, on_delete=models.SET_NULL,
                                          related_name="entity_purchases")
    supplier = models.ForeignKey("core.CompanyModel", null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name="supplier_purchases")

    supplier_pan = models.CharField(max_length=32, null=True, blank=True)
    supplier_gst = models.CharField(max_length=32, null=True, blank=True)

    invoice_number = models.CharField(max_length=128, null=True, blank=True)
    invoice_date = models.DateField(null=True, blank=True)
    invoice_copy = models.FileField(upload_to="license_purchases/invoices/", null=True, blank=True)

    mode = models.CharField(max_length=10, choices=MODE_CHOICES, default=MODE_AMOUNT)

    amount_source = models.CharField(max_length=10, choices=AMOUNT_SOURCE_CHOICES, default=SRC_FOB_INR)
    fob_inr = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0, validators=[MinValueValidator(DEC_0)])
    cif_inr = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0, validators=[MinValueValidator(DEC_0)])
    cif_usd = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0, validators=[MinValueValidator(DEC_0)])
    exchange_rate = models.DecimalField(max_digits=15, decimal_places=6, default=DEC_0,
                                        validators=[MinValueValidator(DEC_0)])
    markup_pct = models.DecimalField(max_digits=15, decimal_places=6, default=DEC_0,
                                     validators=[MinValueValidator(DEC_0)])

    product_name = models.CharField(max_length=255, null=True, blank=True)
    quantity_kg = models.DecimalField(max_digits=15, decimal_places=3, default=DEC_000,
                                      validators=[MinValueValidator(DEC_000)])
    rate_inr = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0,
                                   validators=[MinValueValidator(DEC_0)])

    amount_inr = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0,
                                     validators=[MinValueValidator(DEC_0)])

    class Meta:
        ordering = ["-created_on"]

    def __str__(self):
        base = f"{self.amount_source}" if self.mode == self.MODE_AMOUNT else f"{self.product_name or 'QTY'}"
        return f"Purchase[{self.id}] L#{self.license_id} {base} ₹{self.amount_inr:.2f}"

    def _source_amount(self) -> Decimal:
        if self.amount_source == self.SRC_FOB_INR:
            return _to_decimal(self.fob_inr, DEC_0)
        if self.amount_source == self.SRC_CIF_INR:
            return _to_decimal(self.cif_inr, DEC_0)
        if self.amount_source == self.SRC_CIF_USD:
            return _to_decimal(self.cif_usd, DEC_0)
        return DEC_0

    def _amount_base_inr(self) -> Decimal:
        return self._source_amount()

    def compute_amount_inr(self) -> Decimal:
        if self.mode == self.MODE_AMOUNT:
            source = self._source_amount()
            pct = _to_decimal(self.markup_pct, DEC_0)
            bill = source * (pct / _to_decimal("100"))
            return bill.quantize(DEC_0, rounding=ROUND_HALF_UP)
        q = _to_decimal(self.quantity_kg, DEC_000)
        r = _to_decimal(self.rate_inr, DEC_0)
        amt = q * r
        return amt.quantize(DEC_0, rounding=ROUND_HALF_UP)

    def save(self, *args, **kwargs):
        if self.supplier and not self.supplier_pan:
            try:
                self.supplier_pan = getattr(self.supplier, "pan", self.supplier_pan)
            except Exception:
                pass
        if self.supplier and not self.supplier_gst:
            try:
                self.supplier_gst = getattr(self.supplier, "gst_number", self.supplier_gst)
            except Exception:
                pass

        er = _to_decimal(self.exchange_rate, DEC_0)
        usd = _to_decimal(self.cif_usd, DEC_0)
        inr = _to_decimal(self.cif_inr, DEC_0)

        if er <= DEC_0 and usd > DEC_0 and inr > DEC_0:
            self.exchange_rate = (inr / usd).quantize(_to_decimal("0.001"))

        try:
            if self.markup_pct not in (None, ""):
                self.markup_pct = _to_decimal(self.markup_pct, DEC_0).quantize(_to_decimal("0.000001"))
        except Exception:
            self.markup_pct = DEC_0

        self.amount_inr = self.compute_amount_inr()
        super().save(*args, **kwargs)


# -----------------------------

# ============================================================================
# LicenseDetailsModel sub-tables (vertical-split / normalization Phase 6)
# ----------------------------------------------------------------------------
# These four OneToOne models hold the fields that used to live on
# LicenseDetailsModel. They are populated 1:1 with their parent license and
# auto-created via a post_save signal on LicenseDetailsModel. Old read access
# via `license.is_active` etc. is preserved through @property accessors on
# LicenseDetailsModel (defined further up in the class).
# ============================================================================


class LicenseNotes(models.Model):
    """User-entered text fields associated with a license. Extracted from
    LicenseDetailsModel to keep the main table narrow and avoid PostgreSQL
    TOAST overflow on wide rows.
    """
    license = models.OneToOneField(
        LicenseDetailsModel,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="notes",
    )
    user_comment = models.TextField(null=True, blank=True)
    condition_sheet = models.TextField(null=True, blank=True)
    user_restrictions = models.TextField(null=True, blank=True)
    balance_report_notes = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = "License Notes"
        verbose_name_plural = "License Notes"


class LicenseBalance(models.Model):
    """Materialized balance state for a license. balance_cif is a denormalized
    cache kept in sync by signals.
    """
    license = models.OneToOneField(
        LicenseDetailsModel,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="balance",
    )
    balance_cif = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=DEC_0,
        validators=[MinValueValidator(DEC_0)],
    )
    ledger_date = models.DateField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["balance_cif"]),
        ]


class LicenseFlags(models.Model):
    """Boolean status flags for a license. Extracted so wide writes to flags
    don't touch the main license row.
    """
    license = models.OneToOneField(
        LicenseDetailsModel,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="flags",
    )
    is_active = models.BooleanField(default=True)
    is_audit = models.BooleanField(default=False)
    is_mnm = models.BooleanField(default=False)
    is_not_registered = models.BooleanField(default=False)
    is_null = models.BooleanField(default=False)
    is_au = models.BooleanField(default=False)
    is_incomplete = models.BooleanField(default=False)
    is_expired = models.BooleanField(default=False)
    is_individual = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["is_active", "is_expired"]),
        ]


class LicenseOwnership(models.Model):
    """Current-owner pointer and DGFT-side transfer state. Full ownership
    history lives in LicenseTransferModel (already exists).
    """
    license = models.OneToOneField(
        LicenseDetailsModel,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="ownership",
    )
    current_owner = models.ForeignKey(
        "core.CompanyModel",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="owned_licenses",
    )
    file_transfer_status = models.TextField(null=True, blank=True)
    last_ownership_fetch = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["current_owner"]),
        ]


@receiver(post_save, sender=LicenseDetailsModel)
def _ensure_license_subrows(sender, instance, created, **kwargs):
    """Ensure each LicenseDetailsModel has its 4 OneToOne sub-rows.

    Called for both create and update; cheap because get_or_create is a no-op
    on existing rows. Required so that back-compat @property reads on the
    parent always find a related row.
    """
    if kwargs.get("raw"):
        return
    LicenseNotes.objects.get_or_create(license=instance)
    LicenseBalance.objects.get_or_create(license=instance)
    LicenseFlags.objects.get_or_create(license=instance)
    LicenseOwnership.objects.get_or_create(license=instance)
