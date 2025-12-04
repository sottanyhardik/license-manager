# Generated migration for SION Norm Notes and Conditions

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0023_update_item_display_order'),
    ]

    operations = [
        migrations.CreateModel(
            name='SionNormNote',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_on', models.DateTimeField(auto_now_add=True)),
                ('modified_on', models.DateTimeField(auto_now=True)),
                ('note_text', models.TextField()),
                ('display_order', models.IntegerField(default=0)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_created', to=settings.AUTH_USER_MODEL)),
                ('modified_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_updated', to=settings.AUTH_USER_MODEL)),
                ('sion_norm', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notes', to='core.sionnormclassmodel')),
            ],
            options={
                'verbose_name': 'SION Norm Note',
                'verbose_name_plural': 'SION Norm Notes',
                'ordering': ['display_order', 'id'],
            },
        ),
        migrations.CreateModel(
            name='SionNormCondition',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_on', models.DateTimeField(auto_now_add=True)),
                ('modified_on', models.DateTimeField(auto_now=True)),
                ('condition_text', models.TextField()),
                ('display_order', models.IntegerField(default=0)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_created', to=settings.AUTH_USER_MODEL)),
                ('modified_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_updated', to=settings.AUTH_USER_MODEL)),
                ('sion_norm', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='conditions', to='core.sionnormclassmodel')),
            ],
            options={
                'verbose_name': 'SION Norm Condition',
                'verbose_name_plural': 'SION Norm Conditions',
                'ordering': ['display_order', 'id'],
            },
        ),
    ]
