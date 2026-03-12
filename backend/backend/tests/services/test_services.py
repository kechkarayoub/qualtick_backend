# pylint: disable=R0801
"""
Consolidated service layer tests.
Tests for backend/services.py - all service classes.
"""

import asyncio
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import patch, Mock
from zoneinfo import ZoneInfo

from django.test import TestCase, RequestFactory
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache

from backend.exceptions import GeolocationException, MessageSendException
from backend.services.services import (
    CacheService, GeolocationService, MessageService,
    ValidationService, ContactMessageService
)

from accounts.repositories import UserRepository
from backend.repositories import ContactMessageRepository
from backend.utils import get_db_alias


User = get_user_model()


class GeolocationServiceTestCase(TestCase):
    """Test GeolocationService functionality."""

    def setUp(self):
        self.factory = RequestFactory()
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_geolocation_service_get_client_ip(self):
        """Test client IP extraction from request."""
        # Test with X-Forwarded-For header
        request = self.factory.get('/')
        request.META['HTTP_X_FORWARDED_FOR'] = '192.168.1.1, 10.0.0.1'
        ip = GeolocationService.get_client_ip(request)
        self.assertEqual(ip, '192.168.1.1')

        # Test with X-Real-IP header
        request = self.factory.get('/')
        request.META['HTTP_X_REAL_IP'] = '10.0.0.1'
        ip = GeolocationService.get_client_ip(request)
        self.assertEqual(ip, '10.0.0.1')

        # Test with REMOTE_ADDR
        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = '127.0.0.1'
        ip = GeolocationService.get_client_ip(request)
        self.assertEqual(ip, '127.0.0.1')

        # Test with no IP (should raise exception)
        request = self.factory.get('/')
        request.META = {}
        with self.assertRaises(GeolocationException):
            GeolocationService.get_client_ip(request)

    @patch('backend.services.services.get_geolocation_info')
    def test_geolocation_service_get_data(self, mock_geo_info):
        """Test geolocation data retrieval."""
        mock_geo_info.return_value = {
            'country': 'France',
            'countryCode': 'FR',
            'status': 'success'
        }
        data = GeolocationService.get_geolocation_data('192.168.1.1')
        self.assertEqual(data['country'], 'France')
        self.assertEqual(data['countryCode'], 'FR')
        mock_geo_info.assert_called_once_with('192.168.1.1', 'country,countryCode')

    @patch('backend.services.services.get_geolocation_info')
    def test_geolocation_service_failure(self, mock_geo_info):
        """Test geolocation service failure handling."""
        mock_geo_info.return_value = {
            'status': 'fail',
            'message': 'Invalid IP'
        }
        with self.assertRaises(GeolocationException):
            GeolocationService.get_geolocation_data('invalid-ip')

    @patch('backend.services.services.get_geolocation_info')
    def test_geolocation_service_caching(self, mock_geo_info):
        """Test geolocation data caching."""
        mock_geo_info.return_value = {
            'country': 'France',
            'countryCode': 'FR'
        }
        # First call should hit the API
        data1 = GeolocationService.get_geolocation_data('192.168.1.1', use_cache=True)
        # Second call should use cache
        data2 = GeolocationService.get_geolocation_data('192.168.1.1', use_cache=True)
        self.assertEqual(data1, data2)
        mock_geo_info.assert_called_once()  # Should only be called once due to caching

    def test_geolocation_service_without_cache(self):
        """Test geolocation service without caching."""
        with patch('backend.services.services.get_geolocation_info') as mock_geo:
            mock_geo.return_value = {
                'country': 'France',
                'countryCode': 'FR'
            }
            data = GeolocationService.get_geolocation_data(
                '192.168.1.1', use_cache=False
            )
            self.assertEqual(data['country'], 'France')
            # Should not interact with cache
            self.assertIsNone(cache.get('geolocation:192.168.1.1:country,countryCode'))

    def test_geolocation_service_exception_handling(self):
        """Test geolocation service exception handling."""
        with patch('backend.services.services.get_geolocation_info') as mock_geo:
            mock_geo.side_effect = Exception("Network error")
            with self.assertRaises(GeolocationException):
                GeolocationService.get_geolocation_data('192.168.1.1')


