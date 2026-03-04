"""Test channels jwt middleware"""

import asyncio

from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from accounts.repositories import UserRepository
from accounts.tokens import RefreshToken
from backend.middleware.channels_jwt_middleware import get_user_from_token
from backend.utils import get_db_alias

User = get_user_model()

class GetUserFromTokenTests(TestCase):
    """Tests for get_user_from_token function."""
    def test_get_user_from_token_valid(self):
        """Test valid token returns correct user."""
        async def run():
            db_alias = get_db_alias()
            user = await database_sync_to_async(UserRepository.create_user)(
                email='testuser@example.com', password='testpass123', username='testuser',
                db_alias=db_alias)
            refresh_token = await database_sync_to_async(RefreshToken.for_user)(user)
            access_token = refresh_token.access_token
            result, error = await get_user_from_token(str(access_token), db_alias=db_alias)
            self.assertEqual(result.id, user.id)
            self.assertEqual(error, "valid")
        asyncio.get_event_loop().run_until_complete(run())

    def test_get_user_from_token_invalid(self):
        """Test invalid token returns AnonymousUser."""
        async def run():
            db_alias = get_db_alias()
            invalid_token = 'invalid.token.value'
            result, error = await get_user_from_token(invalid_token, db_alias=db_alias)
            self.assertIsInstance(result, AnonymousUser)
            self.assertEqual(error, "invalid_token")
        asyncio.get_event_loop().run_until_complete(run())

    def test_get_user_from_token_no_user(self):
        """Test token with non-existent user returns AnonymousUser."""
        async def run():
            db_alias = get_db_alias()
            user = await database_sync_to_async(UserRepository.create_user)(
                email='testuser2@example.com', password='testpass123', username='testuser2',
                db_alias=db_alias)
            refresh_token = await database_sync_to_async(RefreshToken.for_user)(user)
            access_token = refresh_token.access_token
            access_token['user_id'] = 999999  # unlikely to exist
            result, error = await get_user_from_token(str(access_token), db_alias=db_alias)
            self.assertIsInstance(result, AnonymousUser)
            self.assertEqual(error, "user_not_found")
        asyncio.get_event_loop().run_until_complete(run())

    def test_get_user_from_token_blacklisted(self):
        """Test blacklisted token returns AnonymousUser."""
        async def run():
            db_alias = get_db_alias()
            user = await database_sync_to_async(UserRepository.create_user)(
                email='blacklistuser@example.com', password='testpass123',
                username='blacklistuser', db_alias=db_alias)
            refresh_token = await database_sync_to_async(RefreshToken.for_user)(user)
            access_token = refresh_token.access_token
            # Get the outstanding refresh token (not access token)
            outstanding_token = await database_sync_to_async(OutstandingToken.objects.using(
                db_alias or None).get)(jti=refresh_token['jti'])
            # Blacklist the refresh token
            await database_sync_to_async(BlacklistedToken.objects.using(
                db_alias or None).create)(token=outstanding_token)
            # Test that the access token is now considered blacklisted because its
            # parent is blacklisted
            result, error = await get_user_from_token(str(access_token), db_alias=db_alias)
            self.assertIsInstance(result, AnonymousUser)
            self.assertEqual(error, "token_blacklisted")
        asyncio.get_event_loop().run_until_complete(run())
