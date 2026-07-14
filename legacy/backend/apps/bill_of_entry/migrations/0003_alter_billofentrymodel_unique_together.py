from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bill_of_entry', '0002_initial'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='billofentrymodel',
            unique_together={('bill_of_entry_number', 'bill_of_entry_date')},
        ),
    ]
