# Generated migration for generic SION rule support

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('license', '0027_add_sion_percentage_constraint'),
        ('core', '0001_initial'),  # Ensure core models exist
    ]

    operations = [
        # Add rule_type to SionPlanningRule to distinguish between cap and split rules
        migrations.AddField(
            model_name='sionplanningrule',
            name='rule_type',
            field=models.CharField(
                max_length=50,
                choices=[
                    ('PERCENTAGE_CAP', 'Master percentage cap'),
                    ('SPLIT_PERCENTAGE', 'Split by percentage'),
                    ('QUANTITY_CAP', 'Quantity cap'),
                ],
                default='PERCENTAGE_CAP',
                help_text='Type of rule: master percentage cap or transaction split strategy'
            ),
        ),
        # Add rule_group_id for grouping related rules
        migrations.AddField(
            model_name='sionplanningrule',
            name='rule_group_id',
            field=models.CharField(
                max_length=120,
                null=True,
                blank=True,
                db_index=True,
                help_text='Identifier for grouping related rules (e.g., "E126_50_50_split")'
            ),
        ),
        # Create SionInputAliasConfig model for data-driven canonical input mapping
        migrations.CreateModel(
            name='SionInputAliasConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_on', models.DateTimeField(auto_now_add=True, null=True)),
                ('modified_on', models.DateTimeField(auto_now=True, null=True)),
                ('canonical_input_code', models.CharField(db_index=True, help_text="Canonical code (e.g., 'PKO', 'OLIVE_OIL', 'CHEESE', or custom for extended norms)", max_length=100)),
                ('alias_normalized', models.CharField(db_index=True, help_text='Normalized alias for exact matching (uppercase, normalized whitespace)', max_length=255, unique=True)),
                ('source_description', models.TextField(blank=True, help_text='Source or reason for this mapping (e.g., "From E126 specification")')),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('output_item', models.ForeignKey(blank=True, help_text='If set, this alias applies only to this output item within the SION', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='sion_input_aliases', to='core.itemnamemodel')),
                ('sion', models.ForeignKey(blank=True, help_text='If set, this alias applies only to this SION norm', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='input_aliases', to='core.sionnormclassmodel')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_created', to=settings.AUTH_USER_MODEL)),
                ('modified_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_updated', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('canonical_input_code', 'alias_normalized'),
            },
        ),
        # Add indexes for alias lookup
        migrations.AddIndex(
            model_name='sioninputaliasconfig',
            index=models.Index(fields=('sion', 'output_item', 'canonical_input_code'), name='sion_alias_sion_output_idx'),
        ),
        migrations.AddIndex(
            model_name='sioninputaliasconfig',
            index=models.Index(fields=('sion', 'alias_normalized'), name='sion_alias_norm_idx'),
        ),
        migrations.AddIndex(
            model_name='sioninputaliasconfig',
            index=models.Index(fields=('alias_normalized', 'is_active'), name='sion_alias_active_idx'),
        ),
    ]
