from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_user_company"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="user",
            name="company",
        ),
    ]
