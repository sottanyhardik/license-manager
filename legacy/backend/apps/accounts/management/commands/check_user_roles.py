"""
Inspect or modify a user's RBAC role assignments.

Usage:
    python manage.py check_user_roles <username>
    python manage.py check_user_roles <username> --assign-all
    python manage.py check_user_roles <username> --assign-viewers
    python manage.py check_user_roles <username> --assign-managers
    python manage.py check_user_roles --list-roles
"""
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import Group

from apps.accounts.models import User
from apps.accounts.views.user_management import ROLE_CODES


class Command(BaseCommand):
    help = "Inspect or modify a user's RBAC role assignments."

    def add_arguments(self, parser):
        parser.add_argument(
            "username",
            nargs="?",
            help="Username to inspect or modify. Omit when using --list-roles.",
        )
        parser.add_argument(
            "--list-roles",
            action="store_true",
            help="List every active role and exit.",
        )
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            "--assign-all",
            action="store_true",
            help="Assign every active role to the user.",
        )
        group.add_argument(
            "--assign-viewers",
            action="store_true",
            help="Assign every active role whose code contains 'VIEWER'.",
        )
        group.add_argument(
            "--assign-managers",
            action="store_true",
            help="Assign every active role whose code contains 'MANAGER'.",
        )

    def handle(self, *args, **opts):
        if opts["list_roles"]:
            self._list_roles()
            return

        username = opts["username"]
        if not username:
            raise CommandError("username is required (or pass --list-roles).")

        user = self._get_user(username)

        if opts["assign_all"]:
            self._assign(user, Group.objects.filter(name__in=ROLE_CODES), label="all")
        elif opts["assign_viewers"]:
            self._assign(
                user,
                Group.objects.filter(name__in=[code for code in ROLE_CODES if "VIEWER" in code]),
                label="viewer",
            )
        elif opts["assign_managers"]:
            self._assign(
                user,
                Group.objects.filter(name__in=[code for code in ROLE_CODES if "MANAGER" in code]),
                label="manager",
            )

        self._print_user(user)

    def _get_user(self, username):
        try:
            return User.objects.get(username=username)
        except User.DoesNotExist as exc:
            raise CommandError(f"User '{username}' not found.") from exc

    def _assign(self, user, queryset, *, label):
        roles = list(queryset)
        user.groups.set(roles)
        self.stdout.write(
            self.style.SUCCESS(f"Assigned {len(roles)} {label} roles to {user.username}.")
        )

    def _print_user(self, user):
        self.stdout.write("")
        self.stdout.write(f"User:         {user.username}")
        self.stdout.write(f"ID:           {user.id}")
        self.stdout.write(f"Email:        {user.email}")
        self.stdout.write(f"Active:       {user.is_active}")
        self.stdout.write(f"Superuser:    {user.is_superuser}")
        self.stdout.write("Roles:")
        roles = list(user.groups.all())
        if not roles:
            self.stdout.write("  (none)")
        for role in roles:
            self.stdout.write(f"  - {role.name}")
        if hasattr(user, "get_role_codes"):
            self.stdout.write(f"Role codes:   {user.get_role_codes()}")

    def _list_roles(self):
        roles = Group.objects.filter(name__in=ROLE_CODES).order_by("name")
        self.stdout.write("Active roles:")
        for i, role in enumerate(roles, 1):
            self.stdout.write(f"  {i:2d}. {role.name}")
