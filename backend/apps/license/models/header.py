"""Licence header (LicenseDetailsModel), its 1:1 sub-tables and the sub-row signal.

Split verbatim from core.py; behaviour unchanged.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, Optional

from django.db import models
from django.db.models import Sum, DecimalField, Value
from django.db.models.functions import Coalesce
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from django.utils.functional import cached_property

from apps.allotment.models import AllotmentItems
from apps.bill_of_entry.models import RowDetails, annotate_and_exclude_hidden
from apps.core.constants import DEC_0, DEC_000, DEBIT
from apps.core.models import AuditModel
from apps.core.utils.decimal_utils import (
    to_decimal as _to_decimal,
    round_decimal_down as round_down,
)


# -----------------------------
# License Header
# -----------------------------
class LicenseDetailsModel(AuditModel):
    # ``None`` deliberately remains the historical behaviour.  This is an
    # opt-in only control: False is also historical/shared behaviour while
    # True makes the import-item CIF ceiling authoritative.
    individual_item_cif_override = models.BooleanField(null=True, blank=True, default=None)

    # Monotonic planning generations.  Source-changing signals increment the
    # first field; a worker only advances the applied field after it has
    # successfully built a plan for that exact generation.
    planning_source_revision = models.PositiveBigIntegerField(default=0)
    planning_applied_revision = models.PositiveBigIntegerField(default=0)
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
    port = models.ForeignKey("core.PortModel", on_delete=models.PROTECT, null=True, blank=True)

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
        """Calculate total debit using centralized service (raw, unconditional BOE debit — matches Balance CIF)."""
        from apps.license.services.balance_calculator import LicenseBalanceCalculator
        return LicenseBalanceCalculator.calculate_boe_debit_total(self)

    def _calculate_license_allotment(self) -> Decimal:
        """Calculate total allotment using centralized service"""
        from apps.license.services.balance_calculator import LicenseBalanceCalculator
        return LicenseBalanceCalculator.calculate_allotment(self)

    @property
    def get_balance_cif(self) -> Decimal:
        """
        Authoritative live "Balance CIF" for this licence — the single
        figure every consumer (list views, dashboard cards, the cached
        `LicenseBalance.balance_cif` field via `update_license_flags`,
        item-level restricted-allocation helpers below, exports/reports)
        reads as "the" business balance. Backed by the Financial Ledger
        formula (`calculate_financial_balance` — Opening Balance/Previous
        Owner Utilisation + Purchase - Sale - Our BOEs - Outstanding
        Allotments), NOT the raw Customs formula (`calculate_balance`).

        `calculate_balance` ("Customs Balance") still exists and is called
        directly wherever the Customs Ledger / three-way reconciliation
        panel deliberately needs that separate, literal figure to compare
        against — this property is the ONLY thing that changed; the two
        engines still intentionally diverge for licences with hidden BOEs,
        that comparison just no longer flows through this property.
        """
        from apps.license.services.balance_calculator import LicenseBalanceCalculator
        return LicenseBalanceCalculator.calculate_financial_balance(self)

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
            # Previous-owner "hidden" rows (genuinely hidden per audit
            # trail, see `annotate_and_exclude_hidden`) are excluded —
            # feeds the borax/rutile split report (`tables.py`), a
            # balance/report figure like any other DEBIT sum.
            debit = _to_decimal(
                annotate_and_exclude_hidden(
                    RowDetails.objects.filter(sr_number__license=self, bill_of_entry__company=biscuit_company_id, transaction_type=DEBIT),
                    boe_field="bill_of_entry",
                )
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
        available_value = max(self.get_balance_cif, DEC_0)  # CAP: clamp (negative balance => 0 availability)
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
        available_value = max(self.get_balance_cif, DEC_0)  # CAP: clamp (negative balance => 0 availability)
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
        available_value = max(self.get_balance_cif, DEC_0)  # CAP: clamp (negative balance => 0 availability)
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
