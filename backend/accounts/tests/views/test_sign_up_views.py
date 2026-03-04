"""Test sign up views."""
from unittest.mock import patch

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from accounts.repositories import UserRepository
from backend.utils import get_db_alias


class SignUpViewTest(TestCase):
    """Test cases for the SignUpView."""

    def setUp(self):
        self.client = APIClient()
        self.url = '/accounts/sign-up/'
        self.default_data = {
            'first_name': '  John  ',
            'last_name': '  Doe ',
            'username': ' johndoe ',
            'email': ' johndoe@example.com ',
            'password': 'testpassword123',
            'selected_language': 'en',
        }

    def test_signup_success(self):
        """Test successful user registration with normalized input."""
        db_alias = get_db_alias()
        response = self.client.post(self.url, self.default_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('username', data)
        self.assertIn('message', data)
        # Check normalization
        user = UserRepository.get_by_email('johndoe@example.com', db_alias=db_alias)
        self.assertEqual(user.first_name, 'John')
        self.assertEqual(user.last_name, 'Doe')
        self.assertEqual(user.username, 'johndoe')

    def test_signup_missing_required_fields(self):
        """Test registration fails with missing required fields."""
        data = self.default_data.copy()
        data.pop('email')
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertFalse(response.json()['success'])
        self.assertIn('errors', response.json())

    def test_signup_duplicate_email(self):
        """Test registration fails if email already exists."""
        db_alias = get_db_alias()
        UserRepository.create_user(username='otheruser', email='johndoe@example.com',
                                   password='pass', db_alias=db_alias)
        response = self.client.post(self.url, self.default_data)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertFalse(response.json()['success'])
        self.assertIn('errors', response.json())

    def test_signup_email_verification_message(self):
        """Test email verification message is returned if enabled."""
        with self.settings(ENABLE_EMAIL_VERIFICATION=True):
            data = self.default_data.copy()
            data['email'] = 'unique@example.com'
            response = self.client.post(self.url, data)
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            self.assertIn('validate your email', response.json()['message'].lower())


class SignUpThirdPartyViewTest(TestCase):
    """Test cases for the SignUpThirdPartyView."""

    def setUp(self):
        self.client = APIClient()
        self.url = '/accounts/sign-up-third-party/'
        self.default_data = {
            'first_name': '  Jane  ',
            'last_name': '  Smith ',
            'email': 'janesmith@example.com',
            'id_token': 'fake_token',
            'type_third_party': 'google',
            'selected_language': 'en',
            'user_image_url': 'http://example.com/image.jpg',
        }

    @patch('accounts.views.id_token.verify_oauth2_token')
    def test_signup_third_party_success(self, mock_verify):
        """Test successful third-party signup with Google OAuth."""
        db_alias = get_db_alias()
        mock_verify.return_value = {'email': 'janesmith@example.com',
                                    'email_verified': True}
        response = self.client.post(self.url, self.default_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertTrue(data['is_new_user'])
        self.assertIn('access_token', data)
        self.assertIn('refresh_token', data)
        self.assertIn('user', data)
        user = UserRepository.get_by_email('janesmith@example.com', db_alias=db_alias)
        self.assertEqual(user.first_name, 'Jane')
        self.assertEqual(user.last_name, 'Smith')
        self.assertTrue(user.is_user_email_validated)

    def test_signup_third_party_missing_fields(self):
        """Test third-party signup fails with missing required fields."""
        data = self.default_data.copy()
        data.pop('email')
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.json()['success'])
        self.assertIn('Email, Id token and Third party type are required',
                      response.json()['message'])

    @patch('accounts.views.id_token.verify_oauth2_token')
    def test_signup_third_party_invalid_token(self, mock_verify):
        """Test third-party signup fails if token is invalid or email mismatch."""
        mock_verify.return_value = {'email': 'other@example.com', 'email_verified': False}
        response = self.client.post(self.url, self.default_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.json()['success'])
        self.assertIn(
            'Unable to verify your account with the provided third-party credentials. '
            'Please check your information or try a different sign-up method.',
            response.json()['message'])

    @patch('accounts.views.id_token.verify_oauth2_token')
    def test_signup_third_party_existing_user(self, mock_verify):
        """Test third-party signup delegates to sign-in if user exists."""
        db_alias = get_db_alias()
        UserRepository.create_user(username='janesmith', email='janesmith@example.com',
                                   password='pass', db_alias=db_alias)
        mock_verify.return_value = {'email': 'janesmith@example.com',
                                    'email_verified': True}
        response = self.client.post(self.url, self.default_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.json().get('is_new_user', False))
        self.assertIn('access_token', response.json())
        self.assertIn('user', response.json())

    @patch('accounts.views.id_token.verify_oauth2_token')
    def test_signup_third_party_creates_and_logs_in_new_user(self, mock_verify):
        """Test that a new user is created and logged in if not existing in the app."""
        db_alias = get_db_alias()
        email = 'newuser@example.com'
        data = self.default_data.copy()
        data['email'] = email
        mock_verify.return_value = {'email': email, 'email_verified': True}
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        resp_data = response.json()
        self.assertTrue(resp_data['success'])
        self.assertTrue(resp_data['is_new_user'])
        self.assertIn('access_token', resp_data)
        self.assertIn('refresh_token', resp_data)
        self.assertIn('user', resp_data)
        # User should now exist in DB
        user = UserRepository.get_by_email(email, db_alias=db_alias)
        self.assertEqual(user.first_name, 'Jane')
        self.assertEqual(user.last_name, 'Smith')
        self.assertTrue(user.is_user_email_validated)
