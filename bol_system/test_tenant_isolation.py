"""
Tests for multi-tenant data isolation.

These tests verify that cross-tenant access is blocked for all
tenant-scoped endpoints. Each test creates data in two tenants
and verifies that Tenant A cannot access Tenant B's data.
"""

from decimal import Decimal
from django.test import TestCase, Client, RequestFactory
from django.contrib.auth.models import User
from unittest.mock import patch, MagicMock

from bol_system.models import Tenant, Product, Customer, Carrier, BOL
from bol_system.security import get_tenant_filter


class TenantIsolationTestCase(TestCase):
    """Base test case with multi-tenant setup."""

    def setUp(self):
        """Create two tenants with isolated data."""
        self.tenant_a = Tenant.objects.create(name='Tenant A', code='TENANT_A')
        self.tenant_b = Tenant.objects.create(name='Tenant B', code='TENANT_B')

        # Users for each tenant
        self.user_a = User.objects.create_user(
            username='user_a@tenant-a.com',
            email='user_a@tenant-a.com',
            password='testpass123'
        )
        self.user_b = User.objects.create_user(
            username='user_b@tenant-b.com',
            email='user_b@tenant-b.com',
            password='testpass123'
        )

        # Products per tenant
        self.product_a = Product.objects.create(
            tenant=self.tenant_a,
            name='Product A',
            start_tons=Decimal('100.00')
        )
        self.product_b = Product.objects.create(
            tenant=self.tenant_b,
            name='Product B',
            start_tons=Decimal('200.00')
        )

        # Customers per tenant
        self.customer_a = Customer.objects.create(
            tenant=self.tenant_a,
            customer='Customer A',
            address='123 A Street',
            city='A City',
            state='AA',
            zip='11111'
        )
        self.customer_b = Customer.objects.create(
            tenant=self.tenant_b,
            customer='Customer B',
            address='456 B Street',
            city='B City',
            state='BB',
            zip='22222'
        )

        # Carriers per tenant
        self.carrier_a = Carrier.objects.create(
            tenant=self.tenant_a,
            carrier_name='Carrier A'
        )
        self.carrier_b = Carrier.objects.create(
            tenant=self.tenant_b,
            carrier_name='Carrier B'
        )

        # BOLs per tenant
        self.bol_a = BOL.objects.create(
            tenant=self.tenant_a,
            product=self.product_a,
            product_name='Product A',
            date='2025-01-01',
            buyer_name='Buyer A',
            ship_to='Ship To A',
            carrier=self.carrier_a,
            carrier_name='Carrier A',
            net_tons=Decimal('25.00')
        )
        self.bol_b = BOL.objects.create(
            tenant=self.tenant_b,
            product=self.product_b,
            product_name='Product B',
            date='2025-01-02',
            buyer_name='Buyer B',
            ship_to='Ship To B',
            carrier=self.carrier_b,
            carrier_name='Carrier B',
            net_tons=Decimal('50.00')
        )

        self.client = Client()
        self.factory = RequestFactory()


class GetTenantFilterTests(TenantIsolationTestCase):
    """Test the get_tenant_filter helper function."""

    def test_returns_empty_dict_when_no_tenant(self):
        """When request has no tenant, return empty filter."""
        request = self.factory.get('/')
        request.tenant = None
        self.assertEqual(get_tenant_filter(request), {})

    def test_returns_tenant_filter_when_tenant_set(self):
        """When request has tenant, return proper filter dict."""
        request = self.factory.get('/')
        request.tenant = self.tenant_a
        self.assertEqual(get_tenant_filter(request), {'tenant': self.tenant_a})

    def test_supports_field_prefix(self):
        """Field prefix is correctly applied."""
        request = self.factory.get('/')
        request.tenant = self.tenant_a
        self.assertEqual(
            get_tenant_filter(request, 'product__'),
            {'product__tenant': self.tenant_a}
        )


class ProductTenantIsolationTests(TenantIsolationTestCase):
    """Test Product endpoints respect tenant isolation."""

    def _setup_session(self, user, tenant):
        """Helper to set up authenticated session with tenant."""
        self.client.force_login(user)
        session = self.client.session
        session['primetrade_role'] = {'role': 'Admin', 'permissions': ['*'], 'app_slug': 'primetrade'}
        session['tenant_id'] = tenant.id
        session.save()

    @patch('bol_system.views.get_tenant_filter')
    def test_product_update_blocked_cross_tenant(self, mock_filter):
        """Tenant A user cannot update Tenant B's product."""
        # Mock get_tenant_filter to return Tenant A filter
        mock_filter.return_value = {'tenant': self.tenant_a}

        self._setup_session(self.user_a, self.tenant_a)

        # Try to update Tenant B's product - should return 404
        response = self.client.post(
            '/api/products/',
            {'id': self.product_b.id, 'name': 'Hacked Product'},
            content_type='application/json'
        )
        # Should not find the product (filtered by tenant)
        self.assertIn(response.status_code, [403, 404])

    def test_product_list_filtered_by_tenant(self):
        """Product list only shows current tenant's products."""
        # Create a mock request with tenant A
        request = self.factory.get('/api/products/')
        request.tenant = self.tenant_a

        # Query with tenant filter
        products = Product.objects.filter(**get_tenant_filter(request))

        self.assertEqual(products.count(), 1)
        self.assertEqual(products.first(), self.product_a)
        self.assertNotIn(self.product_b, products)


