def null_all_export_items():
    from django.apps import apps
    LicenseExportItemModel = apps.get_model('license', 'LicenseExportItemModel')
    LicenseExportItemModel.objects.all().update(item=None)
    LicenseImportItemsModel = apps.get_model('license', 'LicenseImportItemsModel')
    LicenseImportItemsModel.objects.all().update(item=None)
    SionNormClassModel = apps.get_model('core', 'SionNormClassModel')
    SionNormClassModel.objects.all().update(item=None)
    SIONExportModel = apps.get_model('core', 'SIONExportModel')
    SIONExportModel.objects.all().update(item=None)
    SIONImportModel = apps.get_model('core', 'SIONImportModel')
    SIONImportModel.objects.all().update(item=None)
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


def createItem():
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
    ItemNameModel.objects.get_or_create(name='VEGETABLE SHORTENING', head=head)
    ItemNameModel.objects.get_or_create(name='RBD PALMOLEIN OIL', head=head, unit_price=1)
    ItemNameModel.objects.get_or_create(name='EDIBLE VEGETABLE OIL', head=head, unit_price=10)
    ItemNameModel.objects.get_or_create(name='PALM KERNEL OIL', head=head, unit_price=1)
    head, bool = ItemHeadModel.objects.get_or_create(name='BISCUIT 10% Restriction')
    ItemNameModel.objects.get_or_create(name='EMULSIFIER BISCUITS', head=head)
    ItemNameModel.objects.get_or_create(name='BISCUITS ADDITIVES & INGREDIENTS', head=head)
    ItemNameModel.objects.get_or_create(name='FOOD FLAVOUR BISCUITS', head=head)
    ItemNameModel.objects.get_or_create(name='JUICE', head=head, unit_price=4.07)
    ItemNameModel.objects.get_or_create(name='DIETARY FIBRE', head=head)
    ItemNameModel.objects.get_or_create(name='FRUIT/COCOA', head=head, unit_price=3)
    ItemNameModel.objects.get_or_create(name='LEAVENING AGENT', head=head)
    ItemNameModel.objects.get_or_create(name='STARCH 1108', head=head, unit_price=.8)
    ItemNameModel.objects.get_or_create(name='STARCH 3505', head=head, unit_price=.8)
    head, bool = ItemHeadModel.objects.get_or_create(name='MILK & MILK Product')
    ItemNameModel.objects.get_or_create(name='CHEESE', head=head, unit_price=6.5)
    ItemNameModel.objects.get_or_create(name='WPC', head=head, unit_price=15)
    ItemNameModel.objects.get_or_create(name='SWP', head=head, unit_price=1)
    head, bool = ItemHeadModel.objects.get_or_create(name='PACKING MATERIAL')
    ItemNameModel.objects.get_or_create(name='PP', head=head)
    ItemNameModel.objects.get_or_create(name='HDPE', head=head)
    ItemNameModel.objects.get_or_create(name='LDPE', head=head)
    ItemNameModel.objects.get_or_create(name='BOPP', head=head)
    ItemNameModel.objects.get_or_create(name='PAPER & PAPER', head=head)
    ItemNameModel.objects.get_or_create(name='PAPER BOARD', head=head)
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
    ItemNameModel.objects.get_or_create(name='SANITATION AND CLEANING CHEMICALS')
    head, bool = ItemHeadModel.objects.get_or_create(name='GLASS FORMERS')
    ItemNameModel.objects.get_or_create(name='RUTILE', head=head)
    ItemNameModel.objects.get_or_create(name='INTERMEDIATES NAMELY')
    ItemNameModel.objects.get_or_create(name='SODA ASH')
    ItemNameModel.objects.get_or_create(name='TITANIUM DIOXIDE')
    ItemNameModel.objects.get_or_create(name='WIRING HANRNESS')
    ItemNameModel.objects.get_or_create(name='WHEAT FLOUR')
    ItemNameModel.objects.get_or_create(name='WATER PUMP')
    ItemNameModel.objects.get_or_create(name="'O' Ring")
    ItemNameModel.objects.get_or_create(name='BEARING')
    ItemNameModel.objects.get_or_create(name='ANTI OXIDANT')
    ItemNameModel.objects.get_or_create(name='TURBO CHARGER')
    ItemNameModel.objects.get_or_create(name='FOOD COLOUR')
    ItemNameModel.objects.get_or_create(name='STARTER MOTOR')
    ItemNameModel.objects.get_or_create(name='ALLOY STEEL')
    ItemNameModel.objects.get_or_create(name='CLUTCH ASSEMBLY')
    ItemNameModel.objects.get_or_create(name='SEAT ASSEMBLY')
    ItemNameModel.objects.get_or_create(name='STARTER MOTOR')
    ItemNameModel.objects.get_or_create(name='AUTOMOTIVE BATTERY')
    ItemNameModel.objects.get_or_create(name='BRAKE ASSEMBLY')
    ItemNameModel.objects.get_or_create(name='CITRIC ACID / TARTARIC ACID')
    ItemNameModel.objects.get_or_create(name='REARWHEEL TYRE')
    ItemNameModel.objects.get_or_create(name='RADIATOR')
    ItemNameModel.objects.get_or_create(name='REAR WHEELRIM')
    ItemNameModel.objects.get_or_create(name='SAFETY NEUTRAL SWITCH')
    ItemNameModel.objects.get_or_create(name='OIL SEPERATOR')
    ItemNameModel.objects.get_or_create(name='HOT ROLLED STEEL')
    ItemNameModel.objects.get_or_create(name='COLD ROLLED STEEL')
    ItemNameModel.objects.get_or_create(name='FRONT WHEELRIM')
    ItemNameModel.objects.get_or_create(name='ALTERNATOR')
    ItemNameModel.objects.get_or_create(name='HYDROSTATIC TRANSMISSION')
    ItemNameModel.objects.get_or_create(name='OIL PUMP')
    ItemNameModel.objects.get_or_create(name='OIL SEAL')
    ItemNameModel.objects.get_or_create(name='HYDRAULIC VALVES')
    ItemNameModel.objects.get_or_create(name='HYDRAULIC CYLINDER')
    ItemNameModel.objects.get_or_create(name='HYDRAULIC PUMP')
    ItemNameModel.objects.get_or_create(name='FRONT AXLE')
    ItemNameModel.objects.get_or_create(name='FUEL FILTER')
    ItemNameModel.objects.get_or_create(name='OIL SEPERATOR')
    ItemNameModel.objects.get_or_create(name='INTERNAL COMBUSTION ENGINE')
    ItemNameModel.objects.get_or_create(name='AIR FILTER')
    ItemNameModel.objects.get_or_create(name='COKE')
    ItemNameModel.objects.get_or_create(name='BETEL NUT')
    ItemNameModel.objects.get_or_create(name='SUPARI WHOLE')
    ItemNameModel.objects.get_or_create(name='COFFEE BEANS')
    ItemNameModel.objects.get_or_create(name='LIQUID GLUCOSE')
    ItemNameModel.objects.get_or_create(name='OIL SEALS')
    ItemNameModel.objects.get_or_create(name='SYNCHROPACKS')
    ItemNameModel.objects.get_or_create(name='ALUMINIUM OXIDE, ZINC OXIDE, ZIRCONIUM OXIDE')
    ItemNameModel.objects.get_or_create(name='AUXILIARY VALVES')
    ItemNameModel.objects.get_or_create(name='STABILIZING AGENT')
    ItemNameModel.objects.get_or_create(name='FRONTWHEEL TYRE')
    ItemNameModel.objects.get_or_create(name='FUEL INJECTION PUMP')
    ItemNameModel.objects.get_or_create(name='SODA ASH')
    ItemNameModel.objects.get_or_create(name='CERAMIC COLOUR')
    ItemNameModel.objects.get_or_create(name='SODIUM NITRATE')

    return None


