"""Append a MasterChange row on every create/update/delete of a master —
this is what makes deletes and targeted refreshes propagate to consumers."""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import TRACKED_MODELS, MasterChange


def _label(instance) -> str:
    return f"{instance._meta.app_label}.{instance.__class__.__name__}"


@receiver(post_save)
def _record_save(sender, instance, created, **kwargs):
    if sender in TRACKED_MODELS:
        MasterChange.objects.create(
            model_label=_label(instance),
            natural_key=instance.natural_key_value,
            op=MasterChange.OP_CREATE if created else MasterChange.OP_UPDATE,
        )


@receiver(post_delete)
def _record_delete(sender, instance, **kwargs):
    if sender in TRACKED_MODELS:
        MasterChange.objects.create(
            model_label=_label(instance),
            natural_key=instance.natural_key_value,
            op=MasterChange.OP_DELETE,
        )
