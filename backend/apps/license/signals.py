# license/signals.py
import logging
import threading
from contextlib import contextmanager
from decimal import Decimal

from django.db.models.signals import post_delete, post_save, pre_delete
from django.dispatch import receiver
from django.utils import timezone

from apps.allotment.models import AllotmentItems
from apps.bill_of_entry.models import RowDetails
from apps.core.models import CompanyModel
from apps.license.models import LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel
from apps.trade.models import LicenseTradeLine


logger = logging.getLogger(__name__)
DEC_0 = Decimal("0")
SPECIAL_AVAILABLE_VALUE = Decimal("0.01")
BALANCE_ONLY_UPDATE_FIELDS = frozenset(
    {
        "available_quantity",
        "debited_quantity",
        "allotted_quantity",
        "allotted_value",
        "debited_value",
        "available_value",
        "is_restricted",
    }
)


# ── Bulk-operation guard ─────────────────────────────────────────────────────
# Serializers that save many import/export items in one request (e.g. licence
# create with 38 items × cascading balance recalcs) can suspend the per-item
# `update_license_flags` recalculation by entering this context, then call
# `update_license_flags()` ONCE at the end. Without this guard, 38 item
# creates fire ~275 SQL sums each → multi-thousand-query saves.
_bulk_state = threading.local()


def _flags_suspended() -> bool:
    return getattr(_bulk_state, "suspended", False)


@contextmanager
def suspend_license_flag_recalc():
    """Suspend `update_license_flags` calls from license import/export item
    signals on the current thread for the duration of the block.

    Always pair with a manual `update_license_flags(license_obj)` call after
    the bulk work so the licence row's balance/flags stay consistent.
    """
    prev = getattr(_bulk_state, "suspended", False)
    _bulk_state.suspended = True
    try:
        yield
    finally:
        _bulk_state.suspended = prev


def _instance_id(instance) -> str:
    return str(getattr(instance, "pk", None) or getattr(instance, "id", None) or "unsaved")


def _related_license(instance, relation_name):
    related = getattr(instance, relation_name, None)
    return getattr(related, "license", None) if related is not None else None


def _update_all_import_items_available_value(license_instance):
    """
    Update available_value for ALL import items in a license, using the
    pool-based condition_type model.

    Cost is O(M) where M = number of distinct %-condition groups on this
    licence (typically 1–5), rather than O(N²) per-item — the helper
    `condition_pool.compute_condition_pools` issues ~3 SUM queries per group
    and reuses the result across every item that shares that condition_type.

    Semantics (see `available_value_calculated`):
      • `condition_type` ending in "%"  → pool-limited, capped at licence balance
      • `condition_type == "AU"`         → licence balance (non-transferable)
      • empty condition_type             → licence balance (open)

    Uses bulk `.update()` to bypass post_save signals and prevent recursion.
    """
    from apps.license.services.condition_pool import compute_condition_pools

    if license_instance is None or not getattr(license_instance, "pk", None):
        return

    try:
        import_items = list(license_instance.import_license.all())
        if not import_items:
            return

        # `update_license_flags` writes the new balance via .filter().update()
        # on the LicenseBalance sub-table — refresh that sub-row, not the parent.
        # (balance_cif is no longer a field on LicenseDetailsModel.)
        if hasattr(license_instance, "balance") and license_instance.balance is not None:
            license_instance.balance.refresh_from_db(fields=["balance_cif"])
        license_balance = license_instance.balance_cif or DEC_0

        # One-shot computation of remaining pools for every %-condition on
        # this licence (handles 0 groups too — returns an empty dict).
        pools = compute_condition_pools(license_instance)

        updates_made = 0
        for item in import_items:
            try:
                if item.cif_inr == SPECIAL_AVAILABLE_VALUE or item.cif_fc == SPECIAL_AVAILABLE_VALUE:
                    new_av = SPECIAL_AVAILABLE_VALUE
                else:
                    cond = (item.condition_type or "").strip()
                    if cond.endswith("%") and cond in pools:
                        new_av = min(pools[cond], license_balance)
                    else:
                        # "AU" or empty: just track licence balance.
                        new_av = license_balance

                if item.available_value != new_av:
                    LicenseImportItemsModel.objects.filter(pk=item.pk).update(
                        available_value=new_av
                    )
                    updates_made += 1
            except Exception:
                logger.exception(
                    "Error updating available_value for import item %s",
                    _instance_id(item),
                )

        if updates_made > 0:
            logger.info(
                "Updated available_value for %d import items in license %s",
                updates_made, license_instance.license_number,
            )

    except Exception:
        logger.exception(
            "Error updating import items for license %s",
            _instance_id(license_instance),
        )


