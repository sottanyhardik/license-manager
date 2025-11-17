# allotment/signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from allotment.models import AllotmentItems


@receiver(post_save, sender=AllotmentItems)
def update_is_allotted_on_save(sender, instance, created, **kwargs):
    """
    Update is_allotted to True when an AllotmentItems is created or updated
    """
    if instance.allotment:
        instance.allotment.is_allotted = True
        instance.allotment.save(update_fields=['is_allotted'])


@receiver(post_delete, sender=AllotmentItems)
def update_is_allotted_on_delete(sender, instance, **kwargs):
    """
    Update is_allotted to False if no more AllotmentItems exist for this allotment
    """
    if instance.allotment:
        # Check if there are any remaining allotment_details
        has_details = instance.allotment.allotment_details.exists()
        instance.allotment.is_allotted = has_details
        instance.allotment.save(update_fields=['is_allotted'])
