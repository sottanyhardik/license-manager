# accounts/management/commands/assign_roles.py
from django.core.management.base import BaseCommand
from accounts.models import User, Role


class Command(BaseCommand):
    help = 'Assign roles to a user'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='Username')
        parser.add_argument(
            '--all',
            action='store_true',
            help='Assign all roles'
        )
        parser.add_argument(
            '--viewers',
            action='store_true',
            help='Assign all viewer roles'
        )
        parser.add_argument(
            '--managers',
            action='store_true',
            help='Assign all manager roles'
        )
        parser.add_argument(
            '--roles',
            nargs='+',
            help='Specific role codes to assign (e.g., LICENSE_MANAGER TRADE_VIEWER)'
        )

    def handle(self, *args, **options):
        username = options['username']

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'User "{username}" not found!'))
            return

        # Show current roles
        self.stdout.write(f'\n{"="*60}')
        self.stdout.write(f'User: {username}')
        self.stdout.write(f'{"="*60}')
        self.stdout.write(f'Is Superuser: {user.is_superuser}')

        current_roles = user.roles.all()
        if current_roles:
            self.stdout.write('\nCurrent Roles:')
            for role in current_roles:
                self.stdout.write(f'  - {role.name} ({role.code})')
        else:
            self.stdout.write(self.style.WARNING('\nNo roles assigned!'))

        # Assign roles based on options
        if options['all']:
            all_roles = Role.objects.filter(is_active=True)
            user.roles.set(all_roles)
            self.stdout.write(self.style.SUCCESS(f'\n✅ Assigned all {all_roles.count()} roles'))

        elif options['viewers']:
            viewer_roles = Role.objects.filter(code__icontains='VIEWER', is_active=True)
            user.roles.set(viewer_roles)
            self.stdout.write(self.style.SUCCESS(f'\n✅ Assigned {viewer_roles.count()} viewer roles'))

        elif options['managers']:
            manager_roles = Role.objects.filter(code__icontains='MANAGER', is_active=True)
            user.roles.set(manager_roles)
            self.stdout.write(self.style.SUCCESS(f'\n✅ Assigned {manager_roles.count()} manager roles'))

        elif options['roles']:
            role_codes = options['roles']
            roles = Role.objects.filter(code__in=role_codes, is_active=True)

            if roles.count() != len(role_codes):
                found_codes = set(roles.values_list('code', flat=True))
                missing = set(role_codes) - found_codes
                self.stdout.write(self.style.WARNING(f'\nWarning: Some roles not found: {missing}'))

            user.roles.set(roles)
            self.stdout.write(self.style.SUCCESS(f'\n✅ Assigned {roles.count()} specific roles'))

        # Show updated roles
        updated_roles = user.roles.all()
        if updated_roles:
            self.stdout.write('\nUpdated Roles:')
            for role in updated_roles:
                self.stdout.write(self.style.SUCCESS(f'  ✓ {role.name} ({role.code})'))

        self.stdout.write(f'\n{"="*60}')
        self.stdout.write(self.style.WARNING('\n⚠️  User must log out and log in again for changes to take effect!\n'))
