# Data migration to populate SION input aliases for E126 and E132

from django.db import migrations


def populate_aliases(apps, schema_editor):
    """Populate SionInputAliasConfig with E126 and E132 mappings."""
    SionInputAliasConfig = apps.get_model('license', 'SionInputAliasConfig')
    SionNormClassModel = apps.get_model('core', 'SionNormClassModel')
    
    # Get E126 and E132 norms
    e126 = SionNormClassModel.objects.filter(norm_class='E126').first()
    e132 = SionNormClassModel.objects.filter(norm_class='E132').first()
    
    # E126 aliases
    if e126:
        aliases_e126 = [
            {
                'canonical_input_code': 'PKO',
                'alias_normalized': 'PKO',
                'source_description': 'E126 specification: Primary product code',
            },
            {
                'canonical_input_code': 'PKO',
                'alias_normalized': 'PALM KERNEL OIL',
                'source_description': 'E126 specification: Full product name',
            },
            {
                'canonical_input_code': 'OLIVE_OIL',
                'alias_normalized': 'OLIVE OIL',
                'source_description': 'E126 specification: Olive Oil component',
            },
        ]
        for alias_data in aliases_e126:
            SionInputAliasConfig.objects.get_or_create(
                sion=e126,
                alias_normalized=alias_data['alias_normalized'],
                defaults={
                    'canonical_input_code': alias_data['canonical_input_code'],
                    'source_description': alias_data['source_description'],
                    'is_active': True,
                }
            )
    
    # E132 aliases
    if e132:
        aliases_e132 = [
            {
                'canonical_input_code': 'PKO',
                'alias_normalized': 'PKO',
                'source_description': 'E132 specification: Primary product code',
            },
            {
                'canonical_input_code': 'PKO',
                'alias_normalized': 'PALM KERNEL OIL',
                'source_description': 'E132 specification: Full product name',
            },
            {
                'canonical_input_code': 'CHEESE',
                'alias_normalized': 'CHEESE',
                'source_description': 'E132 specification: Cheese component',
            },
        ]
        for alias_data in aliases_e132:
            SionInputAliasConfig.objects.get_or_create(
                sion=e132,
                alias_normalized=alias_data['alias_normalized'],
                defaults={
                    'canonical_input_code': alias_data['canonical_input_code'],
                    'source_description': alias_data['source_description'],
                    'is_active': True,
                }
            )
    
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
