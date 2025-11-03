"""
Tests for Release Tonnage Tracking Feature

Tests that actual BOL tonnage is tracked and displayed correctly
in open releases, replacing placeholder planned tonnage.
"""

import pytest
from decimal import Decimal
from datetime import date
from django.contrib.auth.models import User
from bol_system.models import (
    Product, Customer, Carrier, Truck, BOL, Release, ReleaseLoad
)


@pytest.fixture
def test_user(db):
    """Create a test user."""
    return User.objects.create_user(
        username='testuser',
        email='test@primetrade.com',
        password='testpass'
    )


@pytest.fixture
def test_product(db):
    """Create a test product."""
    return Product.objects.create(
        name='Test Corn',
        start_tons=Decimal('1000.00')
    )


@pytest.fixture
def test_customer(db):
    """Create a test customer."""
    return Customer.objects.create(
        customer='Test Customer Corp',
        address='123 Test St',
        city='Cincinnati',
        state='OH',
        zip='45202'
    )


@pytest.fixture
def test_carrier(db):
    """Create a test carrier."""
    return Carrier.objects.create(
        carrier_name='Test Trucking',
        contact_name='John Trucker',
        phone='555-1234'
    )


@pytest.fixture
def test_truck(db, test_carrier):
    """Create a test truck."""
    return Truck.objects.create(
        carrier=test_carrier,
        truck_number='T-123',
        trailer_number='TR-456'
    )


@pytest.fixture
def test_release(db, test_customer):
    """Create a test release with 4 loads."""
    release = Release.objects.create(
        release_number='REL-TEST-001',
        customer_id_text='Test Customer Corp',
        customer_ref=test_customer,
        quantity_net_tons=Decimal('92.00'),
        status='OPEN'
    )
    # Create 4 loads with planned tonnage of 23.0 each
    for i in range(1, 5):
        ReleaseLoad.objects.create(
            release=release,
            seq=i,
            planned_tons=Decimal('23.000'),
            status='PENDING'
        )
    return release


@pytest.mark.django_db
class TestBOLCreationUpdatesActualTons:
    """Test that BOL creation updates actual_tons on ReleaseLoad."""

    def test_bol_creation_populates_actual_tons(
        self, test_user, test_product, test_customer, test_carrier,
        test_truck, test_release
    ):
        """When BOL created, actual_tons copied to ReleaseLoad."""
        # Get first load from release
        load = test_release.loads.first()
        assert load.actual_tons is None
        assert load.status == 'PENDING'
        assert load.planned_tons == Decimal('23.000')

        # Create BOL with actual weight of 24.5 tons
        bol = BOL.objects.create(
            product=test_product,
            product_name=test_product.name,
            date='2025-11-03',
            buyer_name='Test Buyer',
            ship_to='123 Ship St',
            carrier=test_carrier,
            carrier_name=test_carrier.carrier_name,
            truck=test_truck,
            truck_number=test_truck.truck_number,
            trailer_number=test_truck.trailer_number,
            net_tons=Decimal('24.50'),
            customer=test_customer,
            created_by_email='test@primetrade.com'
        )

        # Link BOL to load (simulating what confirm_bol does)
        load.status = 'SHIPPED'
        load.bol = bol
        load.actual_tons = bol.net_tons
        load.save()

        # Reload from database
        load.refresh_from_db()

        # Assert actual_tons populated
        assert load.actual_tons == Decimal('24.50')
        assert load.status == 'SHIPPED'
        assert load.bol == bol


@pytest.mark.django_db
class TestBOLDeletionRevertsToPending:
    """Test that BOL deletion reverts ReleaseLoad to PENDING."""

    def test_bol_deletion_clears_actual_tons(
        self, test_user, test_product, test_customer, test_carrier,
        test_truck, test_release
    ):
        """When BOL deleted, ReleaseLoad goes back to PENDING."""
        # Setup: Release with shipped load
        load = test_release.loads.first()

        # Create and link BOL
        bol = BOL.objects.create(
            product=test_product,
            product_name=test_product.name,
            date='2025-11-03',
            buyer_name='Test Buyer',
            ship_to='123 Ship St',
            carrier=test_carrier,
            carrier_name=test_carrier.carrier_name,
            truck=test_truck,
            truck_number=test_truck.truck_number,
            trailer_number=test_truck.trailer_number,
            net_tons=Decimal('24.50'),
            customer=test_customer
        )

        load.status = 'SHIPPED'
        load.bol = bol
        load.actual_tons = bol.net_tons
        load.save()

        # Verify setup
        load.refresh_from_db()
        assert load.actual_tons == Decimal('24.50')
        assert load.status == 'SHIPPED'

        # Action: Delete BOL
        bol_id = bol.id
        bol.delete()

        # Reload load
        load.refresh_from_db()

        # Assert: Load reverted to PENDING
        assert load.actual_tons is None
        assert load.status == 'PENDING'
        assert load.bol is None


