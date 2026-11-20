"""
SAT-DEF-150 / C-2 ongoing trigger: when a DEBIT `RowDetails` row is created,
run the exact allotment matcher for that row's BOE once the transaction commits.

Never raises into the save path. `bulk_create` bypasses `post_save`, so rows
created in bulk are covered by the `auto_link_allotments` management command.
OFF by default (audit F6, 2026-11-20): enable with `settings.ALLOTMENT_AUTO_LINK_ON_BOE = True`
only after the owner approves the C-2 data-repair run.
"""
import logging

from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.bill_of_entry.models import RowDetails
from apps.core.constants import DEBIT

logger = logging.getLogger(__name__)


def _run_for_boe(boe_id, license_id):
    try:
        from apps.reconciliation.services.allotment_auto_link import apply_exact_links

        apply_exact_links([license_id], dry_run=False, boe_id=boe_id)
    except Exception:  # noqa: BLE001 - must never break the BOE save path
        logger.exception("allotment auto-link failed for BOE %s", boe_id)


@receiver(post_save, sender=RowDetails, dispatch_uid="reconciliation_auto_link_allotment_on_debit")
def auto_link_on_debit_row(sender, instance, created, raw=False, **kwargs):
    try:
        if raw or not created or not getattr(settings, "ALLOTMENT_AUTO_LINK_ON_BOE", False):
            return
        if instance.transaction_type != DEBIT or not instance.bill_of_entry_id:
            return
        boe_id = instance.bill_of_entry_id
        license_id = instance.sr_number.license_id
        transaction.on_commit(lambda: _run_for_boe(boe_id, license_id))
    except Exception:  # noqa: BLE001
        logger.exception("allotment auto-link signal setup failed")
