"""
Utility module for matching license import items to ItemNameModel items.
This ensures consistent item matching logic across the codebase.
"""
from django.db.models import Q


def get_item_filters():
    """
    Returns the comprehensive filter definitions for matching import items to ItemNameModel items.
    This is the single source of truth for item classification logic.

    Returns:
        list: List of dictionaries containing base_name, norms, and filters for each item type
    """
    return [
        # A3627 Glass & Ceramic items
        {
            'base_name': 'SODIUM NITRATE',
            'norms': ['A3627'],
            'filters': [Q(description__icontains="Sodium Nitrate")]
        },
        {
            'base_name': 'TITANIUM DIOXIDE',
            'norms': ['A3627'],
            'filters': [Q(description__icontains='Titanium Dioxide') & Q(description__icontains='other than')]
        },
        {
            'base_name': 'SILICA',
            'norms': ['A3627'],
            'filters': [
                Q(hs_code__hs_code__startswith='28110000') &
                Q(description__icontains='Silica') &
                ~Q(description__icontains='Fumed Silica')
            ]
        },
        {
            'base_name': 'BORAX',
            'norms': ['A3627'],
            'filters': [
                Q(hs_code__hs_code__startswith='28401900') |
                Q(description__icontains='Borax')
            ]
        },
        {
            'base_name': 'RUTILE',
            'norms': ['A3627'],
            'filters': [
                (Q(hs_code__hs_code__startswith='3206') |
                 Q(description__icontains='Glass Formers') |
                 Q(description__icontains='Rutile') |
                 Q(description__icontains='Formers'))
                & Q(description__icontains='borax')
            ]
        },
        {
            'base_name': 'SODA ASH',
            'norms': ['A3627'],
            'filters': [Q(description__icontains='Soda Ash')]
        },
        {
            'base_name': 'CERAMIC COLOUR',
            'norms': ['A3627'],
            'filters': [Q(description__icontains="CERAMIC COLOUR")]
        },
        {
            'base_name': 'ALUMINIUM OXIDE, ZINC OXIDE, ZIRCONIUM OXIDE',
            'norms': ['A3627'],
            'filters': [Q(description__icontains='ALUMINIUM OXIDE')]
        },
        {
            'base_name': 'PP',
            'norms': ['A3627'],
            'filters': [
                ((Q(hs_code__hs_code__startswith='39020000') |
                  Q(hs_code__hs_code__startswith='39021000') |
                  Q(description__icontains='Polypropylene') |
                  Q(description__icontains='pp granules') |
                  (Q(description__icontains='packing material') & Q(hs_code__hs_code__startswith='39')))) &
                ~Q(description__icontains='BOPP') &
                ~Q(description__icontains='7607') &
                ~Q(description__icontains='ALUMINIUM FOIL') &
                ~Q(hs_code__hs_code__startswith='7607') &
                ~Q(hs_code__hs_code__startswith='4801')
            ]
        },

        # Automotive/Engineering items - C969
        {
            'base_name': 'WIRING HANRNESS',
            'norms': ['C969'],
            'filters': [Q(description__icontains='wiring hanrness')]
        },
        {
            'base_name': 'WATER PUMP',
            'norms': ['C969'],
            'filters': [Q(description__icontains='WATER PUMP')]
        },
        {
            'base_name': "'O' Ring",
            'norms': ['C969'],
            'filters': [
                Q(description__icontains="'O' Ring") |
                Q(hs_code__hs_code__startswith='40169320')
            ]
        },
        {
            'base_name': 'BEARING',
            'norms': ['C969'],
            'filters': [
                Q(description__icontains="BEARING") |
                Q(hs_code__hs_code__startswith='8482')
            ]
        },
        {
            'base_name': 'TURBO CHARGER',
            'norms': ['C969'],
            'filters': [Q(description__icontains="TURBO CHARGER")]
        },
        {
            'base_name': 'STARTER MOTOR',
            'norms': ['C969'],
            'filters': [Q(description__icontains="starter motor")]
        },
        {
            'base_name': 'ALLOY STEEL',
            'norms': ['C969'],
            'filters': [Q(description__icontains="alloy steel rod")]
        },
        {
            'base_name': 'AUTOMOTIVE BATTERY',
            'norms': ['C969'],
            'filters': [
                Q(description__icontains="AUTOMOTIVE BATTERY") |
                Q(description__icontains="AUTOMATIVE BATTERY") |
                Q(description__icontains="Automotive Battery") |
                Q(description__icontains="Battery Automotive")
            ]
        },
        {
            'base_name': 'BRAKE ASSEMBLY',
            'norms': ['C969'],
            'filters': [Q(description__icontains="Brake Assembly")]
        },
        {
            'base_name': 'SEAT ASSEMBLY',
            'norms': ['C969'],
            'filters': [Q(description__icontains="SEAT ASSEMBLY")]
        },
        {
            'base_name': 'REARWHEEL TYRE',
            'norms': ['C969'],
            'filters': [Q(description__icontains="REARWHEEL TYRE")]
        },
        {
            'base_name': 'FRONTWHEEL TYRE',
            'norms': ['C969'],
            'filters': [Q(description__icontains="frontwheel tyre")]
        },
        {
            'base_name': 'RADIATOR',
            'norms': ['C969'],
            'filters': [Q(description__icontains="RADIATOR")]
        },
        {
            'base_name': 'REAR WHEELRIM',
            'norms': ['C969'],
            'filters': [Q(description__icontains="REAR WHEELRIM")]
        },
        {
            'base_name': 'FRONT WHEELRIM',
            'norms': ['C969'],
            'filters': [Q(description__icontains="FRONT WHEELRIM")]
        },
        {
            'base_name': 'SAFETY NEUTRAL SWITCH',
            'norms': ['C969'],
            'filters': [Q(description__icontains="SAFETY NEUTRAL SWITCH")]
        },
        {
            'base_name': 'OIL SEPERATOR',
            'norms': ['C969'],
            'filters': [Q(description__icontains="OIL SEPERATOR")]
        },
        {
            'base_name': 'OIL PUMP',
            'norms': ['C969'],
            'filters': [Q(description__icontains="OIL PUMP")]
        },
        {
            'base_name': 'OIL SEAL',
            'norms': ['C969'],
            'filters': [Q(description__icontains="Oil Seal")]
        },
        {
            'base_name': 'CLUTCH ASSEMBLY',
            'norms': ['C969'],
            'filters': [Q(description__icontains="CLUTCH ASSEMBLY")]
        },
        {
            'base_name': 'ALTERNATOR',
            'norms': ['C969'],
            'filters': [Q(description__icontains="ALTERNATOR")]
        },
        {
            'base_name': 'HYDROSTATIC TRANSMISSION',
            'norms': ['C969'],
            'filters': [
                Q(description__icontains="HYDROSTATIC") &
                Q(description__icontains="TRANSMISSION")
            ]
        },
        {
            'base_name': 'HYDRAULIC VALVES',
            'norms': ['C969'],
            'filters': [Q(description__icontains="HYDRAULIC VALVES")]
        },
        {
            'base_name': 'HYDRAULIC CYLINDER',
            'norms': ['C969'],
            'filters': [Q(description__icontains="HYDRAULIC CYLINDER")]
        },
        {
            'base_name': 'HYDRAULIC PUMP',
            'norms': ['C969'],
            'filters': [Q(description__icontains="HYDRAULIC PUMP")]
        },
        {
            'base_name': 'FRONT AXLE',
            'norms': ['C969'],
            'filters': [Q(description__icontains="FRONT AXLE")]
        },
        {
            'base_name': 'FUEL FILTER',
            'norms': ['C969'],
            'filters': [Q(description__icontains="FUEL FILTER")]
        },
        {
            'base_name': 'FUEL INJECTION PUMP',
            'norms': ['C969'],
            'filters': [Q(description__icontains="FUEL INJECTION PUMP")]
        },
        {
            'base_name': 'INTERNAL COMBUSTION ENGINE',
            'norms': ['C969'],
            'filters': [Q(description__icontains="INTERNAL COMBUSTION ENGINE")]
        },
        {
            'base_name': 'AIR FILTER',
            'norms': ['C969'],
            'filters': [Q(description__icontains="AIR FILTER")]
        },
        {
            'base_name': 'AUXILIARY VALVES',
            'norms': ['C969'],
            'filters': [Q(description__icontains="AUXILIARY VALVES")]
        },
        {
            'base_name': 'SYNCHROPACKS',
            'norms': ['C969'],
            'filters': [Q(description__icontains="synchropacks")]
        },

        # Steel items - C473, C471
        {
            'base_name': 'HOT ROLLED STEEL',
            'norms': ['C473', 'C471', 'C969'],
            'filters': [
                Q(description__icontains="HOT ROLLED") |
                Q(description__icontains="NON ALLOY")
            ]
        },
        {
            'base_name': 'COLD ROLLED STEEL',
            'norms': ['C473', 'C471', 'C969'],
            'filters': [Q(description__icontains="COLD ROLLED")]
        },

        # Food ingredients - multiple norms
        {
            'base_name': 'SUGAR',
            'norms': ['E1', 'E5'],
            'filters': [
                Q(description__icontains='sugar') |
                Q(description__icontains='1701') |
                Q(hs_code__hs_code__startswith='1701')
            ]
        },
        {
            'base_name': 'WHEAT GLUTEN',
            'norms': ['E5'],
            'filters': [
                Q(description__icontains='GLUTEN') |
                Q(description__icontains='1109') |
                Q(hs_code__hs_code__startswith='1109')
            ]
        },
        {
            'base_name': 'WHEAT FLOUR',
            'norms': ['E5'],
            'filters': [
                Q(description__icontains='WHEAT FLOUR') |
                Q(description__icontains='FLOUR')
            ]
        },
        {
            'base_name': 'DIETARY FIBRE',
            'norms': ['E5'],
            'filters': [Q(description__icontains='Dietary Fibre')]
        },
        {
            'base_name': 'CHEESE',
            'norms': ['E1', 'E5', 'E132'],
            'filters': [
                Q(description__icontains="0406") |
                Q(hs_code__hs_code__startswith='0406')
            ]
        },
        {
            'base_name': 'SWP',
            'norms': ['E1', 'E5'],
            'filters': [
                Q(description__icontains="0404") |
                Q(hs_code__hs_code__startswith='0404')
            ]
        },
        {
            'base_name': 'ANTI OXIDANT',
            'norms': ['E1', 'E5'],
            'filters': [
                Q(description__icontains="Anti oxidant") |
                Q(description__icontains="Anti oxident")
            ]
        },
        {
            'base_name': 'FOOD COLOUR',
            'norms': ['E1', 'E5'],
            'filters': [Q(description__icontains="FOOD COLOUR")]
        },
        {
            'base_name': 'STARCH 1108',
            'norms': ['E1', 'E5'],
            'filters': [
                Q(description__icontains="1108") |
                Q(hs_code__hs_code__startswith='1108')
            ]
        },
        {
            'base_name': 'STARCH 3505',
            'norms': ['E1', 'E5'],
            'filters': [
                Q(description__icontains="3505") |
                Q(hs_code__hs_code__startswith='3505') |
                (Q(description__icontains="starch") &
                 (~Q(hs_code__hs_code__startswith='1108') |
                  ~Q(description__icontains="1108")))
            ]
        },
        {
            'base_name': 'LEAVENING AGENT',
            'norms': ['E5'],
            'filters': [
                Q(description__icontains="LEAVENING AGENT") |
                Q(description__icontains='leaving agent') |
                Q(description__icontains='Yeast')
            ]
        },
        {
            'base_name': 'OLIVE OIL',
            'norms': ['E5', 'E126'],
            'filters': [
                Q(description__icontains="1500") |
                Q(description__icontains="1509") |
                Q(description__icontains="1510") |
                Q(hs_code__hs_code__startswith="1509")
            ]
        },
        {
            'base_name': 'RBD PALMOLEIN OIL',
            'norms': ['E1', 'E5', 'E126', 'E132'],
            'filters': [
                Q(description__icontains="vegetable shortening") |
                Q(description__icontains="rbd palmolein oil") |
                Q(hs_code__hs_code__startswith="15119020")
            ],
            'is_active': False
        },
        {
            'base_name': 'PALM KERNEL OIL',
            'norms': ['E1', 'E5', 'E126', 'E132'],
            'filters': [
                Q(hs_code__hs_code__startswith="1513") |
                Q(description__icontains="1513")
            ]
        },
        {
            'base_name': 'LIQUID GLUCOSE',
            'norms': ['E1'],
            'filters': [Q(description__icontains="liquid glucose")]
        },
        {
            'base_name': 'ESSENTIAL OIL',
            'norms': ['E1'],
            'filters': [
                Q(description__icontains="relevant essential oils") |
                Q(description__icontains="ESSENTIAL OILS") |
                Q(description__icontains="Essential Oil")
            ]
        },
        {
            'base_name': 'CEREALS FLAKES',
            'norms': ['E132'],
            'filters': [
                Q(description__icontains='Chickpeas') |
                Q(description__icontains='lentils') |
                Q(description__icontains='Cereal Flakes') |
                Q(description__icontains='Green Peas')
            ]
        },
        {
            'base_name': 'RELEVANT ADDITIVES DESCRIPTION',
            'norms': ['E132'],
            'filters': [
                Q(description__icontains="RELEVANT ADDITIVES DESCRIPTION") |
                Q(description__icontains="Methyl Cellulose")
            ]
        },
        {
            'base_name': 'STABILIZING AGENT',
            'norms': ['E1'],
            'filters': [Q(description__icontains="Stabilizing Agent")]
        },
        {
            'base_name': 'WPC',
            'norms': ['E1', 'E5'],
            'filters': [
                Q(description__icontains="3502") |
                Q(hs_code__hs_code__startswith='3502') |
                Q(description__icontains='WPC')
            ]
        },
        {
            'base_name': 'EMULSIFIER',
            'norms': ['E1'],
            'filters': [
                Q(description__icontains="emulsifier") |
                Q(description__icontains="EMULSIFIER")
            ]
        },
        {
            'base_name': 'FRUIT/COCOA',
            'norms': ['E1', 'E5'],
            'filters': [
                Q(Q(description__icontains="Cocoa") |
                  Q(description__icontains="Coco Powder") |
                  Q(description__icontains="Cocoa Powder") |
                  Q(description__icontains="1802") |
                  Q(description__icontains="1803") |
                  Q(description__icontains="1804") |
                  Q(description__icontains="18050000") |
                  Q(description__icontains='COCO POWDER') |
                  Q(hs_code__hs_code__startswith='18050000') |
                  Q(description__icontains="fruit/cocoa"))
                & ~Q(description__icontains="actual user")
            ]
        },
        {
            'base_name': 'FRUIT JUICE',
            'norms': ['E1', 'E5'],
            'filters': [
                Q(description__icontains="Juice") |
                Q(description__icontains="Fruit Concentrate") |
                Q(description__icontains='Relevant fruit') |
                Q(description__icontains='FRUITS FLAVOUR') |
                Q(description__icontains='Fruit Flavour') |
                Q(description__icontains="2009") |
                Q(hs_code__hs_code__startswith='2009')
            ]
        },
        {
            'base_name': 'FRUIT COCKTAILS',
            'norms': ['E1'],
            'filters': [
                Q(description__icontains="2008") |
                Q(hs_code__hs_code__startswith='2008')
            ]
        },
        {
            'base_name': 'FOOD FLAVOUR',
            'norms': ['E1', 'E5', 'E126', 'E132'],
            'filters': [
                Q(description__icontains="relevant food flavour") |
                Q(description__icontains="FOOD FLAVOUR") |
                Q(description__icontains="relevant (food flour") |
                Q(description__icontains="Flavouring Agent") |
                Q(description__icontains="FOOD FLAVOURS") |
                Q(description__icontains="Flavours") |
                Q(description__icontains="Cardamom") |
                Q(description__icontains="0802") |
                Q(description__icontains="0806") |
                Q(description__icontains="0908") |
                Q(description__icontains='0904') |
                Q(hs_code__hs_code__startswith='0802') |
                Q(hs_code__hs_code__startswith='0806') |
                Q(hs_code__hs_code__startswith='0904') |
                Q(hs_code__hs_code__startswith='0908')
            ]
        },
        {
            'base_name': 'CITRIC ACID / TARTARIC ACID',
            'norms': ['E1', 'E5'],
            'filters': [
                Q(description__icontains="CITRIC ACID") |
                Q(description__icontains="TARTARIC ACID") |
                Q(description__icontains="TARTARIC AICD")
            ]
        },
        {
            'base_name': 'OTHER CONFECTIONERY INGREDIENTS',
            'norms': ['E1'],
            'filters': [
                Q(description__icontains="other confectionery ingredients") |
                Q(description__icontains="nut & nut products") |
                Q(description__icontains="Fruits and Nuts Product") |
                Q(description__icontains="0908") |
                Q(description__icontains="0802") |
                Q(description__icontains="0806") |
                Q(hs_code__hs_code__startswith='0908') |
                Q(hs_code__hs_code__startswith='0802') |
                Q(hs_code__hs_code__startswith='0806')
            ]
        },
        {
            'base_name': 'BISCUITS ADDITIVES & INGREDIENTS',
            'norms': ['E5'],
            'filters': [
                Q(description__icontains="BISCUITS ADDITIVES & INGREDIENTS") &
                ~Q(description__icontains="Yeast")
            ]
        },
        {
            'base_name': 'SANITATION AND CLEANING CHEMICALS',
            'norms': ['E126'],
            'filters': [Q(description__icontains='SANITATION AND CLEANING CHEMICALS')]
        },
        {
            'base_name': 'CMC',
            'norms': ['E132'],
            'filters': [
                Q(description__icontains="TBHQ") |
                Q(description__icontains="3912") |
                Q(hs_code__hs_code__startswith="3912") |
                Q(description__icontains="Cellulose")
            ]
        },
        {
            'base_name': 'RAISIN',
            'norms': ['E1', 'E5', 'E126', 'E132'],
            'filters': [
                Q(description__icontains='0806') |
                Q(hs_code__hs_code__startswith='0806')
            ],
            'is_active': False
        },
        {
            'base_name': 'WALNUT',
            'norms': ['E1', 'E5', 'E126', 'E132'],
            'filters': [
                Q(description__icontains='0802') |
                Q(hs_code__hs_code__startswith='0802')
            ],
            'is_active': False
        },
        {
            'base_name': 'CARDAMOM',
            'norms': ['E1', 'E5', 'E126', 'E132'],
            'filters': [
                Q(description__icontains='0908') |
                Q(hs_code__hs_code__startswith='0908')
            ],
            'is_active': False
        },

        # Packaging materials - COMMON and E1, E5, E132, E126
        {
            'base_name': 'PAPER BOARD',
            'norms': ['COMMON', 'E1', 'E5', 'E132', 'E126'],
            'filters': [
                Q(hs_code__hs_code__startswith='4801') &
                (Q(description__icontains="BOARD") | Q(description__icontains="4801")) &
                ~Q(description__icontains='7607') &
                ~Q(description__icontains='ALUMINIUM FOIL') &
                ~Q(hs_code__hs_code__startswith='7607') &
                ~Q(hs_code__hs_code__startswith='39')
            ]
        },
        {
            'base_name': 'PAPER & PAPER',
            'norms': ['COMMON', 'E1', 'E5', 'E132', 'E126'],
            'filters': [
                Q(hs_code__hs_code__startswith='4801') &
                (Q(description__icontains="PAPER") | Q(description__icontains="4801")) &
                ~Q(description__icontains="BOARD") &
                ~Q(description__icontains='7607') &
                ~Q(description__icontains='ALUMINIUM FOIL') &
                ~Q(hs_code__hs_code__startswith='7607') &
                ~Q(hs_code__hs_code__startswith='39')
            ]
        },
        {
            'base_name': 'BOPP',
            'norms': ['COMMON', 'E1', 'E5', 'E132', 'E126'],
            'filters': [
                Q(description__icontains="BOPP") &
                ~Q(description__icontains='7607') &
                ~Q(description__icontains='ALUMINIUM FOIL') &
                ~Q(hs_code__hs_code__startswith='7607') &
                ~Q(hs_code__hs_code__startswith='4801')
            ]
        },
        {
            'base_name': 'PP',
            'norms': ['COMMON', 'E1', 'E5', 'E132', 'E126'],
            'filters': [
                ((Q(hs_code__hs_code__startswith='39020000') |
                  Q(hs_code__hs_code__startswith='39021000') |
                  Q(description__icontains='Polypropylene') |
                  Q(description__icontains='pp granules') |
                  (Q(description__icontains='packing material') & Q(hs_code__hs_code__startswith='39'))) |
                 (Q(description__icontains='PP ') &
                  Q(hs_code__hs_code__startswith='39'))) &
                ~Q(description__icontains='BOPP') &
                ~Q(description__icontains='7607') &
                ~Q(description__icontains='ALUMINIUM FOIL') &
                ~Q(hs_code__hs_code__startswith='7607') &
                ~Q(hs_code__hs_code__startswith='4801')
            ]
        },
        {
            'base_name': 'HDPE',
            'norms': ['COMMON', 'E1', 'E5', 'E132', 'E126'],
            'filters': [
                (Q(hs_code__hs_code__startswith='39012000') |
                 Q(description__icontains="hdpe") |
                 Q(description__icontains="hdep") |
                 (Q(description__icontains='packing material') & Q(hs_code__hs_code__startswith='39012000'))) &
                ~Q(description__icontains='BOPP') &
                ~Q(description__icontains='7607') &
                ~Q(description__icontains='ALUMINIUM FOIL') &
                ~Q(hs_code__hs_code__startswith='7607') &
                ~Q(hs_code__hs_code__startswith='4801')
            ]
        },
        {
            'base_name': 'LDPE',
            'norms': ['COMMON', 'E1', 'E5', 'E132', 'E126'],
            'filters': [
                Q(description__icontains="LDPE") |
                Q(description__icontains="LDEP")
            ]
        },
        {
            'base_name': 'ALUMINIUM FOIL',
            'norms': ['COMMON', 'E1', 'E5', 'E132', 'E126'],
            'filters': [
                Q(description__icontains='7607') |
                Q(description__icontains='ALUMINIUM FOIL') |
                Q(hs_code__hs_code__startswith='7607')
            ]
        },

        # Miscellaneous - COMMON
        {
            'base_name': 'COKE',
            'norms': ['COMMON'],
            'filters': [Q(description__icontains="COKE")]
        },
        {
            'base_name': 'BETEL NUT',
            'norms': ['COMMON'],
            'filters': [Q(description__icontains="BETEL NUT")]
        },
        {
            'base_name': 'SUPARI WHOLE',
            'norms': ['COMMON'],
            'filters': [Q(description__icontains="SUPARI WHOLE")]
        },
        {
            'base_name': 'COFFEE BEANS',
            'norms': ['COMMON'],
            'filters': [Q(description__icontains="Coffee Beans")]
        },
        {
            'base_name': 'PICKLE',
            'norms': ['E126'],
            'filters': [
                Q(description__icontains='pickle') &
                ~Q(description__icontains='food additive')
            ]
        },
    ]


