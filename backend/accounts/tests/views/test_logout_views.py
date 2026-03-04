"""Test logout views"""
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken, OutstandingToken)

from accounts.models import User
from accounts.repositories import UserRepository
from accounts.tokens import RefreshToken
from backend.utils import get_db_alias


class LogoutViewTest(TestCase):
    """Test cases for logout API view."""
    def setUp(self):
        """Set up test data."""
        db_alias = get_db_alias()
        self.client = APIClient()
        self.user = UserRepository.create_user(
            username='logoutuser',
            email='logout@example.com',
            password='password123',
            is_active=True,
            current_language='en',
            db_alias=db_alias,
        )
        self.url = '/accounts/logout/'
    def test_logout_success(self):
        """Test successful logout with valid refresh token."""
        # First authenticate and get tokens
        refresh_token = RefreshToken.for_user(self.user)
        # Authenticate the client
        self.client.force_authenticate(user=self.user)
        data = {
            'refresh_token': str(refresh_token),
            'selected_language': 'en'
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertIn('successfully logged out', response.data['message'].lower())
    def test_logout_success_with_all_devices(self):
        """Test logout from all devices."""
        refresh_token = RefreshToken.for_user(self.user)
        self.client.force_authenticate(user=self.user)
        data = {
            'refresh_token': str(refresh_token),
            'logout_all_devices': True,
            'selected_language': 'en'
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
    def test_logout_missing_refresh_token(self):
        """Test logout without providing refresh token."""
        self.client.force_authenticate(user=self.user)
        data = {
            'selected_language': 'en'
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['success'])
        self.assertIn('required', response.data['message'].lower())
    def test_logout_invalid_refresh_token(self):
        """Test logout with invalid refresh token."""
        self.client.force_authenticate(user=self.user)
        data = {
            'refresh_token': 'invalid_token',
            'selected_language': 'en'
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['success'])
        self.assertIn('Invalid', response.data['message'])
    def test_logout_token_blacklisting(self):
        """Test that logout properly blacklists tokens."""
        db_alias = get_db_alias()
        refresh_token = RefreshToken.for_user(self.user)
        jti = refresh_token.get('jti')
        self.client.force_authenticate(user=self.user)
        data = {
            'refresh_token': str(refresh_token),
            'selected_language': 'en'
        }
        # Verify token is not blacklisted initially
        outstanding_token = OutstandingToken.objects.using(db_alias or None).get(jti=jti)
        self.assertFalse(BlacklistedToken.objects.using(db_alias or None).filter(token=outstanding_token).exists())
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        # Verify token is blacklisted after logout
        self.assertTrue(BlacklistedToken.objects.using(db_alias or None).filter(token=outstanding_token).exists())
    def test_logout_unauthenticated(self):
        """Test logout without authentication."""
        refresh_token = RefreshToken.for_user(self.user)
        data = {
            'refresh_token': str(refresh_token),
            'selected_language': 'en'
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    def test_logout_already_blacklisted_token(self):
        """Test logout with already blacklisted token."""
        db_alias = get_db_alias()
        refresh_token = RefreshToken.for_user(self.user)
        jti = refresh_token.get('jti')
        # Blacklist the token first
        outstanding_token = OutstandingToken.objects.using(db_alias or None).get(jti=jti)
        BlacklistedToken.objects.using(db_alias or None).create(token=outstanding_token)
        self.client.force_authenticate(user=self.user)
        data = {
            'refresh_token': str(refresh_token),
            'logout_all_devices': True,
            'selected_language': 'en'
        }
        response = self.client.post(self.url, data)
        # Should still succeed (idempotent operation)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
    def test_logout_language_handling(self):
        """Test logout with different languages."""
        db_alias = get_db_alias()
        # Test with different language
        self.user.current_language = 'fr'
        self.user.save(using=db_alias or None)
        refresh_token = RefreshToken.for_user(self.user)
        self.client.force_authenticate(user=self.user)
        data = {
            'refresh_token': str(refresh_token),
            'selected_language': 'ar'
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
