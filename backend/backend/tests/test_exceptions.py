"""
Test suite for backend exception handling.

This module tests:
- Custom exception classes from backend.exceptions
- Exception handling in services (GeolocationService, MessageService)
- Security and validation exception scenarios
"""

from unittest.mock import patch

from django.test import TestCase

from backend.exceptions import (
    GeolocationException,
    MessageSendException,
    FileUploadException
)
from backend.services.services import GeolocationService, MessageService, ValidationService


class ExceptionsTestCase(TestCase):
    """Test custom exceptions."""

    def test_geolocation_exception(self):
        """Test GeolocationException."""
        with self.assertRaises(GeolocationException):
            raise GeolocationException("Test error")

    def test_message_send_exception(self):
        """Test MessageSendException."""
        with self.assertRaises(MessageSendException):
            raise MessageSendException("Test error")

    def test_file_upload_exception(self):
        """Test FileUploadException."""
        with self.assertRaises(FileUploadException):
            raise FileUploadException("Test error")


class ErrorHandlingTestCase(TestCase):
    """Test error handling across services."""

    def test_geolocation_service_exception_handling(self):
        """Test geolocation service exception handling."""
        with patch('backend.services.get_geolocation_info') as mock_geo:
            mock_geo.side_effect = Exception("Network error")
            with self.assertRaises(GeolocationException):
                GeolocationService.get_geolocation_data('192.168.1.1')

    def test_message_service_exception_handling(self):
        """Test message service exception handling."""
        with patch('backend.services.send_whatsapp') as mock_whatsapp:
            mock_whatsapp.side_effect = Exception("WhatsApp API error")
            with self.assertRaises(MessageSendException):
                MessageService.send_verification_code('+1234567890', '123456')

    def test_message_service_bulk_exception_handling(self):
        """Test bulk message service exception handling."""
        with patch('backend.services.send_whatsapp') as mock_whatsapp:
            mock_whatsapp.side_effect = Exception("WhatsApp API error")
            with self.assertRaises(MessageSendException):
                MessageService.send_bulk_message(['+1234567890'], 'Test message')


class GeolocationServiceExceptionTestCase(TestCase):
    """Test GeolocationService exception scenarios."""

    @patch('backend.services.get_geolocation_info')
    def test_geolocation_service_failure(self, mock_geo_info):
        """Test geolocation service failure handling."""
        mock_geo_info.return_value = {
            'status': 'fail',
            'message': 'Invalid IP'
        }
        with self.assertRaises(GeolocationException):
            GeolocationService.get_geolocation_data('invalid-ip')

    def test_geolocation_service_no_ip(self):
        """Test GeolocationService when no IP is provided in request."""
        from django.test import RequestFactory
        
        factory = RequestFactory()
        request = factory.get('/')
        request.META = {}
        
        with self.assertRaises(GeolocationException):
            GeolocationService.get_client_ip(request)


class MessageServiceExceptionTestCase(TestCase):
    """Test MessageService exception scenarios."""

    @patch('backend.services.send_whatsapp')
    def test_message_service_send_verification_code_failure(self, mock_whatsapp):
        """Test verification code sending failure."""
        mock_whatsapp.return_value = {
            'nbr_verification_codes_sent': 0,
            'all_verification_codes_sent': False
        }
        with self.assertRaises(MessageSendException):
            MessageService.send_verification_code('+1234567890', '123456')

    @patch('backend.services.send_sms')
    def test_message_service_sms_exception(self, mock_send_sms):
        """Test SMS sending exception handling."""
        mock_send_sms.side_effect = Exception("SMS API error")
        with self.assertRaises(MessageSendException):
            MessageService.send_verification_code(
                '+1234567890', '123456', method='sms'
            )

    @patch('backend.services.send_sms')
    def test_message_service_bulk_sms_exception(self, mock_send_sms):
        """Test bulk SMS exception handling."""
        mock_send_sms.side_effect = Exception("SMS API error")
        with self.assertRaises(MessageSendException):
            MessageService.send_bulk_message(
                ['+1234567890', '+1234567891'], 'Test message', method='sms'
            )


class ValidationExceptionTestCase(TestCase):
    """Test validation-related exception scenarios."""

    def test_validation_service_invalid_inputs(self):
        """Test validation service with various invalid inputs."""
        
        # Test phone number validation with None
        self.assertFalse(ValidationService.validate_phone_number(None))
        
        # Test phone number validation with empty string
        self.assertFalse(ValidationService.validate_phone_number(''))
        
        # Test phone number validation with invalid format
        self.assertFalse(ValidationService.validate_phone_number('abc'))
        self.assertFalse(ValidationService.validate_phone_number('123'))
        
        # Test email validation with None
        self.assertFalse(ValidationService.validate_email(None))
        
        # Test email validation with empty string
        self.assertFalse(ValidationService.validate_email(''))
        
        # Test email validation with invalid formats
        self.assertFalse(ValidationService.validate_email('not-an-email'))
        self.assertFalse(ValidationService.validate_email('test@'))
        self.assertFalse(ValidationService.validate_email('@test.com'))
        self.assertFalse(ValidationService.validate_email('invalid-email'))


class GeolocationViewExceptionTestCase(TestCase):
    """Test exception handling in geolocation views."""

    def setUp(self):
        from django.test import RequestFactory
        self.factory = RequestFactory()

    @patch('backend.views.GeolocationService.get_client_ip')
    def test_get_geolocation_failure(self, mock_get_ip):
        """Test geolocation request failure."""
        import json
        from backend.views import get_geolocation
        
        mock_get_ip.side_effect = GeolocationException("IP not found")
        request = self.factory.get('/geolocation/')
        response = get_geolocation(request)
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn('error', data)


class SecurityExceptionTestCase(TestCase):
    """Test security-related exception scenarios."""

    def test_timezone_handling_invalid_timezone(self):
        """Test timezone handling with invalid timezone."""
        from datetime import datetime, timezone
        from backend.utils import get_local_datetime
        
        utc_time = datetime.now(timezone.utc)
        
        # Test with invalid timezone should raise KeyError
        with self.assertRaises(KeyError):
            get_local_datetime(utc_time, "Invalid/Timezone")
