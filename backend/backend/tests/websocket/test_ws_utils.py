# pylint: disable=too-few-public-methods
"""
Tests for WebSocket utility functions.
"""

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from channels.layers import InMemoryChannelLayer
from django.test import TestCase

from backend.ws_utils import (
    serialize_for_websocket,
    serialize_dict_for_websocket,
    WebSocketNotificationService,
    notify_profile_update_async,
    notify_profile_update,
    notify_profile_password_update_async,
    notify_profile_password_update,
    notify_user_async,
    notify_user,
    notify_multiple_users_async,
    notify_multiple_users,
    ping_user_connection,
    ping_user_connection_sync,
    notify_profile_password_reset_async,
    notify_profile_password_reset,
)


class TestSerializationFunctions(TestCase):
    """Test the serialization helper functions."""

    def test_serialize_date_object(self):
        """Test serialization of date objects."""
        test_date = date(2023, 12, 25)
        result = serialize_for_websocket(test_date)
        self.assertEqual(result, "2023-12-25")

    def test_serialize_datetime_object(self):
        """Test serialization of datetime objects."""
        test_datetime = datetime(2023, 12, 25, 15, 30, 45)
        result = serialize_for_websocket(test_datetime)
        self.assertEqual(result, "2023-12-25T15:30:45")

    def test_serialize_decimal_object(self):
        """Test serialization of Decimal objects."""
        test_decimal = Decimal("123.45")
        result = serialize_for_websocket(test_decimal)
        self.assertEqual(result, 123.45)
        self.assertIsInstance(result, float)

    def test_serialize_dict(self):
        """Test serialization of dictionary with mixed types."""
        test_dict = {
            "name": "John Doe",
            "birthday": date(1990, 5, 15),
            "created_at": datetime(2023, 12, 25, 10, 30),
            "balance": Decimal("1000.50"),
            "age": 33,
            "active": True,
        }
        result = serialize_for_websocket(test_dict)
        expected = {
            "name": "John Doe",
            "birthday": "1990-05-15",
            "created_at": "2023-12-25T10:30:00",
            "balance": 1000.50,
            "age": 33,
            "active": True,
        }
        self.assertEqual(result, expected)

    def test_serialize_list(self):
        """Test serialization of list with mixed types."""
        test_list = [
            "string",
            date(2023, 1, 1),
            datetime(2023, 1, 1, 12, 0),
            Decimal("99.99"),
            123,
            True,
        ]
        result = serialize_for_websocket(test_list)
        expected = [
            "string",
            "2023-01-01",
            "2023-01-01T12:00:00",
            99.99,
            123,
            True,
        ]
        self.assertEqual(result, expected)

    def test_serialize_nested_dict(self):
        """Test serialization of nested dictionary."""
        test_dict = {
            "user": {
                "name": "Jane",
                "birthday": date(1985, 3, 20),
                "preferences": {
                    "theme": "dark",
                    "last_login": datetime(2023, 12, 25, 14, 0),
                }
            },
            "metadata": {
                "version": Decimal("1.5"),
                "tags": ["user", "active"]
            }
        }
        result = serialize_for_websocket(test_dict)
        expected = {
            "user": {
                "name": "Jane",
                "birthday": "1985-03-20",
                "preferences": {
                    "theme": "dark",
                    "last_login": "2023-12-25T14:00:00",
                }
            },
            "metadata": {
                "version": 1.5,
                "tags": ["user", "active"]
            }
        }
        self.assertEqual(result, expected)

    def test_serialize_dict_for_websocket_filters_private_fields(self):
        """Test that private fields (starting with _) are filtered out."""
        test_dict = {
            "public_field": "visible",
            "_private_field": "hidden",
            "_state": "django_internal",
            "another_public": "also_visible",
        }
        result = serialize_dict_for_websocket(test_dict)
        expected = {
            "public_field": "visible",
            "another_public": "also_visible",
        }
        self.assertEqual(result, expected)

    def test_serialize_model_like_object(self):
        """Test serialization of object with __dict__ attribute."""
        class MockModel:
            """Mock model-like object."""
            def __init__(self):
                self.id = 1
                self.name = "Test"
                self.created_date = date(2023, 1, 1)
                self._state = "hidden"
        mock_obj = MockModel()
        result = serialize_for_websocket(mock_obj)
        expected = {
            "id": 1,
            "name": "Test",
            "created_date": "2023-01-01",
        }
        self.assertEqual(result, expected)

    def test_serialize_primitive_types(self):
        """Test that primitive types are returned as-is."""
        primitives = [
            "string",
            123,
            45.67,
            True,
            False,
            None,
        ]
        for primitive in primitives:
            result = serialize_for_websocket(primitive)
            self.assertEqual(result, primitive)


