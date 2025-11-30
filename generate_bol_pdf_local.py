#!/usr/bin/env python
"""
Quick script to generate BOL PDF locally for printing
Usage: python generate_bol_pdf_local.py PRT-2025-0009
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'primetrade_project.settings')
django.setup()

from bol_system.models import BOL
from bol_system.pdf_generator import generate_bol_pdf

if len(sys.argv) < 2:
    print("Usage: python generate_bol_pdf_local.py <BOL_NUMBER>")
    print("Example: python generate_bol_pdf_local.py PRT-2025-0009")
    sys.exit(1)

bol_number = sys.argv[1]

try:
    bol = BOL.objects.get(bol_number=bol_number)
    output_path = f"/tmp/{bol_number}.pdf"

    # Generate PDF to local file
    generate_bol_pdf(bol, output_path=output_path)

    print(f"✓ PDF generated successfully!")
    print(f"Location: {output_path}")
    print(f"\nOpening PDF...")

    # Open the PDF automatically
    os.system(f'open "{output_path}"')

except BOL.DoesNotExist:
    print(f"✗ BOL {bol_number} not found in database")
    sys.exit(1)
except Exception as e:
    print(f"✗ Error generating PDF: {e}")
    sys.exit(1)
