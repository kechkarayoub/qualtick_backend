"""
Custom JWT Token Classes with Parent-Child Relationship Tracking

This module provides enhanced JWT tokens that track the relationship between
refresh tokens and their generated access tokens for device-specific logout.
"""

from asgiref.sync import sync_to_async
from rest_framework_simplejwt.tokens import RefreshToken as BaseRefreshToken


class RefreshToken(BaseRefreshToken):
    """
    Custom RefreshToken that adds parent_jti to access tokens.
    
    This enables device-specific logout by linking access tokens
    to their parent refresh tokens.
    """
    @property
    def access_token(self):
        """
        Override access_token generation to include parent_jti claim.
        
        The parent_jti claim contains the JTI of this refresh token,
        allowing us to check if the parent refresh token is blacklisted.
        """
        access = super().access_token
        # Add the parent refresh token's JTI to the access token
        access['parent_jti'] = self.get('jti')
        return access
    @classmethod
    @sync_to_async
    def for_user_async(cls, user):
        """
        Adds this token to the outstanding token list.
        """
        token = super().for_user(user)
        return token
