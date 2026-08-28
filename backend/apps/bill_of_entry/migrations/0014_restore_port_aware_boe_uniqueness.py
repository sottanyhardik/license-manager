"""Restore port-aware BOE identity without changing production BOE data."""

from django.db import migrations


OLD_COLUMNS = ("bill_of_entry_number", "bill_of_entry_date", "port_id")
LEGACY_COLUMNS = ("bill_of_entry_number", "bill_of_entry_date")
OLD_FIELDS = ("bill_of_entry_number", "bill_of_entry_date", "port")
LEGACY_FIELDS = ("bill_of_entry_number", "bill_of_entry_date")


def _unique_columns(schema_editor, model):
    with schema_editor.connection.cursor() as cursor:
        constraints = schema_editor.connection.introspection.get_constraints(cursor, model._meta.db_table)
    return {tuple(details.get("columns") or ()) for details in constraints.values() if details.get("unique")}


def restore_port_aware_constraint(apps, schema_editor):
    model = apps.get_model("bill_of_entry", "BillOfEntryModel")
    constraints = _unique_columns(schema_editor, model)
    if LEGACY_COLUMNS in constraints and OLD_COLUMNS not in constraints:
        schema_editor.alter_unique_together(model, {LEGACY_FIELDS}, {OLD_FIELDS})


class Migration(migrations.Migration):
    dependencies = [("bill_of_entry", "0013_repair_boe_number_date_unique_constraint_columns")]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[migrations.RunPython(restore_port_aware_constraint, migrations.RunPython.noop)],
            state_operations=[
                migrations.AlterUniqueTogether(
                    name="billofentrymodel",
                    unique_together={OLD_FIELDS},
                ),
            ],
        ),
    ]
