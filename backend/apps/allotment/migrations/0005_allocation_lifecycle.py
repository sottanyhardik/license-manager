# Generated migration for Phase A.1 — Allocation Lifecycle

from django.db import migrations, models
import django.db.models.deletion
from decimal import Decimal
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('allotment', '0004_alter_allotmentmodel_company_and_more'),
    ]

    operations = [
        # Add lifecycle status field
        migrations.AddField(
            model_name='allotmentitems',
            name='status',
            field=models.CharField(
                choices=[
                    ('CREATED', 'Created'),
                    ('RELEASED', 'Released'),
                    ('REACTIVATED', 'Reactivated'),
                    ('COMPLETED', 'Completed'),
                ],
                db_index=True,
                default='CREATED',
                max_length=20,
            ),
        ),

        # Add release tracking fields
        migrations.AddField(
            model_name='allotmentitems',
            name='released_quantity',
            field=models.DecimalField(
                blank=True,
                decimal_places=3,
                default=Decimal('0.000'),
                max_digits=15,
                null=True,
                validators=[django.core.validators.MinValueValidator(Decimal('0.000'))],
            ),
        ),

        migrations.AddField(
            model_name='allotmentitems',
            name='released_date',
            field=models.DateTimeField(blank=True, null=True),
        ),

        migrations.AddField(
            model_name='allotmentitems',
            name='release_reason',
            field=models.CharField(blank=True, max_length=500, null=True),
        ),

        # Add reactivation tracking fields
        migrations.AddField(
            model_name='allotmentitems',
            name='reactivated_quantity',
            field=models.DecimalField(
                blank=True,
                decimal_places=3,
                default=Decimal('0.000'),
                max_digits=15,
                null=True,
                validators=[django.core.validators.MinValueValidator(Decimal('0.000'))],
            ),
        ),

        migrations.AddField(
            model_name='allotmentitems',
            name='reactivated_date',
            field=models.DateTimeField(blank=True, null=True),
        ),

        migrations.AddField(
            model_name='allotmentitems',
            name='reactivated_from_company',
            field=models.CharField(
                blank=True,
                help_text='Audit label of previous company (if changed during reactivation)',
                max_length=255,
                null=True,
            ),
        ),

        # Add version history field
        migrations.AddField(
            model_name='allotmentitems',
            name='previous_version',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='next_version',
                to='allotment.allotmentitems',
            ),
        ),

        # Add indexes for performance
        migrations.AddIndex(
            model_name='allotmentitems',
            index=models.Index(fields=['status'], name='allotment_a_status_idx'),
        ),

        migrations.AddIndex(
            model_name='allotmentitems',
            index=models.Index(fields=['allotment', 'status'], name='allotment_a_allot_status_idx'),
        ),
    ]
