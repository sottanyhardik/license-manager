"""
Drop CompanyModel.address (redundant with address_line_1 + address_line_2).

Data preservation:
  Before removing the column, copy any non-empty `address` value into
  `address_line_1` for rows where `address_line_1` is empty. This avoids
  losing data on production servers where the bulk of company addresses
  were historically stored in `address` rather than `address_line_1/2`.

After this migration, the canonical address fields are `address_line_1`
and `address_line_2`; `CompanyModel.full_address` joins them.
"""
from django.db import migrations


def backfill_address_line_1(apps, schema_editor):
    Company = apps.get_model("core", "CompanyModel")
    # Only rows where address has content AND address_line_1 is empty
    # (don't clobber address_line_1 if it's already populated).
    qs = Company.objects.exclude(address__isnull=True).exclude(address="")
    updated = 0
    for c in qs.iterator():
        if not (c.address_line_1 or "").strip():
            c.address_line_1 = c.address
            c.save(update_fields=["address_line_1"])
            updated += 1
    if updated:
        print(f"  Backfilled address_line_1 from address on {updated} CompanyModel row(s).")


def noop_reverse(apps, schema_editor):
    # No reverse — once the column is dropped, the original data is in address_line_1.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(backfill_address_line_1, noop_reverse),
        migrations.RemoveField(
            model_name="companymodel",
            name="address",
        ),
    ]
