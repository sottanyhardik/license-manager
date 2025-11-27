# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0016_sionnormclassmodel_is_active'),
    ]

    operations = [
        migrations.AddField(
            model_name='itemnamemodel',
            name='restriction_group',
            field=models.CharField(
                blank=True,
                help_text="Group name for items sharing same restriction (e.g., 'Confectionery', 'Sugar', 'Wheat Flour')",
                max_length=100,
                null=True
            ),
        ),
    ]
