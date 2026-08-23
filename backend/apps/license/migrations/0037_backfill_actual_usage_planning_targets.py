"""Safely initialise historical actual-usage mapping state.

There is deliberately no name/alias based backfill here.  A product label is
not evidence that an historical debit belongs to one of a rule's split
targets.  Existing explicit mappings are preserved; all other records remain
unresolved until the configuration-aware mapping workflow can prove a unique
target (or a user selects one).
"""

from django.db import migrations


def forward(apps, schema_editor):
    # Intentional no-op.  A data migration must be deterministic from its
    # historical state; evaluating today's mutable rules would not be safe.
    # The runtime/management mapping service performs additive deterministic
    # resolution against the current rule context instead.
    return


def reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):
    dependencies = [
        ("license", "0036_correct_e5_wpc_and_dietary_rule_predicates"),
        ("bill_of_entry", "0007_rowdetails_planning_target_mapping"),
        ("allotment", "0007_allotmentitems_planning_target_mapping"),
    ]
    operations = [migrations.RunPython(forward, reverse)]
