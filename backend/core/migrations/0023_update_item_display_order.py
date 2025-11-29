# Data migration to set display_order and is_active for E1 and E5 items

from django.db import migrations


def update_items(apps, schema_editor):
    """Update display_order and is_active for E1 and E5 items"""
    ItemNameModel = apps.get_model('core', 'ItemNameModel')
    SionNormClassModel = apps.get_model('core', 'SionNormClassModel')

    # E1 items configuration
    e1_items_config = [
        ('FRUIT JUICE - E1', 1, 0.00, True),
        ('WPC - E1', 2, 0.00, True),
        ('SWP - E1', 3, 0.00, True),
        ('FRUIT/COCOA - E1', 4, 0.00, True),
        ('CHEESE - E1', 5, 0.00, True),
        ('CITRIC ACID / TARTARIC ACID - E1', 6, 0.00, True),
        ('FOOD FLAVOUR - E1', 7, 5, True),
        ('ESSENTIAL OIL - E1', 8, 5, True),
        ('EMULSIFIER - E1', 9, 3, False),
        ('STABILIZING AGENT - E1', 10, 3, False),
        ('STARCH 1108 - E1', 11, 3, True),
        ('STARCH 3505 - E1', 12, 3, False),
        ('OTHER CONFECTIONERY INGREDIENTS - E1', 13, 2, True),
        ('PALM KERNEL OIL - E1', 14, 2, False),
        ('RBD PALMOLEIN OIL - E1', 15, 2, True),
        ('PP - E1', 16, 0.00, True),
        ('ALUMINIUM FOIL - E1', 17, 0.00, True),
        ('PAPER BOARD - E1', 18, 0.00, True),
        ('PAPER & PAPER - E1', 19, 0.00, True),
        ('LDPE - E1', 20, 0.00, True),
        ('HDPE - E1', 21, 0.00, True),
        ('BOPP - E1', 22, 0.00, True),
        ('SUGAR - E1', 23, 0.00, False),
        ('ANTI OXIDANT - E1', 24, 0.00, False),
        ('FOOD COLOUR - E1', 25, 0.00, False),
        ('LIQUID GLUCOSE - E1', 26, 0.00, False),
    ]

    # E5 items configuration
    e5_items_config = [
        ('VEGETABLE SHORTENING - E5', 1, 0.00, True),
        ('RBD PALMOLEIN OIL - E5', 2, 0.00, True),
        ('PALM KERNEL OIL - E5', 3, 0.00, True),
        ('OLIVE OIL - E5', 4, 0.00, True),
        ('LEAVENING AGENT - E5', 5, 0.00, True),
        ('FRUIT JUICE - E5', 6, 0.00, True),
        ('FOOD FLAVOUR - E5', 7, 0.00, True),
        ('DIETARY FIBRE - E5', 8, 0.00, True),
        ('FRUIT/COCOA - E5', 9, 0.00, True),
        ('STARCH 1108 - E5', 10, 0.00, True),
        ('CHEESE - E5', 11, 0.00, True),
        ('SWP - E5', 12, 0.00, True),
        ('WPC - E5', 13, 0.00, True),
        ('WHEAT GLUTEN - E5', 14, 0.00, True),
        ('WHEAT FLOUR - E5', 15, 0.00, True),
        ('PP - E5', 16, 0.00, True),
        ('PAPER & PAPER - E5', 17, 0.00, True),
        ('PAPER BOARD - E5', 18, 0.00, True),
        ('ALUMINIUM FOIL - E5', 19, 0.00, True),
        ('ANTI OXIDANT - E5', 20, 0.00, False),
        ('BISCUITS ADDITIVES & INGREDIENTS - E5', 21, 0.00, False),
        ('BOPP - E5', 22, 0.00, False),
        ('CITRIC ACID / TARTARIC ACID - E5', 23, 0.00, False),
        ('FOOD COLOUR - E5', 24, 0.00, False),
        ('HDPE - E5', 25, 0.00, False),
        ('LDPE - E5', 26, 0.00, False),
        ('STARCH 3505 - E5', 27, 0.00, False),
        ('SUGAR - E5', 28, 0.00, False),
    ]

    # C460 items configuration
    c460_items_config = [
        ('AUTOMOTIVE BATTERY - C460', 1, 0.00, True),
        ('ALLOY STEEL - C460', 2, 0.00, True),
        ('HOT ROLLED STEEL - C460', 3, 0.00, True),
        ('COLD ROLLED STEEL - C460', 4, 0.00, True),
        ('BEARING - C460', 5, 0.00, True),
        ('RADIATOR - C460', 6, 0.00, True),
        ('CLUTCH ASSEMBLY - C460', 7, 0.00, True),
        ('WIRING HARNNESS - C460', 8, 0.00, True),
        ('BRAKE ASSEMBLY - C460', 9, 0.00, True),
        ('ALTERNATOR - C460', 10, 0.00, True),
        ('FUEL FILTER - C460', 11, 0.00, True),
        ("'O' Ring - C460", 12, 0.00, False),
        ('AIR FILTER - C460', 13, 0.00, False),
        ('AUXILIARY VALVES - C460', 14, 0.00, False),
        ('FRONT AXLE - C460', 15, 0.00, False),
        ('FRONT WHEELRIM - C460', 16, 0.00, False),
        ('FRONTWHEEL TYRE - C460', 17, 0.00, False),
        ('FUEL INJECTION PUMP - C460', 18, 0.00, False),
        ('HYDRAULIC CYLINDER - C460', 19, 0.00, False),
        ('HYDRAULIC PUMP - C460', 20, 0.00, False),
        ('HYDRAULIC VALVES - C460', 21, 0.00, False),
        ('HYDROSTATIC TRANSMISSION - C460', 22, 0.00, False),
        ('INTERNAL COMBUSTION ENGINE - C460', 23, 0.00, False),
        ('OIL PUMP - C460', 24, 0.00, False),
        ('OIL SEAL - C460', 25, 0.00, False),
        ('OIL SEPERATOR - C460', 26, 0.00, False),
        ('REAR WHEELRIM - C460', 27, 0.00, False),
        ('REARWHEEL TYRE - C460', 28, 0.00, False),
        ('SAFETY NEUTRAL SWITCH - C460', 29, 0.00, False),
        ('SEAT ASSEMBLY - C460', 30, 0.00, False),
        ('STARTER MOTOR - C460', 31, 0.00, False),
        ('SYNCHROPACKS - C460', 32, 0.00, False),
        ('TURBO CHARGER - C460', 33, 0.00, False),
        ('WATER PUMP - C460', 34, 0.00, False),
    ]

    # A3627 items configuration
    a3627_items_config = [
        ('RUTILE - A3627', 1, 0.00, True),
        ('SODA ASH - A3627', 2, 0.00, True),
        ('TITANIUM DIOXIDE - A3627', 3, 0.00, True),
        ('PP - A3627', 4, 0.00, True),
        ('ALUMINIUM OXIDE, ZINC OXIDE, ZIRCONIUM OXIDE - A3627', 5, 0.00, False),
        ('CERAMIC COLOUR - A3627', 6, 0.00, False),
        ('SODIUM NITRATE - A3627', 7, 0.00, False),
    ]

    # E132 items configuration
    e132_items_config = [
        ('CEREALS FLAKES - E132', 1, 0.00, True),
        ('PALM KERNEL OIL - E132', 2, 0.00, True),
        ('RBD PALMOLEIN OIL - E132', 3, 0.00, True),
        ('CMC - E132', 4, 5, True),
        ('FOOD FLAVOUR - E132', 5, 3, True),
        ('CHEESE - E132', 6, 3, True),
        ('PP - E132', 7, 0.00, True),
        ('ALUMINIUM FOIL - E132', 8, 0.00, True),
        ('BOPP - E132', 9, 0.00, False),
        ('HDPE - E132', 10, 0.00, False),
        ('LDPE - E132', 11, 0.00, False),
        ('PAPER & PAPER - E132', 12, 0.00, False),
        ('PAPER BOARD - E132', 13, 0.00, False),
        ('RELEVANT ADDITIVES DESCRIPTION - E132', 14, 0.00, False),
    ]

    # E126 items configuration
    e126_items_config = [
        ('OLIVE OIL - E126', 1, 0.00, True),
        ('PALM KERNEL OIL - E126', 2, 0.00, True),
        ('RBD PALMOLEIN OIL - E126', 3, 0.00, True),
        ('FOOD FLAVOUR - E126', 4, 0.00, True),
        ('PP - E126', 5, 0.00, True),
        ('ALUMINIUM FOIL - E126', 6, 0.00, True),
        ('BOPP - E126', 7, 0.00, False),
        ('HDPE - E126', 8, 0.00, False),
        ('LDPE - E126', 9, 0.00, False),
        ('PAPER & PAPER - E126', 10, 0.00, False),
        ('PAPER BOARD - E126', 11, 0.00, False),
        ('SANITATION AND CLEANING CHEMICALS - E126', 12, 0.00, False),
    ]

    # Update E1 items
    try:
        e1_norm = SionNormClassModel.objects.get(norm_class='E1')
        e1_updated_count = 0
        for item_name, display_order, restriction_pct, is_active in e1_items_config:
            try:
                item = ItemNameModel.objects.get(name=item_name, sion_norm_class=e1_norm)
                item.display_order = display_order
                item.restriction_percentage = restriction_pct
                item.is_active = is_active
                item.save()
                e1_updated_count += 1
                print(
                    f"Updated E1: {item_name} (order={display_order}, restriction={restriction_pct}%, active={is_active})")
            except ItemNameModel.DoesNotExist:
                print(f"E1 item not found: {item_name}")
            except ItemNameModel.MultipleObjectsReturned:
                print(f"Multiple E1 items found for: {item_name}, skipping")
        print(f"\nTotal E1 items updated: {e1_updated_count}")
    except SionNormClassModel.DoesNotExist:
        print("E1 norm class not found, skipping E1 items")

    # Update E5 items
    try:
        e5_norm = SionNormClassModel.objects.get(norm_class='E5')
        e5_updated_count = 0
        for item_name, display_order, restriction_pct, is_active in e5_items_config:
            try:
                item = ItemNameModel.objects.get(name=item_name, sion_norm_class=e5_norm)
                item.display_order = display_order
                item.restriction_percentage = restriction_pct
                item.is_active = is_active
                item.save()
                e5_updated_count += 1
                print(
                    f"Updated E5: {item_name} (order={display_order}, restriction={restriction_pct}%, active={is_active})")
            except ItemNameModel.DoesNotExist:
                print(f"E5 item not found: {item_name}")
            except ItemNameModel.MultipleObjectsReturned:
                print(f"Multiple E5 items found for: {item_name}, skipping")
        print(f"\nTotal E5 items updated: {e5_updated_count}")
    except SionNormClassModel.DoesNotExist:
        print("E5 norm class not found, skipping E5 items")

    # Update C460 items
    try:
        c460_norm = SionNormClassModel.objects.get(norm_class='C460')
        c460_updated_count = 0
        for item_name, display_order, restriction_pct, is_active in c460_items_config:
            try:
                item = ItemNameModel.objects.get(name=item_name, sion_norm_class=c460_norm)
                item.display_order = display_order
                item.restriction_percentage = restriction_pct
                item.is_active = is_active
                item.save()
                c460_updated_count += 1
                print(
                    f"Updated C460: {item_name} (order={display_order}, restriction={restriction_pct}%, active={is_active})")
            except ItemNameModel.DoesNotExist:
                print(f"C460 item not found: {item_name}")
            except ItemNameModel.MultipleObjectsReturned:
                print(f"Multiple C460 items found for: {item_name}, skipping")
        print(f"\nTotal C460 items updated: {c460_updated_count}")
    except SionNormClassModel.DoesNotExist:
        print("C460 norm class not found, skipping C460 items")

    # Update A3627 items
    try:
        a3627_norm = SionNormClassModel.objects.get(norm_class='A3627')
        a3627_updated_count = 0
        for item_name, display_order, restriction_pct, is_active in a3627_items_config:
            try:
                item = ItemNameModel.objects.get(name=item_name, sion_norm_class=a3627_norm)
                item.display_order = display_order
                item.restriction_percentage = restriction_pct
                item.is_active = is_active
                item.save()
                a3627_updated_count += 1
                print(
                    f"Updated A3627: {item_name} (order={display_order}, restriction={restriction_pct}%, active={is_active})")
            except ItemNameModel.DoesNotExist:
                print(f"A3627 item not found: {item_name}")
            except ItemNameModel.MultipleObjectsReturned:
                print(f"Multiple A3627 items found for: {item_name}, skipping")
        print(f"\nTotal A3627 items updated: {a3627_updated_count}")
    except SionNormClassModel.DoesNotExist:
        print("A3627 norm class not found, skipping A3627 items")

    # Update E132 items
    try:
        e132_norm = SionNormClassModel.objects.get(norm_class='E132')
        e132_updated_count = 0
        for item_name, display_order, restriction_pct, is_active in e132_items_config:
            try:
                item = ItemNameModel.objects.get(name=item_name, sion_norm_class=e132_norm)
                item.display_order = display_order
                item.restriction_percentage = restriction_pct
                item.is_active = is_active
                item.save()
                e132_updated_count += 1
                print(
                    f"Updated E132: {item_name} (order={display_order}, restriction={restriction_pct}%, active={is_active})")
            except ItemNameModel.DoesNotExist:
                print(f"E132 item not found: {item_name}")
            except ItemNameModel.MultipleObjectsReturned:
                print(f"Multiple E132 items found for: {item_name}, skipping")
        print(f"\nTotal E132 items updated: {e132_updated_count}")
    except SionNormClassModel.DoesNotExist:
        print("E132 norm class not found, skipping E132 items")

    # Update E126 items
    try:
        e126_norm = SionNormClassModel.objects.get(norm_class='E126')
        e126_updated_count = 0
        for item_name, display_order, restriction_pct, is_active in e126_items_config:
            try:
                item = ItemNameModel.objects.get(name=item_name, sion_norm_class=e126_norm)
                item.display_order = display_order
                item.restriction_percentage = restriction_pct
                item.is_active = is_active
                item.save()
                e126_updated_count += 1
                print(
                    f"Updated E126: {item_name} (order={display_order}, restriction={restriction_pct}%, active={is_active})")
            except ItemNameModel.DoesNotExist:
                print(f"E126 item not found: {item_name}")
            except ItemNameModel.MultipleObjectsReturned:
                print(f"Multiple E126 items found for: {item_name}, skipping")
        print(f"\nTotal E126 items updated: {e126_updated_count}")
    except SionNormClassModel.DoesNotExist:
        print("E126 norm class not found, skipping E126 items")


