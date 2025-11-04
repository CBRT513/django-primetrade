"""
One-time migration command to sync official BOL weights to ReleaseLoad actual_tons
Usage: python manage.py sync_official_weights
"""
from django.core.management.base import BaseCommand
from bol_system.models import BOL, ReleaseLoad


class Command(BaseCommand):
    help = 'Sync official BOL weights to ReleaseLoad actual_tons for existing data'

    def handle(self, *args, **options):
        # Find all BOLs with official weights
        bols_with_official = BOL.objects.filter(official_weight_tons__isnull=False)

        self.stdout.write(f"\nFound {bols_with_official.count()} BOLs with official weights\n")

        updated_count = 0
        skipped_count = 0

        for bol in bols_with_official:
            self.stdout.write(f"\nBOL {bol.bol_number}:")
            self.stdout.write(f"  CBRT Weight: {bol.net_tons} tons")
            self.stdout.write(f"  Official Weight: {bol.official_weight_tons} tons")
            self.stdout.write(f"  Variance: {bol.weight_variance_tons} tons ({bol.weight_variance_percent}%)")

            # Find linked ReleaseLoad
            release_loads = ReleaseLoad.objects.filter(bol=bol)

            if release_loads.exists():
                for rl in release_loads:
                    old_actual = rl.actual_tons

                    # Only update if different
                    if old_actual != bol.official_weight_tons:
                        rl.actual_tons = bol.official_weight_tons
                        rl.save()
                        updated_count += 1
                        self.stdout.write(self.style.SUCCESS(
                            f"  ✓ Updated ReleaseLoad {rl.release.release_number} Load #{rl.seq}"
                        ))
                        self.stdout.write(f"    Old actual_tons: {old_actual}")
                        self.stdout.write(f"    New actual_tons: {rl.actual_tons}")
                    else:
                        skipped_count += 1
                        self.stdout.write(self.style.WARNING(
                            f"  ⊘ Skipped ReleaseLoad {rl.release.release_number} Load #{rl.seq} (already correct)"
                        ))
            else:
                self.stdout.write(self.style.WARNING(
                    f"  ⚠ No ReleaseLoad found for this BOL"
                ))

        self.stdout.write(f"\n{'-'*60}")
        self.stdout.write(self.style.SUCCESS(f"\n✓ Updated {updated_count} ReleaseLoad records"))
        if skipped_count > 0:
            self.stdout.write(self.style.WARNING(f"⊘ Skipped {skipped_count} already-correct records"))
        self.stdout.write(f"\nDone!\n")
