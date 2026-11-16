"""Export / import item models and the import-item balance signal.

Split verbatim from core.py; behaviour unchanged.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Dict, Any, Optional

from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import Count, Sum, DecimalField, Value
from django.db.models.functions import Coalesce
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.functional import cached_property

from apps.allotment.models import AllotmentItems
from apps.bill_of_entry.models import RowDetails, annotate_and_exclude_hidden
from apps.core.constants import (
    DEC_0,
    DEC_000,
    UNIT_CHOICES,
    CURRENCY_CHOICES,
    NOTIFICATION_NORM_CHOICES,
    KG,
    USD,
    DEBIT,
)
from apps.core.models import ItemNameModel
from apps.core.utils.decimal_utils import (
    to_decimal as _to_decimal,
    round_decimal_down as round_down,
)


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
        """Calculate total debit for this specific import item.

        Excludes previous-owner "hidden" rows (genuinely hidden per audit
        trail, see `annotate_and_exclude_hidden`) — a debit total by
        definition, and no consumer of this figure should ever silently
        include previous-owner utilisation.
        """
        return _to_decimal(
            annotate_and_exclude_hidden(
                RowDetails.objects.filter(sr_number=self, transaction_type=DEBIT),
                boe_field="bill_of_entry",
            ).aggregate(
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
        Alias for `available_value_calculated` — the single implementation
        of row-level Balance CIF under the condition_type model. Kept as a
        separate property only because several call sites (legacy reports,
        PDF/Excel exporters, sync commands) already read `.balance_cif_fc`;
        it used to duplicate `available_value_calculated`'s formula minus
        the 0.01-CIF-marker special case, which let the two disagree for
        marker items. Delegating removes that gap without touching every
        caller individually.
        """
        return self.available_value_calculated

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
        3. If the import credit row carries a positive FC CIF, non-% items
              use that item's own CIF less its own applicable BOE/allotment
              usage.  A zero-CIF item instead uses the live licence balance.
        4. If condition_type == "AU": the same CIF-source hierarchy applies;
              AU remains non-transferable, not a separate CIF pool.
        5. Otherwise (empty condition_type / "open"): use the same hierarchy.

        For BULK contexts (many items on the same licence) prefer
        `condition_pool.compute_condition_pools(license)` once and reuse the
        returned dict, rather than calling this property per-item — see
        `_update_all_import_items_available_value` in license.signals.

        For BULK contexts spanning MANY licences (e.g. a paginated list
        response mixing items from different licences, such as the
        Allotment "available-items" action) use
        `condition_pool.available_value_bulk_map(items)` instead — it
        composes `LicenseBalanceCalculator.calculate_financial_balance_for_licenses`
        and `condition_pool.compute_condition_pools_bulk` to stay a fixed
        number of queries regardless of batch size. Its branching is kept
        in lock-step with this property's (see
        `condition_pool._resolve_available_value`'s docstring) — never let
        the two drift apart.
        """
        if not self.license_id:
            return DEC_0

        # Special marker value
        if self.cif_inr == Decimal("0.01") or self.cif_fc == Decimal("0.01"):
            return Decimal("0.01")

        # `LicenseBalance.balance_cif` is a denormalized cache. Reconciliation
        # allocations can change the Financial Ledger without refreshing that
        # cache, so this foundational single-item calculation must read the
        # authoritative live balance. Bulk callers use
        # `condition_pool.available_value_bulk_map()` instead.
        from apps.license.services.balance_calculator import LicenseBalanceCalculator
        cond = (self.condition_type or "").strip()

        # Percentage condition — pool-based shared limit.
        if cond.endswith("%"):
            license_balance = max(LicenseBalanceCalculator.calculate_financial_balance(self.license), DEC_0)  # CAP clamp
            from apps.license.services.condition_pool import remaining_for_condition
            remaining = remaining_for_condition(self.license, cond)
            if remaining is None:
                return license_balance
            return min(remaining, license_balance)

        # Positive import-credit CIF is an item-level attribution.  A missing
        # (zero) item CIF retains the authoritative live Financial Ledger
        # fallback; never use the denormalized LicenseBalance cache here.
        from apps.license.services.balance_calculator import ItemBalanceCalculator
        if ItemBalanceCalculator.has_item_attributed_cif(self):
            return ItemBalanceCalculator.calculate_item_attributed_balance(self)
        return max(LicenseBalanceCalculator.calculate_financial_balance(self.license), DEC_0)  # CAP clamp

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
