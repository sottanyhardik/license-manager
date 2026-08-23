from django.db import migrations


class Migration(migrations.Migration):
    """Parent allotment mapping is authoritative; child rows carry source data only."""

    dependencies = [("allotment", "0010_merge_20260818_2005")]

    operations = [
        migrations.RemoveField(model_name="allotmentitems", name="planning_mapping_source"),
        migrations.RemoveField(model_name="allotmentitems", name="planning_mapping_status"),
        migrations.RemoveField(model_name="allotmentitems", name="planning_target_item"),
    ]
