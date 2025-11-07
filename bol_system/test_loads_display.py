"""
Tests for Release Load/BOL History Display Feature

Tests that release detail API includes loads data and summary,
and that the loads display correctly shows BOL information.
"""

import pytest
from decimal import Decimal
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
        name='Test Steel',
        start_tons=Decimal('1000.00')
    )


@pytest.fixture
def test_customer(db):
    """Create a test customer."""
    return Customer.objects.create(
        customer='Test Steel Corp',
        address='456 Steel Ave',
        city='Cincinnati',
        state='OH',
        zip='45202'
    )


@pytest.fixture
def test_carrier(db):
    """Create a test carrier."""
    return Carrier.objects.create(
        carrier_name='Test Steel Logistics',
        contact_name='Jane Hauler',
        phone='555-5678'
    )


@pytest.fixture
def test_truck(db, test_carrier):
    """Create a test truck."""
    return Truck.objects.create(
        carrier=test_carrier,
        truck_number='STL-999',
        trailer_number='TR-888'
    )


@pytest.fixture
def test_release(db, test_customer):
    """Create a test release with 3 loads (mixed status)."""
    release = Release.objects.create(
        release_number='REL-TEST-LOADS',
        customer_id_text='Test Steel Corp',
        customer_ref=test_customer,
        quantity_net_tons=Decimal('75.00'),
        status='OPEN'
    )
    # Create 3 loads: PENDING, SHIPPED, CANCELLED
    ReleaseLoad.objects.create(
        release=release,
        seq=1,
        planned_tons=Decimal('25.000'),
        status='PENDING'
    )
    ReleaseLoad.objects.create(
        release=release,
        seq=2,
        planned_tons=Decimal('25.000'),
        status='PENDING'  # Will be shipped
    )
    ReleaseLoad.objects.create(
        release=release,
        seq=3,
        planned_tons=Decimal('25.000'),
        status='CANCELLED'
    )
    return release


@pytest.mark.django_db
class TestReleaseDetailAPI:
    """Test that release detail API includes loads array."""

    def test_release_detail_includes_loads(
        self, client, test_user, test_release
    ):
        """Release detail API includes loads array with load data."""
        client.force_login(test_user)
        response = client.get(f'/api/releases/{test_release.id}/')

        assert response.status_code == 200
        data = response.json()

        # Assert loads array exists
        assert 'loads' in data
        assert isinstance(data['loads'], list)
        assert len(data['loads']) == 3

        # Assert load fields
        load = data['loads'][0]
        assert 'id' in load
        assert 'seq' in load
        assert 'planned_tons' in load
        assert 'official_weight_tons' in load
        assert 'status' in load
        assert 'bol_number' in load
        assert 'bol_pdf_url' in load
        assert 'bol_created_at' in load


@pytest.mark.django_db
class TestLoadsSummary:
    """Test that loads summary calculates correctly."""

    def test_loads_summary_with_mixed_status(
        self, client, test_user, test_product, test_customer,
        test_carrier, test_truck, test_release
    ):
        """Loads summary shows correct totals with mixed status loads."""
        # Ship the second load with actual tonnage
        load2 = test_release.loads.get(seq=2)
        bol = BOL.objects.create(
            product=test_product,
            product_name=test_product.name,
            date='2025-11-03',
            buyer_name='Test Buyer',
            ship_to='456 Steel Ave, Cincinnati, OH 45202',
            carrier=test_carrier,
            carrier_name=test_carrier.carrier_name,
            truck=test_truck,
            truck_number=test_truck.truck_number,
            trailer_number=test_truck.trailer_number,
            net_tons=Decimal('26.50'),  # Different from planned 25.0
            customer=test_customer
        )
        # Set official weight
        bol.set_official_weight(Decimal('26.50'), 'test@primetrade.com')
        load2.status = 'SHIPPED'
        load2.bol = bol
        load2.save()

        # Get release detail
        client.force_login(test_user)
        response = client.get(f'/api/releases/{test_release.id}/')

        assert response.status_code == 200
        data = response.json()

        # Assert loads_summary exists
        assert 'loads_summary' in data
        summary = data['loads_summary']

        # Assert counts
        assert summary['total_loads'] == 3
        assert summary['shipped_loads'] == 1
        assert summary['pending_loads'] == 1
        assert summary['cancelled_loads'] == 1

        # Assert tonnage (official_weight_tons from BOL used for shipped, not planned)
        assert summary['shipped_tons'] == 26.50
        assert summary['total_tons'] == 75.00


@pytest.mark.django_db
class TestCancelledLoadsIncluded:
    """Test that cancelled loads appear in the list."""

    def test_cancelled_loads_in_loads_array(
        self, client, test_user, test_release
    ):
        """Cancelled loads appear in loads array with correct status."""
        client.force_login(test_user)
        response = client.get(f'/api/releases/{test_release.id}/')

        assert response.status_code == 200
        data = response.json()

        # Find cancelled load
        cancelled_load = next(
            (l for l in data['loads'] if l['status'] == 'CANCELLED'), None
        )
        assert cancelled_load is not None
        assert cancelled_load['seq'] == 3


