"""
Create a voided placeholder BOL for a skipped number.

Usage:
    python manage.py create_void_placeholder PRT-2025-0013 --reason "Number skipped due to failed creation"
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from bol_system.models import BOL, Tenant


class Command(BaseCommand):
    help = 'Create a voided placeholder BOL for a skipped number'

    def add_arguments(self, parser):
        parser.add_argument(
            'bol_number',
            type=str,
            help='The BOL number to create (e.g., PRT-2025-0013)',
        )
        parser.add_argument(
            '--reason',
            type=str,
            default='Number skipped - placeholder void entry',
            help='Reason for the void',
        )
        parser.add_argument(
            '--tenant-code',
            type=str,
            default='PRT',
            help='Tenant code (default: PRT)',
        )

    def handle(self, *args, **options):
        bol_number = options['bol_number']
        reason = options['reason']
        tenant_code = options['tenant_code']

        # Check if BOL already exists
        if BOL.objects.filter(bol_number=bol_number).exists():
            self.stdout.write(self.style.ERROR(
                f'BOL {bol_number} already exists'
            ))
            return

        # Get tenant
        try:
            tenant = Tenant.objects.get(code=tenant_code)
        except Tenant.DoesNotExist:
            tenant = None
            self.stdout.write(self.style.WARNING(
                f'Tenant {tenant_code} not found, creating without tenant'
            ))

        # Create voided placeholder
        bol = BOL(
            tenant=tenant,
            bol_number=bol_number,
            bol_date=timezone.now().date(),
            date=timezone.now().strftime('%Y-%m-%d'),
            is_void=True,
            voided_at=timezone.now(),
            voided_by='system',
            void_reason=reason,
            product_name='[VOID - Placeholder]',
            buyer_name='[VOID]',
            carrier_name='[VOID]',
            net_tons=0,
        )
        bol.save()

        self.stdout.write(self.style.SUCCESS(
            f'Created voided placeholder BOL: {bol_number}'
        ))
        self.stdout.write(f'  Reason: {reason}')
