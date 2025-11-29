# Generated migration to activate specific SION norm classes

from django.db import migrations


def activate_sion_norms(apps, schema_editor):
    """Activate specific SION norm classes"""
    SionNormClassModel = apps.get_model('core', 'SionNormClassModel')

    # List of norm classes to activate
    norms_to_activate = [
        'E1', 'E5', 'E126', 'E132',
        'C473', 'C460', 'C471',
        'A3627', 'C969', 'COMMON'
    ]

    # Update is_active to True for these norms
    updated_count = SionNormClassModel.objects.filter(
        norm_class__in=norms_to_activate
    ).update(is_active=True)

    print(f"Activated {updated_count} SION norm classes: {', '.join(norms_to_activate)}")


def reverse_activate_sion_norms(apps, schema_editor):
    """Reverse operation - deactivate the norms"""
    SionNormClassModel = apps.get_model('core', 'SionNormClassModel')

    norms_to_deactivate = [
        'E1', 'E5', 'E126', 'E132',
        'C473', 'C460', 'C471',
        'A3627', 'C969', 'COMMON'
    ]

    SionNormClassModel.objects.filter(
        norm_class__in=norms_to_deactivate
    ).update(is_active=False)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0021_alter_itemnamemodel_options_and_more'),
    ]

    operations = [
        migrations.RunPython(activate_sion_norms, reverse_activate_sion_norms),
    ]