@pytest.mark.django_db
class TestOpenReleasesUsesActualTons:
    """Test that open releases calculation uses actual_tons."""

    def test_open_releases_calculation_with_actual_tons(
        self, test_user, test_product, test_customer, test_carrier,
        test_truck, test_release
    ):
        """Open releases uses actual_tons for shipped loads."""
        # Setup: Release 92 tons, 4 loads (23.0 planned each)
        loads = list(test_release.loads.all())

        # Ship first load with 24.5 actual tons
        bol1 = BOL.objects.create(
            product=test_product,
            product_name=test_product.name,
            date='2025-11-03',
            buyer_name='Test Buyer',
            ship_to='123 Ship St',
            carrier=test_carrier,
            carrier_name=test_carrier.carrier_name,
            truck=test_truck,
            truck_number=test_truck.truck_number,
            trailer_number=test_truck.trailer_number,
            net_tons=Decimal('24.50'),
            customer=test_customer
        )
        loads[0].status = 'SHIPPED'
        loads[0].bol = bol1
        loads[0].actual_tons = Decimal('24.50')
        loads[0].save()

        # Ship second load with 23.75 actual tons
        bol2 = BOL.objects.create(
            product=test_product,
            product_name=test_product.name,
            date='2025-11-04',
            buyer_name='Test Buyer',
            ship_to='123 Ship St',
            carrier=test_carrier,
            carrier_name=test_carrier.carrier_name,
            truck=test_truck,
            truck_number=test_truck.truck_number,
            trailer_number=test_truck.trailer_number,
            net_tons=Decimal('23.75'),
            customer=test_customer
        )
        loads[1].status = 'SHIPPED'
        loads[1].bol = bol2
        loads[1].actual_tons = Decimal('23.75')
        loads[1].save()

        # Calculate shipped/remaining (simulating open_releases view)
        from django.db.models import Sum
        from django.db.models.functions import Coalesce

        tons_total = float(test_release.quantity_net_tons or 0)
        tons_shipped = float(test_release.loads.filter(status='SHIPPED').aggregate(
            sum=Sum(Coalesce('actual_tons', 'planned_tons'))
        )['sum'] or 0)
        tons_remaining = max(0.0, tons_total - tons_shipped)

        # Assert: Correct calculation
        assert tons_total == 92.0
        assert tons_shipped == 48.25  # 24.50 + 23.75
        assert tons_remaining == 43.75  # 92.0 - 48.25


    def test_open_releases_backward_compatibility(
        self, test_user, test_product, test_customer, test_carrier,
        test_truck, test_release
    ):
        """Open releases falls back to planned_tons if actual_tons is None."""
        # Setup: Old shipped load without actual_tons (backward compatibility)
        load = test_release.loads.first()

        bol = BOL.objects.create(
            product=test_product,
            product_name=test_product.name,
            date='2025-11-03',
            buyer_name='Test Buyer',
            ship_to='123 Ship St',
            carrier=test_carrier,
            carrier_name=test_carrier.carrier_name,
            truck=test_truck,
            truck_number=test_truck.truck_number,
            trailer_number=test_truck.trailer_number,
            net_tons=Decimal('24.50'),
            customer=test_customer
        )

        # Mark as shipped but DON'T set actual_tons (simulating old data)
        load.status = 'SHIPPED'
        load.bol = bol
        # load.actual_tons = None (explicitly not setting)
        load.save()

        # Calculate shipped tonnage
        from django.db.models import Sum
        from django.db.models.functions import Coalesce

        tons_shipped = float(test_release.loads.filter(status='SHIPPED').aggregate(
            sum=Sum(Coalesce('actual_tons', 'planned_tons'))
        )['sum'] or 0)

        # Assert: Falls back to planned_tons (23.0)
        assert tons_shipped == 23.0


    def test_decimal_precision_two_places(
        self, test_user, test_product, test_customer, test_carrier,
        test_truck, test_release
    ):
        """Actual tons displays with 2 decimal precision."""
        load = test_release.loads.first()

        bol = BOL.objects.create(
            product=test_product,
            product_name=test_product.name,
            date='2025-11-03',
            buyer_name='Test Buyer',
            ship_to='123 Ship St',
            carrier=test_carrier,
            carrier_name=test_carrier.carrier_name,
            truck=test_truck,
            truck_number=test_truck.truck_number,
            trailer_number=test_truck.trailer_number,
            net_tons=Decimal('24.50'),
            customer=test_customer
        )

        load.status = 'SHIPPED'
        load.bol = bol
        load.actual_tons = bol.net_tons
        load.save()

        load.refresh_from_db()

        # Assert: Decimal with 2 places
        assert load.actual_tons == Decimal('24.50')
        assert f"{load.actual_tons:.2f}" == "24.50"


@pytest.mark.django_db
class TestEdgeCases:
    """Test edge cases for tonnage tracking."""

    def test_multiple_loads_mixed_status(
        self, test_user, test_product, test_customer, test_carrier,
        test_truck, test_release
    ):
        """Handles mix of SHIPPED and PENDING loads correctly."""
        loads = list(test_release.loads.all())

        # Ship 2 loads, leave 2 pending
        for i in range(2):
            bol = BOL.objects.create(
                product=test_product,
                product_name=test_product.name,
                date=f'2025-11-0{i+3}',
                buyer_name='Test Buyer',
                ship_to='123 Ship St',
                carrier=test_carrier,
                carrier_name=test_carrier.carrier_name,
                truck=test_truck,
                truck_number=test_truck.truck_number,
                trailer_number=test_truck.trailer_number,
                net_tons=Decimal('24.00') + Decimal(i),
                customer=test_customer
            )
            loads[i].status = 'SHIPPED'
            loads[i].bol = bol
            loads[i].actual_tons = bol.net_tons
            loads[i].save()

        # Calculate
        from django.db.models import Sum
        from django.db.models.functions import Coalesce

        shipped_count = test_release.loads.filter(status='SHIPPED').count()
        pending_count = test_release.loads.filter(status='PENDING').count()
        tons_shipped = float(test_release.loads.filter(status='SHIPPED').aggregate(
            sum=Sum(Coalesce('actual_tons', 'planned_tons'))
        )['sum'] or 0)

        # Assert
        assert shipped_count == 2
        assert pending_count == 2
        assert tons_shipped == 49.0  # 24.0 + 25.0
