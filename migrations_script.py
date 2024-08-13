def null_all_export_items():
    from license.models import LicenseExportItemModel
    LicenseExportItemModel.objects.all().update(item=None)
    from core.models import SionNormClassModel
    SionNormClassModel.objects.all().update(item=None)
    return None


def delete_all_items():
    from django.db import models, connection
    from core.models import ItemNameModel
    ItemNameModel.objects.all().delete()
    from core.models import ItemHeadModel
    ItemHeadModel.objects.all().delete()
    with connection.cursor() as cursor:
        cursor.execute("ALTER SEQUENCE core_itemnamemodel_id_seq RESTART WITH 1;")
        cursor.execute("ALTER SEQUENCE core_itemheadmodel_id_seq RESTART WITH 1;")


def createITEM():
    from django.apps import apps
    ItemNameModel = apps.get_model('core',
                                   'ItemNameModel')  # Replace with real app and model name
    ItemHeadModel = apps.get_model('core',
                                   'ItemHeadModel')  # Replace with real app and model name
    head, bool = ItemHeadModel.objects.get_or_create(name='WHEAT GLUTEN')
    ItemNameModel.objects.get_or_create(name='WHEAT GLUTEN', head=head)
    head, bool = ItemHeadModel.objects.get_or_create(name='SUGAR')
    ItemNameModel.objects.get_or_create(name='SUGAR', head=head)
    head, bool = ItemHeadModel.objects.get_or_create(name='VEGETABLE OIL')
    ItemNameModel.objects.get_or_create(name='RBD PALMOLEIN OIL', head=head)
    ItemNameModel.objects.get_or_create(name='EDIBLE VEGETABLE OIL', head=head)
    ItemNameModel.objects.get_or_create(name='PALM KERNEL OIL', head=head)
    head, bool = ItemHeadModel.objects.get_or_create(name='BISCUIT 10% Restriction')
    ItemNameModel.objects.get_or_create(name='FOOD FLAVOUR BISCUITS', head=head)
    ItemNameModel.objects.get_or_create(name='JUICE', head=head)
    ItemNameModel.objects.get_or_create(name='DIETARY FIBRE', head=head)
    ItemNameModel.objects.get_or_create(name='FRUIT/COCOA', head=head)
    ItemNameModel.objects.get_or_create(name='LEAVENING AGENT', head=head)
    ItemNameModel.objects.get_or_create(name='STARCH 1108', head=head)
    ItemNameModel.objects.get_or_create(name='STARCH 3505', head=head)
    head, bool = ItemHeadModel.objects.get_or_create(name='MILK & MILK Product')
    ItemNameModel.objects.get_or_create(name='CHEESE', head=head)
    ItemNameModel.objects.get_or_create(name='WPC', head=head)
    ItemNameModel.objects.get_or_create(name='SWP', head=head)
    head, bool = ItemHeadModel.objects.get_or_create(name='PACKING MATERIAL')
    item, bool = ItemNameModel.objects.get_or_create(name='PP')
    item.head = head
    item.save()
    ItemNameModel.objects.get_or_create(name='PAPER & PAPER', head=head)
    ItemNameModel.objects.get_or_create(name='ALUMINIUM FOIL', head=head)
    head, bool = ItemHeadModel.objects.get_or_create(name='JUICE')
    ItemNameModel.objects.get_or_create(name='FRUIT JUICE', head=head)
    ItemNameModel.objects.get_or_create(name='TARTARIC ACID')
    head, bool = ItemHeadModel.objects.get_or_create(name='CONFECTIONERY 5% Restriction')
    ItemNameModel.objects.get_or_create(name='FOOD FLAVOUR CONFECTIONERY', head=head)
    ItemNameModel.objects.get_or_create(name='ESSENTIAL OIL', head=head)
    head, bool = ItemHeadModel.objects.get_or_create(name='CONFECTIONERY 3% Restriction')
    ItemNameModel.objects.get_or_create(name='EMULSIFIER', head=head)
    head, bool = ItemHeadModel.objects.get_or_create(name='CONFECTIONERY 2% Restriction')
    ItemNameModel.objects.get_or_create(name='OTHER CONFECTIONERY INGREDIENTS', head=head)
    ItemNameModel.objects.get_or_create(name='CEREALS FLAKES')
    head, bool = ItemHeadModel.objects.get_or_create(name='NAMKEEN 5% Restriction')
    ItemNameModel.objects.get_or_create(name='RELEVANT ADDITIVES DESCRIPTION', head=head)
    head, bool = ItemHeadModel.objects.get_or_create(name='NAMKEEN 3% Restriction')
    ItemNameModel.objects.get_or_create(name='FOOD FLAVOUR NAMKEEN', head=head)
    head, bool = ItemHeadModel.objects.get_or_create(name='PICKLE 3% Restriction')
    ItemNameModel.objects.get_or_create(name='FOOD FLAVOUR PICKLE', head=head)
    head, bool = ItemHeadModel.objects.get_or_create(name='GLASS FORMERS')
    ItemNameModel.objects.get_or_create(name='RUTILE', head=head)
    ItemNameModel.objects.get_or_create(name='INTERMEDIATES NAMELY')
    ItemNameModel.objects.get_or_create(name='SODA ASH')
    ItemNameModel.objects.get_or_create(name='TITANIUM DIOXIDE')
    return None


def set_items():
    from django.apps import apps
    from django.db.models import Q
    LicenseImportItemsModel = apps.get_model('license', 'LicenseImportItemsModel')
    ItemNameModel = apps.get_model('core',
                                   'ItemNameModel')  # Replace with real app and model name
    item, bool = ItemNameModel.objects.get_or_create(name='RUTILE')
    LicenseImportItemsModel.objects.filter(description__icontains='Glass Formers').update(item=item)

    item, bool = ItemNameModel.objects.get_or_create(name='CEREALS FLAKES')
    LicenseImportItemsModel.objects.filter(
        Q(description__icontains='Chickpeas') | Q(description__icontains='lentils') | Q(
            description__icontains='Cereal Flakes') | Q(description__icontains='Green Peas')).update(item=item)
    item, bool = ItemNameModel.objects.get_or_create(name='sugar')
    LicenseImportItemsModel.objects.filter(Q(description__icontains='sugar')).update(item=item)
