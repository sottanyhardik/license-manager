"""
Django management command to display cache statistics
======================================================

Usage:
    python manage.py cache_stats
    python manage.py cache_stats --clear
    python manage.py cache_stats --pattern "license_*"
"""

from django.core.cache import cache
from django.core.management.base import BaseCommand

from core.cache_utils import get_cache_stats, invalidate_cache


class Command(BaseCommand):
    help = 'Display Redis cache statistics and manage cache'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear all cache keys',
        )
        parser.add_argument(
            '--pattern',
            type=str,
            help='Clear cache keys matching pattern (e.g., "license_*")',
        )
        parser.add_argument(
            '--keys',
            action='store_true',
            help='List all cache keys',
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write(self.style.WARNING('Clearing all cache...'))
            cache.clear()
            self.stdout.write(self.style.SUCCESS('✅ Cache cleared'))
            return

        if options['pattern']:
            pattern = options['pattern']
            self.stdout.write(f'Clearing cache keys matching: {pattern}')
            count = invalidate_cache(pattern)
            self.stdout.write(self.style.SUCCESS(f'✅ Cleared {count} cache keys'))
            return

        if options['keys']:
            try:
                client = cache.client.get_client()
                keys = client.keys('*')
                self.stdout.write(f'\n📋 Total cache keys: {len(keys)}\n')
                for key in sorted(keys[:100]):  # Show first 100
                    self.stdout.write(f'  - {key.decode() if isinstance(key, bytes) else key}')
                if len(keys) > 100:
                    self.stdout.write(f'\n  ... and {len(keys) - 100} more')
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error: {e}'))
            return

        # Display cache statistics
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.SUCCESS('📊 Redis Cache Statistics'))
        self.stdout.write(self.style.SUCCESS('='*60 + '\n'))

        stats = get_cache_stats()

        if 'error' in stats:
            self.stdout.write(self.style.ERROR(f'❌ Error: {stats["error"]}'))
            return

        # Display stats
        self.stdout.write(f'Cache Hits: {stats["hits"]:,}')
        self.stdout.write(f'Cache Misses: {stats["misses"]:,}')
        self.stdout.write(f'Hit Rate: {stats["hit_rate"]:.2%}')
        self.stdout.write(f'Total Keys: {stats["keys"]:,}')
        self.stdout.write(f'Memory Used: {stats["memory_used"]}')
        self.stdout.write(f'Connected Clients: {stats["connected_clients"]}')

        # Calculate efficiency
        if stats['hit_rate'] > 0.8:
            emoji = '🟢'
            status = 'Excellent'
        elif stats['hit_rate'] > 0.6:
            emoji = '🟡'
            status = 'Good'
        else:
            emoji = '🔴'
            status = 'Needs Improvement'

        self.stdout.write(f'\n{emoji} Cache Performance: {status}')

        self.stdout.write('\n' + '='*60)
        self.stdout.write('\n💡 Tips:')
        if stats['hit_rate'] < 0.5:
            self.stdout.write('  - Hit rate is low. Consider increasing cache TTL.')
            self.stdout.write('  - Check if cache keys are being invalidated too frequently.')
        if stats['keys'] > 10000:
            self.stdout.write('  - Large number of keys. Consider implementing key expiration.')

        self.stdout.write('\n📖 Usage:')
        self.stdout.write('  python manage.py cache_stats                  # Show stats')
        self.stdout.write('  python manage.py cache_stats --keys           # List keys')
        self.stdout.write('  python manage.py cache_stats --clear          # Clear all')
        self.stdout.write('  python manage.py cache_stats --pattern "view:*"  # Clear pattern')
        self.stdout.write('')
