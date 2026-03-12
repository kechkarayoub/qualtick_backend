"""
    Channels middleware
"""

# Import necessary Django and Channels modules
from urllib.parse import parse_qs
import time

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.backends import TokenBackend
from rest_framework_simplejwt.token_blacklist.models import (BlacklistedToken,
                                                             OutstandingToken)

from accounts.repositories import UserRepository
from backend.utils import get_db_alias

# Get the custom user model
User = get_user_model()


# Async function to get user from JWT token
@database_sync_to_async
def get_user_from_token(token, db_alias=''): # pylint: disable=too-many-return-statements
    """
        Get user from token.
        Args:
            token (str): User's token
            db_alias (str): Database alias to use
        Returns:
            User, error_reason (tuple): User of token if valid, if not valid error_reason
                contains reason
    """
    try:
        # Decode the JWT token using SimpleJWT's TokenBackend
        token_backend = TokenBackend(algorithm="HS256", signing_key=settings.SECRET_KEY)
        payload = token_backend.decode(token, verify=True)
        user_id = payload.get("user_id")
        parent_jti = payload.get("parent_jti")  # JWT ID for blacklist checking
        current_time = int(time.time())  # current Unix timestamp
        if payload['exp'] < current_time:
            return AnonymousUser(), "token_expired"
        if user_id is None:
            # If no user_id in token, return AnonymousUser
            return AnonymousUser(), "invalid_token"
        if parent_jti is None:
            # If no parent_jti in token, return AnonymousUser
            return AnonymousUser(), "invalid_token"
        # Check if token is blacklisted
        try:
            outstanding_token = OutstandingToken.objects.using(db_alias or None).get(jti=parent_jti)
            if BlacklistedToken.objects.using(db_alias or None).filter(token=outstanding_token).exists():
                return AnonymousUser(), "token_blacklisted"
        except OutstandingToken.DoesNotExist:
            # Token not found in outstanding tokens, might be invalid
            return AnonymousUser(), "invalid_token"
        try:
            # Try to fetch the user from the database
            user = UserRepository.get_by_id(user_id, db_alias=db_alias)
            return user, "valid"
        except User.DoesNotExist:
            # If user does not exist, return AnonymousUser
            return AnonymousUser(), "user_not_found"
    except Exception as e: # pylint: disable=broad-exception-caught
        # Check if it's a token expiration error
        if "signature has expired" in str(e).lower():
            return AnonymousUser(), "token_expired"
        # If token is invalid or any error occurs, return AnonymousUser
        return AnonymousUser(), "invalid_token"


# Custom Channels middleware to authenticate user from JWT in query string
class QueryAuthMiddleware(BaseMiddleware): #pylint: disable=too-few-public-methods
    """
        Custom middleware to authenticate user from JWT token in query string.
        The token is expected to be passed as a query parameter named 'token'.
    """
    async def __call__(self, scope, receive, send):
        # Parse the query string from the WebSocket connection
        db_alias = get_db_alias()
        query_string = scope.get("query_string", b"").decode()
        query_params = parse_qs(query_string)
        # Extract the token from query params (e.g., ws://.../?token=...)
        token_list = query_params.get("token")
        token = token_list[0] if token_list else None
        # Set the user in scope based on the token (or AnonymousUser if not present/invalid)
        if token:
            user, error_reason = await get_user_from_token(token, db_alias=db_alias)
            scope["user"] = scope.get("user") or user
            scope["auth_error"] = error_reason if error_reason != "valid" else None
        else:
            scope["user"] = scope.get("user") or AnonymousUser()
            scope["auth_error"] = "no_token"
        # Continue processing the connection
        return await super().__call__(scope, receive, send)


# Helper to use the custom middleware in ASGI application
def query_auth_middleware_stack(inner):
    """query auth middleware stack"""
    return QueryAuthMiddleware(inner)
