# pylint: disable=R0801
"""
Focused WebSocket tests for real-time communication.
These tests are kept separate due to TransactionTestCase requirements.
"""

import asyncio
import json

from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase

from accounts.repositories import UserRepository
from accounts.tokens import RefreshToken
from backend.asgi import application
from backend.utils import get_db_alias
from backend.ws_utils import (notify_profile_update_async,
    notify_profile_password_update_async, notify_profile_password_reset_async)


User = get_user_model()


class ProfileConsumerTest(TransactionTestCase):
    """Test WebSocket ProfileConsumer functionality."""

    def setUp(self):
        """Set up test data."""
        db_alias = get_db_alias()
        self.user = UserRepository.create_user(
            email="testuser2u@example.com",
            username="testuser2u",
            password="testpass123",
            first_name="Test",
            last_name="User",
            db_alias=db_alias
        )

    @sync_to_async
    def create_test_user(self):
        """Create test user asynchronously."""
        db_alias = get_db_alias()
        return UserRepository.create_user(
            email="testuser3@example.com",
            username="testuser3",
            password="testpass123",
            first_name="Test",
            last_name="User3",
            db_alias=db_alias
        )

    def test_profile_consumer_connect_and_update(self):
        """Test ProfileConsumer connection and profile update events."""
        async def async_test():
            user_id = str(self.user.id)
            refresh = await database_sync_to_async(RefreshToken.for_user)(self.user)
            communicator = WebsocketCommunicator(
                application, f"/ws/profile/{user_id}/?token={str(refresh.access_token)}")
            # Mock the scope to include authenticated user
            communicator.scope['user'] = self.user
            connected, _ = await communicator.connect()
            self.assertTrue(connected)
            # Test initial connection message
            response = await communicator.receive_from()
            data = json.loads(response)
            self.assertTrue(data["data"]["connected"])
            self.assertEqual(data["data"]["user_id"], user_id)
            # Simulate sending a profile update event to the group using the channel layer
            channel_layer = get_channel_layer()
            new_profile_data = {"id": user_id, "name": "Test User"}
            await channel_layer.group_send(
                f"profile_{user_id}",
                {
                    "type": "profile_update",
                    "new_profile_data": new_profile_data,
                }
            )
            # The consumer should send the new profile data back
            response = await communicator.receive_from()
            data = json.loads(response)
            self.assertEqual(data["type"], "profile_update")
            self.assertEqual(data["data"]["id"], user_id)
            # Disconnect and ensure it completes without error
            disconnect_result = await communicator.disconnect()
            self.assertIsNone(disconnect_result)  # Should return None if clean
        asyncio.get_event_loop().run_until_complete(async_test())

    def test_profile_consumer_unauthenticated(self):
        """Test that unauthenticated users cannot connect."""
        async def async_test():
            user_id = str(self.user.id)
            communicator = WebsocketCommunicator(application, f"/ws/profile/{user_id}/")
            # Mock the scope with anonymous user and auth error
            communicator.scope['user'] = AnonymousUser()
            communicator.scope['auth_error'] = 'no_token'
            connected, _ = await communicator.connect()
            self.assertTrue(connected)  # Connection is initially accepted
            # Should receive auth error message
            response = await communicator.receive_from()
            data = json.loads(response)
            self.assertEqual(data["type"], "auth_error")
            self.assertEqual(data["error"], "no_token")
            # Connection should be closed with appropriate code
            await communicator.disconnect()
        asyncio.get_event_loop().run_until_complete(async_test())

    def test_profile_consumer_unauthorized_user(self):
        """Test that users cannot access other users' profiles."""
        async def async_test():
            # Create another user
            other_user = await self.create_test_user()
            # Try to connect to first user's profile with second user's credentials
            user_id = str(self.user.id)
            other_refresh = await database_sync_to_async(RefreshToken.for_user)(other_user)
            communicator = WebsocketCommunicator(application,
                f"/ws/profile/{user_id}/?token={str(other_refresh.access_token)}")
            # Mock the scope with the other user
            communicator.scope['user'] = other_user
            connected, _ = await communicator.connect()
            self.assertTrue(connected)  # Should be rejected
            # Should receive auth error message
            response = await communicator.receive_from()
            data = json.loads(response)
            self.assertEqual(data["type"], "auth_error")
            self.assertEqual(data["error"], "access_denied")
            # Connection should be closed with appropriate code
            await communicator.disconnect()
        asyncio.get_event_loop().run_until_complete(async_test())

    def test_notify_profile_update_integration(self):
        """Test profile update notification integration."""
        async def async_test():
            user_id = str(self.user.id)
            refresh = await database_sync_to_async(RefreshToken.for_user)(self.user)
            communicator = WebsocketCommunicator(application,
                f"/ws/profile/{user_id}/?token={str(refresh.access_token)}")
            # Mock the scope to include authenticated user
            communicator.scope['user'] = self.user
            connected, _ = await communicator.connect()
            self.assertTrue(connected)
            await communicator.receive_from()  # initial connection message
            # Call the function to notify profile update
            new_profile_data = {"id": user_id, "name": "Integration Test"}
            await notify_profile_update_async(user_id, new_profile_data,
                                              password_updated=True)
            # The consumer should send the new profile data back
            response = await communicator.receive_from()
            data = json.loads(response)
            self.assertEqual(data["type"], "profile_update")
            self.assertEqual(data["data"]["id"], user_id)
            self.assertTrue(data["password_updated"])
            await communicator.disconnect()
        asyncio.get_event_loop().run_until_complete(async_test())

    def test_notify_profile_password_update_integration(self):
        """Test profile password update notification integration."""
        async def async_test():
            user_id = str(self.user.id)
            refresh = await database_sync_to_async(RefreshToken.for_user)(self.user)
            communicator = WebsocketCommunicator(application,
                f"/ws/profile/{user_id}/?token={str(refresh.access_token)}")
            # Mock the scope to include authenticated user
            communicator.scope['user'] = self.user
            connected, _ = await communicator.connect()
            self.assertTrue(connected)
            await communicator.receive_from()  # initial connection message
            # Call the function to notify profile password update
            await notify_profile_password_update_async(user_id)
            # The consumer should send the new profile data back
            response = await communicator.receive_from()
            data = json.loads(response)
            self.assertEqual(data["type"], "profile_password_update")
            self.assertTrue(data["password_updated"])
            await communicator.disconnect()
        asyncio.get_event_loop().run_until_complete(async_test())

    def test_notify_profile_password_reset_integration(self):
        """Test profile password reset notification integration."""
        async def async_test():
            user_id = str(self.user.id)
            refresh = await database_sync_to_async(RefreshToken.for_user)(self.user)
            communicator = WebsocketCommunicator(application,
                f"/ws/profile/{user_id}/?token={str(refresh.access_token)}")
            # Mock the scope to include authenticated user
            communicator.scope['user'] = self.user
            connected, _ = await communicator.connect()
            self.assertTrue(connected)
            await communicator.receive_from()  # initial connection message
            # Call the function to notify profile password reset
            await notify_profile_password_reset_async(user_id)
            # The consumer should send the password reset notification
            response = await communicator.receive_from()
            data = json.loads(response)
            self.assertEqual(data["type"], "profile_password_reset")
            self.assertTrue(data["password_reset"])
            self.assertEqual(data["action"], "logout_required")
            await communicator.disconnect()
        asyncio.get_event_loop().run_until_complete(async_test())

    def test_profile_consumer_ping_event(self):
        """Test ping event handling."""
        async def async_test():
            user_id = str(self.user.id)
            refresh = await database_sync_to_async(RefreshToken.for_user)(self.user)
            communicator = WebsocketCommunicator(application,
                f"/ws/profile/{user_id}/?token={str(refresh.access_token)}")
            # Mock the scope to include authenticated user
            communicator.scope['user'] = self.user
            connected, _ = await communicator.connect()
            self.assertTrue(connected)
            await communicator.receive_from()  # initial connection message
            # Send ping event
            # channel_layer = get_channel_layer()
            # await channel_layer.group_send(
            #     f"profile_{user_id}",
            #     {"type": "ping"}
            # )
            await communicator.send_to(text_data=json.dumps({
                "type": "ping",
            }))
            # Should receive ping response
            response = await communicator.receive_from()
            data = json.loads(response)
            self.assertEqual(data["type"], "pong")
            await communicator.disconnect()
        asyncio.get_event_loop().run_until_complete(async_test())

    def test_profile_consumer_notification_event(self):
        """Test general notification event handling."""
        async def async_test():
            user_id = str(self.user.id)
            refresh = await database_sync_to_async(RefreshToken.for_user)(self.user)
            communicator = WebsocketCommunicator(application,
                f"/ws/profile/{user_id}/?token={str(refresh.access_token)}")
            # Mock the scope to include authenticated user
            communicator.scope['user'] = self.user
            connected, _ = await communicator.connect()
            self.assertTrue(connected)
            await communicator.receive_from()  # initial connection message
            # Send notification event
            channel_layer = get_channel_layer()
            await channel_layer.group_send(
                f"profile_{user_id}",
                {
                    "type": "notification",
                    "message": "Test notification",
                    "data": {"key": "value"}
                }
            )
            # Should receive notification
            response = await communicator.receive_from()
            data = json.loads(response)
            self.assertEqual(data["type"], "notification")
            self.assertEqual(data["message"], "Test notification")
            self.assertEqual(data["data"]["key"], "value")
            await communicator.disconnect()
        asyncio.get_event_loop().run_until_complete(async_test())
