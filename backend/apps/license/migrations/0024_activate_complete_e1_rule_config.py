from decimal import Decimal

from django.db import migrations


def _condition(field, operator, value):
    return {"field": field, "operator": operator, "value": value}


def _any(*conditions):
    return {"operator": "OR", "conditions": list(conditions)}


def _all(*conditions):
    return {"operator": "AND", "conditions": list(conditions)}


def _not(condition):
    return {"operator": "NOT", "conditions": [condition]}


def activate_complete_e1_rules(apps, schema_editor):
    """Replace the incomplete live E1 subset with the audited v2 classifier.

    Version-one rows remain untouched for audit history. Stable keys make this
    deterministic, while deactivation occurs before activation so the active
    priority constraint is never transiently violated.
    """
    Sion = apps.get_model("core", "SionNormClassModel")
    Rule = apps.get_model("license", "SionPlanningRule")
    try:
        sion = Sion.objects.get(norm_class__iexact="E1")
    except Sion.DoesNotExist:
        return

    HSN, ITEM, DESCRIPTION = "HSN_DIGITS", "ITEM_KEY", "PRODUCT_DESCRIPTION"
    specs = (
        ("OTHER CONFECTIONERY INGREDIENTS", Decimal("3.00"), _all(
            _not(_any(_condition(ITEM, "CONTAINS", "food flavour"), _condition(DESCRIPTION, "CONTAINS", "food flavour"))),
            _any(_condition(HSN, "STARTS_WITH", "0802"), _condition(ITEM, "CONTAINS", "other confectionery"), _condition(DESCRIPTION, "CONTAINS", "other confectionery")),
        )),
        ("COCOA MASS", Decimal("10.00"), _any(_condition(HSN, "STARTS_WITH", "1803"), _condition(DESCRIPTION, "CONTAINS", "1803"))),
        ("MILK PRODUCTS", Decimal("6.50"), _all(
            _any(_condition(HSN, "STARTS_WITH", "0404"), _condition(DESCRIPTION, "CONTAINS", "0404")),
            _condition(DESCRIPTION, "CONTAINS", "milk"),
            _not(_any(_condition(HSN, "STARTS_WITH", "1803"), _condition(DESCRIPTION, "CONTAINS", "1803"))),
        )),
        ("EGG ALBUMIN", Decimal("25.00"), _all(
            _any(_condition(HSN, "STARTS_WITH", "3502"), _condition(DESCRIPTION, "CONTAINS", "3502")),
            _not(_any(_condition(HSN, "STARTS_WITH", "1803"), _condition(DESCRIPTION, "CONTAINS", "1803"))),
            _not(_any(_condition(HSN, "STARTS_WITH", "0404"), _condition(DESCRIPTION, "CONTAINS", "0404"))),
        )),
        ("FRUIT JUICE", Decimal("2.50"), _any(_condition(HSN, "STARTS_WITH", "2009"), _condition(DESCRIPTION, "CONTAINS", "juice"))),
        ("TARTARIC ACID", Decimal("1.50"), _any(_condition(HSN, "STARTS_WITH", "2918"), _condition(DESCRIPTION, "CONTAINS", "2918"), _condition(ITEM, "CONTAINS", "tartaric"), _condition(DESCRIPTION, "CONTAINS", "tartaric"))),
        ("ALUMINIUM FOIL", Decimal("4.50"), _any(_condition(HSN, "STARTS_WITH", "7607"), _condition(ITEM, "CONTAINS", "7607"), _condition(DESCRIPTION, "CONTAINS", "7607"))),
        ("POLYPROPYLENE", Decimal("1.20"), _condition(HSN, "STARTS_WITH", "3902")),
    )

    Rule.objects.filter(sion=sion, is_active=True).update(is_active=False)
    for priority, (category, price, expression) in enumerate(specs, start=1):
        Rule.objects.update_or_create(
            sion=sion,
            stable_key=f"E1:RULE:{priority:03d}",
            version=2,
            defaults={
                "name": f"{priority:03d} {category}",
                "expression": expression,
                "max_unit_price": price,
                "unit": "KG",
                "priority": priority,
                "is_active": True,
                "execution_output": category,
            },
        )


class Migration(migrations.Migration):
    dependencies = [("license", "0023_sionplanningrule_execution_output")]
    operations = [
        migrations.RunPython(activate_complete_e1_rules, migrations.RunPython.noop),
    ]
