# accounts/models.py
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin, Group, Permission
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Role(models.Model):
    """
    Role model for RBAC system
    """
    ROLE_CODES = [
        ('LICENSE_MANAGER', 'License Manager'),
        ('LICENSE_VIEWER', 'License Viewer'),
        ('ALLOTMENT_VIEWER', 'Allotment Viewer'),
        ('ALLOTMENT_MANAGER', 'Allotment Manager'),
        ('BOE_VIEWER', 'Bill of Entry Viewer'),
        ('BOE_MANAGER', 'Bill of Entry Manager'),
        ('TRADE_VIEWER', 'Trade Viewer'),
        ('TRADE_MANAGER', 'Trade Manager'),
        ('INCENTIVE_LICENSE_MANAGER', 'Incentive License Manager'),
        ('INCENTIVE_LICENSE_VIEWER', 'Incentive License Viewer'),
        ('USER_MANAGER', 'User Manager'),
        ('REPORT_VIEWER', 'Report Viewer'),
    ]

    code = models.CharField(max_length=50, unique=True, choices=ROLE_CODES)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("role")
        verbose_name_plural = _("roles")
        ordering = ['name']

    def __str__(self):
        return self.name


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, username, email, password, **extra_fields):
        """
        Create and save a user with the given username, email and password.
        """
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
    Custom User model. Uses `username` as unique identifier (separate from email).
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

    # Many-to-Many relationship with Role model
    roles = models.ManyToManyField(
        Role,
        verbose_name=_('roles'),
        blank=True,
        related_name='users',
        help_text=_('The roles assigned to this user.')
    )

    # Override group & permission related_names so they don't clash with auth.User if present
    groups = models.ManyToManyField(
        Group,
        verbose_name=_('groups'),
        blank=True,
        help_text=_(
            'The groups this user belongs to. A user will get all permissions '
            'granted to each of their groups.'
        ),
        related_name='accounts_user_set',
        related_query_name='accounts_user',
    )

    user_permissions = models.ManyToManyField(
        Permission,
        verbose_name=_('user permissions'),
        blank=True,
        help_text=_('Specific permissions for this user.'),
        related_name='accounts_user_permissions_set',
        related_query_name='accounts_user_permissions',
    )

    objects = UserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email"]  # createsuperuser will prompt for email

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def get_short_name(self):
        return self.username or self.email

    def has_role(self, role_code):
        """Check if user has a specific role"""
        if self.is_superuser:
            return True
        return self.roles.filter(code=role_code, is_active=True).exists()

    def has_any_role(self, role_codes):
        """Check if user has any of the specified roles"""
        if self.is_superuser:
            return True
        return self.roles.filter(code__in=role_codes, is_active=True).exists()

    def get_role_codes(self):
        """Get list of role codes assigned to the user"""
        if self.is_superuser:
            return [code for code, _ in Role.ROLE_CODES]
        return list(self.roles.filter(is_active=True).values_list('code', flat=True))
