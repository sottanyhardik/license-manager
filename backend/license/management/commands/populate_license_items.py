# license/management/commands/populate_license_items.py
from django.core.management.base import BaseCommand
from django.db.models import Q
from license.models import LicenseImportItemsModel
from core.models import ItemNameModel


class Command(BaseCommand):
    help = "Populate items (ManyToMany) in LicenseImportItemsModel based on description and HS code filters"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Do not write any changes; just report what would be updated.",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear all existing items before populating.",
        )

    def get_items_and_filters(self):
        """Returns list of (item_name, query_filter) tuples"""
        return [
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
            ('HYDROSTATIC TRANSMISSION', Q(description__icontains="HYDROSTATIC") & Q(description__icontains="TRANSMISSION")),
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
                description__icontains='Fruit Flavour') | Q(description__icontains='2009') | Q(
                hs_code__hs_code__startswith='2009')) &
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
             (Q(description__icontains="EDIBLE VEGETABLE OIL") | Q(description__icontains="150000") | Q(
                 description__icontains="1509") | Q(description__icontains="Relevant Fats and oils") | Q(
                 hs_code__hs_code__startswith="150000") | Q(description__icontains="Relevant Fats & oils")) & ~Q(
                 license__export_license__norm_class__norm_class='E132')),
            ('PALM KERNEL OIL',
             Q(hs_code__hs_code__startswith="1513") | Q(description__icontains="1513")),
            ('OTHER CONFECTIONERY INGREDIENTS',
             Q(description__icontains="other confectionery ingredients") | Q(
                 description__icontains="nut & nut products") | Q(description__icontains="Fruits and Nuts Product")),
            ('LIQUID GLUCOSE', Q(description__icontains="liquid glucose")),
            ('FRUIT JUICE', (Q(description__icontains="Juice") | Q(description__icontains="Fruit Concentrate") | Q(
                description__icontains='Relevant fruit')) & Q(
                license__export_license__norm_class__norm_class='E1')),
            ('WPC', (
                    (Q(hs_code='3502') | Q(description__icontains='milk')) &
                    Q(license__export_license__norm_class__norm_class='E1')
            )),
            ('FOOD FLAVOUR CONFECTIONERY',
             (Q(description__icontains="relevant food flavour") | Q(description__icontains="FOOD FLAVOUR") | Q(
                 description__icontains="relevant (food flour") | Q(description__icontains="Flavouring Agent") | Q(
                 description__icontains="FOOD FLAVOURS") | Q(description__icontains="Flavours")) &
             Q(license__export_license__norm_class__norm_class='E1')),
            ('CITRIC ACID / TARTARIC ACID',
             (Q(description__icontains="CITRIC ACID") | Q(description__icontains="TARTARIC ACID") | Q(
                 description__icontains="TARTARIC AICD") & Q(
                 license__export_license__norm_class__norm_class='E1'))),
            ('ESSENTIAL OIL',
             Q(description__icontains="relevant essential oils") | Q(description__icontains="ESSENTIAL OILS") | Q(
                 description__icontains="Essential Oil")),
            ('FOOD FLAVOUR NAMKEEN',
             (Q(description__icontains="Relevant Food Additives") & (
                     Q(hs_code__hs_code__startswith="0908") | Q(description__icontains="0908") | Q(
                 description__icontains="Cardamom")) & Q(
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
            ('PAPER BOARD', Q(description__icontains="Paper Board") | Q(description__icontains="PAPPER BOARD")),
            ('PAPER & PAPER', Q(description__icontains="PAPER") & ~Q(description__icontains="BOARD")),
            ('BOPP', Q(description__icontains="BOPP")),
            ('PP', (Q(hs_code__hs_code__startswith='39021000') | Q(description__icontains='Polypropylene') | Q(
                description__icontains='pp granules') | Q(
                description__icontains='packing material') | (
                            Q(description__icontains='PP ') & (
                            Q(hs_code__hs_code__startswith='39') | Q(hs_code__hs_code__startswith='48'))) & (
                            ~Q(description__icontains='7607') | ~Q(description__icontains='ALUMINIUM FOIL') | ~Q(
                        hs_code__hs_code__startswith='7607')))),
            ('HDPE', Q(description__icontains="hdpe") | Q(description__icontains="hdep")),
            ('LDPE', Q(description__icontains="LDPE") | Q(description__icontains="LDEP")),
            ('ALUMINIUM FOIL', Q(description__icontains='7607') | Q(description__icontains='ALUMINIUM FOIL') | Q(
                hs_code__hs_code__startswith='7607')),
            ('COKE', Q(description__icontains="COKE")),
            ('BETEL NUT', Q(description__icontains="BETEL NUT")),
            ('SUPARI WHOLE', Q(description__icontains="SUPARI WHOLE")),
            ('COFFEE BEANS', Q(description__icontains="Coffee Beans")),
            ('RELEVANT ADDITIVES DESCRIPTION',
             Q(description__icontains="RELEVANT ADDITIVES DESCRIPTION") | Q(description__icontains="Methyl Cellulose")),
            ('RELEVANT ADDITIVES DESCRIPTION',
             (Q(description__icontains="Relevant Food Additives") & (Q(description__icontains="TBHQ")) & Q(
                 license__export_license__norm_class__norm_class='E132'))),
        ]

    def handle(self, *args, **opts):
        dry_run = bool(opts.get("dry_run"))
        clear_existing = bool(opts.get("clear"))

        self.stdout.write("Populating items in LicenseImportItemsModel...")
        self.stdout.write(f"Dry run: {dry_run}")
        self.stdout.write("")

        # Clear existing items if requested
        if clear_existing:
            self.stdout.write("Clearing all existing item associations...")
            if not dry_run:
                for import_item in LicenseImportItemsModel.objects.all():
                    import_item.items.clear()
            self.stdout.write(self.style.SUCCESS("✓ Cleared all item associations"))
            self.stdout.write("")

        items_and_filters = self.get_items_and_filters()
        total_filters = len(items_and_filters)
        total_matched = 0
        total_updated = 0

        for idx, (item_name, query_filter) in enumerate(items_and_filters, 1):
            try:
                # Get the item
                item = ItemNameModel.objects.get(name=item_name)

                # Find matching import items
                matching_imports = LicenseImportItemsModel.objects.filter(query_filter)
                match_count = matching_imports.count()

                if match_count > 0:
                    self.stdout.write(
                        f"[{idx}/{total_filters}] {item_name}: {match_count} import items matched"
                    )

                    if not dry_run:
                        # Add item to each matching import item (ManyToMany)
                        for import_item in matching_imports:
                            import_item.items.add(item)

                    total_matched += match_count
                    total_updated += 1

            except ItemNameModel.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(f"[{idx}/{total_filters}] Item '{item_name}' not found in database - skipping")
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"[{idx}/{total_filters}] Error processing '{item_name}': {str(e)}")
                )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"✅ Done. Processed {total_filters} filters | "
                f"Updated {total_updated} item types | "
                f"Matched {total_matched} import items | "
                f"dry_run={dry_run}"
            )
        )
