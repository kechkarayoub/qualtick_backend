"""Test cases for password reset views."""
from unittest.mock import patch

from django.contrib.auth.tokens import default_token_generator
from django.test import TestCase
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.timezone import now
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import User
from accounts.repositories import UserRepository
from accounts.utils import send_password_reset_email
from backend.utils import get_db_alias


class PasswordResetViewsTestCase(TestCase):
    """Test cases for password reset API views."""
    def setUp(self):
        """Set up test data."""
        db_alias = get_db_alias()
        self.client = APIClient()
        self.user = UserRepository.create_user(
            username='testuser',
            email='test@example.com',
            password='oldpassword123',
            is_active=True,
            current_language='en',
            db_alias=db_alias,
        )
        self.inactive_user = UserRepository.create_user(
            username='inactiveuser',
            email='inactive@example.com',
            password='password123',
            is_active=False,
            current_language='en',
            db_alias=db_alias,
        )
        self.deleted_user = UserRepository.create_user(
            username='deleteduser',
            email='deleted@example.com',
            password='password123',
            is_active=True,
            is_user_deleted=True,
            current_language='en',
            db_alias=db_alias,
        )

    def test_forgot_password_with_email_success(self):
        """Test forgot password request with valid email."""
        url = '/accounts/forgot-password/'
        data = {
            'email_or_username': 'test@example.com',
            'selected_language': 'en'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertIn('If an account with this email', response.data['message'])

    def test_forgot_password_with_username_success(self):
        """Test forgot password request with valid username."""
        url = '/accounts/forgot-password/'
        data = {
            'email_or_username': 'testuser',
            'selected_language': 'en'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertIn('If an account with this email', response.data['message'])

    def test_forgot_password_nonexistent_user(self):
        """Test forgot password request with non-existent user 
        (should still return success)."""
        url = '/accounts/forgot-password/'
        data = {
            'email_or_username': 'nonexistent@example.com',
            'selected_language': 'en'
        }
        response = self.client.post(url, data)
        # Should still return success for security reasons
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertIn('If an account with this email', response.data['message'])

    def test_forgot_password_inactive_user(self):
        """Test forgot password request with inactive user (should still return success)."""
        url = '/accounts/forgot-password/'
        data = {
            'email_or_username': 'inactive@example.com',
            'selected_language': 'en'
        }
        response = self.client.post(url, data)
        # Should still return success for security reasons
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])

    def test_forgot_password_deleted_user(self):
        """Test forgot password request with deleted user 
        (should still return success)."""
        url = '/accounts/forgot-password/'
        data = {
            'email_or_username': 'deleted@example.com',
            'selected_language': 'en'
        }
        response = self.client.post(url, data)
        # Should still return success for security reasons
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])

    def test_forgot_password_missing_email_or_username(self):
        """Test forgot password request without email or username."""
        url = '/accounts/forgot-password/'
        data = {
            'selected_language': 'en'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['success'])
        self.assertIn('required', response.data['message'].lower())

    def test_forgot_password_language_handling(self):
        """Test that user's language is updated during forgot password."""
        # User has different language than request
        db_alias = get_db_alias()
        self.user.current_language = 'fr'
        self.user.save(using=db_alias or None)

        url = '/accounts/forgot-password/'
        data = {
            'email_or_username': 'test@example.com',
            'selected_language': 'en'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check that user's language was updated
        self.user.refresh_from_db(using=db_alias)
        self.assertEqual(self.user.current_language, 'en')

    def test_reset_password_success(self):
        """Test successful password reset with valid token."""
        # Generate a valid token first
        db_alias = get_db_alias()
        _status_code, (uid, token) = send_password_reset_email(
            self.user, do_not_mock_api=False)

        url = '/accounts/reset-password/'
        data = {
            'uid': uid,
            'token': token,
            'new_password': 'newpassword123',
            'selected_language': 'en'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertIn('successfully', response.data['message'].lower())

        # Verify password was actually changed
        self.user.refresh_from_db(using=db_alias or None)
        self.assertTrue(self.user.check_password('newpassword123'))

    def test_reset_password_invalid_uid(self):
        """Test password reset with invalid UID."""
        url = '/accounts/reset-password/'
        data = {
            'uid': 'invalid_uid',
            'token': 'some_tokenx_*_1234567890',
            'new_password': 'newpassword123',
            'selected_language': 'en'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['success'])
        self.assertIn('Invalid', response.data['message'])

    def test_reset_password_expired_token(self):
        """Test password reset with expired token."""
        # Create an expired token (25 hours old)
        old_timestamp = now().timestamp() - (25 * 3600)  # 25 hours ago
        token_ = default_token_generator.make_token(self.user)
        token = token_ + "_*_" + str(old_timestamp)
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))

        url = '/accounts/reset-password/'
        data = {
            'uid': uid,  # Remove .decode() since it's already a string
            'token': token,
            'new_password': 'newpassword123',
            'selected_language': 'en'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['success'])
        self.assertIn('expired', response.data['message'].lower())

    def test_reset_password_inactive_user(self):
        """Test password reset with inactive user."""
        # Create a token for inactive user
        token_ = default_token_generator.make_token(self.inactive_user)
        timestamp_str = str(now().timestamp())
        token = token_ + "_*_" + timestamp_str
        uid = urlsafe_base64_encode(force_bytes(self.inactive_user.pk))

        url = '/accounts/reset-password/'
        data = {
            'uid': uid,  # Remove .decode() since it's already a string
            'token': token,
            'new_password': 'newpassword123',
            'selected_language': 'en'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['success'])
        self.assertIn('disabled', response.data['message'].lower())

    def test_reset_password_missing_fields(self):
        """Test password reset with missing required fields."""
        url = '/accounts/reset-password/'

        # Test missing uid
        data = {
            'token': 'some_tokenx',
            'new_password': 'newpassword123',
            'selected_language': 'en'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('required', response.data['message'].lower())

        # Test missing token
        data = {
            'uid': 'some_uid',
            'new_password': 'newpassword123',
            'selected_language': 'en'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('required', response.data['message'].lower())

        # Test missing new_password
        data = {
            'uid': 'some_uid',
            'token': 'some_tokenx',
            'selected_language': 'en'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('required', response.data['message'].lower())

    def test_reset_password_invalid_token_format(self):
        """Test password reset with invalid token format."""
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))

        url = '/accounts/reset-password/'
        data = {
            'uid': uid,  # Remove .decode() since it's already a string
            'token': 'invalid_token_format',  # Missing timestamp separator
            'new_password': 'newpassword123',
            'selected_language': 'en'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['success'])
        self.assertIn('Invalid', response.data['message'])

    def test_reset_password_integration_flow(self):
        """Test complete password reset flow from forgot to reset."""
        db_alias = get_db_alias()
        # Step 1: Request password reset
        forgot_url = '/accounts/forgot-password/'
        forgot_data = {
            'email_or_username': 'test@example.com',
            'selected_language': 'en'
        }
        forgot_response = self.client.post(forgot_url, forgot_data)
        self.assertEqual(forgot_response.status_code, status.HTTP_200_OK)

        # Step 2: Generate token (simulating email link)
        status_code, (uid, token) = send_password_reset_email(
            self.user, do_not_mock_api=False)
        self.assertEqual(status_code, 200)

        # Step 3: Reset password using token
        reset_url = '/accounts/reset-password/'
        reset_data = {
            'uid': uid,
            'token': token,
            'new_password': 'completelynewpassword123',
            'selected_language': 'en'
        }
        reset_response = self.client.post(reset_url, reset_data)
        self.assertEqual(reset_response.status_code, status.HTTP_200_OK)
        self.assertTrue(reset_response.data['success'])

        # Step 4: Verify password was changed
        self.user.refresh_from_db(using=db_alias)
        self.assertTrue(self.user.check_password('completelynewpassword123'))
        self.assertFalse(self.user.check_password('oldpassword123'))

    @patch('accounts.utils.send_password_reset_email')
    def test_forgot_password_error_handling(self, mock_send_email):
        """Test forgot password view handles email sending errors gracefully."""
        # Mock an exception during email sending
        mock_send_email.side_effect = Exception("Email service error")

        url = '/accounts/forgot-password/'
        data = {
            'email_or_username': 'test@example.com',
            'selected_language': 'en'
        }
        response = self.client.post(url, data)

        # Should still return success for security reasons
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])

    def test_reset_password_user_language_activation(self):
        """Test that user's language is activated during password reset."""
        # Set user language different from request
        db_alias = get_db_alias()
        self.user.current_language = 'fr'
        self.user.save(using=db_alias or None)

        # Generate token
        _status_code, (uid, token) = send_password_reset_email(
            self.user, do_not_mock_api=False)

        url = '/accounts/reset-password/'
        data = {
            'uid': uid,
            'token': token,
            'new_password': 'newpassword123',
            'selected_language': 'en'  # Different from user's language
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
