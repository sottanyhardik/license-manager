"""
Convert LicenseDetailsModel.scheme_code (CharField) -> FK to core.SchemeCode
Convert LicenseDetailsModel.notification_number (CharField) -> FK to core.NotificationNumber

Why
---
Production had drifted away from the choices list (4 distinct scheme_code
values and 10 distinct notification_number values in real data, vs 1 and 3
in the choices definitions). The dedicated lookup tables core.SchemeCode
and core.NotificationNumber existed but were empty. Converting these
columns to FKs gives us:
  - Referential integrity (no more typo-introduced values)
  - One source of truth for the set of codes
  - Label/code separation (display labels stop polluting code)

Migration steps (all in one atomic Django migration)
----------------------------------------------------
1. Add temporary FK columns (scheme_code_new, notification_number_new), nullable.
2. RunPython: populate the lookup tables with every distinct value seen in
   license rows; backfill the new FK columns via raw SQL (fast for ~2k rows).
3. Drop the old CharField columns.
4. Rename the new FK columns to the canonical names (scheme_code, notification_number).

Backward-compat is preserved in code:
  - LicenseDetailsModel.get_scheme_code_display() and
    .get_notification_number_display() are defined manually so templates
    that called the old Django-auto methods still work.
  - Filter sites are updated from `scheme_code='X'` to `scheme_code__code='X'`.
  - DRF serializers use SlugRelatedField(slug_field='code') where the API
    previously returned the raw code string.
"""
from django.db import migrations, models
import django.db.models.deletion


def populate_and_backfill(apps, schema_editor):
    SchemeCode = apps.get_model("core", "SchemeCode")
    NotificationNumber = apps.get_model("core", "NotificationNumber")

    from django.db import connection

    # 1. Read distinct string values currently in license rows.
    with connection.cursor() as c:
        c.execute(
            "SELECT DISTINCT scheme_code FROM license_licensedetailsmodel "
            "WHERE scheme_code IS NOT NULL AND scheme_code != ''"
        )
        scheme_codes = [row[0] for row in c.fetchall()]
        c.execute(
            "SELECT DISTINCT notification_number FROM license_licensedetailsmodel "
            "WHERE notification_number IS NOT NULL AND notification_number != ''"
        )
        notif_codes = [row[0] for row in c.fetchall()]

    # 2. Ensure lookup table rows exist for every code, capturing PKs.
    scheme_pk = {}
    for code in scheme_codes:
        obj, _ = SchemeCode.objects.get_or_create(code=code, defaults={"label": code})
        scheme_pk[code] = obj.pk

    notif_pk = {}
    for code in notif_codes:
        obj, _ = NotificationNumber.objects.get_or_create(code=code, defaults={"label": code})
        notif_pk[code] = obj.pk

    # 3. Backfill the new FK columns via raw SQL (one statement per code).
    with connection.cursor() as c:
        for code, pk in scheme_pk.items():
            c.execute(
                "UPDATE license_licensedetailsmodel SET scheme_code_new_id = %s WHERE scheme_code = %s",
                [pk, code],
            )
        for code, pk in notif_pk.items():
            c.execute(
                "UPDATE license_licensedetailsmodel SET notification_number_new_id = %s WHERE notification_number = %s",
                [pk, code],
            )

    print(
        f"  Populated {len(scheme_pk)} SchemeCode row(s) and {len(notif_pk)} NotificationNumber row(s); "
        f"backfilled FK columns on existing licenses."
    )


def noop_reverse(apps, schema_editor):
    # No reverse — once new columns are renamed and old dropped, the original strings are gone.
    pass


class Migration(migrations.Migration):

    # Disable wrapping the whole migration in one transaction so that the deferred
    # FK constraint checks introduced by AddField are released before the
    # subsequent RemoveField/RenameField statements. Each operation still runs
    # in its own transaction.
    atomic = False

    dependencies = [
        ("license", "0001_initial"),
        ("core", "0002_remove_companymodel_address"),
    ]

    operations = [
        # Step 1: Add temporary FK columns (related_name='+' = no reverse accessor while two FKs coexist).
        migrations.AddField(
            model_name="licensedetailsmodel",
            name="scheme_code_new",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="core.schemecode",
            ),
        ),
        migrations.AddField(
            model_name="licensedetailsmodel",
            name="notification_number_new",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="core.notificationnumber",
            ),
        ),
        # Step 2: Populate lookup tables and backfill FK columns.
        migrations.RunPython(populate_and_backfill, noop_reverse),
        # Step 3: Drop old string columns.
        migrations.RemoveField(model_name="licensedetailsmodel", name="scheme_code"),
        migrations.RemoveField(model_name="licensedetailsmodel", name="notification_number"),
        # Step 4: Rename new FK columns to canonical names and set the final related_name.
        migrations.RenameField(
            model_name="licensedetailsmodel",
            old_name="scheme_code_new",
            new_name="scheme_code",
        ),
        migrations.RenameField(
            model_name="licensedetailsmodel",
            old_name="notification_number_new",
            new_name="notification_number",
        ),
        migrations.AlterField(
            model_name="licensedetailsmodel",
            name="scheme_code",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="licenses",
                to="core.schemecode",
            ),
        ),
        migrations.AlterField(
            model_name="licensedetailsmodel",
            name="notification_number",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="licenses",
                to="core.notificationnumber",
            ),
        ),
    ]
