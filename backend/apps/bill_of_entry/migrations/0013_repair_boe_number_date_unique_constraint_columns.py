"""Complete the BOE uniqueness repair for databases exposing ``port_id``."""

from django.db import migrations


OLD_COLUMNS = ("bill_of_entry_number", "bill_of_entry_date", "port_id")
NEW_COLUMNS = ("bill_of_entry_number", "bill_of_entry_date")
OLD_FIELDS = ("bill_of_entry_number", "bill_of_entry_date", "port")
NEW_FIELDS = ("bill_of_entry_number", "bill_of_entry_date")


def _unique_columns(schema_editor, model):
    with schema_editor.connection.cursor() as cursor:
        constraints = schema_editor.connection.introspection.get_constraints(cursor, model._meta.db_table)
    return {tuple(details.get("columns") or ()) for details in constraints.values() if details.get("unique")}


def repair_constraint(apps, schema_editor):
    model = apps.get_model("bill_of_entry", "BillOfEntryModel")
    constraints = _unique_columns(schema_editor, model)
    if OLD_COLUMNS in constraints and NEW_COLUMNS not in constraints:
        schema_editor.alter_unique_together(model, {OLD_FIELDS}, {NEW_FIELDS})


class Migration(migrations.Migration):
    dependencies = [("bill_of_entry", "0012_repair_boe_number_date_unique_constraint")]

    operations = [migrations.RunPython(repair_constraint, migrations.RunPython.noop)]
