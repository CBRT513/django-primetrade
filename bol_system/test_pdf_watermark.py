"""
Tests for PDF watermarking functionality
"""
import pytest
from decimal import Decimal
from django.test import TestCase
from django.core.files.storage import default_storage
from bol_system.models import BOL, Product, Customer, Carrier, Truck
from bol_system.pdf_generator import generate_bol_pdf
from bol_system.pdf_watermark import watermark_bol_pdf


class PDFWatermarkTestCase(TestCase):
    """Test PDF watermarking when official weights are set"""

    def setUp(self):
        """Create test fixtures"""
        self.product = Product.objects.create(
            name='Test Steel',
            start_tons=1000
        )
        self.customer = Customer.objects.create(
            customer='Test Customer',
            address='123 Test St',
            city='Test City',
            state='OH',
            zip='45202'
        )
        self.carrier = Carrier.objects.create(
            carrier_name='Test Carrier',
            contact_name='John Doe',
            phone='555-1234'
        )
        self.truck = Truck.objects.create(
            carrier=self.carrier,
            truck_number='TEST-123',
            trailer_number='TRAILER-456'
        )

    def test_watermark_bol_without_official_weight(self):
        """Watermarking should fail if no official weight is set"""
        bol = BOL.objects.create(
            product=self.product,
            customer=self.customer,
            buyer_name='Test Buyer',
            ship_to='123 Ship St\nShip City, OH 45202',
            carrier=self.carrier,
            truck=self.truck,
            truck_number='TEST-123',
            trailer_number='TRAILER-456',
            date='2025-01-15',
            net_tons=Decimal('25.50')
        )

        # Should return None if no official weight
        result = watermark_bol_pdf(bol)
        self.assertIsNone(result)

    def test_watermark_bol_without_pdf(self):
        """Watermarking should fail if no PDF exists"""
        bol = BOL.objects.create(
            product=self.product,
            customer=self.customer,
            buyer_name='Test Buyer',
            ship_to='123 Ship St\nShip City, OH 45202',
            carrier=self.carrier,
            truck=self.truck,
            truck_number='TEST-123',
            trailer_number='TRAILER-456',
            date='2025-01-15',
            net_tons=Decimal('25.50'),
            official_weight_tons=Decimal('25.75')
        )

        # Should return None if no PDF exists
        result = watermark_bol_pdf(bol)
        self.assertIsNone(result)

    def test_set_official_weight_creates_stamped_pdf(self):
        """Setting official weight should automatically create stamped PDF"""
        # Create BOL data
        bol_data = {
            'bolNumber': 'TEST-001',
            'customerPO': 'PO-123',
            'carrierName': 'Test Carrier',
            'truckNumber': 'TEST-123',
            'trailerNumber': 'TRAILER-456',
            'buyerName': 'Test Buyer',
            'shipTo': '123 Ship St\nShip City, OH 45202',
            'productName': 'Test Steel',
            'netTons': 25.50,
            'date': '2025-01-15',
            'releaseNumber': 'REL-001'
        }

        # Generate PDF first
        pdf_url = generate_bol_pdf(bol_data)

        # Create BOL in database
        bol = BOL.objects.create(
            product=self.product,
            customer=self.customer,
            buyer_name='Test Buyer',
            ship_to='123 Ship St\nShip City, OH 45202',
            carrier=self.carrier,
            truck=self.truck,
            truck_number='TEST-123',
            trailer_number='TRAILER-456',
            date='2025-01-15',
            net_tons=Decimal('25.50'),
            pdf_url=pdf_url
        )

        # Verify no stamped PDF initially
        self.assertEqual(bol.stamped_pdf_url, '')

        # Set official weight (should trigger watermarking)
        bol.set_official_weight(Decimal('25.75'), 'test@example.com')

        # Refresh from database
        bol.refresh_from_db()

        # Verify official weight was set
        self.assertEqual(bol.official_weight_tons, Decimal('25.75'))
        self.assertEqual(bol.weight_variance_tons, Decimal('0.25'))

        # Verify stamped PDF was created
        self.assertIsNotNone(bol.stamped_pdf_url)
        self.assertIn('-stamped.pdf', bol.stamped_pdf_url)

        # Verify stamped PDF exists in storage
        stamped_path = bol.stamped_pdf_url.split('?')[0]
        if 'amazonaws.com/' in stamped_path:
            s3_key = stamped_path.split('amazonaws.com/')[-1]
        else:
            s3_key = stamped_path.replace('/media/', '')

        self.assertTrue(default_storage.exists(s3_key),
                       f"Stamped PDF should exist at {s3_key}")

    def test_watermark_preserves_original_pdf(self):
        """Original PDF should remain unchanged after watermarking"""
        # Create BOL data
        bol_data = {
            'bolNumber': 'TEST-002',
            'customerPO': 'PO-456',
            'carrierName': 'Test Carrier',
            'truckNumber': 'TEST-456',
            'trailerNumber': 'TRAILER-789',
            'buyerName': 'Test Buyer 2',
            'shipTo': '456 Ship Ave\nShip Town, OH 45203',
            'productName': 'Test Steel',
            'netTons': 30.00,
            'date': '2025-01-16',
            'releaseNumber': 'REL-002'
        }

        # Generate PDF
        pdf_url = generate_bol_pdf(bol_data)
        original_pdf_url = pdf_url

        # Create BOL
        bol = BOL.objects.create(
            product=self.product,
            customer=self.customer,
            buyer_name='Test Buyer 2',
            ship_to='456 Ship Ave\nShip Town, OH 45203',
            carrier=self.carrier,
            truck=self.truck,
            truck_number='TEST-456',
            trailer_number='TRAILER-789',
            date='2025-01-16',
            net_tons=Decimal('30.00'),
            pdf_url=pdf_url
        )

        # Set official weight
        bol.set_official_weight(Decimal('29.85'), 'test@example.com')
        bol.refresh_from_db()

        # Verify original PDF URL unchanged
        self.assertEqual(bol.pdf_url, original_pdf_url)

        # Verify stamped PDF is different
        self.assertNotEqual(bol.stamped_pdf_url, bol.pdf_url)

        # Verify both PDFs exist
        original_path = bol.pdf_url.split('?')[0]
        if 'amazonaws.com/' in original_path:
            original_key = original_path.split('amazonaws.com/')[-1]
        else:
            original_key = original_path.replace('/media/', '')

        self.assertTrue(default_storage.exists(original_key),
                       "Original PDF should still exist")
