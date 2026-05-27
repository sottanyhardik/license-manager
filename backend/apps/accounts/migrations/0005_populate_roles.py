# Data migration to populate predefined roles

from django.db import migrations


def populate_roles(apps, schema_editor):
    """Create 12 predefined roles"""
    Role = apps.get_model('accounts', 'Role')

    roles_data = [
        {
            'code': 'LICENSE_MANAGER',
            'name': 'License Manager',
            'description': 'Can manage all license CRUD operations and access ledger upload'
        },
        {
            'code': 'LICENSE_VIEWER',
            'name': 'License Viewer',
            'description': 'Can view all licenses'
        },
        {
            'code': 'ALLOTMENT_VIEWER',
            'name': 'Allotment Viewer',
            'description': 'Can view all allotments'
        },
        {
            'code': 'ALLOTMENT_MANAGER',
            'name': 'Allotment Manager',
            'description': 'Can manage all allotment CRUD operations'
        },
        {
            'code': 'BOE_VIEWER',
            'name': 'Bill of Entry Viewer',
            'description': 'Can view all bill of entries'
        },
        {
            'code': 'BOE_MANAGER',
            'name': 'Bill of Entry Manager',
            'description': 'Can manage all bill of entry CRUD operations'
        },
        {
            'code': 'TRADE_VIEWER',
            'name': 'Trade Viewer',
            'description': 'Can view all trades and license ledger'
        },
        {
            'code': 'TRADE_MANAGER',
            'name': 'Trade Manager',
            'description': 'Can manage all trade CRUD operations and view license ledger'
        },
        {
            'code': 'INCENTIVE_LICENSE_MANAGER',
            'name': 'Incentive License Manager',
            'description': 'Can manage all incentive license CRUD operations'
        },
        {
            'code': 'INCENTIVE_LICENSE_VIEWER',
            'name': 'Incentive License Viewer',
            'description': 'Can view all incentive licenses'
        },
        {
            'code': 'USER_MANAGER',
            'name': 'User Manager',
            'description': 'Can access all user CRUD operations and role assignment'
        },
        {
            'code': 'REPORT_VIEWER',
            'name': 'Report Viewer',
            'description': 'Can view all reports'
        },
    ]

    for role_data in roles_data:
        Role.objects.get_or_create(
            code=role_data['code'],
            defaults={
                'name': role_data['name'],
                'description': role_data['description'],
                'is_active': True
            }
        )


def reverse_populate_roles(apps, schema_editor):
    """Remove predefined roles"""
    Role = apps.get_model('accounts', 'Role')
    Role.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_role_user_roles'),
    ]

    operations = [
        migrations.RunPython(populate_roles, reverse_populate_roles),
    ]
