import re
from django.core.management.base import BaseCommand
from bol_system.models import BOL


class Command(BaseCommand):
    help = 'Migrate legacy BOL pdf_url values to pdf_key for signed URL generation'

    def handle(self, *args, **options):
        bols = BOL.objects.exclude(pdf_url__isnull=True).exclude(pdf_url='')
        updated = 0

        for bol in bols:
            key = None
            # If pdf_url already looks like a key, reuse it
            if not bol.pdf_url.startswith('http'):
                key = bol.pdf_url.lstrip('/')
            else:
                match = re.search(r'(media/.+)$', bol.pdf_url)
                if match:
                    key = match.group(1)

            if key:
                bol.pdf_key = key
                bol.save(update_fields=['pdf_key'])
                updated += 1
                self.stdout.write(f"Updated BOL {bol.bol_number}: {bol.pdf_key}")
            else:
                self.stdout.write(self.style.WARNING(
                    f"Could not extract key from BOL {bol.bol_number}: {bol.pdf_url}"
                ))

        self.stdout.write(self.style.SUCCESS(f"Successfully migrated {updated} BOL PDF keys"))
