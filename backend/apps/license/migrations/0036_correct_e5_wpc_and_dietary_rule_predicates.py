from django.db import migrations


WPC_EXPRESSION = {
    "operator": "AND",
    "conditions": [
        {"field": "PRODUCT_DESCRIPTION", "comparator": "CONTAINS", "value": "milk"},
        {"field": "HSN", "comparator": "STARTS_WITH", "value": "3502"},
        {"field": "HSN", "comparator": "NOT_STARTS_WITH", "value": "0404"},
    ],
}

DIETARY_FIBRE_EXPRESSION = {
    "field": "PRODUCT_DESCRIPTION",
    "comparator": "CONTAINS",
    "value": "dietary",
}


def correct_e5_rule_predicates(apps, schema_editor):
    SionPlanningRule = apps.get_model("license", "SionPlanningRule")
    SionPlanningRule.objects.filter(
        sion__norm_class__iexact="E5",
        name__iexact="WPC - E5",
    ).update(expression=WPC_EXPRESSION)
    SionPlanningRule.objects.filter(
        sion__norm_class__iexact="E5",
        name__iexact="DIETARY FIBRE - E5",
    ).update(expression=DIETARY_FIBRE_EXPRESSION)


class Migration(migrations.Migration):

    dependencies = [
        ("license", "0035_allow_zero_unit_value_preferred_price"),
    ]

    operations = [
        migrations.RunPython(correct_e5_rule_predicates, migrations.RunPython.noop),
    ]
