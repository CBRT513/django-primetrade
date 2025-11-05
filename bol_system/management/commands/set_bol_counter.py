"""
Set the BOL number counter to a specific value.

Usage:
    python manage.py set_bol_counter 4

This will make the next BOL number PRT-2025-0005
"""

from django.core.management.base import BaseCommand
from bol_system.models import BOLCounter
from datetime import datetime


class Command(BaseCommand):
    help = 'Set the BOL number counter to a specific value'

    def add_arguments(self, parser):
        parser.add_argument('sequence', type=int, help='Sequence number (e.g., 4 for next BOL to be 0005)')

    def handle(self, *args, **options):
        sequence = options['sequence']
        current_year = datetime.now().year

        counter, created = BOLCounter.objects.get_or_create(
            year=current_year,
            defaults={'sequence': sequence}
        )

        if not created:
            counter.sequence = sequence
            counter.save()

        next_bol = f"PRT-{current_year}-{counter.sequence + 1:04d}"

        self.stdout.write(self.style.SUCCESS(f'✅ BOL counter set to {sequence}'))
        self.stdout.write(f'   Next BOL will be: {next_bol}')
