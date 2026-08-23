"""
Migration: add standalone DB indexes to AllotmentItems.item and .allotment.

The unique_together = ("item", "allotment") already creates a compound index on
(item_id, allotment_id) — usable when filtering by item_id alone (leftmost column).
Adding a standalone index on allotment_id enables the JOIN in the batch query:

    AllotmentItems.objects.filter(
        item__license_id__in=[...],
        allotment__is_allotted=True,
        allotment__bill_of_entry__isnull=True,
    )

to use an index scan on allotment_id for the JOIN rather than a full table scan.
Both indexes are CONCURRENTLY-safe in Postgres (adding index never locks writes).
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("allotment", "0002_initial"),
    ]

    operations = [
        # item_id standalone index (redundant with unique_together leading column
        # but explicit — keeps the intent clear and aids query planner on NULLable FK).
        migrations.AlterField(
            model_name="allotmentitems",
            name="item",
            field=models.ForeignKey(
                blank=True,
                db_index=True,
                null=True,
                on_delete=models.deletion.CASCADE,
                related_name="allotment_details",
                to="license.licenseimportitemsmodel",
            ),
        ),
        # allotment_id standalone index for the JOIN filter.
        migrations.AlterField(
            model_name="allotmentitems",
            name="allotment",
            field=models.ForeignKey(
                blank=True,
                db_index=True,
                null=True,
                on_delete=models.deletion.CASCADE,
                related_name="allotment_details",
                to="allotment.allotmentmodel",
            ),
        ),
    ]
