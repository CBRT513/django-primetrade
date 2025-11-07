"""
Tests for JWT signature verification in PrimeTrade

These tests verify that:
1. Valid signed tokens from SSO are accepted
2. Forged/tampered tokens are rejected
3. Expired tokens are rejected
4. Tokens with wrong audience are rejected
5. Tokens from wrong issuer are rejected
"""

import jwt
from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from unittest.mock import patch, MagicMock
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import time


class JWTVerificationTests(TestCase):
    """Test JWT signature verification security"""

    def setUp(self):
        self.client = Client()

        # Generate test RSA keypair
        self.private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        self.public_key = self.private_key.public_key()

        # Valid JWT payload
        self.valid_payload = {
            "sub": "test-user-id",
            "email": "test@barge2rail.com",
            "name": "Test User",
            "aud": "test-client-id",
            "iss": "https://sso.barge2rail.com/o",
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,  # 1 hour from now
            "application_roles": {
                "primetrade": {
                    "role": "Admin",
                    "permissions": ["full_access"]
                }
            }
        }

    @override_settings(
        SSO_BASE_URL="https://sso.barge2rail.com",
        SSO_CLIENT_ID="test-client-id",
        SSO_CLIENT_SECRET="test-secret",
        SSO_REDIRECT_URI="https://prt.barge2rail.com/auth/callback/"
    )
    @patch('primetrade_project.auth_views.requests.post')
    @patch('primetrade_project.auth_views.PyJWKClient')
    def test_valid_signed_token_accepted(self, mock_jwk_client, mock_post):
        """Valid JWT with correct signature should be accepted"""
        # Create signed token
        token = jwt.encode(
            self.valid_payload,
            self.private_key,
            algorithm="RS256",
            headers={"kid": "test-key-id"}
        )

        # Mock token exchange response
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "access_token": "test-access-token",
            "id_token": token,
            "refresh_token": "test-refresh-token",
            "expires_in": 900
        }
        mock_post.return_value.ok = True

        # Mock JWKS client to return our public key
        mock_signing_key = MagicMock()
        mock_signing_key.key = self.public_key
        mock_signing_key.key_id = "test-key-id"
        mock_jwk_client.return_value.get_signing_key_from_jwt.return_value = mock_signing_key

        # Simulate SSO callback with valid code
        with patch('primetrade_project.auth_views.validate_and_consume_oauth_state', return_value=(True, None)):
            response = self.client.get('/auth/callback/', {
                'code': 'valid-auth-code',
                'state': 'valid-state'
            })

        # Should redirect successfully (not return 403)
        self.assertEqual(response.status_code, 302)

        # User should be created
        self.assertTrue(User.objects.filter(email="test@barge2rail.com").exists())

    @override_settings(
        SSO_BASE_URL="https://sso.barge2rail.com",
        SSO_CLIENT_ID="test-client-id",
        SSO_CLIENT_SECRET="test-secret",
        SSO_REDIRECT_URI="https://prt.barge2rail.com/auth/callback/"
    )
    @patch('primetrade_project.auth_views.requests.post')
    @patch('primetrade_project.auth_views.PyJWKClient')
    def test_forged_token_rejected(self, mock_jwk_client, mock_post):
        """JWT with modified claims should be rejected (signature invalid)"""
        # Create signed token
        token = jwt.encode(
            self.valid_payload,
            self.private_key,
            algorithm="RS256"
        )

        # Tamper with token by modifying payload
        # Decode without verification, modify, re-encode with different key
        forged_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )

        forged_payload = self.valid_payload.copy()
        forged_payload["application_roles"]["primetrade"]["role"] = "SuperAdmin"  # Escalate privileges

        forged_token = jwt.encode(
            forged_payload,
            forged_key,  # Different key = invalid signature
            algorithm="RS256"
        )

        # Mock token exchange to return forged token
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "access_token": "test-access-token",
            "id_token": forged_token,
            "refresh_token": "test-refresh-token"
        }

        # Mock JWKS client to return our original public key
        mock_signing_key = MagicMock()
        mock_signing_key.key = self.public_key  # Original key, not forged key
        mock_signing_key.key_id = "test-key-id"
        mock_jwk_client.return_value.get_signing_key_from_jwt.return_value = mock_signing_key

        # Simulate SSO callback
        with patch('primetrade_project.auth_views.validate_and_consume_oauth_state', return_value=(True, None)):
            response = self.client.get('/auth/callback/', {
                'code': 'valid-auth-code',
                'state': 'valid-state'
            })

        # Should reject with 403
        self.assertEqual(response.status_code, 403)
        self.assertIn(b'Invalid token signature', response.content)

    @override_settings(
        SSO_BASE_URL="https://sso.barge2rail.com",
        SSO_CLIENT_ID="test-client-id",
        SSO_CLIENT_SECRET="test-secret",
        SSO_REDIRECT_URI="https://prt.barge2rail.com/auth/callback/"
    )
    @patch('primetrade_project.auth_views.requests.post')
    @patch('primetrade_project.auth_views.PyJWKClient')
    def test_expired_token_rejected(self, mock_jwk_client, mock_post):
        """Expired JWT should be rejected"""
        expired_payload = self.valid_payload.copy()
        expired_payload["exp"] = int(time.time()) - 3600  # Expired 1 hour ago

        token = jwt.encode(
            expired_payload,
            self.private_key,
            algorithm="RS256"
        )

        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "access_token": "test-access-token",
            "id_token": token
        }

        mock_signing_key = MagicMock()
        mock_signing_key.key = self.public_key
        mock_jwk_client.return_value.get_signing_key_from_jwt.return_value = mock_signing_key

        with patch('primetrade_project.auth_views.validate_and_consume_oauth_state', return_value=(True, None)):
            response = self.client.get('/auth/callback/', {
                'code': 'valid-auth-code',
                'state': 'valid-state'
            })

        self.assertEqual(response.status_code, 403)
        self.assertIn(b'expired', response.content.lower())

    @override_settings(
        SSO_BASE_URL="https://sso.barge2rail.com",
        SSO_CLIENT_ID="test-client-id",
        SSO_CLIENT_SECRET="test-secret",
        SSO_REDIRECT_URI="https://prt.barge2rail.com/auth/callback/"
    )
    @patch('primetrade_project.auth_views.requests.post')
    @patch('primetrade_project.auth_views.PyJWKClient')
    def test_wrong_audience_rejected(self, mock_jwk_client, mock_post):
        """JWT with wrong audience should be rejected"""
        wrong_aud_payload = self.valid_payload.copy()
        wrong_aud_payload["aud"] = "different-client-id"  # Wrong audience

        token = jwt.encode(
            wrong_aud_payload,
            self.private_key,
            algorithm="RS256"
        )

        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "access_token": "test-access-token",
            "id_token": token
        }

        mock_signing_key = MagicMock()
        mock_signing_key.key = self.public_key
        mock_jwk_client.return_value.get_signing_key_from_jwt.return_value = mock_signing_key

        with patch('primetrade_project.auth_views.validate_and_consume_oauth_state', return_value=(True, None)):
            response = self.client.get('/auth/callback/', {
                'code': 'valid-auth-code',
                'state': 'valid-state'
            })

        self.assertEqual(response.status_code, 403)
        self.assertIn(b'audience', response.content.lower())

    @override_settings(
        SSO_BASE_URL="https://sso.barge2rail.com",
        SSO_CLIENT_ID="test-client-id",
        SSO_CLIENT_SECRET="test-secret",
        SSO_REDIRECT_URI="https://prt.barge2rail.com/auth/callback/"
    )
    @patch('primetrade_project.auth_views.requests.post')
    @patch('primetrade_project.auth_views.PyJWKClient')
    def test_wrong_issuer_rejected(self, mock_jwk_client, mock_post):
        """JWT from wrong issuer should be rejected"""
        wrong_iss_payload = self.valid_payload.copy()
        wrong_iss_payload["iss"] = "https://evil.com/o"  # Wrong issuer

        token = jwt.encode(
            wrong_iss_payload,
            self.private_key,
            algorithm="RS256"
        )

        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "access_token": "test-access-token",
            "id_token": token
        }

        mock_signing_key = MagicMock()
        mock_signing_key.key = self.public_key
        mock_jwk_client.return_value.get_signing_key_from_jwt.return_value = mock_signing_key

        with patch('primetrade_project.auth_views.validate_and_consume_oauth_state', return_value=(True, None)):
            response = self.client.get('/auth/callback/', {
                'code': 'valid-auth-code',
                'state': 'valid-state'
            })

        self.assertEqual(response.status_code, 403)
        self.assertIn(b'issuer', response.content.lower())