def match_import_item_to_items(import_item, license_norm_classes):
    """
    Match a single import item to ItemNameModel items based on comprehensive filters.

    Args:
        import_item: LicenseImportItemsModel instance
        license_norm_classes: List of norm class strings for the license

    Returns:
        QuerySet: ItemNameModel items that match this import item
    """
    from core.models import ItemNameModel

    if not license_norm_classes:
        return ItemNameModel.objects.none()

    filters = get_item_filters()
    matched_item_names = []

    for item_config in filters:
        # Check if this item config applies to any of the license norms
        if not any(norm in item_config['norms'] for norm in license_norm_classes):
            continue

        # Check if the import item matches any of the filters for this item type
        for filter_q in item_config['filters']:
            # Create a queryset with just this import item and apply the filter
            from license.models import LicenseImportItemsModel
            test_qs = LicenseImportItemsModel.objects.filter(id=import_item.id).filter(filter_q)

            if test_qs.exists():
                # This import item matches this filter, find the corresponding ItemNameModel
                item_name = f"{item_config['base_name']} - {license_norm_classes[0]}"

                # Try to find the ItemNameModel (it might not exist yet)
                matching_items = ItemNameModel.objects.filter(
                    name=item_name,
                    sion_norm_class__norm_class__in=license_norm_classes
                )

                matched_item_names.extend(matching_items)
                break  # Found a match for this item config, move to next

    # Return unique ItemNameModel items
    if matched_item_names:
        item_ids = list(set(item.id for item in matched_item_names))
        return ItemNameModel.objects.filter(id__in=item_ids)

    return ItemNameModel.objects.none()