def set_items():
    from django.apps import apps
    from django.db.models import Q

    LicenseImportItemsModel = apps.get_model('license', 'LicenseImportItemsModel')
    ItemNameModel = apps.get_model('core', 'ItemNameModel')

    items_and_filters = [
        ('SODIUM NITRATE', Q(description__icontains="Sodium Nitrate")),
        ('TITANIUM DIOXIDE', Q(description__icontains='Titanium Dioxide')),
        ('RUTILE', Q(description__icontains='Glass Formers') | Q(description__icontains='Formers')),
        ('SODA ASH', Q(description__icontains='Soda Ash')),
        ('ALUMINIUM OXIDE, ZINC OXIDE, ZIRCONIUM OXIDE',
         Q(description__icontains='ALUMINIUM OXIDE') & Q(license__export_license__norm_class__norm_class='A3627')),
        ('WIRING HANRNESS', Q(description__icontains='wiring hanrness')),
        ('WATER PUMP', Q(description__icontains='WATER PUMP')),
        ("'O' Ring", Q(description__icontains="'O' Ring") | Q(hs_code__hs_code__startswith='40169320')),
        ('BEARING', Q(description__icontains="BEARING") | Q(hs_code__hs_code__startswith='8482')),
        ('TURBO CHARGER', Q(description__icontains="TURBO CHARGER")),
        ('STARTER MOTOR', Q(description__icontains="starter motor")),
        ('ALLOY STEEL', Q(description__icontains="alloy steel rod")),
        ('AUTOMOTIVE BATTERY',
         Q(description__icontains="AUTOMOTIVE BATTERY") | Q(description__icontains="AUTOMATIVE BATTERY") | Q(
             description__icontains="Automotive Battery") | Q(description__icontains="Battery Automotive")),
        ('BRAKE ASSEMBLY', Q(description__icontains="Brake Assembly")),
        ('SEAT ASSEMBLY', Q(description__icontains="SEAT ASSEMBLY")),
        ('REARWHEEL TYRE', Q(description__icontains="REARWHEEL TYRE")),
        ('RADIATOR', Q(description__icontains="RADIATOR")),
        ('REAR WHEELRIM', Q(description__icontains="REAR WHEELRIM")),
        ('SAFETY NEUTRAL SWITCH', Q(description__icontains="SAFETY NEUTRAL SWITCH")),
        ('OIL SEPERATOR', Q(description__icontains="OIL SEPERATOR")),
        ('CLUTCH ASSEMBLY', Q(description__icontains="CLUTCH ASSEMBLY")),
        ('HOT ROLLED STEEL', Q(description__icontains="HOT ROLLED") | Q(description__icontains="NON ALLOY")),
        ('COLD ROLLED STEEL', Q(description__icontains="COLD ROLLED")),
        ('FRONT WHEELRIM', Q(description__icontains="FRONT WHEELRIM")),
        ('ALTERNATOR', Q(description__icontains="ALTERNATOR")),
        (
            'HYDROSTATIC TRANSMISSION',
            Q(description__icontains="HYDROSTATIC") & Q(description__icontains="TRANSMISSION")),
        ('OIL PUMP', Q(description__icontains="OIL PUMP")),
        ('OIL SEAL', Q(description__icontains="Oil Seal")),
        ('HYDRAULIC VALVES', Q(description__icontains="HYDRAULIC VALVES")),
        ('HYDRAULIC CYLINDER', Q(description__icontains="HYDRAULIC CYLINDER")),
        ('HYDRAULIC PUMP', Q(description__icontains="HYDRAULIC PUMP")),
        ('FRONT AXLE', Q(description__icontains="FRONT AXLE")),
        ('FUEL FILTER', Q(description__icontains="FUEL FILTER")),
        ('INTERNAL COMBUSTION ENGINE', Q(description__icontains="INTERNAL COMBUSTION ENGINE")),
        ('AIR FILTER', Q(description__icontains="AIR FILTER")),
        ('OIL SEALS', Q(description__icontains="OIL SEALS")),
        ('AUXILIARY VALVES', Q(description__icontains="AUXILIARY VALVES")),
        ('STABILIZING AGENT',
         Q(description__icontains="Stabilizing Agent") & Q(license__export_license__norm_class__norm_class="E1")),
        ('OIL SEALS', Q(description__icontains="Flavours")),
        ('FUEL INJECTION PUMP', Q(description__icontains="FUEL INJECTION PUMP")),
        ('FRONTWHEEL TYRE', Q(description__icontains="frontwheel tyre")),
        ('BISCUITS ADDITIVES & INGREDIENTS',
         Q(description__icontains="BISCUITS ADDITIVES & INGREDIENTS") & ~Q(description__icontains="Yeast")),
        ('CERAMIC COLOUR', Q(description__icontains="CERAMIC COLOUR")),
        ('SYNCHROPACKS', Q(description__icontains="synchropacks")),
        ('SUGAR', Q(description__icontains='sugar')),
        ('WHEAT GLUTEN', Q(description__icontains='GLUTEN') | Q(description__icontains='1109') |
         Q(hs_code__hs_code__startswith='1109')),
        ('WHEAT FLOUR', Q(description__icontains='WHEAT FLOUR') | Q(description__icontains='FLOUR')),
        ('DIETARY FIBRE', Q(description__icontains='Dietary Fibre')),
        ('WPC', Q(description__icontains="Milk & Milk") | Q(description__icontains="3502") | Q(
            hs_code__hs_code__startswith='3502') &
         ~(Q(description__icontains="0406") | Q(hs_code__hs_code__startswith='0406') |
           Q(description__icontains="0404") | Q(hs_code__hs_code__startswith='0404'))),
        ('CHEESE', Q(description__icontains="0406") | Q(hs_code__hs_code__startswith='0406')),
        ('SWP', Q(description__icontains="0404") | Q(hs_code__hs_code__startswith='0404') &
         ~Q(description__icontains="0406") & ~Q(hs_code__hs_code__startswith='0406')),
        ('FRUIT/COCOA', Q(description__icontains="Coco Powder") | Q(description__icontains="Cocoa Powder") |
         Q(description__icontains="18050000") | Q(description__icontains='COCO POWDER') | Q(
            hs_code__hs_code__startswith='18050000') | Q(description__icontains="fruit/cocoa")),
        ('ANTI OXIDANT', Q(description__icontains="Anti oxidant") | Q(description__icontains="Anti oxident")),
        ('FOOD COLOUR', Q(description__icontains="FOOD COLOUR")),
        ('STARCH 1108', Q(description__icontains="1108") | Q(hs_code__hs_code__startswith='1108')),
        ('STARCH 3505', Q(description__icontains="3505") | Q(hs_code__hs_code__startswith='3505') |
         (Q(description__icontains="starch") & (
                 ~Q(hs_code__hs_code__startswith='1108') | ~Q(description__icontains="1108")))),
        ('EMULSIFIER BISCUITS',
         (Q(description__icontains="EMULSIFIER") & Q(license__export_license__norm_class__norm_class='E5'))),
        ('FOOD FLAVOUR BISCUITS',
         (Q(description__icontains="relevant food flavour") | Q(description__icontains="FOOD FLAVOUR") | Q(
             description__icontains="relevant (food flour") | Q(description__icontains="Flavouring Agent") | Q(
             description__icontains=" Flavour Improvers") | Q(
             description__icontains="FOOD FLAVOURS") | Q(description__icontains="Flavours")) &
         Q(license__export_license__norm_class__norm_class='E5')),
        ('JUICE', (Q(description__icontains="Relevant Fruit") | Q(description__icontains='FRUITS FLAVOUR') | Q(
            description__icontains='Fruit Flavour') | Q(description__icontains='2009') | Q(hs_code__hs_code__startswith='2009')) &
         Q(license__export_license__norm_class__norm_class='E5')),
        ('LEAVENING AGENT', Q(description__icontains="LEAVENING AGENT") | Q(description__icontains='leaving agent') | Q(
            description__icontains='Yeast')),
        ('EMULSIFIER',
         (Q(description__icontains="emulsifier") | Q(description__icontains="EMULSIFIER")) & Q(
             license__export_license__norm_class__norm_class='E1')),
        ('VEGETABLE SHORTENING',
         Q(description__icontains="vegetable shortening") | Q(description__icontains="rbd palm oil")),
        ('RBD PALMOLEIN OIL',
         Q(description__icontains="vegetable shortening") | Q(description__icontains="rbd palmolein oil") | Q(
             hs_code__hs_code__startswith="15119020")),
        ('EDIBLE VEGETABLE OIL',
         Q(description__icontains="EDIBLE VEGETABLE OIL") | Q(description__icontains="1500") | Q(
             description__icontains="1509") | Q(description__icontains="Relevant Fats and oils") | Q(
             hs_code__hs_code__startswith="1500") | Q(description__icontains="Relevant Fats & oils")),
        ('PALM KERNEL OIL',
         Q(hs_code__hs_code__startswith="1513") | Q(description__icontains="1513")),
        ('OTHER CONFECTIONERY INGREDIENTS',
         Q(description__icontains="other confectionery ingredients") | Q(
             description__icontains="nut & nut products") | Q(description__icontains="Fruits and Nuts Product")),
        ('LIQUID GLUCOSE', Q(description__icontains="liquid glucose")),
        ('FRUIT JUICE', (Q(description__icontains="Juice") | Q(description__icontains="Fruit Concentrate") | Q(
            description__icontains='Relevant fruit')) & Q(
            license__export_license__norm_class__norm_class='E1')),
        ('FOOD FLAVOUR CONFECTIONERY',
         (Q(description__icontains="relevant food flavour") | Q(description__icontains="FOOD FLAVOUR") | Q(
             description__icontains="relevant (food flour") | Q(description__icontains="Flavouring Agent") | Q(
             description__icontains="FOOD FLAVOURS") | Q(description__icontains="Flavours")) &
         Q(license__export_license__norm_class__norm_class='E1')),
        ('CITRIC ACID / TARTARIC ACID',
         (Q(description__icontains="CITRIC ACID") | Q(description__icontains="TARTARIC ACID") | Q(
             description__icontains="TARTARIC AICD") & Q(
             license__export_license__norm_class__norm_class='E1'))),
        ('EMULSIFIER',
         (Q(description__icontains="EMULSIFIER") & Q(license__export_license__norm_class__norm_class='E1'))),
        ('ESSENTIAL OIL',
         Q(description__icontains="relevant essential oils") | Q(description__icontains="ESSENTIAL OILS") | Q(
             description__icontains="Essential Oil")),
        ('FOOD FLAVOUR NAMKEEN',
         (Q(description__icontains="Relevant Food Additives") & (
                 Q(hs_code__hs_code__startswith="0908") | Q(description__icontains="0908") | Q(
             description__icontains="Cardamom")) & Q(
             license__export_license__norm_class__norm_class='E132'))),
        ('FOOD FLAVOUR NAMKEEN',
         (Q(description__icontains="Relevant Food Additives") & (Q(description__icontains="TBHQ")) & Q(
             license__export_license__norm_class__norm_class='E132'))),
        ('FOOD FLAVOUR NAMKEEN',
         (Q(description__icontains="relevant food flavour") | Q(description__icontains="FOOD FLAVOUR") | Q(
             description__icontains="relevant (food flour") | Q(description__icontains="Flavouring Agent") | Q(
             description__icontains="FOOD FLAVOURS") | Q(description__icontains="Flavours")) &
         Q(license__export_license__norm_class__norm_class='E132')),
        ('CEREALS FLAKES',
         Q(description__icontains='Chickpeas') | Q(description__icontains='lentils') |
         Q(description__icontains='Cereal Flakes') | Q(description__icontains='Green Peas')),
        ('FOOD FLAVOUR PICKLE',
         (Q(description__icontains="relevant food flavour") | Q(description__icontains="FOOD FLAVOUR") | Q(
             description__icontains="relevant (food flour") | Q(description__icontains="Flavouring Agent") | Q(
             description__icontains="FOOD FLAVOURS") | Q(description__icontains="Flavours")) &
         Q(license__export_license__norm_class__norm_class='E126')),
        ('FOOD FLAVOUR PICKLE',
         (Q(description__icontains="Relevant Food Additives") | (
                 Q(hs_code__hs_code__startswith="0908") | Q(description__icontains="0908") | Q(
             description__icontains="Cardamom")) & Q(
             license__export_license__norm_class__norm_class='E126'))),
        ('SANITATION AND CLEANING CHEMICALS', Q(description__icontains='SANITATION AND CLEANING CHEMICALS') &
         Q(license__export_license__norm_class__norm_class='E126')),
        ('ALUMINIUM FOIL', Q(description__icontains='7607') | Q(description__icontains='ALUMINIUM FOIL') | Q(
            hs_code__hs_code__startswith='7607')),
        ('PAPER BOARD', Q(description__icontains="Paper Board") | Q(description__icontains="PAPPER BOARD")),
        ('PAPER & PAPER', Q(description__icontains="PAPER") & ~Q(description__icontains="BOARD")),
        ('BOPP', Q(description__icontains="BOPP")),
        ('PP', (Q(hs_code__hs_code__startswith='39021000') | Q(description__icontains='Polypropylene') | Q(
            description__icontains='pp granules') | Q(
            description__icontains='packing material') | (
                        Q(description__icontains='PP') & (
                        Q(hs_code__hs_code__startswith='39') | Q(hs_code__hs_code__startswith='48'))) & (
                        ~Q(description__icontains='7607') | ~Q(description__icontains='ALUMINIUM FOIL') | ~Q(
                    hs_code__hs_code__startswith='7607')))),
        ('HDPE', Q(description__icontains="hdpe") | Q(description__icontains="hdep")),
        ('LDPE', Q(description__icontains="LDPE") | Q(description__icontains="LDEP")),
        ('COKE', Q(description__icontains="COKE")),
        ('BETEL NUT', Q(description__icontains="BETEL NUT")),
        ('SUPARI WHOLE', Q(description__icontains="SUPARI WHOLE")),
        ('COFFEE BEANS', Q(description__icontains="Coffee Beans")),
    ]

    for item_name, query_filter in items_and_filters:
        item = ItemNameModel.objects.get(name=item_name)
        LicenseImportItemsModel.objects.filter(query_filter).update(item=item)
