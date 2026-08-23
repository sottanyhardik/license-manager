"""
Ignore/restore workflow for Licence Balance Workspace warnings
(`apps.license.services.license_balance_ledger_builder.build_warnings`).

Pure workflow bookkeeping — see `IgnoredWarning`'s docstring. These
functions never touch any financial record (no allocation, invoice, BOE,
allotment, or balance is read or written here), and the audit trail is the
same `ReconciliationLog` every other reconciliation action already writes
to, not a second logging mechanism.
"""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone


def ignore_warning(license_obj, warning_type, entity_type, entity_id, user, reason=""):
    """
    Marks a warning (identified by `warning_type`/`entity_type`/`entity_id`
    on this licence) as ignored. Idempotent: ignoring an already-ignored
    warning just refreshes who/when/why.
    """
    from apps.reconciliation.models import IgnoredWarning, ReconciliationLog

    entity_id = str(entity_id)
    with transaction.atomic():
        obj, created = IgnoredWarning.objects.select_for_update().get_or_create(
            license=license_obj, warning_type=warning_type, entity_type=entity_type, entity_id=entity_id,
            defaults={
                'ignored': True, 'ignored_by': user, 'ignored_at': timezone.now(), 'reason': reason,
            },
        )
        if not created:
            obj.ignored = True
            obj.ignored_by = user
            obj.ignored_at = timezone.now()
            obj.reason = reason
            obj.restored_by = None
            obj.restored_at = None
            obj.save(update_fields=['ignored', 'ignored_by', 'ignored_at', 'reason', 'restored_by', 'restored_at'])

        ReconciliationLog.objects.create(
            action=ReconciliationLog.ACTION_WARNING_IGNORED,
            reason=reason,
            user=user,
            before={'ignored': False},
            after={
                'ignored': True, 'warning_type': warning_type,
                'entity_type': entity_type, 'entity_id': entity_id,
            },
        )
    return obj


def restore_warning(ignored_warning, user, reason=""):
    """Un-ignores a warning — it reappears in Active Warnings on the next
    `build_warnings()` call. The row is never deleted (kept for audit
    history of who ignored/restored it and when)."""
    from apps.reconciliation.models import ReconciliationLog

    with transaction.atomic():
        ignored_warning.ignored = False
        ignored_warning.restored_by = user
        ignored_warning.restored_at = timezone.now()
        ignored_warning.save(update_fields=['ignored', 'restored_by', 'restored_at'])

        ReconciliationLog.objects.create(
            action=ReconciliationLog.ACTION_WARNING_RESTORED,
            reason=reason,
            user=user,
            before={'ignored': True},
            after={
                'ignored': False, 'warning_type': ignored_warning.warning_type,
                'entity_type': ignored_warning.entity_type, 'entity_id': ignored_warning.entity_id,
            },
        )
    return ignored_warning
