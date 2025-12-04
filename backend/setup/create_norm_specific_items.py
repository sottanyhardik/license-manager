"""
Data migration script to create norm-specific item names
Run this script to create new ItemNameModel entries for norm-specific items
"""

from django.core.management import setup_environ
import sys
import os

# Add the backend directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def create_norm_specific_items():
    """Create new ItemNameModel entries for norm-specific items"""
    from core.models import ItemNameModel

    # List of new norm-specific item names
    new_items = [
        # E1 Confectionery items
        'STABILIZING AGENT - E1',
        'WPC - E1',
        'EMULSIFIER - E1',
        'FRUIT/COCOA - E1',
        'FRUIT JUICE - E1',
        'FOOD FLAVOUR - E1',
        'CITRIC ACID / TARTARIC ACID - E1',
        'OTHER CONFECTIONERY INGREDIENTS - E1',

        # E5 Biscuits items
        'BISCUITS ADDITIVES & INGREDIENTS - E5',
        'EMULSIFIER - E5',
        'FOOD FLAVOUR - E5',
        'FRUIT/COCOA - E5',
        'JUICE - E5',

        # E126 Pickle items
        'FOOD FLAVOUR - E126',
        'FOOD ADDITIVES - E126',
        'SANITATION AND CLEANING CHEMICALS - E126',

        # E132 Namkeen items
        'FOOD FLAVOUR - E132',
        'FOOD ADDITIVES - E132',
        'FOOD ADDITIVES TBHQ - E132',
        'EDIBLE VEGETABLE OIL - E132',
    ]

    created_count = 0
    existing_count = 0

    print("Creating norm-specific item names...")
    print("=" * 80)

    for item_name in new_items:
        item, created = ItemNameModel.objects.get_or_create(name=item_name)
        if created:
            created_count += 1
            print(f"✓ Created: {item_name}")
        else:
            existing_count += 1
            print(f"  Already exists: {item_name}")

    print("=" * 80)
    print(f"✅ Complete!")
    print(f"   - Created: {created_count} new items")
    print(f"   - Existing: {existing_count} items")
    print(f"   - Total: {len(new_items)} items")
    print("=" * 80)

    return created_count, existing_count


if __name__ == "__main__":
    import django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()

    create_norm_specific_items()
