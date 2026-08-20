from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    """Record the balance authority used by each allocation.

    Existing rows have no persisted, unambiguous plan-line reference, so they
    are conservatively backfilled as ACTUAL rather than guessing from amounts.
    """

    dependencies = [('allotment', '0011_remove_allotmentitems_planning_mapping_fields')]

    operations = [
        migrations.AddField(
            model_name='allotmentitems', name='allocation_basis',
            field=models.CharField(choices=[('ACTUAL', 'Actual'), ('PLAN', 'Plan')], db_index=True, default='ACTUAL', max_length=10),
        ),
        migrations.AddField(
            model_name='allotmentitems', name='planning_target_item',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='allotment_allocations_following_plan', to='core.itemnamemodel'),
        ),
        migrations.AddField(
            model_name='allotmentitems', name='plan_line',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='allotment_allocations', to='license.licenseitemplan'),
        ),
    ]
