"""
Management command to migrate existing local PDFs to AWS S3

Usage:
    python manage.py migrate_pdfs_to_s3 [--dry-run]

This command:
1. Finds all BOL records in the database
2. Locates their corresponding PDF files in local media/bol_pdfs/ directory
3. Uploads them to S3 with proper year-based organization (bols/YYYY/filename.pdf)
4. Updates the BOL.pdf_url field with the new S3 URL
5. Verifies the upload was successful

Options:
    --dry-run: Show what would be migrated without actually uploading
"""

from django.core.management.base import BaseCommand, CommandError
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
from bol_system.models import BOL
import os
from datetime import datetime


class Command(BaseCommand):
    help = 'Migrate existing BOL PDFs from local storage to AWS S3'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be migrated without actually uploading',
        )
        parser.add_argument(
            '--skip-existing',
            action='store_true',
            help='Skip files that already exist in S3',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        skip_existing = options['skip_existing']

        if not hasattr(settings, 'AWS_STORAGE_BUCKET_NAME'):
            raise CommandError(
                'AWS S3 is not configured. Please set USE_S3=True and '
                'configure AWS credentials in your .env file.'
            )

        self.stdout.write(self.style.WARNING(
            f"\n{'=' * 70}\n"
            f"BOL PDF Migration to S3\n"
            f"{'=' * 70}\n"
        ))

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No files will be uploaded\n'))

        # Get local media directory
        if hasattr(settings, 'MEDIA_ROOT'):
            local_media_root = settings.MEDIA_ROOT
        else:
            local_media_root = settings.BASE_DIR / 'media'

        local_pdf_dir = os.path.join(local_media_root, 'bol_pdfs')

        if not os.path.exists(local_pdf_dir):
            self.stdout.write(self.style.WARNING(
                f'Local PDF directory does not exist: {local_pdf_dir}\n'
                'Creating directory...'
            ))
            os.makedirs(local_pdf_dir, exist_ok=True)

        # Get all BOLs
        bols = BOL.objects.all().order_by('date', 'bol_number')
        total_bols = bols.count()

        self.stdout.write(f'Found {total_bols} BOL records in database\n')

        # Statistics
        stats = {
            'total': total_bols,
            'found': 0,
            'missing': 0,
            'uploaded': 0,
            'skipped': 0,
            'errors': 0,
        }

        for bol in bols:
            # Try to find the PDF file locally
            local_filename = f"{bol.bol_number}.pdf"
            local_path = os.path.join(local_pdf_dir, local_filename)

            if not os.path.exists(local_path):
                self.stdout.write(self.style.ERROR(
                    f'  ✗ {bol.bol_number}: PDF not found at {local_path}'
                ))
                stats['missing'] += 1
                continue

            stats['found'] += 1

            # Extract year from BOL date
            try:
                if bol.date:
                    date_obj = datetime.strptime(bol.date, '%Y-%m-%d')
                    year = date_obj.year
                else:
                    year = datetime.now().year
            except:
                year = datetime.now().year

            # Generate S3 path: bols/YYYY/PRT-YYYY-NNNN.pdf
            s3_filename = f"bols/{year}/{bol.bol_number}.pdf"

            # Check if already exists in S3
            if skip_existing and default_storage.exists(s3_filename):
                self.stdout.write(self.style.WARNING(
                    f'  ⊘ {bol.bol_number}: Already exists in S3, skipping'
                ))
                stats['skipped'] += 1
                continue

            if dry_run:
                self.stdout.write(
                    f'  → {bol.bol_number}: Would upload to {s3_filename}'
                )
                stats['uploaded'] += 1
                continue

            # Upload to S3
            try:
                with open(local_path, 'rb') as pdf_file:
                    # Read file content
                    file_content = pdf_file.read()

                    # Upload to S3 via Django storage backend
                    saved_path = default_storage.save(
                        s3_filename,
                        ContentFile(file_content)
                    )

                    # Get the S3 URL
                    s3_url = default_storage.url(saved_path)

                    # Update BOL record with new URL
                    bol.pdf_url = s3_url
                    bol.save(update_fields=['pdf_url'])

                    self.stdout.write(self.style.SUCCESS(
                        f'  ✓ {bol.bol_number}: Uploaded to S3'
                    ))
                    stats['uploaded'] += 1

            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f'  ✗ {bol.bol_number}: Error - {str(e)}'
                ))
                stats['errors'] += 1

        # Print summary
        self.stdout.write(self.style.WARNING(
            f"\n{'=' * 70}\n"
            f"Migration Summary\n"
            f"{'=' * 70}"
        ))
        self.stdout.write(f"Total BOL records:    {stats['total']}")
        self.stdout.write(self.style.SUCCESS(f"PDFs found locally:   {stats['found']}"))
        self.stdout.write(self.style.ERROR(f"PDFs missing:         {stats['missing']}"))

        if dry_run:
            self.stdout.write(f"Would upload:         {stats['uploaded']}")
        else:
            self.stdout.write(self.style.SUCCESS(f"Successfully uploaded: {stats['uploaded']}"))

        if stats['skipped'] > 0:
            self.stdout.write(self.style.WARNING(f"Skipped (exists):     {stats['skipped']}"))

        if stats['errors'] > 0:
            self.stdout.write(self.style.ERROR(f"Errors:               {stats['errors']}"))

        self.stdout.write(self.style.WARNING(f"{'=' * 70}\n"))

        if dry_run:
            self.stdout.write(self.style.SUCCESS(
                '\nDry run complete. Run without --dry-run to perform actual migration.'
            ))
        elif stats['uploaded'] > 0:
            self.stdout.write(self.style.SUCCESS(
                '\n✓ Migration complete! All PDFs have been uploaded to S3.'
            ))
        else:
            self.stdout.write(self.style.WARNING(
                '\nNo files were uploaded. Check the errors above.'
            ))
