from django.db import migrations, models


class Migration(migrations.Migration):
    """Make the allocation ledger identity match PLAN split semantics."""

    dependencies = [
        ("allotment", "0013_allotmentitems_search_mode"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="allotmentitems",
            unique_together=set(),
        ),
        migrations.AddConstraint(
            model_name="allotmentitems",
            constraint=models.UniqueConstraint(
                fields=("item", "allotment", "plan_line"),
                name="allotment_unique_item_plan_line",
            ),
        ),
        migrations.AddConstraint(
            model_name="allotmentitems",
            constraint=models.UniqueConstraint(
                condition=models.Q(plan_line__isnull=True),
                fields=("item", "allotment"),
                name="allotment_unique_item_without_plan_line",
            ),
        ),
    ]