@pytest.mark.django_db
class TestFullWorkflow:
    """Integration test: Full workflow from release to BOL creation."""

    def test_create_bol_updates_load_display(
        self, client, test_user, test_product, test_customer,
        test_carrier, test_truck, test_release
    ):
        """Creating BOL updates load to SHIPPED in release detail."""
        client.force_login(test_user)

        # Initial state: All loads pending or cancelled
        response = client.get(f'/api/releases/{test_release.id}/')
        data = response.json()
        shipped_before = data['loads_summary']['shipped_loads']
        assert shipped_before == 0

        # Create BOL for first load
        load1 = test_release.loads.get(seq=1)
        bol = BOL.objects.create(
            product=test_product,
            product_name=test_product.name,
            date='2025-11-03',
            buyer_name='Test Buyer',
            ship_to='456 Steel Ave, Cincinnati, OH 45202',
            carrier=test_carrier,
            carrier_name=test_carrier.carrier_name,
            truck=test_truck,
            truck_number=test_truck.truck_number,
            trailer_number=test_truck.trailer_number,
            net_tons=Decimal('25.75'),
            customer=test_customer
        )
        # Set official weight
        bol.set_official_weight(Decimal('25.75'), 'test@primetrade.com')
        load1.status = 'SHIPPED'
        load1.bol = bol
        load1.save()

        # Verify load appears as shipped
        response = client.get(f'/api/releases/{test_release.id}/')
        data = response.json()

        assert data['loads_summary']['shipped_loads'] == 1
        assert data['loads_summary']['shipped_tons'] == 25.75

        # Find shipped load in array
        shipped_load = next(
            (l for l in data['loads'] if l['seq'] == 1), None
        )
        assert shipped_load is not None
        assert shipped_load['status'] == 'SHIPPED'
        assert shipped_load['bol_number'] == bol.bol_number
        assert shipped_load['official_weight_tons'] == '25.75'


    def test_delete_bol_reverts_load_to_pending(
        self, client, test_user, test_product, test_customer,
        test_carrier, test_truck, test_release
    ):
        """Deleting BOL reverts load to PENDING in release detail."""
        client.force_login(test_user)

        # Setup: Create and ship a load
        load1 = test_release.loads.get(seq=1)
        bol = BOL.objects.create(
            product=test_product,
            product_name=test_product.name,
            date='2025-11-03',
            buyer_name='Test Buyer',
            ship_to='456 Steel Ave, Cincinnati, OH 45202',
            carrier=test_carrier,
            carrier_name=test_carrier.carrier_name,
            truck=test_truck,
            truck_number=test_truck.truck_number,
            trailer_number=test_truck.trailer_number,
            net_tons=Decimal('25.75'),
            customer=test_customer
        )
        load1.status = 'SHIPPED'
        load1.bol = bol
        load1.save()

        # Verify shipped
        response = client.get(f'/api/releases/{test_release.id}/')
        data = response.json()
        assert data['loads_summary']['shipped_loads'] == 1

        # Delete BOL
        bol.delete()

        # Verify load reverted to PENDING
        response = client.get(f'/api/releases/{test_release.id}/')
        data = response.json()

        assert data['loads_summary']['shipped_loads'] == 0
        assert data['loads_summary']['pending_loads'] == 2  # Back to 2 pending

        # Find reverted load
        reverted_load = next(
            (l for l in data['loads'] if l['seq'] == 1), None
        )
        assert reverted_load is not None
        assert reverted_load['status'] == 'PENDING'
        assert reverted_load['bol_number'] is None
        assert reverted_load['official_weight_tons'] is None


@pytest.mark.django_db
class TestLoadDetailAPI:
    """Test the load detail API endpoint for BOL pre-fill."""

    def test_load_detail_returns_release_context(
        self, client, test_user, test_release
    ):
        """Load detail API returns load and release data for pre-fill."""
        client.force_login(test_user)
        load1 = test_release.loads.get(seq=1)

        response = client.get(f'/api/releases/load/{load1.id}/')

        assert response.status_code == 200
        data = response.json()

        # Assert structure
        assert 'load' in data
        assert 'release' in data

        # Assert load data
        assert data['load']['id'] == load1.id
        assert data['load']['seq'] == 1

        # Assert release context
        release_data = data['release']
        assert release_data['id'] == test_release.id
        assert release_data['release_number'] == 'REL-TEST-LOADS'
        assert release_data['customer_id_text'] == 'Test Steel Corp'
        assert 'customer_ref_id' in release_data
        assert 'ship_to_street' in release_data
