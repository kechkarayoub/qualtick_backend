"""
Test cases for backend utility functions.
Consolidated from test_comprehensive.py, test_functionalities.py, and test_additional.py.
"""

import os
from datetime import datetime, timezone
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase
from django.utils.timezone import now
from django.utils.translation import activate, gettext_lazy as _

from accounts.repositories.user_repository import UserRepository
from backend.utils import (
    execute_native_query,
    generate_random_code,
    generate_random_string,
    get_all_timezones,
    get_db_alias,
    get_email_base_context,
    get_geolocation_info,
    get_local_datetime,
    remove_file,
    send_phone_message,
    send_whatsapp,
    upload_file,
)


User = get_user_model()


class UtilsTestCase(TestCase):
    """Test utility functions from backend/utils.py."""

    def setUp(self):
        """Set up test data."""
        db_alias = get_db_alias()
        self.factory = RequestFactory()
        self.user = UserRepository.create_user(
            email="testuser@example.com",
            first_name="First name",
            last_name="Last name",
            password="testpassword123",
            user_phone_number_to_verify="+212612505257",
            username="testuser",
            db_alias=db_alias,
        )

    def test_generate_random_string_default_length(self):
        """Test the `generate_random_string` function with default length."""
        s = generate_random_string()
        self.assertEqual(len(s), 10)
        self.assertTrue(s.isalnum())

    def test_generate_random_string_custom_length(self):
        """Test the `generate_random_string` function with custom lengths."""
        for length in [1, 5, 20, 50]:
            s = generate_random_string(length)
            self.assertEqual(len(s), length)
            self.assertTrue(s.isalnum())

    def test_generate_random_string_zero_length(self):
        """Test the `generate_random_string` function with zero length."""
        s = generate_random_string(0)
        self.assertEqual(s, "")

    def test_generate_random_string_negative_length(self):
        """Test the `generate_random_string` function with negative length."""
        s = generate_random_string(-5)
        self.assertEqual(s, "")

    def test_execute_native_query(self):
        """Test the `execute_native_query` function."""
        db_alias = get_db_alias()
        # Test SELECT query
        query_get_users = "SELECT * FROM backend_user WHERE is_active=True;"
        users = execute_native_query(query_get_users)
        self.assertEqual(len(users), 1)

        # Test INSERT query
        query_set_user = """
            INSERT INTO backend_user (email, first_name, is_active, last_name, username,
                password, is_superuser, is_staff, date_joined,
                nbr_phone_number_verification_code_used, user_gender, is_user_deleted,
                current_language, is_user_email_validated, is_user_phone_number_validated,
                user_phone_number_verified_by, user_timezone, user_theme)
            VALUES ('email2@yopmail.com', 'first_name', True, 'last_name', 'username2',
                'password', False, False, NOW(), 0, '', False, 'fr', False, False, '',
                'UTC', 'light'),
                ('email3@yopmail.com', 'first_name', True, 'last_name', 'username3',
                'password', False, False, NOW(), 0, '', False, 'ar', False, False, '',
                'Africa/Casablanca', 'light');
        """
        result = execute_native_query(query_set_user, is_get=False, db_alias=db_alias)
        self.assertIsNone(result)

        # Test query count after insert
        query_get_users = "SELECT * FROM backend_user WHERE email LIKE '%@yopmail.com';"
        users = execute_native_query(query_get_users, db_alias=db_alias)
        self.assertEqual(len(users), 2)

        # Test UPDATE query
        query_update_user = """
            UPDATE backend_user SET email='email2@example.com'
            WHERE email='email2@yopmail.com';
        """
        result = execute_native_query(query_update_user, is_get=False, db_alias=db_alias)
        self.assertIsNone(result)

        # Test query count after update
        query_get_users = "SELECT * FROM backend_user WHERE email LIKE '%@yopmail.com';"
        users = execute_native_query(query_get_users, db_alias=db_alias)
        self.assertEqual(len(users), 1)

        # Test DELETE query
        query_delete_user = """
            DELETE FROM backend_user WHERE email LIKE '%@yopmail.com';
        """
        result = execute_native_query(query_delete_user, is_get=False, db_alias=db_alias)
        self.assertIsNone(result)

        # Test query count after delete
        query_get_users = "SELECT * FROM backend_user WHERE email LIKE '%@yopmail.com';"
        users = execute_native_query(query_get_users, is_get=True, db_alias=db_alias)
        self.assertEqual(len(users), 0)

    def test_generate_random_code(self):
        """Test the `generate_random_code` function."""
        # Test edge cases with zero/negative digits
        empty_random_code = generate_random_code(nbr_digit=0)
        self.assertEqual(len(empty_random_code), 0)
        self.assertEqual(empty_random_code, "")

        empty_random_code = generate_random_code(nbr_digit=-1)
        self.assertEqual(len(empty_random_code), 0)
        self.assertEqual(empty_random_code, "")

        # Test default 6-digit code
        normal_random_code = generate_random_code()
        self.assertEqual(len(normal_random_code), 6)
        self.assertTrue(normal_random_code.isdigit())
        self.assertTrue(0 <= int(normal_random_code) <= 999999)

        # Test custom length
        custom_random_code = generate_random_code(nbr_digit=4)
        self.assertEqual(len(custom_random_code), 4)
        self.assertTrue(custom_random_code.isdigit())

        custom_random_code = generate_random_code(nbr_digit=8)
        self.assertEqual(len(custom_random_code), 8)
        self.assertTrue(0 <= int(custom_random_code) <= 99999999)

    def test_get_all_timezones(self):
        """Test the `get_all_timezones` function."""
        activate('en')

        # Test as tuples (default)
        timezones = get_all_timezones()
        self.assertIsInstance(timezones, list)
        self.assertTrue(len(timezones) > 0)
        self.assertEqual(timezones[0], ('', 'Select'))
        self.assertTrue(
            all(isinstance(item, tuple) and len(item) == 2 for item in timezones[1:])
        )
        self.assertTrue(all(isinstance(item[0], str) for item in timezones[1:]))
        self.assertTrue(all(isinstance(item[1], str) for item in timezones[1:]))

        # Test as lists
        timezones_list = get_all_timezones(as_list=True)
        self.assertEqual(timezones_list[0], ['', 'Select'])
        self.assertTrue(
            all(isinstance(item, list) and len(item) == 2 for item in timezones_list[1:])
        )
        self.assertTrue(all(isinstance(item[0], str) for item in timezones_list[1:]))
        self.assertTrue(all(isinstance(item[1], str) for item in timezones_list[1:]))

    @patch("requests.get")
    def test_get_geolocation_info(self, mock_get):
        """Test the `get_geolocation_info` function."""
        valid_ip = "8.8.8.8"
        fields = "country,countryCode,city"
        mock_success_response = {
            "country": "United States",
            "countryCode": "US",
            "city": "Mountain View",
        }
        mock_response = Mock()
        mock_response.json.return_value = mock_success_response
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Call the function
        result = get_geolocation_info(valid_ip, fields=fields)

        # Assertions
        self.assertEqual(result, mock_success_response)
        self.assertEqual(result["country"], "United States")
        self.assertEqual(result["countryCode"], "US")
        self.assertEqual(result["city"], "Mountain View")
        mock_get.assert_called_once_with(
            f"http://ip-api.com/json/{valid_ip}",
            params={"fields": fields},
            timeout=5,
        )

    def test_get_local_datetime(self):
        """Test the `get_local_datetime` function with a valid timezone."""
        utc_time = datetime.now(timezone.utc)

        # Test with America/New_York timezone
        custom_timezone = "America/New_York"
        localized_time = get_local_datetime(utc_time, custom_timezone)
        self.assertEqual(localized_time.tzinfo, ZoneInfo("America/New_York"))
        # Since New York is UTC-5, localized time should be later
        self.assertTrue(
            localized_time.strftime("%Y-%m-%d %H:%M")
            < utc_time.strftime("%Y-%m-%d %H:%M")
        )

        # Test with Europe/Paris timezone
        localized_time_paris = get_local_datetime(utc_time, "Europe/Paris")
        self.assertEqual(localized_time_paris.tzinfo, ZoneInfo("Europe/Paris"))

        # Test with UTC as the timezone
        custom_timezone = "UTC"
        localized_time = get_local_datetime(utc_time, custom_timezone)
        self.assertEqual(localized_time.tzinfo, ZoneInfo("UTC"))
        # Time should be the same
        self.assertEqual(
            localized_time.strftime("%Y-%m-%d %H:%M"),
            utc_time.strftime("%Y-%m-%d %H:%M"),
        )

        # Test with an invalid timezone
        custom_timezone = "Invalid/Timezone"
        with self.assertRaises(KeyError):
            get_local_datetime(utc_time, custom_timezone)

    def test_get_email_base_context(self):
        """Test the `get_email_base_context` function."""
        # Test default context
        email_base_context = get_email_base_context()
        self.assertEqual(len(email_base_context.keys()), 6)
        self.assertEqual(email_base_context["company_address"], settings.COMPANY_ADDRESS)
        self.assertEqual(email_base_context["app_name"], settings.APPLICATION_NAME)
        self.assertEqual(email_base_context["current_year"], now().year)
        self.assertEqual(email_base_context["direction"], "ltr")
        self.assertEqual(email_base_context["from_email"], settings.DEFAULT_FROM_EMAIL)
        self.assertEqual(
            email_base_context["frontend_endpoint"], settings.FRONTEND_ENDPOINT
        )

        # Test required keys
        required_keys = [
            "company_address",
            "app_name",
            "current_year",
            "direction",
            "from_email",
            "frontend_endpoint",
        ]
        for key in required_keys:
            self.assertIn(key, email_base_context)

        # Test Arabic language direction (RTL)
        context_ar = get_email_base_context("ar")
        self.assertEqual(context_ar["direction"], "rtl")

        email_base_context_rtl = get_email_base_context(selected_language="ar")
        self.assertEqual(email_base_context_rtl["direction"], "rtl")

        # Test other languages direction (LTR)
        context_en = get_email_base_context("en")
        self.assertEqual(context_en["direction"], "ltr")

        email_base_context_ltr = get_email_base_context(selected_language="en")
        self.assertEqual(email_base_context_ltr["direction"], "ltr")

        context_fr = get_email_base_context("fr")
        self.assertEqual(context_fr["direction"], "ltr")

    @patch("django.core.files.storage.default_storage.exists")
    @patch("os.remove")
    def test_remove_file(self, mock_remove, mock_exists):
        """Test file removal."""
        # Set up the mock to simulate the file's existence
        mock_exists.return_value = True

        # Define the file URL to be removed
        file_url = "http://testserver/media/profile_images/test_image.jpg"

        # Simulate the file removal
        request = self.factory.post("/test/")
        remove_file(request, file_url)

        # Assert that the file removal was called
        mock_exists.assert_called_once_with("profile_images/test_image.jpg")
        mock_remove.assert_called_once_with(
            os.path.join(settings.MEDIA_ROOT, "profile_images/test_image.jpg")
        )

    @patch("django.core.files.storage.default_storage.exists")
    def test_remove_file_not_found(self, mock_exists):
        """Test file removal when file doesn't exist."""
        # Set up the mock to simulate the file not existing
        mock_exists.return_value = False

        # Define the file URL to be removed
        file_url = "http://testserver/media/profile_images/test_image.jpg"

        # Simulate the file removal
        request = self.factory.post("/update-profile/")
        remove_file(request, file_url)

        # Assert that the remove_file function did not attempt to remove a file
        mock_exists.assert_called_once_with("profile_images/test_image.jpg")

    @patch("django.core.files.storage.default_storage.save")
    def test_upload_file(self, mock_save):
        """Test the `upload_file` function."""
        # Create a fake image file (for the test)
        test_file = SimpleUploadedFile(
            name="test_image.jpg",
            content=b"fake_image_content",
            content_type="image/jpeg",
        )

        # Mock the `save` method to simulate file saving
        mock_save.return_value = "profile_images/profile_test_image.jpg"

        # Simulate request with the file
        request = self.factory.post("/test/")
        file_url, file_path = upload_file(
            request, test_file, "profile_images", prefix="profile_"
        )

        # Assert that the file URL and path are correct
        expected_url = f'{request.build_absolute_uri(settings.MEDIA_URL)}profile_images/profile_test_image.jpg'
        self.assertEqual(file_url, expected_url)
        self.assertEqual(file_path, "profile_images/profile_test_image.jpg")

        # Test with None file
        file_url, file_path = upload_file(
            request, None, "profile_images", prefix="profile_"
        )
        self.assertIsNone(file_url)
        self.assertIsNone(file_path)

    def test_send_whatsapp(self):
        """Test the `send_whatsapp` function."""
        db_alias = get_db_alias()
        self.assertEqual(self.user.nbr_phone_number_verification_code_used, 0)

        # Test single phone number
        response = send_whatsapp("test", ["+212612505257"])
        self.assertEqual(response.get("nbr_verification_codes_sent"), 1)
        self.assertTrue(response.get("all_verification_codes_sent"))
        self.user = UserRepository.get_by_id(self.user.id, db_alias=db_alias)
        self.assertEqual(self.user.nbr_phone_number_verification_code_used, 0)

        # Test multiple phone numbers
        response = send_whatsapp("test", ["+212612505257", "+212612505257"])
        self.assertEqual(response.get("nbr_verification_codes_sent"), 2)
        self.assertTrue(response.get("all_verification_codes_sent"))
        self.user = UserRepository.get_by_id(self.user.id, db_alias=db_alias)
        self.assertEqual(self.user.nbr_phone_number_verification_code_used, 0)

        # Test with error handling
        response = send_whatsapp("test", ["+212612505257"], handle_error=True)
        self.assertEqual(response.get("nbr_verification_codes_sent"), 0)
        self.assertFalse(response.get("all_verification_codes_sent"))
        self.user = UserRepository.get_by_id(self.user.id, db_alias=db_alias)
        self.assertEqual(self.user.nbr_phone_number_verification_code_used, 0)

    def test_send_phone_message(self):
        """Test the `send_phone_message` function."""
        db_alias = get_db_alias()
        self.assertEqual(self.user.nbr_phone_number_verification_code_used, 0)

        # Test single phone number
        response = send_phone_message("test", ["+212612505257"])
        self.assertEqual(response.get("nbr_verification_codes_sent"), 1)
        self.assertTrue(response.get("all_verification_codes_sent"))
        self.user = UserRepository.get_by_id(self.user.id, db_alias=db_alias)
        self.assertEqual(self.user.nbr_phone_number_verification_code_used, 0)

        # Test multiple phone numbers
        response = send_phone_message("test", ["+212612505257", "+212612505257"])
        self.assertEqual(response.get("nbr_verification_codes_sent"), 2)
        self.assertTrue(response.get("all_verification_codes_sent"))
        self.user = UserRepository.get_by_id(self.user.id, db_alias=db_alias)
        self.assertEqual(self.user.nbr_phone_number_verification_code_used, 0)

        # Test with error handling
        response = send_phone_message("test", ["+212612505257"], handle_error=True)
        self.assertEqual(response.get("nbr_verification_codes_sent"), 0)
        self.assertFalse(response.get("all_verification_codes_sent"))
        self.user = UserRepository.get_by_id(self.user.id, db_alias=db_alias)
        self.assertEqual(self.user.nbr_phone_number_verification_code_used, 0)


class LocalizationTestCase(TestCase):
    """Test localization functionality for utilities."""

    def test_timezone_handling(self):
        """Test timezone handling in utilities."""
        utc_time = datetime.now(timezone.utc)

        # Test with valid timezone
        localized_time = get_local_datetime(utc_time, "Europe/Paris")
        self.assertEqual(localized_time.tzinfo, ZoneInfo("Europe/Paris"))

        # Test with UTC timezone
        utc_localized = get_local_datetime(utc_time, "UTC")
        self.assertEqual(utc_localized.tzinfo, ZoneInfo("UTC"))

        # Test with invalid timezone should raise KeyError
        with self.assertRaises(KeyError):
            get_local_datetime(utc_time, "Invalid/Timezone")

    def test_email_context_languages(self):
        """Test email context for different languages."""
        # Test RTL languages
        context_ar = get_email_base_context("ar")
        self.assertEqual(context_ar["direction"], "rtl")

        # Test LTR languages
        context_en = get_email_base_context("en")
        self.assertEqual(context_en["direction"], "ltr")

        context_fr = get_email_base_context("fr")
        self.assertEqual(context_fr["direction"], "ltr")

        # Test default language
        context_default = get_email_base_context()
        self.assertEqual(context_default["direction"], "ltr")
