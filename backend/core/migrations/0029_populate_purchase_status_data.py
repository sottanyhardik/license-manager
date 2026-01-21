# Generated manually for version 4.4

from django.db import migrations


def populate_purchase_status(apps, schema_editor):
    """Populate PurchaseStatus with data from LICENCE_PURCHASE_CHOICES_FULL"""
    PurchaseStatus = apps.get_model('core', 'PurchaseStatus')

    # Data from core.constants.LICENCE_PURCHASE_CHOICES_FULL
    purchase_statuses = [
        ('GE', 'GE Purchase', True, 1),
        ('MI', 'GE Operating', True, 2),
        ('IP', 'GE Item Purchase', True, 3),
        ('SM', 'SM Purchase', True, 4),
        ('GO', 'GO Purchase', True, 5),
        ('OT', 'OT Purchase', True, 6),
        ('CO', 'Conversion', True, 7),
        ('RA', 'Ravi Foods', True, 8),
        ('LM', 'LM Purchase', False, 9),
    ]

    for code, label, is_active, display_order in purchase_statuses:
        PurchaseStatus.objects.update_or_create(
            code=code,
            defaults={
                'label': label,
                'is_active': is_active,
                'display_order': display_order
            }
        )


def reverse_populate(apps, schema_editor):
    """Reverse migration - keep the records but reset is_active and display_order"""
    PurchaseStatus = apps.get_model('core', 'PurchaseStatus')
    PurchaseStatus.objects.all().update(is_active=True, display_order=0)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0028_add_fields_to_purchase_status'),
    ]

    operations = [
        migrations.RunPython(populate_purchase_status, reverse_populate),
    ]