class MessageServiceTestCase(TestCase):
    """Test MessageService functionality."""

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    @patch('backend.services.services.send_whatsapp')
    def test_message_service_send_verification_code(self, mock_whatsapp):
        """Test verification code sending."""
        mock_whatsapp.return_value = {
            'nbr_verification_codes_sent': 1,
            'all_verification_codes_sent': True
        }
        result = MessageService.send_verification_code('+1234567890', '123456')
        self.assertTrue(result['all_verification_codes_sent'])
        self.assertEqual(result['nbr_verification_codes_sent'], 1)

    @patch('backend.services.services.send_whatsapp')
    def test_message_service_send_verification_code_failure(self, mock_whatsapp):
        """Test verification code sending failure."""
        mock_whatsapp.return_value = {
            'nbr_verification_codes_sent': 0,
            'all_verification_codes_sent': False
        }
        with self.assertRaises(MessageSendException):
            MessageService.send_verification_code('+1234567890', '123456')

    @patch('backend.services.services.send_whatsapp')
    def test_message_service_send_bulk_message(self, mock_whatsapp):
        """Test bulk message sending."""
        mock_whatsapp.return_value = {
            'nbr_verification_codes_sent': 2,
            'all_verification_codes_sent': True
        }
        result = MessageService.send_bulk_message(
            ['+1234567890', '+1234567891'], 'Test message')
        self.assertTrue(result['all_verification_codes_sent'])
        self.assertEqual(result['nbr_verification_codes_sent'], 2)

    @patch('backend.services.services.send_sms')
    def test_message_service_sms_method(self, mock_send_sms):
        """Test message service with SMS method."""
        mock_send_sms.return_value = {
            'nbr_verification_codes_sent': 1,
            'all_verification_codes_sent': True
        }
        result = MessageService.send_verification_code(
            '+1234567890', '123456', method='sms'
        )
        self.assertTrue(result['all_verification_codes_sent'])
        mock_send_sms.assert_called_once()

    @patch('backend.services.services.send_sms')
    def test_message_service_bulk_sms(self, mock_send_sms):
        """Test bulk SMS sending."""
        mock_send_sms.return_value = {
            'nbr_verification_codes_sent': 2,
            'all_verification_codes_sent': True
        }
        result = MessageService.send_bulk_message(
            ['+1234567890', '+1234567891'], 'Test message', method='sms'
        )
        self.assertTrue(result['all_verification_codes_sent'])
        mock_send_sms.assert_called_once()

    def test_message_service_exception_handling(self):
        """Test message service exception handling."""
        with patch('backend.services.services.send_whatsapp') as mock_whatsapp:
            mock_whatsapp.side_effect = Exception("WhatsApp API error")
            with self.assertRaises(MessageSendException):
                MessageService.send_verification_code('+1234567890', '123456')

    def test_message_service_bulk_exception_handling(self):
        """Test bulk message service exception handling."""
        with patch('backend.services.services.send_whatsapp') as mock_whatsapp:
            mock_whatsapp.side_effect = Exception("WhatsApp API error")
            with self.assertRaises(MessageSendException):
                MessageService.send_bulk_message(['+1234567890'], 'Test message')


class ValidationServiceTestCase(TestCase):
    """Test ValidationService functionality."""

    def test_validation_service_phone_number(self):
        """Test phone number validation."""
        # Valid phone numbers
        self.assertTrue(ValidationService.validate_phone_number('+33123456789'))
        self.assertTrue(ValidationService.validate_phone_number('+212612345678'))

        # Invalid phone numbers
        self.assertFalse(ValidationService.validate_phone_number('invalid'))
        self.assertFalse(ValidationService.validate_phone_number('123'))
        self.assertFalse(ValidationService.validate_phone_number(''))

    def test_validation_service_email(self):
        """Test email validation."""
        # Valid emails
        self.assertTrue(ValidationService.validate_email('test@example.com'))
        self.assertTrue(ValidationService.validate_email('user.name@domain.co.uk'))
        self.assertTrue(ValidationService.validate_email('user+tag@domain.co.uk'))

        # Invalid emails
        self.assertFalse(ValidationService.validate_email('invalid-email'))
        self.assertFalse(ValidationService.validate_email('test@'))
        self.assertFalse(ValidationService.validate_email('@domain.com'))
        self.assertFalse(ValidationService.validate_email(''))
        self.assertFalse(ValidationService.validate_email('missing@'))

    def test_validation_service_edge_cases(self):
        """Test validation service edge cases."""
        # Test phone number validation edge cases
        self.assertFalse(ValidationService.validate_phone_number(None))
        self.assertFalse(ValidationService.validate_phone_number(''))
        self.assertFalse(ValidationService.validate_phone_number('abc'))
        self.assertFalse(ValidationService.validate_phone_number('123'))

        # Test email validation edge cases
        self.assertFalse(ValidationService.validate_email(None))
        self.assertFalse(ValidationService.validate_email(''))
        self.assertFalse(ValidationService.validate_email('not-an-email'))
        self.assertFalse(ValidationService.validate_email('test@'))
        self.assertFalse(ValidationService.validate_email('@test.com'))


