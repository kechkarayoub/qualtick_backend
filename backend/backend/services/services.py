# pylint: disable=broad-exception-caught,logging-fstring-interpolation
"""
Service layer utilities for the backend project.
Provides high-level business logic and service operations.
"""

import logging
from typing import Optional, Dict, Any

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils.translation import gettext_lazy as _
import phonenumbers

from backend.exceptions import GeolocationException, MessageSendException
from backend.utils import get_geolocation_info, send_whatsapp, send_sms
from backend.repositories import ContactMessageRepository
from backend.utils import get_db_alias


logger = logging.getLogger(__name__)


class GeolocationService:
    """Service for handling geolocation operations."""
    CACHE_TIMEOUT = 3600  # 1 hour
    @classmethod
    def get_client_ip(cls, request):
        """
        Extract client IP address from request.
        Args:
            request: Django request object
        Returns:
            str: Client IP address
        Raises:
            GeolocationException: If IP cannot be determined
        """
        ip = (
            request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip() or
            request.META.get("HTTP_X_REAL_IP") or
            request.META.get("REMOTE_ADDR")
        )
        if not ip:
            raise GeolocationException(
                _("Geolocation service unavailable. Try again later."))
        return ip

    @classmethod
    def get_geolocation_data(cls, ip_address, fields="country,countryCode", use_cache=True):
        """
        Get geolocation data for IP address with caching.
        Args:
            ip_address (str): IP address to lookup
            fields (str): Comma-separated fields to retrieve
            use_cache (bool): Whether to use caching
        Returns:
            dict: Geolocation data
        Raises:
            GeolocationException: If geolocation fails
        """
        cache_key = f"geolocation:{ip_address}:{fields}"
        if use_cache:
            cached_data = cache.get(cache_key)
            if cached_data:
                return cached_data
        try:
            data = get_geolocation_info(ip_address, fields)
            if data.get("status") == "fail":
                raise GeolocationException(data.get("message",
                                                    "Geolocation service failed"))
            if use_cache:
                cache.set(cache_key, data, cls.CACHE_TIMEOUT)
            return data
        except Exception as e:
            logger.error(f"Geolocation error for IP {ip_address}: {str(e)}")
            raise GeolocationException(_("Geolocation service unavailable")) from e


class MessageService:
    """Service for handling message operations."""
    @classmethod
    def send_verification_code(cls, phone_number, code, method="whatsapp"):
        """
        Send verification code to phone number.
        Args:
            phone_number (str): Phone number to send to
            code (str): Verification code
            method (str): Sending method (whatsapp/sms)
        Returns:
            dict: Result of sending operation
        Raises:
            MessageSendException: If sending fails
        """
        message = _("Your verification code is: {code}").format(code=code)
        try:
            if method == "whatsapp":
                result = send_whatsapp(message, [phone_number])
            else:
                result = send_sms(message, [phone_number])
            if not result.get("all_verification_codes_sent"):
                raise MessageSendException(_("Failed to send verification code"))
            return result
        except Exception as e:
            logger.error(f"Message send error to {phone_number}: {str(e)}")
            raise MessageSendException(_("Message sending service unavailable")) from e

    @classmethod
    def send_bulk_message(cls, phone_numbers, message, method="whatsapp"):
        """
        Send bulk message to multiple phone numbers.
        Args:
            phone_numbers (list): List of phone numbers
            message (str): Message content
            method (str): Sending method (whatsapp/sms)
        Returns:
            dict: Result of bulk sending operation
        """
        try:
            if method == "whatsapp":
                result = send_whatsapp(message, phone_numbers)
            else:
                result = send_sms(message, phone_numbers)
            return result
        except Exception as e:
            logger.error(f"Bulk message send error: {str(e)}")
            raise MessageSendException(_("Bulk message sending failed")) from e