class TestWebSocketNotificationService(TestCase):
    """Test the WebSocketNotificationService class."""

    def setUp(self):
        """Set up test environment."""
        self.channel_layer = InMemoryChannelLayer()

    @patch('backend.ws_utils.get_channel_layer')
    async def test_send_to_group_success(self, mock_get_channel_layer):
        """Test successful sending to group."""
        mock_get_channel_layer.return_value = self.channel_layer
        group_name = "test_group"
        event_type = "test_event"
        data = {
            "message": "Hello",
            "timestamp": date(2023, 1, 1),
            "amount": Decimal("100.50")
        }
        await WebSocketNotificationService.send_to_group(group_name, event_type, data)
        # Check that the event was added to the channel layer
        # Note: InMemoryChannelLayer doesn't have direct access to check sent messages
        # but we can verify no exceptions were raised

    @patch('backend.ws_utils.get_channel_layer')
    @patch('backend.ws_utils.logger')
    async def test_send_to_group_with_exception(self, mock_logger, mock_get_channel_layer):
        """Test error handling when sending to group fails."""
        mock_channel_layer = AsyncMock()
        mock_channel_layer.group_send.side_effect = Exception("Channel error")
        mock_get_channel_layer.return_value = mock_channel_layer
        await WebSocketNotificationService.send_to_group("test_group", "test_event", {})
        # Verify error was logged
        mock_logger.error.assert_called_once()
        self.assertIn("Failed to send WebSocket event", str(mock_logger.error.call_args))

    @patch('backend.ws_utils.get_channel_layer')
    @patch('backend.ws_utils.logger')
    async def test_send_to_group_no_channel_layer(self, mock_logger,
                                                  mock_get_channel_layer):
        """Test behavior when channel layer is not configured."""
        mock_get_channel_layer.return_value = None
        await WebSocketNotificationService.send_to_group("test_group", "test_event", {})
        # Verify warning was logged
        mock_logger.warning.assert_called_once_with("Channel layer not configured")

    @patch('backend.ws_utils.get_channel_layer')
    async def test_send_to_group_serializes_data(self, mock_get_channel_layer):
        """Test that data is properly serialized before sending."""
        mock_channel_layer = AsyncMock()
        mock_get_channel_layer.return_value = mock_channel_layer
        data = {
            "user_birthday": date(2023, 1, 1),
            "balance": Decimal("999.99"),
            "login_time": datetime(2023, 12, 25, 15, 30)
        }
        await WebSocketNotificationService.send_to_group("test_group", "test_event", data)
        # Verify group_send was called
        mock_channel_layer.group_send.assert_called_once()
        # Get the actual call arguments
        call_args = mock_channel_layer.group_send.call_args[0]
        sent_data = call_args[1]
        # Verify data was serialized
        self.assertEqual(sent_data["user_birthday"], "2023-01-01")
        self.assertEqual(sent_data["balance"], 999.99)
        self.assertEqual(sent_data["login_time"], "2023-12-25T15:30:00")
        self.assertEqual(sent_data["type"], "test_event")
        self.assertIn("timestamp", sent_data)


class TestProfileNotificationFunctions(TestCase):
    """Test profile notification functions."""

    @patch('backend.ws_utils.WebSocketNotificationService.send_to_group')
    async def test_notify_profile_update_async(self, mock_send_to_group):
        """Test async profile update notification."""
        user_id = 123
        profile_data = {
            "name": "John Doe",
            "birthday": date(1990, 1, 1),
            "balance": Decimal("1000.00")
        }
        await notify_profile_update_async(user_id, profile_data,
                                          password_updated=True, device_id="device123")
        mock_send_to_group.assert_called_once_with(
            "profile_123",
            "profile_update",
            {
                "new_profile_data": profile_data,
                "password_updated": True,
                "device_id": "device123",
            }
        )

    @patch('backend.ws_utils.async_to_sync')
    def test_notify_profile_update_sync(self, mock_async_to_sync):
        """Test sync profile update notification."""
        user_id = 123
        profile_data = {"name": "John Doe"}
        notify_profile_update(user_id, profile_data)
        mock_async_to_sync.assert_called_once()

    @patch('backend.ws_utils.WebSocketNotificationService.send_to_group')
    async def test_notify_profile_password_update_async(self, mock_send_to_group):
        """Test async profile password update notification."""
        user_id = 456
        device_id = "device456"
        await notify_profile_password_update_async(user_id, device_id)
        mock_send_to_group.assert_called_once_with(
            "profile_456",
            "profile_password_update",
            {
                "password_updated": True,
                "device_id": device_id,
            }
        )

    @patch('backend.ws_utils.async_to_sync')
    def test_notify_profile_password_update_sync(self, mock_async_to_sync):
        """Test sync profile password update notification."""
        user_id = 456
        notify_profile_password_update(user_id)
        mock_async_to_sync.assert_called_once()


