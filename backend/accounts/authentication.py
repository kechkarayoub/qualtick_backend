"""
Custom JWT Authentication with Parent Token Tracking

This module provides enhanced JWT authentication that links access tokens
to their parent refresh tokens for device-specific logout behavior.
"""

import logging

from django.contrib.auth import get_user_model
from rest_framework import exceptions
from rest_framework_simplejwt.authentication import \
    JWTAuthentication as BaseJWTAuthentication
from rest_framework_simplejwt.token_blacklist.models import (BlacklistedToken,
                                                             OutstandingToken)

logger = logging.getLogger(__name__)
User = get_user_model()
from backend.utils import get_db_alias


class JWTAuthentication(BaseJWTAuthentication):
    """
    Custom JWT Authentication that tracks parent refresh tokens.
    
    BEST PRACTICE SOLUTION:
    - Add 'parent_jti' claim to access tokens during generation
    - This links access tokens to their parent refresh token
    - Check if parent refresh token is blacklisted
    - Simple, reliable, no external dependencies
    """
    def authenticate(self, request):
        """
        Authenticate the request and check if parent refresh token is blacklisted.
        """
        db_alias = get_db_alias(request=request)
        result = super().authenticate(request)
        if result is None:
            return result
        user, validated_token = result
        # Check if the parent refresh token is blacklisted
        if self.is_parent_token_blacklisted(validated_token, db_alias=db_alias):
            logger.warning(
                "User %s attempted to use access token from blacklisted parent session",
                user.username
            )
            raise exceptions.AuthenticationFailed(
                'Device session has been terminated. Please log in again.',
                code='device_session_terminated'
            )
        return user, validated_token
    def is_parent_token_blacklisted(self, validated_token, db_alias=''):
        """
        Check if the parent refresh token that generated this access token is blacklisted.
        
        This uses the 'parent_jti' claim that we add to access tokens during generation.
        This claim contains the JTI of the refresh token that created the access token.
        
        Args:
            validated_token: The decoded JWT access token
            db_alias: Database alias to use
            
        Returns:
            bool: True if parent refresh token is blacklisted, False otherwise
        """
        try:
            # Get the parent JTI from the access token
            parent_jti = validated_token.get('parent_jti')
            if not parent_jti:
                # If no parent_jti, this access token wasn't generated with our custom logic
                # Fall back to standard behavior (allow the request)
                logger.debug("No parent_jti found in access token, allowing request")
                return False
            # Check if the parent refresh token is blacklisted
            try:
                outstanding_token = OutstandingToken.objects.using(db_alias or None).get(jti=parent_jti)
                is_blacklisted = BlacklistedToken.objects.using(db_alias or None).filter(
                    token=outstanding_token).exists()
                if is_blacklisted:
                    logger.info("Parent refresh token %s is blacklisted", parent_jti)
                    return True
                return False
            except OutstandingToken.DoesNotExist:
                # Parent token not found - might be expired or cleaned up
                logger.debug("Parent token with JTI %s not found, allowing request", parent_jti)
                return False
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error checking parent token blacklist status: %s", str(e))
            # In case of error, allow the request (fail open for availability)
            return False
    def is_user_logged_out(self, validated_token, db_alias=''):
        """
        Check if the parent refresh token that generated this access token is blacklisted.
        
        This uses the 'parent_jti' claim that we add to access tokens during generation.
        This claim contains the JTI of the refresh token that created the access token.
        
        Args:
            validated_token: The decoded JWT access token
            db_alias: Database alias to use
            
        Returns:
            bool: True if parent refresh token is blacklisted, False otherwise
        """
        return self.is_parent_token_blacklisted(validated_token, db_alias=db_alias)
