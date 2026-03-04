"""
Test Middleware

Tests that the custom timezone middleware properly sets the user's timezone.
"""

from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase
from django.utils.timezone import get_current_timezone

from accounts.middleware import TimezoneMiddleware
from accounts.models import User
from accounts.repositories.user_repository import UserRepository
from backend.utils import get_db_alias


class TimezoneMiddlewareTestCase(TestCase):
    """
        Test cases for the TimezoneMiddleware.
    """
    def setUp(self):
        """
            Set up the test environment with a RequestFactory and sample users.
        """
        db_alias = get_db_alias()
        self.factory = RequestFactory()
        self.middleware = TimezoneMiddleware(get_response=lambda x: x)
        self.default_timezone_user = UserRepository.create_user(
            email="default_timezone_user@example.com",
            first_name="First name2",
            last_name="Last name2",
            password="testpassword123",
            username="default_timezone_user",
            db_alias=db_alias,
        )
        # setattr(self.default_timezone_user, "is_authenticated", True)
        self.timezone_user = UserRepository.create_user(
            email="timezone_user@example.com",
            first_name="First name2",
            last_name="Last name2",
            password="testpassword123",
            user_timezone="America/New_York",
            username="timezone_user",
            db_alias=db_alias,
        )
        # setattr(self.timezone_user, "is_authenticated", True)
        self.invalid_timezone_user = UserRepository.create_user(
            email="invalid_timezone_user@example.com",
            first_name="First name3",
            last_name="Last name3",
            password="testpassword123",
            user_timezone="Invalid/Timezone",
            username="invalid_timezone_user",
            db_alias=db_alias,
        )
        # setattr(self.invalid_timezone_user, "is_authenticated", True)
    def test_authenticated_user_with_default_timezone(self):
        """
            Test if the middleware correctly sets the timezone for an 
            authenticated user with a default timezone.
        """
        self.client.login(username='default_timezone_user', password='testpassword123')
        request = self.factory.get('/')
        request.user = self.default_timezone_user
        self.middleware(request)
        self.assertEqual(get_current_timezone(), ZoneInfo(settings.TIME_ZONE))
    def test_authenticated_user_with_valid_timezone(self):
        """
            Test if the middleware correctly sets the timezone for an 
            authenticated user with a valid timezone.
        """
        self.client.login(username='timezone_user', password='testpassword123')
        request = self.factory.get('/')
        request.user = self.timezone_user
        self.middleware(request)
        self.assertEqual(get_current_timezone(), ZoneInfo("America/New_York"))
    def test_authenticated_user_with_invalid_timezone(self):
        """
            Test if the middleware falls back to settings.TIME_ZONE for 
            an authenticated user with an invalid timezone.
        """
        self.client.login(username='invalid_timezone_user', password='testpassword123')
        request = self.factory.get('/')
        request.user = self.invalid_timezone_user
        self.middleware(request)
        self.assertEqual(get_current_timezone(), ZoneInfo(settings.TIME_ZONE))
    def test_unauthenticated_user(self):
        """
        Test if the middleware sets settings.TIME_ZONE as the timezone for 
        an unauthenticated user.
        """
        request = self.factory.get('/')
        request.user = AnonymousUser()
        self.middleware(request)
        self.assertEqual(get_current_timezone(), ZoneInfo(settings.TIME_ZONE))
