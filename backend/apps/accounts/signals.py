# FILE: accounts/signals.py
import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction
from django.db.models.signals import m2m_changed, post_delete, post_save, pre_save
from django.dispatch import receiver

from . import superuser_roles

User = get_user_model()
logger = logging.getLogger(__name__)


@receiver(post_delete, sender=User)
def delete_avatar_on_user_delete(sender, instance, **kwargs):
    # remove file from disk when user deleted
    try:
        if instance.avatar:
            instance.avatar.delete(save=False)
    except Exception:
        logger.warning("Failed to delete avatar for deleted user id=%s", instance.pk, exc_info=True)


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
            logger.warning("Failed to delete replaced avatar for user id=%s", instance.pk, exc_info=True)


# ── Superusers hold every role (see apps/accounts/superuser_roles.py) ─────────
# Grants run on commit so they land after Admin / API code finishes its own
# ``groups.set()``; the grant itself sends no m2m_changed, so nothing recurses.


@receiver(post_save, sender=User)
def grant_roles_to_new_or_promoted_superuser(sender, instance, raw=False, using="default", **kwargs):
    if raw or not instance.is_superuser:
        return
    user_id = instance.pk
    transaction.on_commit(lambda: superuser_roles.grant_all_roles_to_user(user_id, using), using=using)


@receiver(post_save, sender=Group)
def grant_new_role_to_superusers(sender, instance, created, raw=False, using="default", **kwargs):
    if raw or not created:
        return
    group_id = instance.pk
    transaction.on_commit(lambda: superuser_roles.grant_role_to_superusers(group_id, using), using=using)


@receiver(m2m_changed, sender=User.groups.through)
def keep_superuser_roles_after_removal(sender, instance, action, reverse, using="default", **kwargs):
    if action not in ("post_remove", "post_clear"):
        return
    if reverse:  # group.user_set.remove(...) / .clear()
        group_id = instance.pk
        transaction.on_commit(lambda: superuser_roles.grant_role_to_superusers(group_id, using), using=using)
    elif instance.is_superuser:  # user.groups.remove(...) / .set(...) / .clear()
        user_id = instance.pk
        transaction.on_commit(lambda: superuser_roles.grant_all_roles_to_user(user_id, using), using=using)


def sync_superuser_roles_after_migrate(sender, using="default", **kwargs):
    """Existing superusers + roles created by data migrations (no model signals there)."""
    superuser_roles.sync_all_superusers(using)
