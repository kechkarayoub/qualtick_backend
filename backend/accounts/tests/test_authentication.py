"""
Test Custom JWT Authentication

Tests that the custom JWT authentication properly handles user logout detection.
"""

import unittest

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import exceptions
from rest_framework.test import APIRequestFactory
from rest_framework_simplejwt.backends import TokenBackend
from rest_framework_simplejwt.token_blacklist.models import (BlacklistedToken,
                                                             OutstandingToken)

from accounts.authentication import JWTAuthentication
from accounts.repositories.user_repository import UserRepository
from accounts.tokens import RefreshToken
from backend.utils import get_db_alias

User = get_user_model()


class CustomJWTAuthenticationTests(TestCase):
    """Test cases for custom JWT authentication with user logout detection."""
    def setUp(self):
        """Set up test data."""
        db_alias = get_db_alias()
        self.user = UserRepository.create_user(
            email='testuser@example.com',
            password='testpass123',
            username='testuser',
            db_alias=db_alias,
        )
        self.auth = JWTAuthentication()
        self.factory = APIRequestFactory()
    def test_authenticate_valid_token(self):
        """Test authentication with valid token."""
        refresh_token = RefreshToken.for_user(self.user)
        access_token = refresh_token.access_token
        request = self.factory.get(
            '/test/', HTTP_AUTHORIZATION=f'Bearer {access_token}'
        )
        result = self.auth.authenticate(request)
        self.assertIsNotNone(result)
        authenticated_user, _validated_token = result
        self.assertEqual(authenticated_user.id, self.user.id)
    def test_authenticate_blacklisted_token(self):
        """Test authentication with user who has been logged out."""
        refresh_token = RefreshToken.for_user(self.user)
        access_token = refresh_token.access_token
        db_alias = get_db_alias()
        # Blacklist the refresh token to simulate logout
        outstanding_token = OutstandingToken.objects.using(db_alias or '').get(jti=refresh_token['jti'])
        BlacklistedToken.objects.using(db_alias or '').create(token=outstanding_token)
        request = self.factory.get('/test/', HTTP_AUTHORIZATION=f'Bearer {access_token}')
        with self.assertRaises(exceptions.AuthenticationFailed) as context:
            self.auth.authenticate(request)
        self.assertIn(
            'Device session has been terminated. Please log in again.',
            str(context.exception)
        )
    def test_authenticate_no_token(self):
        """Test authentication with no token."""
        request = self.factory.get('/test/')
        result = self.auth.authenticate(request)
        self.assertIsNone(result)
    def test_is_user_logged_out_false(self):
        """Test logout checking for active user."""
        db_alias = get_db_alias()
        refresh_token = RefreshToken.for_user(self.user)
        access_token = refresh_token.access_token
        token_backend = TokenBackend(algorithm="HS256", signing_key=settings.SECRET_KEY)
        payload = token_backend.decode(str(access_token), verify=True)
        is_logged_out = self.auth.is_user_logged_out(payload, db_alias=db_alias)
        self.assertFalse(is_logged_out)
    def test_is_user_logged_out_true(self):
        """Test logout checking for user who has been logged out."""
        db_alias = get_db_alias()
        refresh_token = RefreshToken.for_user(self.user)
        access_token = refresh_token.access_token
        # Blacklist the refresh token to simulate logout
        outstanding_token = OutstandingToken.objects.using(db_alias or '').get(jti=refresh_token['jti'])
        BlacklistedToken.objects.using(db_alias or '').create(token=outstanding_token)
        token_backend = TokenBackend(algorithm="HS256", signing_key=settings.SECRET_KEY)
        payload = token_backend.decode(str(access_token), verify=True)
        is_logged_out = self.auth.is_user_logged_out(payload, db_alias=db_alias)
        self.assertTrue(is_logged_out)
    def tearDown(self):
        """Clean up test data."""
        db_alias = get_db_alias()
        self.user.delete(using=db_alias or None)

if __name__ == '__main__':
    unittest.main()
