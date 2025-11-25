"""
Regenerate stamped PDF for a BOL with official weight.

Usage:
    python manage.py restamp_bol PRT-2025-0017
"""
from django.core.management.base import BaseCommand
from bol_system.models import BOL
from bol_system.pdf_watermark import watermark_bol_pdf


class Command(BaseCommand):
    help = 'Regenerate stamped PDF for a BOL'

    def add_arguments(self, parser):
        parser.add_argument('bol_number', help='BOL number (e.g., PRT-2025-0017)')

    def handle(self, *args, **options):
        bol_number = options['bol_number']

        try:
            bol = BOL.objects.get(bol_number=bol_number)
        except BOL.DoesNotExist:
            self.stderr.write(self.style.ERROR(f'BOL {bol_number} not found'))
            return

        if not bol.official_weight_tons:
            self.stderr.write(self.style.ERROR(f'BOL {bol_number} has no official weight set'))
            return

        self.stdout.write(f'BOL: {bol.bol_number}')
        self.stdout.write(f'CBRT Weight: {bol.net_tons} tons')
        self.stdout.write(f'Official Weight: {bol.official_weight_tons} tons')
        self.stdout.write(f'Variance: {bol.weight_variance_tons} tons ({bol.weight_variance_percent}%)')
        self.stdout.write('')
        self.stdout.write('Regenerating stamped PDF...')

        url = watermark_bol_pdf(bol)
        if url:
            bol.stamped_pdf_url = url
            bol.save(update_fields=['stamped_pdf_url'])
            self.stdout.write(self.style.SUCCESS(f'Done! New stamped PDF: {url}'))
        else:
            self.stderr.write(self.style.ERROR('Failed to generate stamped PDF'))
