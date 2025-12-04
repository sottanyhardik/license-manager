"""
Management command to update exchange rate and recalculate CIF INR values.
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from allotment.models import AllotmentModel


class Command(BaseCommand):
    help = 'Update exchange rate and recalculate CIF INR for allotments and their items'

    def add_arguments(self, parser):
        parser.add_argument(
            '--exchange-rate',
            type=float,
            default=89.5,
            help='Exchange rate to set (default: 89.5)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without actually updating',
        )
        parser.add_argument(
            '--filter-company',
            type=str,
            help='Filter by company name (partial match)',
        )
        parser.add_argument(
            '--filter-type',
            type=str,
            help='Filter by allotment type (e.g., AT, BOE)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        exchange_rate = Decimal(str(options['exchange_rate']))

        # Build queryset with filters
        allotments = AllotmentModel.objects.all()

        if options['filter_company']:
            allotments = allotments.filter(company__name__icontains=options['filter_company'])

        if options['filter_type']:
            allotments = allotments.filter(type=options['filter_type'])

        # Get allotments that have cif_fc but need exchange rate update
        allotments = allotments.filter(is_boe=False).select_related('company')

        count = allotments.count()

        if count == 0:
            self.stdout.write(self.style.WARNING('No allotments found to update'))
            return

        self.stdout.write(f'\nFound {count} allotments to update')
        self.stdout.write(f'Exchange rate: {exchange_rate}')

        if dry_run:
            self.stdout.write(self.style.WARNING('\n=== DRY RUN MODE ===\n'))

            # Show sample of what would be updated
            for allotment in allotments[:10]:
                old_cif_inr = allotment.cif_inr or Decimal('0')
                new_cif_inr = (allotment.cif_fc * exchange_rate).quantize(Decimal('0.01'))

                self.stdout.write(
                    f'\nAllotment ID: {allotment.id}'
                    f'\n  Company: {allotment.company.name}'
                    f'\n  Item: {allotment.item_name}'
                    f'\n  CIF FC: {allotment.cif_fc}'
                    f'\n  Old Exchange Rate: {allotment.exchange_rate or 0}'
                    f'\n  New Exchange Rate: {exchange_rate}'
                    f'\n  Old CIF INR: {old_cif_inr}'
                    f'\n  New CIF INR: {new_cif_inr}'
                )

                # Show items
                items = allotment.allotment_details.filter(cif_fc__gt=0)
                if items.exists():
                    self.stdout.write(f'\n  Items ({items.count()}):')
                    for item in items[:5]:
                        old_item_cif_inr = item.cif_inr or Decimal('0')
                        new_item_cif_inr = (item.cif_fc * exchange_rate).quantize(Decimal('0.01'))
                        self.stdout.write(
                            f'    - Item {item.id}: CIF FC={item.cif_fc}, '
                            f'Old CIF INR={old_item_cif_inr}, New CIF INR={new_item_cif_inr}'
                        )

            if count > 10:
                self.stdout.write(f'\n... and {count - 10} more allotments')

            self.stdout.write(self.style.WARNING('\nRun without --dry-run to apply changes'))
        else:
            # Perform actual update
            self.stdout.write(self.style.SUCCESS('\n=== UPDATING ===\n'))

            updated_allotments = 0
            updated_items = 0

            with transaction.atomic():
                for allotment in allotments:
                    # Update allotment
                    allotment.exchange_rate = exchange_rate
                    allotment.cif_inr = (allotment.cif_fc * exchange_rate).quantize(Decimal('0.01'))
                    allotment.save(update_fields=['exchange_rate', 'cif_inr'])
                    updated_allotments += 1

                    # Update allotment items
                    items = allotment.allotment_details.filter(cif_fc__gt=0)
                    for item in items:
                        item.cif_inr = (item.cif_fc * exchange_rate).quantize(Decimal('0.01'))
                        item.save(update_fields=['cif_inr'])
                        updated_items += 1

                    if updated_allotments % 100 == 0:
                        self.stdout.write(f'  Processed {updated_allotments} allotments...')

            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✓ Successfully updated:'
                    f'\n  - {updated_allotments} allotments'
                    f'\n  - {updated_items} allotment items'
                    f'\n  - Exchange rate set to: {exchange_rate}'
                )
            )
