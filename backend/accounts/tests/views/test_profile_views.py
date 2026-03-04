"""Test profile views"""
import json
from unittest.mock import patch

from django.contrib.auth import authenticate
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.request import Request
from rest_framework.test import APIClient, APIRequestFactory

from accounts.models import User
from accounts.repositories import UserRepository
from backend.utils import generate_random_code, get_db_alias


class UpdateProfileViewTest(TestCase):
    """Test cases for the UpdateProfileView."""
    def setUp(self):
        db_alias = get_db_alias()
        # Create a test user
        self.user = UserRepository.create_user(
            username='testuser', email='testuser@example.com',
            password='testpassword', user_phone_number='+212672937219',
            db_alias=db_alias)
        self.user2 = UserRepository.create_user(
            username='testuser2', email='testuser2@example.com',
            password='testpassword', user_phone_number='+212612505257',
            db_alias=db_alias)
        self.user3 = UserRepository.create_user(
            username='testuser3', email='testuser3@example.com',
            password='testpassword', user_phone_number='+21312345678',
            db_alias=db_alias)
        # The URL for the update profile view (you should change this to match your URL pattern)
        self.url = reverse('update-profile')
        # Create an APIClient instance for testing
        self.client = APIClient()

    def authenticate_user(self):
        """Authenticate user"""
        # Log in the test user for authentication
        self.client.force_authenticate(user=self.user)

    def authenticate_user2(self):
        """Authenticate user2"""
        # Log in the test user for authentication
        self.client.force_authenticate(user=self.user2)

    def authenticate_user3(self):
        """Authenticate user3"""
        # Log in the test user for authentication
        self.client.force_authenticate(user=self.user3)

    def test_update_password(self):
        """Test updating password"""
        db_alias = get_db_alias()
        # Log in first
        self.authenticate_user()
        # Prepare the data for the request
        data = {
            'action': 'update_password',
            'current_password': 'testpassword',
            'new_password': 'newpassword',
            'current_language': 'en'
        }
        # Make a POST request to update the profile
        response = self.client.put(self.url, data)
        # Assert that the response status code is HTTP 200 OK
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = json.loads(response.content.decode('utf-8'))
        message = data.get("message")
        self.assertEqual(message, "Your password has been updated successfully.")
        self.assertTrue(data.get("success"))
        self.assertFalse(data.get("wrong_password"))
        # Assert that the user's profile was updated in the database
        self.user.refresh_from_db(using=db_alias or None)
        # inside your test method
        factory = APIRequestFactory()
        # fake request just to satisfy the `authenticate` function
        fake_request = factory.post(self.url)
        request = Request(fake_request)
        not_authenticated_user = authenticate(
            request, username=self.user.username, password="testpassword")
        self.assertIsNone(not_authenticated_user)
        authenticated_user = authenticate(
            request, username=self.user.username, password="newpassword")
        self.assertIsNotNone(authenticated_user)

    def test_update_profile_with_password(self):
        """Test updating profile with password change"""
        db_alias = get_db_alias()
        # Log in first
        self.authenticate_user()
        # Prepare the data for the request
        data = {
            'action': 'update_profile',
            'first_name': 'John',
            'last_name': 'Doe',
            'user_birthday': '1990-01-01',
            'user_gender': 'male',
            'email': 'testuser@example.com',
            'username': 'testuser',
            'user_cin': 'CN123456',
            'user_initials_bg_color': '#00FFFF',
            'current_password': 'testpassword',
            'new_password': 'newpassword',
            'update_password': "true",
            'image_updated': "false",
            'current_language': 'en'
        }
        # Make a POST request to update the profile
        response = self.client.put(self.url, data)
        # Assert that the response status code is HTTP 200 OK
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Assert that the user's profile was updated in the database
        self.user.refresh_from_db(using=db_alias or None)
        self.assertEqual(self.user.first_name, 'John')
        self.assertEqual(self.user.last_name, 'Doe')
        self.assertEqual(self.user.user_initials_bg_color, '#00FFFF')
        self.assertEqual(self.user.user_cin, data.get('user_cin'))
        # inside your test method
        factory = APIRequestFactory()
        # fake request just to satisfy the `authenticate` function
        fake_request = factory.post(self.url)
        request = Request(fake_request)
        not_authenticated_user = authenticate(
            request, username=self.user.username, password="testpassword")
        self.assertIsNone(not_authenticated_user)
        authenticated_user = authenticate(
            request, username=self.user.username, password="newpassword")
        self.assertIsNotNone(authenticated_user)

    def test_update_profile_with_invalid_data(self):
        """Test updating profile with invalid data"""
        # Log in first
        self.authenticate_user()
        # Prepare the data for the request
        data = {
            'action': 'update_profile',
            'first_name': '',
            'last_name': '',
            'user_birthday': 'wrong date',
            'user_gender': '',
            'email': 'testuser@example.com',
            'username': 'testuser',
            'user_initials_bg_color': '#00FFFF',
            'current_password': 'testpassword',
            'current_language': 'en'
        }
        # Make a POST request to update the profile
        response = self.client.put(self.url, data)
        # Assert that the response status code is HTTP 409 OK
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        data = json.loads(response.content.decode('utf-8'))
        message = data.get("message")
        self.assertEqual(message, "Your profile could not be updated due to the "
                         "errors listed above. Please correct them and try again.")
        self.assertIsNotNone(data.get('errors', {}).get('first_name'))
        self.assertIsNotNone(data.get('errors', {}).get('last_name'))
        self.assertIsNotNone(data.get('errors', {}).get('user_birthday'))
        self.assertFalse(data.get("success"))

    def test_update_profile_without_password(self):
        """Test updating profile without changing password"""
        db_alias = get_db_alias()
        # Log in first
        self.authenticate_user2()
        # Prepare the data for the request
        data = {
            'action': 'update_profile',
            'first_name': 'John2',
            'last_name': 'Doe2',
            'user_birthday': '1990-01-01',
            'user_gender': 'male',
            'email': 'testuser2@example.com',
            'username': 'testuser2',
            'user_cin': 'CN123457',
            'user_initials_bg_color': '#00FFFF',
            'current_password': 'testpassword',
            'new_password': 'newpassword',
            'update_password': "false",
            'image_updated': "false",
            'current_language': 'en'
        }
        self.assertIsNotNone(self.user2.user_phone_number)
        # Make a POST request to update the profile
        response = self.client.put(self.url, data)
        # Assert that the response status code is HTTP 200 OK
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Assert that the user's profile was updated in the database
        self.user2.refresh_from_db(using=db_alias or None)
        self.assertEqual(self.user2.first_name, 'John2')
        self.assertEqual(self.user2.last_name, 'Doe2')
        self.assertEqual(self.user2.user_cin, data.get('user_cin'))
        self.assertIsNone(self.user2.user_phone_number)
        # inside your test method
        factory = APIRequestFactory()
        # fake request just to satisfy the `authenticate` function
        fake_request = factory.post(self.url)
        request = Request(fake_request)
        not_authenticated_user = authenticate(
            request, username=self.user2.username, password="testpassword")
        self.assertIsNotNone(not_authenticated_user)
        authenticated_user = authenticate(
            request, username=self.user2.username, password="newpassword")
        self.assertIsNone(authenticated_user)

    def test_update_profile_with_same_phone_number(self):
        """Test updating profile with the same phone number"""
        db_alias = get_db_alias()
        # Log in first
        self.authenticate_user()
        # Prepare the data for the request
        data = {
            'action': 'update_profile',
            'first_name': 'John2',
            'last_name': 'Doe2',
            'user_birthday': '1990-01-01',
            'user_gender': 'male',
            'email': 'testuser@example.com',
            'username': 'testuser',
            'user_initials_bg_color': '#00FFFF',
            'current_password': 'testpassword',
            'new_password': 'newpassword',
            'update_password': "false",
            'image_updated': "false",
            'current_language': 'en',
            'user_phone_number': '+212672937219',
        }
        self.assertEqual(self.user.user_phone_number, '+212672937219')
        # Make a POST request to update the profile
        response = self.client.put(self.url, data)
        # Assert that the response status code is HTTP 200 OK
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Assert that the user's profile was updated in the database
        self.user.refresh_from_db(using=db_alias or None)
        self.assertEqual(self.user.first_name, 'John2')
        self.assertEqual(self.user.last_name, 'Doe2')
        self.assertEqual(self.user.user_phone_number, '+212672937219')

    def test_update_profile_with_different_phone_number(self):
        """Test updating profile with a different phone number"""
        db_alias = get_db_alias()
        # Log in first
        self.authenticate_user3()
        # Prepare the data for the request
        data = {
            'action': 'update_profile',
            'first_name': 'John2',
            'last_name': 'Doe2',
            'user_birthday': '1990-01-01',
            'user_gender': 'male',
            'email': 'testuser3@example.com',
            'username': 'testuser3',
            'user_initials_bg_color': '#00FFFF',
            'current_password': 'testpassword',
            'new_password': 'newpassword',
            'update_password': "false",
            'image_updated': "false",
            'current_language': 'en',
            'user_phone_number': '+21312345699',
        }
        self.assertEqual(self.user3.user_phone_number, '+21312345678')
        # Make a POST request to update the profile
        response = self.client.put(self.url, data)
        # Assert that the response status code is HTTP 200 OK
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Assert that the user's profile was updated in the database
        self.user3.refresh_from_db(using=db_alias or None)
        self.assertEqual(self.user3.first_name, 'John2')
        self.assertEqual(self.user3.last_name, 'Doe2')
        self.assertEqual(self.user3.user_phone_number, '+21312345699')

    def test_update_profile_with_existing_cin(self):
        """Test updating profile with existing CIN"""
        db_alias = get_db_alias()
        # Log in user first
        self.authenticate_user()
        # Prepare the data for the request
        data1 = {
            'action': 'update_profile',
            'first_name': 'John2',
            'last_name': 'Doe2',
            'user_birthday': '1990-01-01',
            'user_gender': 'male',
            'email': 'testuser@example.com',
            'username': 'testuser',
            'user_cin': 'CN123455',
            'user_initials_bg_color': '#00FFFF',
            'current_password': 'testpassword',
            'new_password': 'newpassword',
            'update_password': "false",
            'image_updated': "false",
            'current_language': 'en',
            'user_phone_number': '+212672937219',
        }
        data3 = {
            'action': 'update_profile',
            'first_name': 'John2',
            'last_name': 'Doe2',
            'user_birthday': '1990-01-01',
            'user_gender': 'male',
            'email': 'testuser3@example.com',
            'username': 'testuser3',
            'user_cin': 'CN123455',
            'user_initials_bg_color': '#00FFFF',
            'current_password': 'testpassword',
            'new_password': 'newpassword',
            'update_password': "false",
            'image_updated': "false",
            'current_language': 'en',
            'user_phone_number': '+21312345699',
        }
        # Make a POST request to update the profile
        response = self.client.put(self.url, data1)
        # Assert that the response status code is HTTP 200 OK
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Assert that the user's profile was updated in the database
        self.user.refresh_from_db(using=db_alias or None)
        self.assertEqual(self.user.user_cin, data1.get('user_cin'))
        # Log in user3 first
        self.authenticate_user3()
        # Make a POST request to update the profile
        response = self.client.put(self.url, data3)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertFalse(response.json()['success'])
        self.assertIn('errors', response.json())
        # Assert that the user's profile was updated in the database
        self.user3.refresh_from_db(using=db_alias or None)
        self.assertNotEqual(self.user3.user_cin, data3.get('user_cin'))

    def test_update_password_invalid_password(self):
        """Test updating password with invalid current password"""
        # Log in first
        self.authenticate_user3()
        # Prepare the data for the request
        data = {
            'action': 'update_password',
            'current_password': 'wrongpassword',
            'new_password': 'newpassword',
            'current_language': 'en'
        }
        # Make a POST request to update the profile
        response = self.client.put(self.url, data)
        # Assert that the response status code is HTTP 200 OK
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = json.loads(response.content.decode('utf-8'))
        message = data.get("message")
        self.assertEqual(message, "Your password update failed. Please check your "
                         "current password and try again.")
        self.assertTrue(data.get("success"))
        self.assertTrue(data.get("wrong_password"))
        # inside your test method
        factory = APIRequestFactory()
        # fake request just to satisfy the `authenticate` function
        fake_request = factory.post(self.url)
        request = Request(fake_request)
        not_authenticated_user = authenticate(
            request, username=self.user3.username, password="testpassword")
        self.assertIsNotNone(not_authenticated_user)
        authenticated_user = authenticate(
            request, username=self.user3.username, password="newpassword")
        self.assertIsNone(authenticated_user)

    def test_update_profile_with_invalid_password(self):
        """Test updating profile with invalid current password"""
        # Log in first
        self.authenticate_user3()
        # Prepare the data for the request
        data = {
            'action': 'update_profile',
            'first_name': 'John',
            'last_name': 'Doe',
            'user_birthday': '1990-01-01',
            'user_gender': 'male',
            'email': 'testuser@example.com',
            'username': 'testuser',
            'user_initials_bg_color': '#00FFFF',
            'current_password': 'wrongpassword',
            'new_password': 'newpassword',
            'update_password': "true",
            'image_updated': "false",
            'current_language': 'en'
        }
        # Make a POST request to update the profile
        response = self.client.put(self.url, data)
        # Assert that the response status code is HTTP 200 OK
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = json.loads(response.content.decode('utf-8'))
        message = data.get("message")
        self.assertEqual(message, "Your profile has been updated successfully.")
        self.assertTrue(data.get("success"))
        self.assertTrue(data.get("wrong_password"))
        # inside your test method
        factory = APIRequestFactory()
        # fake request just to satisfy the `authenticate` function
        fake_request = factory.post(self.url)
        request = Request(fake_request)
        not_authenticated_user = authenticate(
            request, username=self.user3.username, password="testpassword")
        self.assertIsNotNone(not_authenticated_user)
        authenticated_user = authenticate(
            request, username=self.user3.username, password="newpassword")
        self.assertIsNone(authenticated_user)

    @patch('backend.utils.upload_file')  # Mock upload_file function
    def test_update_profile_with_image(self, _mock_upload_file):
        """Test updating profile with image"""
        db_alias = get_db_alias()
        # Log in first
        self.authenticate_user()
        # Prepare the data with profile image update
        random_name = generate_random_code()
        data = {
            'action': 'update_profile',
            'first_name': 'John',
            'last_name': 'Doe',
            'user_birthday': '1990-01-01',
            'user_gender': 'male',
            'user_initials_bg_color': '#FFFFFF',
            'email': 'testuser@example.com',
            'username': 'testuser',
            'current_password': 'testpassword',
            'new_password': 'newpassword',
            'update_password': "false",
            'image_updated': "true",
            'profile_image': SimpleUploadedFile(
                name=f'test_image{random_name}.jpg', content=b'fake_image_content',
                content_type='image/jpeg'),  # This should be a file in actual test
            'current_language': 'en'
        }
        # Make a POST request to update the profile
        response = self.client.put(self.url, data)
        # Assert that the response status code is HTTP 200 OK
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Assert that the user's profile image URL was updated
        self.user.refresh_from_db(using=db_alias or None)
        self.assertEqual(self.user.user_image_url,
            f'http://testserver/media/profile_images/profile_test_image{random_name}.jpg')
        # Prepare the data with profile image update
        data = {
            'action': 'update_profile',
            'first_name': 'John',
            'last_name': 'Doe',
            'user_birthday': '1990-01-01',
            'user_gender': 'male',
            'user_initials_bg_color': '#FFFFFF',
            'email': 'testuser@example.com',
            'username': 'testuser',
            'current_password': 'testpassword',
            'new_password': 'newpassword',
            'update_password': "false",
            'image_updated': "true",
            'current_language': 'en'
        }
        # Make a POST request to update the profile
        response = self.client.put(self.url, data)
        # Assert that the response status code is HTTP 200 OK
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Assert that the user's profile image URL was updated
        self.user.refresh_from_db(using=db_alias or None)
        self.assertIsNone(self.user.user_image_url)