def reverse_update(apps, schema_editor):
    """Reverse operation - reset display_order to 1"""
    ItemNameModel = apps.get_model('core', 'ItemNameModel')
    SionNormClassModel = apps.get_model('core', 'SionNormClassModel')

    try:
        e1_norm = SionNormClassModel.objects.get(norm_class='E1')
        ItemNameModel.objects.filter(sion_norm_class=e1_norm).update(
            display_order=1,
            is_active=True
        )
    except SionNormClassModel.DoesNotExist:
        pass

    try:
        e5_norm = SionNormClassModel.objects.get(norm_class='E5')
        ItemNameModel.objects.filter(sion_norm_class=e5_norm).update(
            display_order=1,
            is_active=True
        )
    except SionNormClassModel.DoesNotExist:
        pass

    try:
        c460_norm = SionNormClassModel.objects.get(norm_class='C460')
        ItemNameModel.objects.filter(sion_norm_class=c460_norm).update(
            display_order=1,
            is_active=True
        )
    except SionNormClassModel.DoesNotExist:
        pass

    try:
        a3627_norm = SionNormClassModel.objects.get(norm_class='A3627')
        ItemNameModel.objects.filter(sion_norm_class=a3627_norm).update(
            display_order=1,
            is_active=True
        )
    except SionNormClassModel.DoesNotExist:
        pass

    try:
        e132_norm = SionNormClassModel.objects.get(norm_class='E132')
        ItemNameModel.objects.filter(sion_norm_class=e132_norm).update(
            display_order=1,
            is_active=True
        )
    except SionNormClassModel.DoesNotExist:
        pass

    try:
        e126_norm = SionNormClassModel.objects.get(norm_class='E126')
        ItemNameModel.objects.filter(sion_norm_class=e126_norm).update(
            display_order=1,
            is_active=True
        )
    except SionNormClassModel.DoesNotExist:
        pass


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0022_activate_sion_norms'),
    ]

    operations = [
        migrations.RunPython(update_items, reverse_update),
    ]
