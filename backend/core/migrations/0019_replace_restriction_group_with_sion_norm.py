# Generated manually

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0018_add_restriction_percentage_to_item_name'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='itemnamemodel',
            name='restriction_group',
        ),
        migrations.AddField(
            model_name='itemnamemodel',
            name='sion_norm_class',
            field=models.ForeignKey(
                blank=True,
                help_text='SION norm class for restriction grouping (e.g., E1, E2)',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='items',
                to='core.sionnormclassmodel'
            ),
        ),
    ]
