#!/usr/bin/env python
"""
Generate a sample Hickman Williams branded BOL using recent database data
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'primetrade_project.settings')
django.setup()

from bol_system.models import BOL
from bol_system.pdf_generator_hw_sample import generate_bol_pdf
from datetime import date

def main():
    """Generate HW-branded sample BOL from most recent BOL in database"""

    # Get the most recent BOL
    try:
        latest_bol = BOL.objects.select_related('lot_ref').order_by('-created_at').first()

        if not latest_bol:
            print("No BOLs in database - creating sample data...")
            # Create sample BOL data as dictionary for demo
            latest_bol = {
                'bol_number': 'PRT-2024-1234',
                'date': date.today().strftime('%Y-%m-%d'),
                'customer_po': 'PO-ABC-5678',
                'carrier_name': 'XYZ Transport Inc.',
                'truck_number': 'TRK-456',
                'trailer_number': 'TRL-789',
                'buyer_name': 'Acme Steel Manufacturing',
                'ship_to': 'Acme Steel Manufacturing\n123 Industrial Way\nPittsburgh, PA 15222',
                'product_name': 'Low Carbon Steel Scrap',
                'net_tons': 22.5,
                'release_number': 'REL-2024-001',
                'lot_ref': None,
                'special_instructions': ''
            }
            print("✓ Created sample data for demonstration")
        else:
            print(f"✓ Found BOL: {latest_bol.bol_number}")
            print(f"  Customer: {latest_bol.buyer_name}")
            print(f"  Product: {latest_bol.product_name}")
            print(f"  Weight: {latest_bol.net_tons} tons")
        print()

        # Generate the HW-branded PDF
        output_path = os.path.join(os.getcwd(), 'hw_branded_bol_sample.pdf')

        print("Generating HW-branded BOL...")
        result_path = generate_bol_pdf(latest_bol, output_path=output_path)

        print()
        print("=" * 60)
        print("✓ SUCCESS: HW-branded sample BOL generated")
        print("=" * 60)
        print(f"Location: {result_path}")
        print()
        print("Changes from original BOL:")
        print("  • Logo: Added HW logo (blue shield) in header")
        print("  • c/o Line: Changed from 'c/o PrimeTrade, LLC'")
        print("            to 'c/o Hickman, Williams & Company'")
        print()
        print("Unchanged:")
        print("  • Shipper name: Cincinnati Barge & Rail Terminal, LLC")
        print("  • Address: 1707 Riverside Drive, Cincinnati, Ohio 45202")
        print("  • Phone: (513) 721-1707")
        print("  • All other BOL content (customer, product, weight, etc.)")

    except Exception as e:
        print(f"❌ Error generating sample: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
