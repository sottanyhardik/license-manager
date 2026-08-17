# Data migration to seed initial SION canonical inputs and aliases for E126/E132

from django.db import migrations


def seed_aliases(apps, schema_editor):
    """Seed E126/E132 canonical inputs and verified aliases only.

    E126: PKO 50%, OLIVE_OIL 50%
    E132: PKO 60%, CHEESE 40%
    """
    SionCanonicalInput = apps.get_model('license', 'SionCanonicalInput')
    SionInputAlias = apps.get_model('license', 'SionInputAlias')

    # Only create canonical inputs actually used in E126/E132
    inputs_data = [
        ("PKO", "Palm Kernel Oil"),
        ("OLIVE_OIL", "Olive Oil"),
        ("CHEESE", "Cheese Cream Butter and Fats"),
    ]

    inputs_map = {}
    for code, display_name in inputs_data:
        obj = SionCanonicalInput.objects.create(
            code=code,
            display_name=display_name,
            is_active=True
        )
        inputs_map[code] = obj

    # Create VERIFIED aliases only (no speculative entries)
    # These are exact product name variants found in actual repository data or confirmed by requirements
    aliases_data = {
        "PKO": [
            "PKO",
            "PALM KERNEL OIL",
        ],
        "OLIVE_OIL": [
            "OLIVE OIL",
        ],
        "CHEESE": [
            "CHEESE",
        ],
    }

    for code, aliases_list in aliases_data.items():
        canonical = inputs_map[code]
        for alias in aliases_list:
            # Normalize: uppercase, single spaces
            normalized = " ".join(alias.strip().upper().split())
            # Skip if already exists (idempotent)
            if not SionInputAlias.objects.filter(normalized_alias=normalized).exists():
                SionInputAlias.objects.create(
                    canonical_input=canonical,
                    alias=alias,
                    normalized_alias=normalized
                )


def reverse_seed(apps, schema_editor):
    """Reverse: delete all seeded aliases and inputs."""
    SionCanonicalInput = apps.get_model('license', 'SionCanonicalInput')
    SionCanonicalInput.objects.filter(
        code__in=["PKO", "OLIVE_OIL", "CHEESE"]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('license', '0027_sion_input_percentage_rules'),
    ]

    operations = [
        migrations.RunPython(seed_aliases, reverse_seed),
    ]
