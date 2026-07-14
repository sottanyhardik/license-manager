# accounts/models.py
"""
Proxy model over the legacy `accounts_user` table.

managed=False means Django will NOT create, alter, or drop this table —
it already exists and is owned by the legacy backend. Field definitions
must exactly match the legacy schema (legacy/backend/apps/accounts/models.py).
"""
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin, Group, Permission
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.validators import FileExtensionValidator


class UserManager(BaseUserManager):
    use_in_migrations = False  # False: we own no migrations for this table

    def _create_user(self, username, email, password, **extra_fields):
        if not username:
            raise ValueError("The username must be set")
        email = self.normalize_email(email) if email else None
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(username, email, password, **extra_fields)

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(username, email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Proxy over the legacy accounts_user table.

    managed=False: Django will NOT create/alter this table.
    Field names must exactly match the legacy schema.
    Role membership is via Django's built-in Group model (group name = role code).
    """

    username = models.CharField(_("username"), max_length=150, unique=True)
    email = models.EmailField(_("email address"), unique=True, max_length=255, null=True, blank=True)

    first_name = models.CharField(_("first name"), max_length=30, blank=True)
    last_name = models.CharField(_("last name"), max_length=150, blank=True)

    is_staff = models.BooleanField(
        _("staff status"),
        default=False,
        help_text=_("Designates whether the user can log into this admin site."),
    )
    is_active = models.BooleanField(
        _("active"),
        default=True,
        help_text=_("Designates whether this user should be treated as active."),
    )
    date_joined = models.DateTimeField(_("date joined"), default=timezone.now)

    # Override M2M related_names to avoid clashes if auth.User is also present.
    groups = models.ManyToManyField(
        Group,
        verbose_name=_("groups"),
        blank=True,
        help_text=_(
            "The groups this user belongs to. A user will get all permissions "
            "granted to each of their groups."
        ),
        related_name="accounts_user_set",
        related_query_name="accounts_user",
    )

    user_permissions = models.ManyToManyField(
        Permission,
        verbose_name=_("user permissions"),
        blank=True,
        help_text=_("Specific permissions for this user."),
        related_name="accounts_user_permissions_set",
        related_query_name="accounts_user_permissions",
    )

    avatar = models.ImageField(
        upload_to="avatars/",
        null=True,
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=["png", "jpg", "jpeg"])],
    )

    objects = UserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email"]  # createsuperuser prompts for email

    class Meta:
        managed = False  # DO NOT touch the accounts_user table
        db_table = "accounts_user"
        app_label = "accounts"
        verbose_name = _("user")
        verbose_name_plural = _("users")

    def get_full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def get_short_name(self) -> str:
        return self.username or self.email

    # ── Role helpers (backed by Django's built-in Group model) ────────────────

    def has_role(self, role_code: str) -> bool:
        """Return True if this user belongs to the group named *role_code*."""
        return self.groups.filter(name=role_code).exists()

    def has_any_role(self, role_codes) -> bool:
        """Return True if this user belongs to at least one of the named groups."""
        return self.groups.filter(name__in=role_codes).exists()

    def get_role_codes(self) -> list:
        """Return a list of group names (role codes) this user belongs to."""
        return list(self.groups.values_list("name", flat=True))

    def is_admin(self) -> bool:
        """Return True if the user is a superuser."""
        return self.is_superuser
