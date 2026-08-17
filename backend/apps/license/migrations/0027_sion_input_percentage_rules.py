# Generated migration for SION input classification and percentage rules

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.core.validators
from decimal import Decimal


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('license', '0026_sionplanningrule_output_item'),
    ]

    operations = [
        # Create SionCanonicalInput model
        migrations.CreateModel(
            name='SionCanonicalInput',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_on', models.DateTimeField(auto_now_add=True)),
                ('modified_on', models.DateTimeField(auto_now=True)),
                ('code', models.CharField(help_text='Canonical code (e.g., PKO, OLIVE_OIL, CHEESE)', max_length=50, unique=True)),
                ('display_name', models.CharField(help_text='Human-readable name (e.g., Palm Kernel Oil)', max_length=255)),
                ('is_active', models.BooleanField(db_index=True, default=True, help_text='Inactive inputs are not matched against product names')),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('modified_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('code',),
            },
        ),

        # Create SionInputAlias model
        migrations.CreateModel(
            name='SionInputAlias',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_on', models.DateTimeField(auto_now_add=True)),
                ('modified_on', models.DateTimeField(auto_now=True)),
                ('alias', models.CharField(help_text="Raw product name variant (e.g., 'PALM KERNEL OIL', 'PKO', 'palm kernel oil')", max_length=255)),
                ('normalized_alias', models.CharField(db_index=True, help_text='Normalized form for case-insensitive matching (UPPERCASE, single spaces)', max_length=255)),
                ('canonical_input', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='aliases', to='license.sioncanonicalinput')),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('modified_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('canonical_input', 'alias'),
            },
        ),

        # Add unique constraint to SionInputAlias
        migrations.AddConstraint(
            model_name='sioninputalias',
            constraint=models.UniqueConstraint(fields=['normalized_alias'], name='uniq_normalized_alias'),
        ),

        # Add index to SionInputAlias
        migrations.AddIndex(
            model_name='sioninputalias',
            index=models.Index(fields=['normalized_alias'], name='license_sio_normalized_alias_idx'),
        ),

        # Add index to SionCanonicalInput
        migrations.AddIndex(
            model_name='sioncanonicalinput',
            index=models.Index(fields=['is_active', 'code'], name='license_sio_is_active_code_idx'),
        ),

        # Add percentage_constraint field to SionPlanningRule
        migrations.AddField(
            model_name='sionplanningrule',
            name='percentage_constraint',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Maximum percentage of total eligible license quantity that can be allocated to this rule's output item (e.g., 50.00 for 50%). Null means no constraint.",
                max_digits=5,
                null=True,
                validators=[django.core.validators.MinValueValidator(Decimal('0'))],
            ),
        ),

        # Add check constraint for percentage_constraint
        migrations.AddConstraint(
            model_name='sionplanningrule',
            constraint=models.CheckConstraint(
                condition=models.Q(('percentage_constraint__isnull', True)) | models.Q(('percentage_constraint__lte', Decimal('100'))),
                name='sion_rule_percentage_constraint_lte_100',
            ),
        ),
    ]
