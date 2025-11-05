"""
Management command to regenerate a BOL PDF and upload it to S3.

Usage:
    python manage.py regenerate_bol_pdf PRT-2025-0005

This regenerates the PDF from the BOL data in the database and uploads it to S3.
"""

from django.core.management.base import BaseCommand
from bol_system.models import BOL
from bol_system.pdf_generator import generate_bol_pdf


class Command(BaseCommand):
    help = 'Regenerate a BOL PDF and upload it to S3'

    def add_arguments(self, parser):
        parser.add_argument('bol_number', type=str, help='BOL number (e.g., PRT-2025-0005)')

    def handle(self, *args, **options):
        bol_number = options['bol_number']

        # Validate BOL exists
        try:
            bol = BOL.objects.get(bol_number=bol_number)
        except BOL.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'❌ BOL not found: {bol_number}'))
            return

        self.stdout.write(f'Found BOL: {bol.bol_number} (ID: {bol.id})')
        self.stdout.write(f'Current URL: {bol.pdf_url if bol.pdf_url else "None"}')

        self.stdout.write(f'\n📄 Regenerating PDF from BOL data...')

        try:
            # Generate PDF (will upload to S3 if USE_S3=True)
            new_url = generate_bol_pdf(bol)

            # Update database
            bol.pdf_url = new_url
            bol.save()

            self.stdout.write(self.style.SUCCESS(f'\n✅ Success!'))
            self.stdout.write(f'   New URL: {new_url[:100]}...')
            self.stdout.write(f'   Updated database for BOL {bol.bol_number}')

            # Check if S3
            if 's3.amazonaws.com' in new_url:
                self.stdout.write(self.style.SUCCESS(f'   ✓ PDF uploaded to S3'))
            else:
                self.stdout.write(self.style.WARNING(f'   ⚠ PDF saved locally (S3 not enabled)'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n❌ Error: {str(e)}'))
            raise
