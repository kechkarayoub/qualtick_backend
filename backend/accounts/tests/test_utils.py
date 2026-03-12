"""
    Test utility functions for user accounts
"""
from datetime import date

from django.conf import settings
from django.test import TestCase

from accounts.constants import GENDERS_CHOICES
from accounts.models import User
from accounts.repositories.user_repository import UserRepository
from accounts.utils import (format_phone_number,
                             send_phone_number_verification_code)
from backend.utils import get_db_alias


class UserUtilsTest(TestCase):
    """Test utility functions for user accounts"""
    def setUp(self):
        db_alias = get_db_alias()
        self.user = UserRepository.create_user(
            user_address="123 Test Street",
            user_birthday=date(2000, 1, 1),
            user_cin="Cin test",
            user_country="Testland",
            email="testuser@example.com",
            first_name="First name",
            user_gender=GENDERS_CHOICES[1][0],
            user_image_url="https://www.s3.com/image_url",
            user_initials_bg_color="#dd5588",
            last_name="Last name",
            password="testpassword123",
            user_phone_number_to_verify="+212612505257",
            user_phone_number_verified_by="sms",
            username="testuser",
            db_alias=db_alias,
        )
    def test_format_phone_number(self):
        """Test phone number formatting"""
        formatted_phone_number = format_phone_number("0612505252")
        self.assertEqual(formatted_phone_number, "+212612505252")
        formatted_phone_number = format_phone_number("06 12-505 252")
        self.assertEqual(formatted_phone_number, "+212612505252")
        formatted_phone_number = format_phone_number("+212612505252")
        self.assertEqual(formatted_phone_number, "+212612505252")
        formatted_phone_number = format_phone_number("+212 6 12 5052.52")
        self.assertEqual(formatted_phone_number, "+212612505252")
        formatted_phone_number = format_phone_number("+kjmnj")
        self.assertEqual(formatted_phone_number, "+kjmnj")
        formatted_phone_number = format_phone_number("+123")
        self.assertEqual(formatted_phone_number, "+123")
    def test_send_phone_number_verification_code(self):
        """Test sending phone number verification code"""
        db_alias = get_db_alias()
        if settings.ENABLE_PHONE_NUMBER_VERIFICATION:
            self.assertIsNone(self.user.user_phone_number_verification_code)
            status_code, _ = send_phone_number_verification_code(self.user,
                handle_send_phone_number_verification_sms_error=True, do_not_mock_api=False)
            self.user = UserRepository.get_by_id(self.user.id, db_alias=db_alias)
            self.assertEqual(status_code, 500)
            self.assertIsNone(self.user.user_phone_number_verification_code)
            status_code, (_uid, verification_code) = send_phone_number_verification_code(self.user)
            self.user = UserRepository.get_by_id(self.user.id, db_alias=db_alias)
            self.assertEqual(status_code, 200)
            self.assertEqual(self.user.user_phone_number_verification_code, verification_code)
        else:
            self.assertEqual(2, 1 + 1)
