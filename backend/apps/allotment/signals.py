# allotment/signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from apps.allotment.models import AllotmentItems


@receiver(post_save, sender=AllotmentItems)
def update_is_allotted_on_save(sender, instance, created, **kwargs):
    """
    Update is_allotted to True when an AllotmentItems is created or updated
    Balance refresh is deliberately not performed here.  The model-level
    on-commit receiver is the sole balance-refresh path, preventing a
    rolled-back allocation from updating a live licence balance.
    """
    # Prevent recursive signal calls
    if kwargs.get('raw', False):
        return

    if instance.allotment:
        instance.allotment.is_allotted = True
        instance.allotment.save(update_fields=['is_allotted'])

@receiver(post_delete, sender=AllotmentItems)
def update_is_allotted_on_delete(sender, instance, **kwargs):
    """
    Update is_allotted after the requested row is gone.  Never cascade-delete
    sibling allocations from a single-row deallocation.
    """
    try:
        allotment = instance.allotment
        if allotment and not allotment.allotment_details.exists() and allotment.is_allotted:
            allotment.is_allotted = False
            allotment.save(update_fields=['is_allotted'])
    except Exception:
        # A parent cascade may already have removed the allotment.
        pass
