# Generated migration for backfilling strategy field

from django.db import migrations
from decimal import Decimal

def backfill_strategy(apps, schema_editor):
    """Backfill strategy field for existing rules and create percentage rows for legacy rules."""
    SionPlanningRule = apps.get_model('license', 'SionPlanningRule')
    SionPlanningPercentageRow = apps.get_model('license', 'SionPlanningPercentageRow')
    ItemNameModel = apps.get_model('core', 'ItemNameModel')

    # Rules with percentage_constraint and rule_type=SPLIT_BY_PERCENTAGE become SPLIT_BY_PERCENT
    for rule in SionPlanningRule.objects.filter(rule_type='SPLIT_BY_PERCENTAGE', percentage_constraint__isnull=False):
        if not rule.strategy:
            rule.strategy = 'SPLIT_BY_PERCENT'
            rule.save(update_fields=['strategy'])

            # Create a single percentage row from the legacy percentage_constraint
            if rule.import_item:
                SionPlanningPercentageRow.objects.create(
                    rule=rule,
                    import_item=rule.import_item,
                    percentage=rule.percentage_constraint,
                    unit_price=rule.max_unit_price,
                    priority=0,
                )

    # All other rules default to STANDARD
    for rule in SionPlanningRule.objects.filter(strategy__isnull=True):
        rule.strategy = 'STANDARD'
        rule.save(update_fields=['strategy'])

def reverse_backfill(apps, schema_editor):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('license', '0032_rename_output_item_to_import_item'),
    ]

    operations = [
        migrations.RunPython(backfill_strategy, reverse_backfill),
    ]
