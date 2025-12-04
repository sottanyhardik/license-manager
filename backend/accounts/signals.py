# FILE: accounts/signals.py
from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .services import remove_avatar
import os

User = get_user_model()


@receiver(post_delete, sender=User)
def delete_avatar_on_user_delete(sender, instance, **kwargs):
    # remove file from disk when user deleted
    try:
        if instance.avatar:
            instance.avatar.delete(save=False)
    except Exception:
        pass


@receiver(pre_save, sender=User)
def delete_old_avatar_on_change(sender, instance, **kwargs):
    # when avatar is changed, delete old file
    if not instance.pk:
        return
    try:
        old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return
    old_avatar = getattr(old, "avatar", None)
    new_avatar = getattr(instance, "avatar", None)
    if old_avatar and old_avatar != new_avatar:
        try:
            old_avatar.delete(save=False)
        except Exception:
            pass
