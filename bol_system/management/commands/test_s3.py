"""
Test S3 configuration and connectivity
Usage: python manage.py test_s3
"""
from django.core.management.base import BaseCommand
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
import sys


class Command(BaseCommand):
    help = 'Test S3 configuration and connectivity'

    def handle(self, *args, **options):
        self.stdout.write("\n" + "="*60)
        self.stdout.write(self.style.SUCCESS("S3 Configuration Test"))
        self.stdout.write("="*60 + "\n")

        # Check USE_S3 setting
        use_s3 = getattr(settings, 'USE_S3', False)
        self.stdout.write(f"USE_S3: {use_s3}")

        if not use_s3:
            self.stdout.write(self.style.ERROR("\n✗ USE_S3 is False - using local storage"))
            self.stdout.write("\nTo enable S3, set environment variable: USE_S3=True\n")
            return

        # Check AWS credentials
        self.stdout.write("\nAWS Configuration:")
        self.stdout.write(f"  AWS_ACCESS_KEY_ID: {'Set' if getattr(settings, 'AWS_ACCESS_KEY_ID', None) else 'NOT SET'}")
        self.stdout.write(f"  AWS_SECRET_ACCESS_KEY: {'Set' if getattr(settings, 'AWS_SECRET_ACCESS_KEY', None) else 'NOT SET'}")
        self.stdout.write(f"  AWS_STORAGE_BUCKET_NAME: {getattr(settings, 'AWS_STORAGE_BUCKET_NAME', 'NOT SET')}")
        self.stdout.write(f"  AWS_S3_REGION_NAME: {getattr(settings, 'AWS_S3_REGION_NAME', 'NOT SET')}")

        # Check storage backend
        self.stdout.write(f"\nStorage Backend: {default_storage.__class__.__name__}")
        self.stdout.write(f"Storage Module: {default_storage.__class__.__module__}")

        # Test S3 connection
        self.stdout.write("\nTesting S3 connectivity...")
        try:
            # Create a test file
            test_content = ContentFile(b"S3 test file - can be deleted")
            test_path = "test/connectivity_test.txt"

            self.stdout.write(f"  Uploading test file to: {test_path}")
            saved_path = default_storage.save(test_path, test_content)
            self.stdout.write(self.style.SUCCESS(f"  ✓ Upload successful: {saved_path}"))

            # Get URL
            url = default_storage.url(saved_path)
            self.stdout.write(f"  Generated URL: {url[:100]}...")

            # Check if file exists
            exists = default_storage.exists(saved_path)
            self.stdout.write(f"  File exists: {exists}")

            # Delete test file
            default_storage.delete(saved_path)
            self.stdout.write(self.style.SUCCESS("  ✓ Test file deleted"))

            self.stdout.write(self.style.SUCCESS("\n✓ S3 is configured correctly and working!"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n✗ S3 test failed: {str(e)}"))
            self.stdout.write(f"\nError type: {type(e).__name__}")
            import traceback
            self.stdout.write("\nFull traceback:")
            traceback.print_exc()
            sys.exit(1)

        self.stdout.write("\n" + "="*60 + "\n")