class TestGeneralNotificationFunctions(TestCase):
    """Test general notification functions."""

    @patch('backend.ws_utils.WebSocketNotificationService.send_to_group')
    async def test_notify_user_async(self, mock_send_to_group):
        """Test async user notification."""
        user_id = 789
        message = "Test notification"
        data = {"key": "value"}
        await notify_user_async(user_id, message, data)
        mock_send_to_group.assert_called_once_with(
            "profile_789",
            "notification",
            {
                "message": message,
                "data": data,
            }
        )

    @patch('backend.ws_utils.WebSocketNotificationService.send_to_group')
    async def test_notify_user_async_no_data(self, mock_send_to_group):
        """Test async user notification without additional data."""
        user_id = 789
        message = "Test notification"
        await notify_user_async(user_id, message)
        mock_send_to_group.assert_called_once_with(
            "profile_789",
            "notification",
            {
                "message": message,
                "data": {},
            }
        )

    @patch('backend.ws_utils.async_to_sync')
    def test_notify_user_sync(self, mock_async_to_sync):
        """Test sync user notification."""
        user_id = 789
        message = "Test notification"
        notify_user(user_id, message)
        mock_async_to_sync.assert_called_once()

    @patch('backend.ws_utils.notify_user_async')
    async def test_notify_multiple_users_async(self, mock_notify_user_async):
        """Test async multiple users notification."""
        user_ids = [1, 2, 3]
        message = "Broadcast message"
        data = {"broadcast": True}
        await notify_multiple_users_async(user_ids, message, data)
        # Verify notify_user_async was called for each user
        self.assertEqual(mock_notify_user_async.call_count, 3)
        for user_id in user_ids:
            mock_notify_user_async.assert_any_call(user_id, message, data)

    @patch('backend.ws_utils.async_to_sync')
    def test_notify_multiple_users_sync(self, mock_async_to_sync):
        """Test sync multiple users notification."""
        user_ids = [1, 2, 3]
        message = "Broadcast message"
        notify_multiple_users(user_ids, message)
        mock_async_to_sync.assert_called_once()


class TestConnectionMonitoring(TestCase):
    """Test connection monitoring functions."""

    @patch('backend.ws_utils.WebSocketNotificationService.send_to_group')
    async def test_ping_user_connection(self, mock_send_to_group):
        """Test async ping user connection."""
        user_id = 999
        await ping_user_connection(user_id)
        mock_send_to_group.assert_called_once_with(
            "profile_999",
            "ping",
            {}
        )

    @patch('backend.ws_utils.async_to_sync')
    def test_ping_user_connection_sync(self, mock_async_to_sync):
        """Test sync ping user connection."""
        user_id = 999
        ping_user_connection_sync(user_id)
        mock_async_to_sync.assert_called_once()


class TestPasswordResetNotifications(TestCase):
    """Test password reset notification functions."""

    @patch('backend.ws_utils.WebSocketNotificationService.send_to_group')
    async def test_notify_profile_password_reset_async(self, mock_send_to_group):
        """Test async profile password reset notification."""
        user_id = 111
        device_id = "device111"
        await notify_profile_password_reset_async(user_id, device_id)
        mock_send_to_group.assert_called_once_with(
            "profile_111",
            "profile_password_reset",
            {
                "password_reset": True,
                "action": "logout_required",
                "device_id": device_id,
            }
        )

    @patch('backend.ws_utils.async_to_sync')
    def test_notify_profile_password_reset_sync(self, mock_async_to_sync):
        """Test sync profile password reset notification."""
        user_id = 111
        notify_profile_password_reset(user_id)
        mock_async_to_sync.assert_called_once()


