"""
PDF Comparison Helper for PrimeTrade BOL migration.

Generates BOL PDFs using both generators for visual comparison:
1. ReportLab (legacy standalone format)
2. WeasyPrint (new pigiron template)

Usage:
    python manage.py compare_bol_pdfs --bol-number PRT-2025-0001
    python manage.py compare_bol_pdfs --bol-id 42
    python manage.py compare_bol_pdfs --sample 5  # Compare 5 random BOLs
"""

from django.core.management.base import BaseCommand, CommandError
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Generate BOL PDFs using both generators for visual comparison'

    def add_arguments(self, parser):
        parser.add_argument(
            '--bol-number',
            help='Specific BOL number to compare (e.g., PRT-2025-0001)'
        )
        parser.add_argument(
            '--bol-id',
            type=int,
            help='Specific BOL ID to compare'
        )
        parser.add_argument(
            '--sample',
            type=int,
            default=0,
            help='Number of random BOLs to sample for comparison'
        )
        parser.add_argument(
            '--output-dir',
            default='pdf_comparison',
            help='Output directory for comparison PDFs (default: pdf_comparison)'
        )
        parser.add_argument(
            '--tenant-code',
            default='PRT',
            help='Tenant code filter (default: PRT)'
        )

    def handle(self, *args, **options):
        from bol_system.models import BOL, Tenant

        output_dir = Path(options['output_dir'])
        output_dir.mkdir(parents=True, exist_ok=True)

        # Collect BOLs to compare
        bols = []

        if options['bol_number']:
            try:
                bol = BOL.objects.get(bol_number=options['bol_number'])
                bols.append(bol)
            except BOL.DoesNotExist:
                raise CommandError(f"BOL not found: {options['bol_number']}")

        elif options['bol_id']:
            try:
                bol = BOL.objects.get(id=options['bol_id'])
                bols.append(bol)
            except BOL.DoesNotExist:
                raise CommandError(f"BOL not found with ID: {options['bol_id']}")

        elif options['sample'] > 0:
            # Get random sample of BOLs
            try:
                tenant = Tenant.objects.get(code=options['tenant_code'])
            except Tenant.DoesNotExist:
                tenant = None

            queryset = BOL.objects.filter(is_void=False)
            if tenant:
                queryset = queryset.filter(tenant=tenant)

            bols = list(queryset.order_by('?')[:options['sample']])

            if not bols:
                raise CommandError('No BOLs found for sampling')

        else:
            raise CommandError(
                'Specify --bol-number, --bol-id, or --sample to select BOLs'
            )

        self.stdout.write(f'Comparing {len(bols)} BOL(s)...')
        self.stdout.write(f'Output directory: {output_dir.absolute()}')

        for bol in bols:
            self.compare_bol(bol, output_dir)

        self.stdout.write(self.style.SUCCESS(f'\nComparison complete! Check {output_dir}/'))

    def compare_bol(self, bol, output_dir):
        """Generate both PDF versions for a single BOL."""
        self.stdout.write(f'\n--- {bol.bol_number} ---')

        # Generate ReportLab version (legacy)
        reportlab_path = output_dir / f'{bol.bol_number}_reportlab.pdf'
        try:
            self.generate_reportlab_pdf(bol, reportlab_path)
            self.stdout.write(self.style.SUCCESS(f'  ReportLab: {reportlab_path}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  ReportLab FAILED: {e}'))

        # Generate WeasyPrint version (new)
        weasyprint_path = output_dir / f'{bol.bol_number}_weasyprint.pdf'
        try:
            self.generate_weasyprint_pdf(bol, weasyprint_path)
            self.stdout.write(self.style.SUCCESS(f'  WeasyPrint: {weasyprint_path}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  WeasyPrint FAILED: {e}'))

        # Generate comparison summary
        self.generate_comparison_notes(bol, output_dir)

    def generate_reportlab_pdf(self, bol, output_path):
        """Generate PDF using legacy ReportLab generator."""
        from bol_system.pdf_generator import generate_bol_pdf

        generate_bol_pdf(bol, output_path=str(output_path))

    def generate_weasyprint_pdf(self, bol, output_path):
        """Generate PDF using new WeasyPrint template."""
        from bol_system.services.pigiron_bol_pdf import generate_pigiron_bol_pdf

        pdf_bytes = generate_pigiron_bol_pdf(bol)
        with open(output_path, 'wb') as f:
            f.write(pdf_bytes)

    def generate_comparison_notes(self, bol, output_dir):
        """Write comparison notes for manual review."""
        notes_path = output_dir / f'{bol.bol_number}_notes.txt'

        with open(notes_path, 'w') as f:
            f.write(f"BOL Comparison Notes: {bol.bol_number}\n")
            f.write("=" * 50 + "\n\n")

            f.write("Key Fields to Verify:\n")
            f.write("-" * 30 + "\n")
            f.write(f"BOL Number:     {bol.bol_number}\n")
            f.write(f"Date:           {bol.bol_date or bol.date}\n")
            f.write(f"Product:        {bol.product_name}\n")
            f.write(f"Customer:       {bol.buyer_name}\n")
            f.write(f"Carrier:        {bol.carrier_name}\n")
            f.write(f"Truck:          {bol.truck_number}\n")
            f.write(f"Trailer:        {bol.trailer_number}\n")
            f.write(f"Net Tons:       {bol.net_tons}\n")
            f.write(f"Net Lbs:        {bol.total_weight_lbs}\n")
            f.write(f"Customer PO:    {bol.customer_po or 'N/A'}\n")
            f.write(f"Release:        {bol.release_display or bol.release_number or 'N/A'}\n")

            f.write("\nChemistry:\n")
            f.write("-" * 30 + "\n")
            if bol.lot:
                f.write(f"Lot Code:       {bol.lot.code}\n")
                f.write(f"Chemistry:      {bol.lot.format_chemistry()}\n")
            elif bol.lot_ref:
                f.write(f"Lot Code:       {bol.lot_ref.code}\n")
                f.write(f"Chemistry:      {bol.lot_ref.format_chemistry()}\n")
            else:
                f.write("No lot reference\n")

            f.write("\nShip To:\n")
            f.write("-" * 30 + "\n")
            f.write(f"{bol.ship_to}\n")

            if bol.special_instructions:
                f.write("\nSpecial Instructions:\n")
                f.write("-" * 30 + "\n")
                f.write(f"{bol.special_instructions}\n")

            if bol.care_of_co:
                f.write(f"\nCare Of: {bol.care_of_co}\n")

            f.write("\n" + "=" * 50 + "\n")
            f.write("VISUAL CHECK POINTS:\n")
            f.write("[ ] Header/BOL Number positioning\n")
            f.write("[ ] Ship From address\n")
            f.write("[ ] Consignee (Ship To) formatting\n")
            f.write("[ ] Material/Product section\n")
            f.write("[ ] Chemistry display (if applicable)\n")
            f.write("[ ] Carrier information\n")
            f.write("[ ] Weight table formatting\n")
            f.write("[ ] Special instructions visibility\n")
            f.write("[ ] Signature lines\n")
            f.write("[ ] Overall layout (landscape)\n")