def update_license_flags(license_instance):
    """
    Helper function to update is_null, is_expired flags and balance_cif for a license.
    Also updates available_value for ALL import items when balance changes.
    This is critical for dashboard accuracy - it recalculates balance_cif on every change.

    NOTE: After the 4-table split (LicenseFlags / LicenseBalance), flags and
    balance live on OneToOne sub-tables. We write to each sub-table directly
    via queryset.update() to avoid triggering the post_save signal recursion.
    """
    # Import locally to avoid circular imports at module load
    from apps.license.models import LicenseFlags, LicenseBalance

    if license_instance is None or not getattr(license_instance, "pk", None):
        return

    flag_updates = {}
    balance_updates = {}
    balance_changed = False

    # Update is_expired based on license_expiry_date
    # BUSINESS RULE: Expired = expiry date < today
    if license_instance.license_expiry_date:
        new_is_expired = license_instance.license_expiry_date < timezone.now().date()
        if license_instance.is_expired != new_is_expired:
            flag_updates['is_expired'] = new_is_expired

    # Update balance_cif and is_null based on current balance calculation
    try:
        balance = license_instance.get_balance_cif

        if license_instance.balance_cif != balance:
            balance_changed = True
            balance_updates['balance_cif'] = balance

        # BUSINESS RULE: Null DFIA = balance < $500
        new_is_null = balance < Decimal('500')
        if license_instance.is_null != new_is_null:
            flag_updates['is_null'] = new_is_null
    except Exception:
        logger.exception(
            "Error calculating balance for license %s",
            _instance_id(license_instance),
        )

    if flag_updates:
        LicenseFlags.objects.filter(license_id=license_instance.pk).update(**flag_updates)
    if balance_updates:
        LicenseBalance.objects.filter(license_id=license_instance.pk).update(**balance_updates)

    # CRITICAL: Update available_value for ALL import items when balance changes
    # This ensures that when Item A gets debited, Items B, C, D also get updated
    if balance_changed:
        _update_all_import_items_available_value(license_instance)


@receiver(post_save, sender=LicenseDetailsModel)
def auto_fetch_import_items(sender, instance, created, **kwargs):
    """
    Automatically link ItemNameModel items to existing LicenseImportItemsModel when a license is saved.
    Also updates is_null and is_expired flags.
    This works like populate_license_items command - matches based on description/HS filters and norm class.
    """
    # Prevent infinite recursion by checking if we're already in a save
    if kwargs.get('raw', False):
        return
    # Bulk operation in progress — serializer will call update_license_flags
    # explicitly after all child rows are written.
    if _flags_suspended():
        return

    # Update license flags
    update_license_flags(instance)

    # Only auto-link items if import items exist
    if not instance.import_license.exists():
        return

    # Get license export norm classes
    license_norm_classes = list(
        instance.export_license.values_list('norm_class__norm_class', flat=True).distinct()
    )

    if not license_norm_classes:
        return

    # Use the shared item matcher utility for consistent matching logic
    from apps.license.utils.item_matcher import match_import_item_to_items

    # For each import item in the license, find and link matching ItemNameModel items
    for import_item in instance.import_license.all():
        # Skip if items are already linked
        if import_item.items.exists():
            continue

        matching_items = match_import_item_to_items(import_item, license_norm_classes)

        # Link all matching ItemNameModel items. `is_restricted` is no longer
        # auto-set from ItemNameModel.restriction_percentage — restrictions
        # come exclusively from the licence's condition sheet via
        # `condition_type`.
        for item_name in matching_items:
            if not import_item.items.filter(id=item_name.id).exists():
                import_item.items.add(item_name)


@receiver(post_save, sender=LicenseExportItemModel)
def update_license_on_export_item_change(sender, instance, created, **kwargs):
    """
    Update license flags when export items are added/modified.
    This ensures is_null and is_expired are updated after export items are created.
    """
    if kwargs.get('raw', False):
        return
    if _flags_suspended():
        return

    if instance.license:
        update_license_flags(instance.license)


@receiver(post_delete, sender=LicenseExportItemModel)
def update_license_on_export_item_delete(sender, instance, **kwargs):
    """
    Update license flags when export items are deleted.
    """
    if kwargs.get('raw', False):
        return
    if _flags_suspended():
        return

    if instance.license:
        update_license_flags(instance.license)