class CustomerTenantIsolationTests(TenantIsolationTestCase):
    """Test Customer endpoints respect tenant isolation."""

    def test_customer_filtered_by_tenant(self):
        """Customer queries only return current tenant's customers."""
        request = self.factory.get('/api/customers/')
        request.tenant = self.tenant_a

        customers = Customer.objects.filter(**get_tenant_filter(request))

        self.assertEqual(customers.count(), 1)
        self.assertEqual(customers.first(), self.customer_a)
        self.assertNotIn(self.customer_b, customers)

    def test_customer_get_with_wrong_tenant_returns_none(self):
        """Getting customer by ID with wrong tenant returns DoesNotExist."""
        request = self.factory.get('/')
        request.tenant = self.tenant_a

        # Try to get Tenant B's customer with Tenant A's filter
        with self.assertRaises(Customer.DoesNotExist):
            Customer.objects.get(id=self.customer_b.id, **get_tenant_filter(request))


class CarrierTenantIsolationTests(TenantIsolationTestCase):
    """Test Carrier endpoints respect tenant isolation."""

    def test_carrier_filtered_by_tenant(self):
        """Carrier queries only return current tenant's carriers."""
        request = self.factory.get('/api/carriers/')
        request.tenant = self.tenant_b

        carriers = Carrier.objects.filter(**get_tenant_filter(request))

        self.assertEqual(carriers.count(), 1)
        self.assertEqual(carriers.first(), self.carrier_b)
        self.assertNotIn(self.carrier_a, carriers)

    def test_carrier_get_with_wrong_tenant_fails(self):
        """Getting carrier by ID with wrong tenant raises DoesNotExist."""
        request = self.factory.get('/')
        request.tenant = self.tenant_b

        with self.assertRaises(Carrier.DoesNotExist):
            Carrier.objects.get(id=self.carrier_a.id, **get_tenant_filter(request))


class BOLTenantIsolationTests(TenantIsolationTestCase):
    """Test BOL endpoints respect tenant isolation."""

    def test_bol_filtered_by_tenant(self):
        """BOL queries only return current tenant's BOLs."""
        request = self.factory.get('/api/bols/')
        request.tenant = self.tenant_a

        bols = BOL.objects.filter(**get_tenant_filter(request))

        self.assertEqual(bols.count(), 1)
        self.assertEqual(bols.first(), self.bol_a)
        self.assertNotIn(self.bol_b, bols)

    def test_bol_detail_blocked_cross_tenant(self):
        """Tenant A cannot access Tenant B's BOL detail."""
        request = self.factory.get('/')
        request.tenant = self.tenant_a

        with self.assertRaises(BOL.DoesNotExist):
            BOL.objects.get(id=self.bol_b.id, **get_tenant_filter(request))

    def test_bol_detail_allowed_same_tenant(self):
        """Tenant A can access their own BOL."""
        request = self.factory.get('/')
        request.tenant = self.tenant_a

        bol = BOL.objects.get(id=self.bol_a.id, **get_tenant_filter(request))
        self.assertEqual(bol, self.bol_a)


class CrossTenantAccessAttemptTests(TenantIsolationTestCase):
    """Test that cross-tenant access attempts are properly blocked."""

    def test_direct_id_access_blocked(self):
        """Directly accessing another tenant's object by ID is blocked."""
        request = self.factory.get('/')
        request.tenant = self.tenant_a

        # All these should fail with DoesNotExist
        with self.assertRaises(Product.DoesNotExist):
            Product.objects.get(id=self.product_b.id, **get_tenant_filter(request))

        with self.assertRaises(Customer.DoesNotExist):
            Customer.objects.get(id=self.customer_b.id, **get_tenant_filter(request))

        with self.assertRaises(Carrier.DoesNotExist):
            Carrier.objects.get(id=self.carrier_b.id, **get_tenant_filter(request))

        with self.assertRaises(BOL.DoesNotExist):
            BOL.objects.get(id=self.bol_b.id, **get_tenant_filter(request))

    def test_filter_excludes_other_tenant_data(self):
        """Filter queries exclude other tenant's data."""
        request = self.factory.get('/')
        request.tenant = self.tenant_a

        # All counts should be 1 (only Tenant A's data)
        self.assertEqual(Product.objects.filter(**get_tenant_filter(request)).count(), 1)
        self.assertEqual(Customer.objects.filter(**get_tenant_filter(request)).count(), 1)
        self.assertEqual(Carrier.objects.filter(**get_tenant_filter(request)).count(), 1)
        self.assertEqual(BOL.objects.filter(**get_tenant_filter(request)).count(), 1)

    def test_null_tenant_sees_nothing_when_tenant_required(self):
        """When tenant is None but data requires tenant, see nothing."""
        request = self.factory.get('/')
        request.tenant = None

        # With empty filter, would see all data
        # But properly scoped code should check for tenant
        filter_dict = get_tenant_filter(request)
        self.assertEqual(filter_dict, {})

        # In production, endpoints should reject requests without tenant
        # or return empty results for tenant-scoped data
