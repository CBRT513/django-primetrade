"""
Health check for the BOL system
Usage: python manage.py health_check
"""
import django
from django.core.management.base import BaseCommand
from django.db import connection
from bol_system.models import BOL


class Command(BaseCommand):
    help = 'Report system health: database, BOL count, last BOL, Django version'

    def handle(self, *args, **options):
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("BOL System Health Check"))
        self.stdout.write("=" * 60 + "\n")

        # 1. Database connection status
        self.stdout.write("Database Connection:")
        try:
            connection.ensure_connection()
            self.stdout.write(self.style.SUCCESS("  ✓ Connected"))
            self.stdout.write(f"  Engine: {connection.vendor}")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  ✗ Failed: {e}"))

        # 2. BOL count
        self.stdout.write("\nBOL Statistics:")
        try:
            bol_count = BOL.objects.count()
            self.stdout.write(f"  Total BOLs: {bol_count}")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  ✗ Could not count BOLs: {e}"))

        # 3. Last BOL created date
        try:
            last_bol = BOL.objects.order_by('-created_at').first()
            if last_bol:
                self.stdout.write(f"  Last BOL Created: {last_bol.created_at}")
            else:
                self.stdout.write("  Last BOL Created: No BOLs in system")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  ✗ Could not get last BOL: {e}"))

        # 4. Django version
        self.stdout.write(f"\nDjango Version: {django.get_version()}")

        self.stdout.write("\n" + "=" * 60 + "\n")