# Signals for balance updates on import items
@receiver(post_save, sender=LicenseImportItemsModel)
def update_license_on_import_item_change(sender, instance, created, **kwargs):
    """
    Update license flags when import items are added/modified.
    Also auto-link ItemNameModel items based on description/HS code and norm class.
    This ensures balance_cif, available_quantity, and available_value are updated.
    """
    if kwargs.get('raw', False):
        logger.debug("Signal skipped (raw=True) for import item %s", _instance_id(instance))
        return
    if _flags_suspended():
        # Bulk serializer operation in progress — the caller will flush
        # update_license_flags once after all items are written.
        logger.debug("Signal skipped (flags suspended) for import item %s", _instance_id(instance))
        return

    # Skip if only balance fields changed — those updates come from
    # `update_balance_values` (the on_commit job) and the licence balance was
    # already recomputed when whatever triggered THAT change ran. Re-running
    # update_license_flags here is just expensive duplicate work and creates
    # an O(N) cascade after every bulk save commits.
    update_fields = kwargs.get('update_fields')
    if update_fields is not None:
        if set(update_fields).issubset(BALANCE_ONLY_UPDATE_FIELDS):
            return

    logger.info("Signal fired for import item %s (created=%s)", _instance_id(instance), created)

    if instance.license:
        update_license_flags(instance.license)

        # Only auto-link items if no items are currently linked (items field is empty)
        if instance.items.exists():
            logger.info(
                "Import item %s already has items linked. Skipping auto-link.",
                _instance_id(instance),
            )
            return

        # Auto-link ItemNameModel items when import item is created or updated
        # Get license export norm classes
        license_norm_classes = list(
            instance.license.export_license.values_list('norm_class__norm_class', flat=True).distinct()
        )

        logger.info("License norm classes: %s", license_norm_classes)

        if license_norm_classes and instance.description:
            # Use the shared item matcher utility for consistent matching logic
            from apps.license.utils.item_matcher import match_import_item_to_items

            matching_items = match_import_item_to_items(instance, license_norm_classes)

            logger.info(
                "Found %d matching items using comprehensive filters",
                matching_items.count(),
            )

            # Link ALL matching items. `is_restricted` is no longer auto-set
            # from ItemNameModel.restriction_percentage — restrictions come
            # exclusively from the licence's condition sheet via condition_type.
            for item_name in matching_items:
                if not instance.items.filter(id=item_name.id).exists():
                    logger.info(
                        "Linking item %s (%s) to import item %s",
                        item_name.id,
                        item_name.name,
                        _instance_id(instance),
                    )
                    instance.items.add(item_name)
                else:
                    logger.debug(
                        "Item %s already linked to import item %s",
                        item_name.id,
                        _instance_id(instance),
                    )
        else:
            if not license_norm_classes:
                logger.warning(
                    "No license norm classes found for license %s",
                    _instance_id(instance.license),
                )
            if not instance.description:
                logger.warning("No description for import item %s", _instance_id(instance))


@receiver(post_delete, sender=LicenseImportItemsModel)
def update_license_on_import_item_delete(sender, instance, **kwargs):
    """
    Update license flags when import items are deleted.
    """
    if kwargs.get('raw', False):
        return
    if _flags_suspended():
        return

    if instance.license:
        update_license_flags(instance.license)


# Signals for balance updates on allotment items
@receiver(post_save, sender=AllotmentItems)
@receiver(post_delete, sender=AllotmentItems)
def update_license_on_allotment_item_change(sender, instance, **kwargs):
    """
    Update license flags when allotment items are added/modified/deleted.
    This ensures balance_cif is updated when allocations change.
    """
    if kwargs.get('raw', False):
        return

    license_obj = _related_license(instance, "item")
    if license_obj:
        update_license_flags(license_obj)


# Signals for balance updates on BOE items
@receiver(post_save, sender=RowDetails)
@receiver(post_delete, sender=RowDetails)
def update_license_on_boe_item_change(sender, instance, **kwargs):
    """
    Update license flags when BOE row details are added/modified/deleted.
    This ensures balance_cif is updated when BOE debits are made.
    """
    if kwargs.get('raw', False):
        return

    license_obj = _related_license(instance, "sr_number")
    if license_obj:
        update_license_flags(license_obj)


# Signals for balance updates on Trade Line items
@receiver(post_save, sender=LicenseTradeLine)
@receiver(post_delete, sender=LicenseTradeLine)
def update_license_on_trade_line_change(sender, instance, **kwargs):
    """
    Update license flags when trade lines are added/modified/deleted.
    This ensures balance_cif is updated when trade CIF changes.
    """
    if kwargs.get('raw', False):
        return

    license_obj = _related_license(instance, "sr_number")
    if license_obj:
        update_license_flags(license_obj)


# Snapshot the exporter name onto each license BEFORE the company is deleted.
# With exporter.on_delete=SET_NULL, the FK becomes NULL post-delete; this signal
# preserves the human-readable name in `archived_exporter_name`.
@receiver(pre_delete, sender=CompanyModel)
def snapshot_exporter_name_on_company_delete(sender, instance, **kwargs):
    LicenseDetailsModel.objects.filter(exporter=instance).update(
        archived_exporter_name=instance.name or ""
    )
