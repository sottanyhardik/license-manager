"""
Management command to refresh materialized views.

Usage:
    python manage.py refresh_materialized_views
    python manage.py refresh_materialized_views --view license_balance_mv
    python manage.py refresh_materialized_views --all
    python manage.py refresh_materialized_views --stats
"""

from django.core.management.base import BaseCommand
from core.materialized_views import (
    refresh_all_materialized_views,
    refresh_materialized_view,
    get_materialized_view_stats,
    check_materialized_view_freshness
)


class Command(BaseCommand):
    help = 'Refresh materialized views'

    def add_arguments(self, parser):
        parser.add_argument(
            '--view',
            type=str,
            help='Specific view to refresh (license_balance_mv, item_balance_mv, dashboard_stats_mv)'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Refresh all materialized views'
        )
        parser.add_argument(
            '--no-concurrent',
            action='store_true',
            help='Refresh without CONCURRENTLY (locks table but faster)'
        )
        parser.add_argument(
            '--stats',
            action='store_true',
            help='Show materialized view statistics'
        )

    def handle(self, *args, **options):
        view_name = options.get('view')
        refresh_all = options.get('all')
        concurrent = not options.get('no_concurrent')
        show_stats = options.get('stats')

        if show_stats:
            self.show_stats()
            return

        if view_name:
            self.stdout.write(f'Refreshing {view_name}...')
            try:
                refresh_materialized_view(view_name, concurrently=concurrent)
                self.stdout.write(self.style.SUCCESS(f'✓ Refreshed {view_name}'))

                # Show freshness
                freshness = check_materialized_view_freshness(view_name)
                if freshness:
                    self.stdout.write(f"Last refreshed: {freshness['last_refreshed']}")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'✗ Failed: {e}'))
                raise

        elif refresh_all:
            self.stdout.write('Refreshing all materialized views...')
            try:
                refresh_all_materialized_views(concurrently=concurrent)
                self.stdout.write(self.style.SUCCESS('✓ All views refreshed'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'✗ Failed: {e}'))
                raise

        else:
            self.stdout.write(self.style.WARNING(
                'Please specify --view <name>, --all, or --stats'
            ))
            self.stdout.write('\nAvailable views:')
            self.stdout.write('  - license_balance_mv')
            self.stdout.write('  - item_balance_mv')
            self.stdout.write('  - dashboard_stats_mv')

    def show_stats(self):
        """Show statistics about materialized views."""
        self.stdout.write(self.style.SUCCESS('\n=== Materialized View Statistics ===\n'))

        try:
            stats = get_materialized_view_stats()
            if not stats:
                self.stdout.write('No statistics available')
                return

            for stat in stats:
                self.stdout.write(f"\nView: {stat['view_name']}")
                self.stdout.write(f"  Size: {stat['size']}")
                self.stdout.write(f"  Rows inserted: {stat['rows_inserted']}")
                self.stdout.write(f"  Rows updated: {stat['rows_updated']}")
                self.stdout.write(f"  Rows deleted: {stat['rows_deleted']}")

                if stat['last_autovacuum']:
                    self.stdout.write(f"  Last autovacuum: {stat['last_autovacuum']}")
                if stat['last_autoanalyze']:
                    self.stdout.write(f"  Last autoanalyze: {stat['last_autoanalyze']}")

            # Check freshness
            self.stdout.write(self.style.SUCCESS('\n=== Freshness Check ===\n'))
            for view in ['license_balance_mv', 'item_balance_mv', 'dashboard_stats_mv']:
                freshness = check_materialized_view_freshness(view)
                if freshness:
                    self.stdout.write(f"{view}: {freshness['last_refreshed']}")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error getting stats: {e}'))
