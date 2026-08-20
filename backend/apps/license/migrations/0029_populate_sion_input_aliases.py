# Data migration to populate SION input aliases for E126 and E132

from django.db import migrations


def populate_aliases(apps, schema_editor):
    """Populate globally reusable SION input aliases.

    ``alias_normalized`` is globally unique in the schema created by migration
    0028.  These aliases are shared by E126 and E132, so seed them once as
    global aliases; the resolver falls back to global aliases when no
    SION-specific mapping exists.
    """
    SionInputAliasConfig = apps.get_model('license', 'SionInputAliasConfig')
    # Global aliases (available for all norms)
    global_aliases = [
        {
            'canonical_input_code': 'PKO',
            'alias_normalized': 'PKO',
            'source_description': 'Global PKO alias',
        },
        {
            'canonical_input_code': 'PKO',
            'alias_normalized': 'PALM KERNEL OIL',
            'source_description': 'Global Palm Kernel Oil alias',
        },
        {
            'canonical_input_code': 'OLIVE_OIL',
            'alias_normalized': 'OLIVE OIL',
            'source_description': 'Global Olive Oil alias',
        },
        {
            'canonical_input_code': 'CHEESE',
            'alias_normalized': 'CHEESE',
            'source_description': 'Global Cheese alias',
        },
    ]
    for alias_data in global_aliases:
        SionInputAliasConfig.objects.get_or_create(
            sion=None,  # Global
            output_item=None,
            alias_normalized=alias_data['alias_normalized'],
            defaults={
                'canonical_input_code': alias_data['canonical_input_code'],
                'source_description': alias_data['source_description'],
                'is_active': True,
            }
        )


def reverse_aliases(apps, schema_editor):
    """Remove populated aliases."""
    SionInputAliasConfig = apps.get_model('license', 'SionInputAliasConfig')
    SionInputAliasConfig.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('license', '0028_sion_generic_rules'),
    ]

    operations = [
        migrations.RunPython(populate_aliases, reverse_aliases),
    ]
