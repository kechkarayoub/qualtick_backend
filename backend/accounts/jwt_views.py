"""
Custom JWT Views with Parent-Child Relationship Tracking

This module provides enhanced JWT views that use our custom RefreshToken
to maintain parent-child relationships between tokens.
"""

import logging

from django.contrib.auth import authenticate, get_user_model
from rest_framework import status
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.views import \
    TokenObtainPairView as BaseTokenObtainPairView
from rest_framework_simplejwt.views import \
    TokenRefreshView as BaseTokenRefreshView

from accounts.repositories import UserRepository
from accounts.tokens import RefreshToken
from backend.utils import get_db_alias

logger = logging.getLogger(__name__)


class TokenObtainPairView(BaseTokenObtainPairView):
    """
    Custom TokenObtainPairView that uses our custom RefreshToken class.
    
    This ensures that initial token generation includes the parent_jti claim
    for device-specific logout tracking.
    """
    def post(self, request, *args, **kwargs):
        """
        Override to use our custom RefreshToken class.
        """
        db_alias = get_db_alias(request=request)
        try:
            # Get user credentials
            username = request.data.get('username')
            password = request.data.get('password')
            if not username or not password:
                return Response({
                    'detail': 'Username and password are required'
                }, status=status.HTTP_400_BAD_REQUEST)
            # Authenticate user (simplified - you might want to use Django's authenticate)
            User = get_user_model()
            # Try to find user by username or email
            if '@' in username:
                user = UserRepository.get_by_email(email=username, db_alias=db_alias).first()
                if user:
                    user = authenticate(request, username=user.username, password=password)
            else:
                user = authenticate(request, username=username, password=password)
            if not user:
                return Response({
                    'detail': 'Invalid credentials'
                }, status=status.HTTP_401_UNAUTHORIZED)
            # Generate tokens using our custom RefreshToken
            refresh = RefreshToken.for_user(user)
            data = {
                'access': str(refresh.access_token),
                'refresh': str(refresh)
            }
            logger.info("Tokens generated successfully with parent_jti "
                        "tracking for user %s", user.username)
            return Response(data, status=status.HTTP_200_OK)
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Unexpected error during token generation: %s", str(e))
            return Response({
                'detail': 'Token generation failed'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TokenRefreshView(BaseTokenRefreshView):
    """
    Custom TokenRefreshView that uses our custom RefreshToken class.
    
    This ensures that when tokens are refreshed, the new access tokens
    maintain the parent_jti claim for device-specific logout tracking.
    """
    def post(self, request, *args, **kwargs):
        """
        Override to use our custom RefreshToken class.
        """
        db_alias = get_db_alias(request=request)
        try:
            refresh_token_str = request.data.get('refresh')
            if not refresh_token_str:
                return Response({
                    'detail': 'Refresh token is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            # Use our custom RefreshToken class
            refresh = RefreshToken(refresh_token_str)
            # Generate new access token with parent_jti claim
            new_access_token = refresh.access_token
            data = {
                'access': str(new_access_token)
            }
            # Optionally rotate refresh token (if ROTATE_REFRESH_TOKENS is True)
            if api_settings.ROTATE_REFRESH_TOKENS:
                # Get user from refresh token
                User = get_user_model()
                user_id = refresh.payload.get('user_id')
                user = UserRepository.get_by_id(user_id, db_alias=db_alias)
                # Create new refresh token
                new_refresh = RefreshToken.for_user(user)
                data['refresh'] = str(new_refresh)
                # Blacklist old refresh token if blacklisting is enabled
                if api_settings.BLACKLIST_AFTER_ROTATION:
                    try:
                        refresh.blacklist()
                    except AttributeError:
                        # Token blacklisting not available
                        pass
            logger.info("Token refreshed successfully with parent_jti tracking")
            return Response(data, status=status.HTTP_200_OK)
        except TokenError as e:
            logger.warning("Token refresh failed: %s", str(e))
            return Response({
                'detail': 'Invalid or expired refresh token'
            }, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Unexpected error during token refresh: %s", str(e))
            return Response({
                'detail': 'Token refresh failed'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
