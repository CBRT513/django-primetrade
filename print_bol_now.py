#!/usr/bin/env python
"""Generate BOL PRT-2025-0009 for immediate printing"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'primetrade_project.settings')
# Use local storage, not S3
os.environ['USE_S3'] = 'False'
django.setup()

from bol_system.pdf_generator import generate_bol_pdf

# BOL data from production database
bol_data = {
    'bol_number': 'PRT-2025-0009',
    'date': '2025-11-11',
    'customer_po': '155811',
    'release_number': '60003-2',
    'carrier_name': 'R&J Trucking',
    'truck_number': '15111',
    'trailer_number': '1666',
    'buyer_name': 'ST. MARYS',
    'ship_to': 'St. Marys Foundry\n405-409 E. South St. Saint Marys, OH 45885',
    'product_name': 'NODULAR PIG IRON',
    'net_tons': 24.30,
    'special_instructions': '',
    'lot_ref': type('Lot', (), {
        'code': '050N711A',
        'c': 4.286,
        'si': 0.025,
        's': 0.011,
        'p': 0.038,
        'mn': 0.027
    })()
}

output_path = "/tmp/PRT-2025-0009.pdf"
generate_bol_pdf(bol_data, output_path=output_path)

print(f"✓ PDF generated: {output_path}")
print("Opening for printing...")
os.system(f'open "{output_path}"')
