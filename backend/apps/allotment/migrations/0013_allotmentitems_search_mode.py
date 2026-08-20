from django.db import migrations, models


class Migration(migrations.Migration):
    """Add the persisted search mode to databases that already ran 0012.

    ``0012`` was applied before this field was introduced in the working
    model.  Keep this as a separate additive migration so those databases do
    not remain in a recorded-but-incomplete schema state.
    """

    dependencies = [('allotment', '0012_allotmentitems_allocation_basis')]

    operations = [
        migrations.AddField(
            model_name='allotmentitems',
            name='search_mode',
            field=models.CharField(
                choices=[('ACTUAL', 'Actual'), ('PLAN', 'Plan')],
                db_index=True,
                default='ACTUAL',
                max_length=10,
            ),
        ),
    ]
