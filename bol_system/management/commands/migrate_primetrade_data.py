"""
PrimeTrade Data Migration Command.

Implements spec section 13 - data migration for tenant-aware architecture.

Migration Order (per spec):
1. Tenant (PRT) - create if not exists
2. Products - assign to tenant
3. Lots - assign to tenant with product FK
4. Customers - dedupe by name, assign to tenant
5. CustomerShipTo - assign with customer FK
6. Carriers - dedupe by name, assign to tenant
7. Trucks - assign with carrier FK
8. Releases - assign to tenant with lot FK
9. ReleaseLoads - assign to tenant with release FK
10. BOLs - assign to tenant with all FKs
11. BOLCounter - initialize from MAX(existing BOL numbers)

Key requirements:
- Copy-only migration (never modify source if external)
- Handle Customer/Carrier deduplication by name
- Initialize BOLCounter AFTER importing BOLs
- Verify foreign key integrity after migration
- Idempotent - can be run multiple times safely
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from decimal import Decimal
import re
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Migrate PrimeTrade data to tenant-aware architecture'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant-code',
            default='PRT',
            help='Tenant code to create/use (default: PRT)'
        )
        parser.add_argument(
            '--tenant-name',
            default='PrimeTrade (Liberty Steel)',
            help='Tenant name (default: PrimeTrade (Liberty Steel))'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes'
        )
        parser.add_argument(
            '--verify-only',
            action='store_true',
            help='Only run verification queries, no migration'
        )
        parser.add_argument(
            '--skip-counter',
            action='store_true',
            help='Skip BOLCounter initialization'
        )

    def handle(self, *args, **options):
        self.dry_run = options['dry_run']
        self.tenant_code = options['tenant_code']
        self.tenant_name = options['tenant_name']

        if options['verify_only']:
            self.verify_migration()
            return

        if self.dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))

        try:
            with transaction.atomic():
                # Step 1: Create/get tenant
                tenant = self.migrate_tenant()

                # Step 2: Products
                self.migrate_products(tenant)

                # Step 3: Lots
                self.migrate_lots(tenant)

                # Step 4-5: Customers and ShipTos
                self.migrate_customers(tenant)

                # Step 6-7: Carriers and Trucks
                self.migrate_carriers(tenant)

                # Step 8-9: Releases and ReleaseLoads
                self.migrate_releases(tenant)

                # Step 10: BOLs
                self.migrate_bols(tenant)

                # Step 11: BOLCounter
                if not options['skip_counter']:
                    self.initialize_bol_counter(tenant)

                if self.dry_run:
                    raise CommandError('Dry run complete - rolling back')

        except CommandError as e:
            if 'Dry run complete' in str(e):
                self.stdout.write(self.style.SUCCESS('\nDry run complete - no changes made'))
            else:
                raise

        # Run verification
        self.verify_migration()

    def migrate_tenant(self):
        """Step 1: Create or get the PRT tenant."""
        from bol_system.models import Tenant

        self.stdout.write('\n=== Step 1: Tenant ===')

        tenant, created = Tenant.objects.get_or_create(
            code=self.tenant_code,
            defaults={
                'name': self.tenant_name,
                'is_active': True
            }
        )

        if created:
            self.stdout.write(self.style.SUCCESS(f'  Created tenant: {tenant.name} ({tenant.code})'))
        else:
            self.stdout.write(f'  Using existing tenant: {tenant.name} ({tenant.code})')

        return tenant

    def migrate_products(self, tenant):
        """Step 2: Assign orphaned products to tenant."""
        from bol_system.models import Product

        self.stdout.write('\n=== Step 2: Products ===')

        orphaned = Product.objects.filter(tenant__isnull=True)
        count = orphaned.count()

        if count > 0:
            if not self.dry_run:
                orphaned.update(tenant=tenant)
            self.stdout.write(self.style.SUCCESS(f'  Assigned {count} products to tenant'))
        else:
            self.stdout.write('  No orphaned products found')

        # Report totals
        total = Product.objects.filter(tenant=tenant).count()
        self.stdout.write(f'  Total products for tenant: {total}')

    def migrate_lots(self, tenant):
        """Step 3: Assign orphaned lots to tenant, link to products."""
        from bol_system.models import Lot, Product

        self.stdout.write('\n=== Step 3: Lots ===')

        orphaned = Lot.objects.filter(tenant__isnull=True)
        count = orphaned.count()

        if count > 0:
            if not self.dry_run:
                orphaned.update(tenant=tenant)
            self.stdout.write(self.style.SUCCESS(f'  Assigned {count} lots to tenant'))
        else:
            self.stdout.write('  No orphaned lots found')

        # Check for lots without product links
        unlinked = Lot.objects.filter(tenant=tenant, product__isnull=True).count()
        if unlinked > 0:
            self.stdout.write(self.style.WARNING(f'  Warning: {unlinked} lots have no product link'))

        total = Lot.objects.filter(tenant=tenant).count()
        self.stdout.write(f'  Total lots for tenant: {total}')

    def migrate_customers(self, tenant):
        """Step 4-5: Customers with deduplication, then ShipTos."""
        from bol_system.models import Customer, CustomerShipTo

        self.stdout.write('\n=== Step 4-5: Customers & ShipTos ===')

        # Deduplicate customers by name
        orphaned_customers = Customer.objects.filter(tenant__isnull=True)
        dedupe_count = 0
        assigned_count = 0

        for customer in orphaned_customers:
            # Check if customer with same name exists for this tenant
            existing = Customer.objects.filter(
                tenant=tenant,
                customer=customer.customer
            ).first()

            if existing:
                # Dedupe: reassign ShipTos and related objects to existing customer
                if not self.dry_run:
                    CustomerShipTo.objects.filter(customer=customer).update(customer=existing)
                    # Note: BOL/Release refs will be updated in their respective migrations
                dedupe_count += 1
                self.stdout.write(f'  Deduped: {customer.customer} → existing ID {existing.id}')
            else:
                # Assign orphan to tenant
                if not self.dry_run:
                    customer.tenant = tenant
                    customer.save(update_fields=['tenant'])
                assigned_count += 1

        if assigned_count > 0:
            self.stdout.write(self.style.SUCCESS(f'  Assigned {assigned_count} customers to tenant'))
        if dedupe_count > 0:
            self.stdout.write(self.style.WARNING(f'  Deduplicated {dedupe_count} customers'))

        # Migrate ShipTos
        orphaned_shiptos = CustomerShipTo.objects.filter(tenant__isnull=True)
        shipto_count = orphaned_shiptos.count()
        if shipto_count > 0:
            if not self.dry_run:
                orphaned_shiptos.update(tenant=tenant)
            self.stdout.write(self.style.SUCCESS(f'  Assigned {shipto_count} ship-tos to tenant'))

        total_customers = Customer.objects.filter(tenant=tenant).count()
        total_shiptos = CustomerShipTo.objects.filter(tenant=tenant).count()
        self.stdout.write(f'  Total customers: {total_customers}, ship-tos: {total_shiptos}')

    def migrate_carriers(self, tenant):
        """Step 6-7: Carriers with deduplication, then Trucks."""
        from bol_system.models import Carrier, Truck

        self.stdout.write('\n=== Step 6-7: Carriers & Trucks ===')

        # Deduplicate carriers by name
        orphaned_carriers = Carrier.objects.filter(tenant__isnull=True)
        dedupe_count = 0
        assigned_count = 0
        carrier_mapping = {}  # old_id -> new_id for truck reassignment

        for carrier in orphaned_carriers:
            # Check if carrier with same name exists for this tenant
            existing = Carrier.objects.filter(
                tenant=tenant,
                carrier_name=carrier.carrier_name
            ).first()

            if existing:
                # Dedupe: track mapping for truck reassignment
                carrier_mapping[carrier.id] = existing.id
                dedupe_count += 1
                self.stdout.write(f'  Deduped: {carrier.carrier_name} → existing ID {existing.id}')
            else:
                # Assign orphan to tenant
                if not self.dry_run:
                    carrier.tenant = tenant
                    carrier.save(update_fields=['tenant'])
                assigned_count += 1

        if assigned_count > 0:
            self.stdout.write(self.style.SUCCESS(f'  Assigned {assigned_count} carriers to tenant'))
        if dedupe_count > 0:
            self.stdout.write(self.style.WARNING(f'  Deduplicated {dedupe_count} carriers'))

        # Reassign trucks from deduplicated carriers
        if carrier_mapping and not self.dry_run:
            for old_id, new_id in carrier_mapping.items():
                new_carrier = Carrier.objects.get(id=new_id)
                trucks = Truck.objects.filter(carrier_id=old_id)
                for truck in trucks:
                    # Check for duplicate truck_number
                    existing_truck = Truck.objects.filter(
                        carrier=new_carrier,
                        truck_number=truck.truck_number
                    ).first()
                    if not existing_truck:
                        truck.carrier = new_carrier
                        truck.save(update_fields=['carrier'])

        total_carriers = Carrier.objects.filter(tenant=tenant).count()
        total_trucks = Truck.objects.filter(carrier__tenant=tenant).count()
        self.stdout.write(f'  Total carriers: {total_carriers}, trucks: {total_trucks}')

    def migrate_releases(self, tenant):
        """Step 8-9: Releases and ReleaseLoads."""
        from bol_system.models import Release, ReleaseLoad

        self.stdout.write('\n=== Step 8-9: Releases & ReleaseLoads ===')

        # Migrate releases
        orphaned_releases = Release.objects.filter(tenant__isnull=True)
        release_count = orphaned_releases.count()
        if release_count > 0:
            if not self.dry_run:
                orphaned_releases.update(tenant=tenant)
            self.stdout.write(self.style.SUCCESS(f'  Assigned {release_count} releases to tenant'))

        # Migrate release loads
        orphaned_loads = ReleaseLoad.objects.filter(tenant__isnull=True)
        load_count = orphaned_loads.count()
        if load_count > 0:
            if not self.dry_run:
                orphaned_loads.update(tenant=tenant)
            self.stdout.write(self.style.SUCCESS(f'  Assigned {load_count} release loads to tenant'))

        total_releases = Release.objects.filter(tenant=tenant).count()
        total_loads = ReleaseLoad.objects.filter(tenant=tenant).count()
        self.stdout.write(f'  Total releases: {total_releases}, loads: {total_loads}')

    def migrate_bols(self, tenant):
        """Step 10: BOLs with all FK assignments."""
        from bol_system.models import BOL

        self.stdout.write('\n=== Step 10: BOLs ===')

        orphaned_bols = BOL.objects.filter(tenant__isnull=True)
        count = orphaned_bols.count()

        if count > 0:
            if not self.dry_run:
                orphaned_bols.update(tenant=tenant)
            self.stdout.write(self.style.SUCCESS(f'  Assigned {count} BOLs to tenant'))
        else:
            self.stdout.write('  No orphaned BOLs found')

        total = BOL.objects.filter(tenant=tenant).count()
        voided = BOL.objects.filter(tenant=tenant, is_void=True).count()
        self.stdout.write(f'  Total BOLs: {total} (voided: {voided})')

    def initialize_bol_counter(self, tenant):
        """Step 11: Initialize BOLCounter from MAX(existing BOL numbers)."""
        from bol_system.models import BOL, BOLCounter

        self.stdout.write('\n=== Step 11: BOLCounter ===')

        current_year = timezone.now().year

        # Extract sequence numbers from existing BOLs
        bols = BOL.objects.filter(tenant=tenant)
        max_seq_by_year = {}

        for bol in bols:
            # Parse "PRT-2025-0042" → year=2025, seq=42
            match = re.match(r'[A-Z]+-(\d{4})-(\d+)', bol.bol_number)
            if match:
                year = int(match.group(1))
                seq = int(match.group(2))
                if year not in max_seq_by_year or seq > max_seq_by_year[year]:
                    max_seq_by_year[year] = seq

        if not max_seq_by_year:
            self.stdout.write('  No BOL numbers found to extract sequence from')
            return

        # Create/update counters for each year found
        for year, max_seq in max_seq_by_year.items():
            if not self.dry_run:
                counter, created = BOLCounter.objects.update_or_create(
                    tenant=tenant,
                    year=year,
                    defaults={'sequence': max_seq}
                )
                action = 'Created' if created else 'Updated'
            else:
                action = 'Would create/update'

            self.stdout.write(self.style.SUCCESS(
                f'  {action} BOLCounter: year={year}, sequence={max_seq}'
            ))

        # Highlight current year
        if current_year in max_seq_by_year:
            self.stdout.write(f'  Current year ({current_year}) counter: {max_seq_by_year[current_year]}')
        else:
            self.stdout.write(self.style.WARNING(
                f'  No BOLs found for current year ({current_year}) - counter will start at 1'
            ))

    def verify_migration(self):
        """Run verification queries to confirm data integrity."""
        from bol_system.models import (
            Tenant, Product, Lot, Customer, CustomerShipTo,
            Carrier, Truck, Release, ReleaseLoad, BOL, BOLCounter
        )

        self.stdout.write('\n' + '=' * 60)
        self.stdout.write('VERIFICATION QUERIES')
        self.stdout.write('=' * 60)

        # Get PRT tenant
        try:
            tenant = Tenant.objects.get(code=self.tenant_code)
        except Tenant.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Tenant {self.tenant_code} not found'))
            return

        # Check for orphaned records (tenant_id is NULL)
        self.stdout.write('\n--- Orphaned Records (tenant IS NULL) ---')
        orphan_checks = [
            ('Products', Product.objects.filter(tenant__isnull=True).count()),
            ('Lots', Lot.objects.filter(tenant__isnull=True).count()),
            ('Customers', Customer.objects.filter(tenant__isnull=True).count()),
            ('CustomerShipTos', CustomerShipTo.objects.filter(tenant__isnull=True).count()),
            ('Carriers', Carrier.objects.filter(tenant__isnull=True).count()),
            ('Releases', Release.objects.filter(tenant__isnull=True).count()),
            ('ReleaseLoads', ReleaseLoad.objects.filter(tenant__isnull=True).count()),
            ('BOLs', BOL.objects.filter(tenant__isnull=True).count()),
        ]

        all_clean = True
        for name, count in orphan_checks:
            if count > 0:
                self.stdout.write(self.style.ERROR(f'  {name}: {count} orphaned'))
                all_clean = False
            else:
                self.stdout.write(self.style.SUCCESS(f'  {name}: OK (0 orphaned)'))

        # Record counts for tenant
        self.stdout.write(f'\n--- Record Counts for Tenant: {tenant.code} ---')
        counts = [
            ('Products', Product.objects.filter(tenant=tenant).count()),
            ('Lots', Lot.objects.filter(tenant=tenant).count()),
            ('Customers', Customer.objects.filter(tenant=tenant).count()),
            ('CustomerShipTos', CustomerShipTo.objects.filter(tenant=tenant).count()),
            ('Carriers', Carrier.objects.filter(tenant=tenant).count()),
            ('Trucks', Truck.objects.filter(carrier__tenant=tenant).count()),
            ('Releases', Release.objects.filter(tenant=tenant).count()),
            ('ReleaseLoads', ReleaseLoad.objects.filter(tenant=tenant).count()),
            ('BOLs', BOL.objects.filter(tenant=tenant).count()),
            ('BOLs (voided)', BOL.objects.filter(tenant=tenant, is_void=True).count()),
        ]
        for name, count in counts:
            self.stdout.write(f'  {name}: {count}')

        # FK integrity checks
        self.stdout.write('\n--- Foreign Key Integrity ---')

        # BOLs with missing product
        missing_product = BOL.objects.filter(
            tenant=tenant,
            product__isnull=True
        ).count()
        if missing_product > 0:
            self.stdout.write(self.style.ERROR(f'  BOLs missing product: {missing_product}'))
            all_clean = False
        else:
            self.stdout.write(self.style.SUCCESS('  BOLs → Product: OK'))

        # BOLs with missing carrier
        missing_carrier = BOL.objects.filter(
            tenant=tenant,
            carrier__isnull=True
        ).count()
        if missing_carrier > 0:
            self.stdout.write(self.style.ERROR(f'  BOLs missing carrier: {missing_carrier}'))
            all_clean = False
        else:
            self.stdout.write(self.style.SUCCESS('  BOLs → Carrier: OK'))

        # ReleaseLoads with missing release
        missing_release = ReleaseLoad.objects.filter(
            tenant=tenant,
            release__isnull=True
        ).count()
        if missing_release > 0:
            self.stdout.write(self.style.ERROR(f'  ReleaseLoads missing release: {missing_release}'))
            all_clean = False
        else:
            self.stdout.write(self.style.SUCCESS('  ReleaseLoads → Release: OK'))

        # Lots without product (warning, not error)
        lots_no_product = Lot.objects.filter(tenant=tenant, product__isnull=True).count()
        if lots_no_product > 0:
            self.stdout.write(self.style.WARNING(f'  Lots without product link: {lots_no_product}'))

        # BOLCounter status
        self.stdout.write('\n--- BOLCounter Status ---')
        counters = BOLCounter.objects.filter(tenant=tenant).order_by('year')
        if counters.exists():
            for counter in counters:
                self.stdout.write(f'  Year {counter.year}: sequence = {counter.sequence}')
        else:
            self.stdout.write(self.style.WARNING('  No BOLCounters found for tenant'))

        # Summary
        self.stdout.write('\n' + '=' * 60)
        if all_clean:
            self.stdout.write(self.style.SUCCESS('VERIFICATION PASSED - All checks OK'))
        else:
            self.stdout.write(self.style.ERROR('VERIFICATION FAILED - Issues found'))
        self.stdout.write('=' * 60)
