# Generated manually on 2025-12-18

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('trade', '0007_commissionagent_commission_commissionslab_and_more'),
        ('license', '0013_incentivelicense'),
    ]

    operations = [
        migrations.AddField(
            model_name='licensetrade',
            name='license_type',
            field=models.CharField(
                choices=[('DFIA', 'DFIA License'), ('INCENTIVE', 'Incentive License')],
                default='DFIA',
                db_index=True,
                help_text='Type of license to use for this trade',
                max_length=20
            ),
        ),
        migrations.AddField(
            model_name='licensetrade',
            name='incentive_license',
            field=models.ForeignKey(
                blank=True,
                help_text='Incentive License (RODTEP/ROSTL/MEIS) - used when license_type is INCENTIVE',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='trades',
                to='license.incentivelicense'
            ),
        ),
    ]
