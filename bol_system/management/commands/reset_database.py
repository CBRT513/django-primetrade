"""
Reset the entire database to clean state.

Usage:
    python manage.py reset_database

WARNING: This deletes ALL data!
"""

from django.core.management.base import BaseCommand
from bol_system.models import (
    ReleaseLoad, BOL, Release, Carrier, Truck,
    Product, Customer, Warehouse, Lot
)


class Command(BaseCommand):
    help = 'Reset the entire database (deletes all data)'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('⚠️  WARNING: This will delete ALL data!'))
        self.stdout.write('\nDeleting all records...')

        # Delete in correct order (respecting foreign keys)
        count_loads = ReleaseLoad.objects.all().delete()[0]
        self.stdout.write(f'  ✓ Deleted {count_loads} release loads')

        count_bols = BOL.objects.all().delete()[0]
        self.stdout.write(f'  ✓ Deleted {count_bols} BOLs')

        count_releases = Release.objects.all().delete()[0]
        self.stdout.write(f'  ✓ Deleted {count_releases} releases')

        count_trucks = Truck.objects.all().delete()[0]
        self.stdout.write(f'  ✓ Deleted {count_trucks} trucks')

        count_carriers = Carrier.objects.all().delete()[0]
        self.stdout.write(f'  ✓ Deleted {count_carriers} carriers')

        count_lots = Lot.objects.all().delete()[0]
        self.stdout.write(f'  ✓ Deleted {count_lots} lots')

        count_products = Product.objects.all().delete()[0]
        self.stdout.write(f'  ✓ Deleted {count_products} products')

        count_customers = Customer.objects.all().delete()[0]
        self.stdout.write(f'  ✓ Deleted {count_customers} customers')

        count_warehouses = Warehouse.objects.all().delete()[0]
        self.stdout.write(f'  ✓ Deleted {count_warehouses} warehouses')

        self.stdout.write(self.style.SUCCESS('\n✅ Database reset complete!'))
        self.stdout.write('\nNext steps:')
        self.stdout.write('  1. Set BOL counter: python manage.py set_bol_counter 4')
        self.stdout.write('  2. Reload your data')
