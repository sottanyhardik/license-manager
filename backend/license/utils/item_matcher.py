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
                (Q(hs_code__hs_code__startswith='32061190') |
                 Q(hs_code__hs_code__startswith='32061110') |
                 Q(description__icontains='Glass Formers') |
                 Q(description__icontains='Rutile') |
                 Q(description__icontains='Formers'))
                & ~Q(description__icontains='other than')
                & ~Q(description__icontains='Titanium Dioxide')
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
        {
            'base_name': 'ALUMINIUM FOIL',
            'norms': ['A3627'],
            'filters': [
                Q(hs_code__hs_code__startswith='7607') |
                Q(description__icontains='7607') |
                Q(description__icontains='ALUMINIUM FOIL')
            ]
        },

        # COMMON and E1, E5, E132, E126 items
        {
            'base_name': 'PAPER BOARD',
            'norms': ['COMMON', 'E1', 'E5', 'E132', 'E126'],
            'filters': [
                Q(hs_code__hs_code__startswith='4801') &
                Q(description__icontains="BOARD") &
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
                Q(description__icontains="PAPER") &
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
            'base_name': 'SUGAR',
            'norms': ['E1', 'E5'],
            'filters': [
                Q(description__icontains='sugar') |
                Q(description__icontains='1701') |
                Q(hs_code__hs_code__startswith='1701')
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
        {
            'base_name': 'RBD PALMOLEIN OIL',
            'norms': ['E1'],
            'filters': [
                Q(description__icontains='1510') |
                Q(hs_code__hs_code__startswith='1510')
            ],
            'is_active': False
        },
        {
            'base_name': 'OLIVE OIL',
            'norms': ['E126'],
            'filters': [Q(description__icontains='olive')]
        },
        {
            'base_name': 'PICKLE',
            'norms': ['E126'],
            'filters': [
                Q(description__icontains='pickle') &
                ~Q(description__icontains='food additive')
            ]
        },
        {
            'base_name': 'FOOD FLAVOUR',
            'norms': ['E126'],
            'filters': [
                Q(description__icontains='food additive') |
                Q(description__icontains='flavour')
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
