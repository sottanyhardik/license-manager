"""Repair databases whose 0003 state was recorded without changing its constraint."""

from django.db import migrations


OLD_FIELDS = ("bill_of_entry_number", "bill_of_entry_date", "port")
NEW_FIELDS = ("bill_of_entry_number", "bill_of_entry_date")


def _constraint_columns(schema_editor, model):
    with schema_editor.connection.cursor() as cursor:
        constraints = schema_editor.connection.introspection.get_constraints(cursor, model._meta.db_table)
    return {tuple(details.get("columns") or ()) for details in constraints.values() if details.get("unique")}


def repair_constraint(apps, schema_editor):
    """Make the physical schema match migration 0003 without touching data."""
    model = apps.get_model("bill_of_entry", "BillOfEntryModel")
    constraints = _constraint_columns(schema_editor, model)
    if OLD_FIELDS in constraints and NEW_FIELDS not in constraints:
        # This fails safely if a database contains conflicting historical BOEs;
        # no BOE, ledger, allocation, or audit record is deleted or changed.
        schema_editor.alter_unique_together(model, {OLD_FIELDS}, {NEW_FIELDS})


def reverse_repair_constraint(apps, schema_editor):
    model = apps.get_model("bill_of_entry", "BillOfEntryModel")
    constraints = _constraint_columns(schema_editor, model)
    if NEW_FIELDS in constraints and OLD_FIELDS not in constraints:
        schema_editor.alter_unique_together(model, {NEW_FIELDS}, {OLD_FIELDS})


class Migration(migrations.Migration):
    dependencies = [("bill_of_entry", "0011_merge_20260818_2005")]

    operations = [migrations.RunPython(repair_constraint, reverse_repair_constraint)]