class TestErrorHandling(TestCase):
    """Test error handling in WebSocket utilities."""

    @patch('backend.ws_utils.WebSocketNotificationService.send_to_group')
    @patch('backend.ws_utils.logger')
    async def test_notify_profile_update_async_with_exception(self, mock_logger,
                                                              mock_send_to_group):
        """Test error handling in async profile update notification."""
        mock_send_to_group.side_effect = Exception("WebSocket error")
        user_id = 123
        profile_data = {"name": "John"}
        await notify_profile_update_async(user_id, profile_data)
        # Verify error was logged
        mock_logger.error.assert_called_once()
        self.assertIn("Failed to send profile update notification",
                      str(mock_logger.error.call_args))

    @patch('backend.ws_utils.async_to_sync')
    @patch('backend.ws_utils.logger')
    def test_notify_profile_update_sync_with_exception(self, mock_logger,
                                                       mock_async_to_sync):
        """Test error handling in sync profile update notification."""
        mock_async_to_sync.side_effect = Exception("Sync error")
        user_id = 123
        profile_data = {"name": "John"}
        notify_profile_update(user_id, profile_data)
        # Verify error was logged
        mock_logger.error.assert_called_once()
        self.assertIn("Failed to send sync profile update notification",
                      str(mock_logger.error.call_args))


class TestIntegration(TestCase):
    """Integration tests for WebSocket utilities."""

    def setUp(self):
        """Set up test environment."""
        self.channel_layer = InMemoryChannelLayer()

    @patch('backend.ws_utils.get_channel_layer')
    async def test_end_to_end_profile_update(self, mock_get_channel_layer):
        """Test end-to-end profile update notification."""
        mock_get_channel_layer.return_value = self.channel_layer
        # Create profile data with various data types
        profile_data = {
            "id": 123,
            "name": "John Doe",
            "email": "john@example.com",
            "birthday": date(1990, 5, 15),
            "last_login": datetime(2023, 12, 25, 14, 30, 45),
            "balance": Decimal("1500.75"),
            "is_active": True,
            "preferences": {
                "theme": "dark",
                "notifications": True,
                "created_at": datetime(2023, 1, 1, 0, 0, 0)
            }
        }
        # Send the notification
        await notify_profile_update_async(
            user_id=123,
            new_profile_data=profile_data,
            password_updated=False,
            device_id="device123"
        )
        # This test mainly verifies that no exceptions are raised
        # and the serialization works correctly
    def test_complex_serialization_scenario(self):
        """Test complex nested data serialization."""
        complex_data = {
            "user": {
                "id": 1,
                "profile": {
                    "personal": {
                        "birthday": date(1985, 12, 25),
                        "preferences": {
                            "last_updated": datetime(2023, 12, 25, 15, 30, 45),
                            "settings": {
                                "theme": "dark",
                                "balance": Decimal("2500.99"),
                                "rates": [Decimal("1.5"), Decimal("2.0"), Decimal("3.75")]
                            }
                        }
                    }
                }
            },
            "metadata": {
                "timestamps": [
                    datetime(2023, 1, 1, 12, 0, 0),
                    datetime(2023, 6, 15, 18, 30, 0)
                ],
                "dates": [date(2023, 1, 1), date(2023, 12, 31)],
                "amounts": [Decimal("100.00"), Decimal("250.50"), Decimal("999.99")]
            }
        }
        result = serialize_for_websocket(complex_data)
        # Verify all datetime objects are converted to strings
        self.assertEqual(result["user"]["profile"]["personal"]["birthday"], "1985-12-25")
        self.assertEqual(
            result["user"]["profile"]["personal"]["preferences"]["last_updated"],
            "2023-12-25T15:30:45"
        )
        # Verify all Decimal objects are converted to floats
        self.assertEqual(
            result["user"]["profile"]["personal"]["preferences"]["settings"]["balance"],
            2500.99
        )
        # Verify lists are properly handled
        expected_rates = [1.5, 2.0, 3.75]
        self.assertEqual(
            result["user"]["profile"]["personal"]["preferences"]["settings"]["rates"],
            expected_rates
        )
        expected_timestamps = ["2023-01-01T12:00:00", "2023-06-15T18:30:00"]
        self.assertEqual(result["metadata"]["timestamps"], expected_timestamps)
        expected_dates = ["2023-01-01", "2023-12-31"]
        self.assertEqual(result["metadata"]["dates"], expected_dates)
        expected_amounts = [100.0, 250.5, 999.99]
        self.assertEqual(result["metadata"]["amounts"], expected_amounts)
