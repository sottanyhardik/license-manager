# Generated migration for adding is_approved field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('allotment', '0012_add_performance_indexes'),
    ]

    operations = [
        migrations.AddField(
            model_name='allotmentmodel',
            name='is_approved',
            field=models.BooleanField(default=False, help_text='Indicates if the allotment has been approved'),
        ),
    ]
