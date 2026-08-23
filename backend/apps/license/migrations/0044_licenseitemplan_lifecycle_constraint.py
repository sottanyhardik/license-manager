from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [("license", "0043_licenseitemplan_lifecycle_state")]

    operations = [
        migrations.AddConstraint(
            model_name="licenseitemplan",
            constraint=models.CheckConstraint(
                condition=~(Q(is_active=True) & (Q(is_deleted=True) | Q(is_cancelled=True))),
                name="license_item_plan_active_not_deleted_or_cancelled",
            ),
        ),
    ]