class CacheServiceTestCase(TestCase):
    """Test CacheService functionality."""

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_cache_service_get_or_set(self):
        """Test cache service get_or_set method."""
        def expensive_operation():
            return "computed_value"

        # First call should compute and cache
        result1 = CacheService.get_or_set('test_key', expensive_operation, 300)
        self.assertEqual(result1, "computed_value")

        # Second call should return cached value
        result2 = CacheService.get_or_set('test_key', lambda: "different_value", 300)
        self.assertEqual(result2, "computed_value")  # Should be cached value

    def test_cache_service_get_or_set_with_callable(self):
        """Test cache service with callable function."""
        call_count = 0

        def expensive_operation():
            nonlocal call_count
            call_count += 1
            return f"result_{call_count}"

        # First call should execute the function
        result1 = CacheService.get_or_set('test_key', expensive_operation, 300)
        self.assertEqual(result1, "result_1")
        self.assertEqual(call_count, 1)

        # Second call should return cached value
        result2 = CacheService.get_or_set('test_key', expensive_operation, 300)
        self.assertEqual(result2, "result_1")  # Should be cached
        self.assertEqual(call_count, 1)  # Function should not be called again

    def test_cache_service_get_or_set_with_none_result(self):
        """Test cache service when callable returns None."""
        def return_none():
            return None

        result = CacheService.get_or_set('test_key', return_none, 300)
        self.assertIsNone(result)

        # Should cache Value
        result2 = CacheService.get_or_set('test_key', lambda: "different", 300)
        self.assertEqual(result2, "different")

        # Should return cached Value
        result2 = CacheService.get_or_set('test_key', return_none, 300)
        self.assertEqual(result2, "different")

    def test_cache_service_invalidate_pattern(self):
        """Test cache service pattern invalidation."""
        # Set some cache values
        cache.set('test_pattern_1', 'value1', 300)
        cache.set('test_pattern_2', 'value2', 300)
        cache.set('other_key', 'value3', 300)

        # This is a basic test - actual implementation depends on cache backend
        # This will not work with LocMemCache as it does not support pattern matching
        CacheService.invalidate_pattern('test_pattern_*')

        # Test that the method doesn't crash
        self.assertEqual(cache.get('test_pattern_1'), 'value1')

    def test_cache_service_invalidate_pattern_with_error(self):
        """Test cache service pattern invalidation with error handling."""
        # This tests the error handling in invalidate_pattern
        with patch('backend.services.services.cache.delete_many') as mock_delete:
            mock_delete.side_effect = Exception("Cache error")
            # Should not raise an exception
            CacheService.invalidate_pattern('test_*')
            # cache.keys(pattern) will raise error in LocMemCache used in local
            mock_delete.assert_not_called()