class CacheService:
    """Service for handling cache operations."""
    @classmethod
    def get_or_set(cls, key, callable_func, timeout=300):
        """
        Get value from cache or set it if not exists.
        Args:
            key (str): Cache key
            callable_func: Function to call if cache miss
            timeout (int): Cache timeout in seconds
        Returns:
            Any: Cached or computed value
        """
        value = cache.get(key)
        if value is None:
            value = callable_func()
            cache.set(key, value, timeout)
        return value

    @classmethod
    def invalidate_pattern(cls, pattern):
        """
        Invalidate cache keys matching pattern.
        Args:
            pattern (str): Pattern to match cache keys
        """
        try:
            cache.delete_many(cache.keys(pattern))
        except Exception as e:
            logger.warning(f"Cache invalidation failed for pattern {pattern}: {str(e)}")


class ValidationService:
    """Service for handling validation operations."""
    @classmethod
    def validate_phone_number(cls, phone_number):
        """
        Validate phone number format.
        Args:
            phone_number (str): Phone number to validate
        Returns:
            bool: True if valid
        """
        try:
            parsed = phonenumbers.parse(phone_number, settings.DEFAULT_PHONE_NUMBER_COUNTRY_CODE)
            return phonenumbers.is_valid_number(parsed)
        except phonenumbers.NumberParseException:
            return False

    @classmethod
    def validate_email(cls, email):
        """
        Validate email format.
        Args:
            email (str): Email to validate
        Returns:
            bool: True if valid
        """
        try:
            validate_email(email)
            return True
        except ValidationError:
            return False


class ContactMessageService:
    """Service for handling contact message business logic."""
    
    @classmethod
    def create_contact_message(cls, data: Dict[str, Any], user=None, db_alias: str = '') -> Dict[str, Any]:
        """
        Create a new contact message.
        
        Args:
            data: Dictionary containing message data (name, email, subject, message)
            user: Optional authenticated user
            
        Returns:
            Dictionary with success status and created message or error
            
        Raises:
            ValidationError: If data is invalid
        """
        try:
            # Validate email
            if not ValidationService.validate_email(data.get('email', '')):
                return {
                    'success': False,
                    'error': _('Invalid email address')
                }
            
            # Create message data
            message_data = {
                'name': data.get('name'),
                'email': data.get('email'),
                'subject': data.get('subject'),
                'message': data.get('message'),
            }
            
            if user and user.is_authenticated:
                message_data['user_id'] = user.id
            
            # Create through repository
            contact_message = ContactMessageRepository.create(db_alias=db_alias, **message_data)
            
            logger.info(
                f"Contact message created: ID {contact_message.id} from {contact_message.email}"
            )
            
            return {
                'success': True,
                'message': contact_message,
                'id': contact_message.id
            }
            
        except Exception as e:
            logger.error(f"Error creating contact message: {str(e)}")
            raise
    
    @classmethod
    def get_message_by_id(cls, message_id: int, db_alias: str = '') -> Optional[Any]:
        """Get contact message by ID."""
        return ContactMessageRepository.get_by_id(message_id, db_alias=db_alias)
    
    @classmethod
    def get_user_messages(cls, user_id: int, db_alias: str = ''):
        """Get all messages from a specific user."""
        return ContactMessageRepository.get_by_user(user_id, db_alias=db_alias)
    
    @classmethod
    def get_messages_by_status(cls, status: str, db_alias: str = ''):
        """Get all messages with a specific status."""
        return ContactMessageRepository.get_by_status(status, db_alias=db_alias)
    
    @classmethod
    def get_pending_messages(cls, db_alias: str = ''):
        """Get all pending messages."""
        return ContactMessageRepository.get_pending(db_alias=db_alias)
    
    @classmethod
    def update_message_status(cls, message_id: int, status: str, admin_notes: Optional[str] = None, db_alias: str = '') -> Optional[Any]:
        """
        Update the status of a contact message.
        
        Args:
            message_id: ID of the message
            status: New status
            admin_notes: Optional admin notes
            db_alias: Database alias to use
            
        Returns:
            Updated message or None
        """
        return ContactMessageRepository.update_status(
            message_id, status, admin_notes, db_alias=db_alias
        )
    
    @classmethod
    def search_messages(cls, query: str, db_alias: str = ''):
        """Search contact messages."""
        return ContactMessageRepository.search(query, db_alias=db_alias)
    
    @classmethod
    def get_statistics(cls, db_alias: str = '') -> Dict[str, int]:
        """Get contact message statistics."""
        return ContactMessageRepository.get_statistics(db_alias=db_alias)

