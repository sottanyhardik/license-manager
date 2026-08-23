# Data migration to set rule_type and rule_group_id for existing percentage rules

from django.db import migrations


def populate_rule_types(apps, schema_editor):
    """Populate rule_type and rule_group_id for existing percentage-constraint rules."""
    SionPlanningRule = apps.get_model('license', 'SionPlanningRule')
    SionNormClassModel = apps.get_model('core', 'SionNormClassModel')
    
    # Get E126 and E132 norms
    e126 = SionNormClassModel.objects.filter(norm_class='E126').first()
    e132 = SionNormClassModel.objects.filter(norm_class='E132').first()
    
    # Mark all existing percentage_constraint rules as PERCENTAGE_CAP
    rules_with_percentage = SionPlanningRule.objects.exclude(
        percentage_constraint__isnull=True
    )
    
    for rule in rules_with_percentage:
        if rule.rule_type in ['', None]:  # Not yet set or default value
            rule.rule_type = 'PERCENTAGE_CAP'
        
        # Set rule group ID for E126 and E132 rules with output items
        if rule.sion == e126 and rule.output_item:
            rule.rule_group_id = f"E126_{rule.output_item.id}_percentage_cap"
        elif rule.sion == e132 and rule.output_item:
            rule.rule_group_id = f"E132_{rule.output_item.id}_percentage_cap"
        
        rule.save(update_fields=['rule_type', 'rule_group_id'])


def reverse_rule_types(apps, schema_editor):
    """Reverse: clear rule_type and rule_group_id."""
    SionPlanningRule = apps.get_model('license', 'SionPlanningRule')
    SionPlanningRule.objects.all().update(rule_type='PERCENTAGE_CAP', rule_group_id=None)


class Migration(migrations.Migration):

    dependencies = [
        ('license', '0029_populate_sion_input_aliases'),
    ]

    operations = [
        migrations.RunPython(populate_rule_types, reverse_rule_types),
    ]