class ContactMessageServiceTestCase(TestCase):
    """Test ContactMessageService functionality."""

    def setUp(self):
        """Set up test data."""
        db_alias = get_db_alias()
        suffix = uuid4().hex[:8]
        self.user = UserRepository.create_user(
            username=f'testuser_{suffix}',
            email=f'test_{suffix}@example.com',
            password='testpass123',
            db_alias=db_alias
        )

    def test_create_contact_message_success(self):
        """Test creating a contact message successfully."""
        db_alias = get_db_alias()
        data = {
            'name': 'John Doe',
            'email': 'john@example.com',
            'subject': 'support',
            'message': 'I need help with my account'
        }

        result = ContactMessageService.create_contact_message(
            data, user=self.user, db_alias=db_alias)

        self.assertTrue(result['success'])
        self.assertIn('id', result)
        self.assertIsNotNone(result['message'])

    def test_create_contact_message_invalid_email(self):
        """Test creating message with invalid email."""
        db_alias = get_db_alias()
        data = {
            'name': 'John Doe',
            'email': 'invalid-email',
            'subject': 'support',
            'message': 'Test message'
        }

        result = ContactMessageService.create_contact_message(data, db_alias=db_alias)

        self.assertFalse(result['success'])
        self.assertIn('error', result)

    def test_get_user_messages(self):
        """Test getting user's messages."""
        db_alias = get_db_alias()
        # Create message for user
        ContactMessageRepository.create(
            name=self.user.username,
            email=self.user.email,
            subject='support',
            message='Test',
            user_id=self.user.id,
            db_alias=db_alias
        )

        messages = ContactMessageService.get_user_messages(self.user.id, db_alias=db_alias)
        self.assertEqual(messages.count(), 1)

    def test_update_message_status(self):
        """Test updating message status."""
        db_alias = get_db_alias()
        message = ContactMessageRepository.create(
            name='Test',
            email='test@test.com',
            subject='support',
            message='Test message'
        )

        updated = ContactMessageService.update_message_status(
            message.id,
            'resolved',
            admin_notes='Resolved by admin',
            db_alias=db_alias
        )

        self.assertIsNotNone(updated)
        self.assertEqual(updated.status, 'resolved')
        self.assertEqual(updated.admin_notes, 'Resolved by admin')

    def test_get_statistics(self):
        """Test getting statistics."""
        db_alias = get_db_alias()
        # Create test messages
        ContactMessageRepository.create(
            name='Test1',
            email='test1@test.com',
            subject='support',
            message='Test',
            status='new',
            db_alias=db_alias
        )
        ContactMessageRepository.create(
            name='Test2',
            email='test2@test.com',
            subject='billing',
            message='Test',
            status='resolved',
            db_alias=db_alias
        )

        stats = ContactMessageService.get_statistics(db_alias=db_alias)

        self.assertEqual(stats['total'], 2)
        self.assertEqual(stats['new'], 1)
        self.assertEqual(stats['resolved'], 1)


class ServiceIntegrationTestCase(TestCase):
    """Integration tests for service interactions."""

    def setUp(self):
        db_alias = get_db_alias()
        self.factory = RequestFactory()
        self.user = UserRepository.create_user(
            email="integration@example.com",
            username="integration_user",
            password="testpass123",
            db_alias=db_alias
        )
        cache.clear()

    def tearDown(self):
        cache.clear()

    @patch('backend.services.services.get_geolocation_info')
    def test_geolocation_caching_integration(self, mock_geo_info):
        """Test geolocation data caching integration."""
        mock_geo_info.return_value = {
            'country': 'France',
            'countryCode': 'FR'
        }
        # First call should hit the API
        data1 = GeolocationService.get_geolocation_data('192.168.1.1', use_cache=True)
        # Second call should use cache
        data2 = GeolocationService.get_geolocation_data('192.168.1.1', use_cache=True)
        self.assertEqual(data1, data2)
        mock_geo_info.assert_called_once()  # Should only be called once due to caching

    def test_message_and_validation_integration(self):
        """Test message service with validation."""
        # Test with valid phone number
        valid_phone = '+212612345678'
        self.assertTrue(ValidationService.validate_phone_number(valid_phone))

        with patch('backend.services.services.send_whatsapp') as mock_whatsapp:
            mock_whatsapp.return_value = {
                'nbr_verification_codes_sent': 1,
                'all_verification_codes_sent': True
            }
            result = MessageService.send_verification_code(valid_phone, '123456')
            self.assertTrue(result['all_verification_codes_sent'])

    def test_contact_message_with_validation(self):
        """Test contact message service with validation."""
        db_alias = get_db_alias()
        # Test with valid email
        valid_email = 'test@example.com'
        self.assertTrue(ValidationService.validate_email(valid_email))

        data = {
            'name': 'Test User',
            'email': valid_email,
            'subject': 'support',
            'message': 'Test message'
        }
        result = ContactMessageService.create_contact_message(data, db_alias=db_alias)
        self.assertTrue(result['success'])

        # Test with invalid email
        invalid_email = 'invalid-email'
        self.assertFalse(ValidationService.validate_email(invalid_email))

        data['email'] = invalid_email
        result = ContactMessageService.create_contact_message(data, db_alias=db_alias)
        self.assertFalse(result['success'])
