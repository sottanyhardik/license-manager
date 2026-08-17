# Data migration to seed initial SION canonical inputs and aliases

from django.db import migrations


def seed_aliases(apps, schema_editor):
    """Seed initial E126/E132 canonical inputs and aliases."""
    SionCanonicalInput = apps.get_model('license', 'SionCanonicalInput')
    SionInputAlias = apps.get_model('license', 'SionInputAlias')

    # Create canonical inputs
    inputs_data = [
        ("PKO", "Palm Kernel Oil"),
        ("OLIVE_OIL", "Olive Oil"),
        ("CHEESE", "Cheese Cream Butter and Fats"),
        ("NUT", "Nuts and Seeds"),
        ("YEAST", "Yeast and Baking Products"),
        ("RBD", "RBD Palmolein Oil"),
        ("SWP", "Sweet Whey Powder"),
        ("DWP", "Demineralized Whey Powder"),
        ("WPC", "Whey Protein Concentrate"),
        ("ALUMINIUM_FOIL", "Aluminium Foil"),
    ]

    inputs_map = {}
    for code, display_name in inputs_data:
        obj = SionCanonicalInput.objects.create(
            code=code,
            display_name=display_name,
            is_active=True
        )
        inputs_map[code] = obj

    # Create aliases
    aliases_data = {
        "PKO": [
            "PKO", "pko", "Pko",
            "PALM KERNEL OIL", "Palm Kernel Oil", "palm kernel oil",
            "Pure Palm Kernel Oil", "pure palm kernel oil"
        ],
        "OLIVE_OIL": [
            "OLIVE OIL", "Olive Oil", "olive oil",
            "Extra Virgin Olive Oil", "extra virgin olive oil",
            "OLIVE OIL - E126"
        ],
        "CHEESE": [
            "CHEESE", "Cheese", "cheese",
            "CHEESE CREAM BUTTER AND FATS", "Cheese Cream Butter and Fats",
            "cheese cream butter and fats"
        ],
        "NUT": [
            "NUT", "NUTS", "Nuts", "nuts",
            "NUT & NUTS - E132", "nut & nuts - e132",
            "Nuts and Seeds", "nuts and seeds",
            "Cashew", "cashew", "Almonds", "almonds"
        ],
        "YEAST": [
            "YEAST", "Yeast", "yeast",
            "Bakers Yeast", "bakers yeast",
            "Yeast - E132", "yeast - e132"
        ],
        "RBD": [
            "RBD", "rbd", "Rbd",
            "RBD OIL", "rbd oil",
            "RBD PALMOLEIN OIL", "rbd palmolein oil",
            "RBD Palm Oil", "rbd palm oil",
            "RBD Palmolein Oil", "rbd palmolein oil",
            "RBD - E132", "rbd - e132"
        ],
        "SWP": [
            "SWP", "swp", "Swp",
            "Sweet Whey Powder", "sweet whey powder",
            "SWP - E132", "swp - e132"
        ],
        "DWP": [
            "DWP", "dwp", "Dwp",
            "Demineralized Whey Powder", "demineralized whey powder",
            "DWP - E132", "dwp - e132"
        ],
        "WPC": [
            "WPC", "wpc", "Wpc",
            "Whey Protein Concentrate", "whey protein concentrate",
            "WPC - E132", "wpc - e132"
        ],
        "ALUMINIUM_FOIL": [
            "ALUMINIUM FOIL", "Aluminium Foil", "aluminium foil",
            "Aluminium Foil - E132", "aluminium foil - e132"
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
        code__in=["PKO", "OLIVE_OIL", "CHEESE", "NUT", "YEAST", "RBD", "SWP", "DWP", "WPC", "ALUMINIUM_FOIL"]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('license', '0027_sion_input_percentage_rules'),
    ]

    operations = [
        migrations.RunPython(seed_aliases, reverse_seed),
    ]
