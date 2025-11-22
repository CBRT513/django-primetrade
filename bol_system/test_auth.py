from django.test import TestCase, Client
from django.contrib.auth.models import User


class AuthenticationTests(TestCase):
    """Test authentication and authorization."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='test@example.com',
            email='test@example.com',
            password='testpass123'
        )

    def test_unauthenticated_redirects_to_login(self):
        """Verify unauthenticated users redirect to login."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_authenticated_user_can_access_home(self):
        """Verify authenticated users can access home."""
        self.client.force_login(self.user)
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

    def test_current_user_endpoint(self):
        """Verify /api/auth/me/ returns user info including role keys."""
        self.client.force_login(self.user)

        # Set up session with primetrade_role (populated by SSO OAuth callback)
        session = self.client.session
        session['primetrade_role'] = {
            'role': 'Admin',
            'permissions': ['view_bol', 'edit_bol'],
            'app_slug': 'primetrade'
        }
        session.save()

        response = self.client.get('/api/auth/me/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['email'], 'test@example.com')
        self.assertTrue(data['is_authenticated'])
        # role fields present (may be None if not set)
        self.assertIn('role', data)
        self.assertIn('permissions', data)
