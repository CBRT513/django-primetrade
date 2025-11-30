"""
Management command to upload a local BOL PDF to S3 and update the database.

Usage:
    python manage.py upload_bol_pdf PRT-2025-0005 /path/to/PRT-2025-0005.pdf

This is useful for migrating old BOL PDFs that were created before S3 was enabled.
"""

from django.core.management.base import BaseCommand
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from bol_system.models import BOL
import os


class Command(BaseCommand):
    help = 'Upload a local BOL PDF to S3 and update the database record'

    def add_arguments(self, parser):
        parser.add_argument('bol_number', type=str, help='BOL number (e.g., PRT-2025-0005)')
        parser.add_argument('pdf_path', type=str, help='Path to local PDF file')

    def handle(self, *args, **options):
        bol_number = options['bol_number']
        pdf_path = options['pdf_path']

        # Validate file exists
        if not os.path.exists(pdf_path):
            self.stdout.write(self.style.ERROR(f'❌ File not found: {pdf_path}'))
            return

        # Validate BOL exists
        try:
            bol = BOL.objects.get(bol_number=bol_number)
        except BOL.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'❌ BOL not found: {bol_number}'))
            return

        self.stdout.write(f'Found BOL: {bol.bol_number} (ID: {bol.id})')
        self.stdout.write(f'Current URL: {bol.pdf_url if bol.pdf_url else "None"}')

        # Extract year from BOL number (e.g., PRT-2025-0005 -> 2025)
        year = bol_number.split('-')[1]

        # S3 path should be: bols/YYYY/PRT-YYYY-NNNN.pdf
        s3_path = f"bols/{year}/{bol_number}.pdf"

        self.stdout.write(f'\n📤 Uploading to S3: {s3_path}')

        try:
            # Read local file
            with open(pdf_path, 'rb') as f:
                file_content = f.read()

            # Upload to S3
            saved_path = default_storage.save(s3_path, ContentFile(file_content))

            # Get signed URL
            s3_url = default_storage.url(saved_path)

            # Update database
            bol.pdf_url = s3_url
            bol.save()

            self.stdout.write(self.style.SUCCESS(f'\n✅ Success!'))
            self.stdout.write(f'   Uploaded: {saved_path}')
            self.stdout.write(f'   New URL: {s3_url[:100]}...')
            self.stdout.write(f'   Updated database for BOL {bol.bol_number}')

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n❌ Error: {str(e)}'))
            raise