class UpdateSettingsViewTest(TestCase):
    """Test the update settings view."""
    def setUp(self):
        db_alias = get_db_alias()
        self.user = UserRepository.create_user(
            username='testuser',
            email='test@example.com',
            password='password123',
            current_language='en',
            user_timezone='UTC',
            user_theme='light',
            db_alias=db_alias,
        )
        self.client = APIClient()
        self.url = reverse('update-settings')

    def test_update_settings_unauthenticated(self):
        """Test that unauthenticated users cannot update settings."""
        data = {
            'current_language': 'fr',
            'user_timezone': 'Europe/Paris',
            'user_theme': 'dark'
        }
        response = self.client.put(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_update_language_success(self):
        """Test successful language update."""
        db_alias = get_db_alias()
        self.client.force_authenticate(user=self.user)
        data = {
            'current_language': 'fr',
            'selected_language': 'en'
        }
        response = self.client.put(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['user']['current_language'], 'fr')
        # Verify in database
        self.user.refresh_from_db(using=db_alias or None)
        self.assertEqual(self.user.current_language, 'fr')

    def test_update_timezone_success(self):
        """Test successful timezone update."""
        db_alias = get_db_alias()
        self.client.force_authenticate(user=self.user)
        data = {
            'user_timezone': 'Europe/Paris',
            'selected_language': 'en'
        }
        response = self.client.put(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['user']['user_timezone'], 'Europe/Paris')
        # Verify in database
        self.user.refresh_from_db(using=db_alias or None)
        self.assertEqual(self.user.user_timezone, 'Europe/Paris')

    def test_update_theme_success(self):
        """Test successful theme update."""
        db_alias = get_db_alias()
        self.client.force_authenticate(user=self.user)
        data = {
            'user_theme': 'dark',
            'selected_language': 'en'
        }
        response = self.client.put(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['user']['user_theme'], 'dark')
        # Verify in database
        self.user.refresh_from_db(using=db_alias or None)
        self.assertEqual(self.user.user_theme, 'dark')

    def test_update_all_settings_success(self):
        """Test updating all settings at once."""
        db_alias = get_db_alias()
        self.client.force_authenticate(user=self.user)
        data = {
            'current_language': 'ar',
            'user_timezone': 'Asia/Dubai',
            'user_theme': 'default',
            'selected_language': 'en'
        }
        response = self.client.put(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['user']['current_language'], 'ar')
        self.assertEqual(response.data['user']['user_timezone'], 'Asia/Dubai')
        self.assertEqual(response.data['user']['user_theme'], 'default')
        # Verify in database
        self.user.refresh_from_db(using=db_alias or None)
        self.assertEqual(self.user.current_language, 'ar')
        self.assertEqual(self.user.user_timezone, 'Asia/Dubai')
        self.assertEqual(self.user.user_theme, 'default')

    def test_invalid_language(self):
        """Test updating with invalid language."""
        self.client.force_authenticate(user=self.user)
        data = {
            'current_language': 'invalid_lang',
            'selected_language': 'en'
        }
        response = self.client.put(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['success'])
        self.assertIn('Invalid language selection', response.data['message'])

    def test_invalid_timezone(self):
        """Test updating with invalid timezone."""
        self.client.force_authenticate(user=self.user)
        data = {
            'user_timezone': 'Invalid/Timezone',
            'selected_language': 'en'
        }
        response = self.client.put(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['success'])
        self.assertIn('Invalid timezone selection', response.data['message'])

    def test_invalid_theme(self):
        """Test updating with invalid theme."""
        self.client.force_authenticate(user=self.user)
        data = {
            'user_theme': 'invalid_theme',
            'selected_language': 'en'
        }
        response = self.client.put(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['success'])
        self.assertIn('Invalid theme selection', response.data['message'])

    def test_no_changes_detected(self):
        """Test when no changes are provided."""
        self.client.force_authenticate(user=self.user)
        data = {
            'current_language': 'en',  # Same as current
            'user_timezone': 'UTC',    # Same as current
            'user_theme': 'light',     # Same as current
            'selected_language': 'en'
        }
        response = self.client.put(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['success'])
        self.assertIn('No changes detected', response.data['message'])

    def test_empty_request(self):
        """Test with empty request data."""
        self.client.force_authenticate(user=self.user)
        response = self.client.put(self.url, {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['success'])
        self.assertIn('No changes detected', response.data['message'])
