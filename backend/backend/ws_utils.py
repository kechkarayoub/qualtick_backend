# pylint: disable=broad-exception-caught,logging-fstring-interpolation
"""
WebSocket utility functions for real-time notifications.
"""

import logging
from datetime import date, datetime
from decimal import Decimal

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.utils import timezone


logger = logging.getLogger(__name__)


def serialize_for_websocket(obj):
    """
    Convert non-serializable objects to JSON-serializable format.
    Args:
        obj: Object to serialize
    Returns:
        JSON-serializable object
    """
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if hasattr(obj, '__dict__'):
        # Handle model instances
        return serialize_dict_for_websocket(obj.__dict__)
    if isinstance(obj, dict):
        return serialize_dict_for_websocket(obj)
    if isinstance(obj, (list, tuple)):
        return [serialize_for_websocket(item) for item in obj]
    return obj


def serialize_dict_for_websocket(data_dict):
    """
    Recursively serialize a dictionary for WebSocket transmission.
    Args:
        data_dict (dict): Dictionary to serialize
    Returns:
        dict: Serialized dictionary
    """
    if not isinstance(data_dict, dict):
        return serialize_for_websocket(data_dict)
    serialized = {}
    for key, value in data_dict.items():
        # Skip Django model internal fields
        if key.startswith('_'):
            continue
        serialized[key] = serialize_for_websocket(value)
    return serialized


class WebSocketNotificationService:
    """Service for sending WebSocket notifications."""
    @staticmethod
    def get_channel_layer():
        """Get the channel layer instance."""
        return get_channel_layer()

    @staticmethod
    async def send_to_group(group_name, event_type, data):
        """
        Send an event to a WebSocket group.
        Args:
            group_name (str): Name of the group to send to
            event_type (str): Type of event (e.g., 'profile_update')
            data (dict): Event data
        """
        channel_layer = get_channel_layer()
        if channel_layer:
            try:
                # Serialize the data to handle datetime and other non-JSON serializable
                # objects
                serialized_data = serialize_dict_for_websocket(data)
                event_data = {
                    "type": event_type,
                    "timestamp": timezone.now().isoformat(),
                    **serialized_data
                }
                await channel_layer.group_send(group_name, event_data)
                logger.info(f"Sent WebSocket event '{event_type}' to group"
                            f" '{group_name}' with data: {event_data}")
            except Exception as e:
                logger.error("Failed to send WebSocket event to group"
                             f" {group_name}: {str(e)}")
        else:
            logger.warning("Channel layer not configured")


# Async version: Use this in async contexts
async def notify_profile_update_async(user_id, new_profile_data, password_updated=False,
                                      device_id=None):
    """
    Asynchronously sends a profile update event to all WebSocket clients in the user's 
        group.
    Args:
        user_id (str or int): The ID of the user whose profile was updated
        new_profile_data (dict): The updated profile data to send to clients
        password_updated (bool): Whether the password was updated (default: False)
        device_id (str, optional): Device ID to exclude from receiving the update
    """
    try:
        logger.info(f"Sending profile update notification for user {user_id}")
        await WebSocketNotificationService.send_to_group(
            f"profile_{user_id}",
            "profile_update",
            {
                "new_profile_data": new_profile_data,
                "password_updated": password_updated,
                "device_id": device_id,
            }
        )
    except Exception as e:
        logger.error(f"Failed to send profile update notification for user {user_id}"
                     f": {str(e)}")



# Async version: Use this in async contexts
async def notify_profile_password_update_async(user_id, device_id=None):
    """
    Asynchronously sends a profile password update event to all WebSocket clients in the
        user's group.
    Args:
        user_id (str or int): The ID of the user whose profile was updated
        new_profile_data (dict): The updated profile data to send to clients
        device_id (str, optional): Device ID to exclude from receiving the update
    """
    try:
        await WebSocketNotificationService.send_to_group(
            f"profile_{user_id}",
            "profile_password_update",
            {
                "password_updated": True,
                "device_id": device_id,
            }
        )
    except Exception as e:
        logger.error("Failed to send profile password update notification for user"
                     f" {user_id}: {str(e)}")



# Sync version: Use this in synchronous Django code
def notify_profile_password_update(user_id, device_id=None):
    """
    Synchronously sends a profile password update event to all WebSocket clients in
        the user's group.
    This wraps the async version for use in non-async code.
    Args:
        user_id (str or int): The ID of the user whose profile was updated
        device_id (str, optional): Device ID to exclude from receiving the update
    """
    try:
        async_to_sync(notify_profile_password_update_async)(user_id, device_id)
    except Exception as e:
        logger.error("Failed to send sync profile password update notification for "
            f"user {user_id}: {str(e)}")

# Sync version: Use this in synchronous Django code
def notify_profile_update(user_id, new_profile_data,
                          password_updated=False, device_id=None):
    """
    Synchronously sends a profile update event to all WebSocket clients in the user's
    group.
    This wraps the async version for use in non-async code.
    Args:
        user_id (str or int): The ID of the user whose profile was updated
        new_profile_data (dict): The updated profile data to send to clients
        password_updated (bool): Whether the password was updated (default: False)
        device_id (str, optional): Device ID to exclude from receiving the update
    """
    try:
        logger.info(f"Sending sync profile update notification for user {user_id}")
        async_to_sync(notify_profile_update_async)(user_id, new_profile_data,
                                                   password_updated, device_id)
    except Exception as e:
        logger.error(f"Failed to send sync profile update notification for user {user_id}:"
                     f" {str(e)}")


# General notification functions
async def notify_user_async(user_id, message, data=None):
    """
    Send a general notification to a user.
    Args:
        user_id (str or int): User ID to notify
        message (str): Notification message
        data (dict, optional): Additional data
    """
    try:
        await WebSocketNotificationService.send_to_group(
            f"profile_{user_id}",
            "notification",
            {
                "message": message,
                "data": data or {},
            }
        )
    except Exception as e:
        logger.error(f"Failed to send notification to user {user_id}: {str(e)}")


def notify_user(user_id, message, data=None):
    """
    Synchronously send a general notification to a user.
    Args:
        user_id (str or int): User ID to notify
        message (str): Notification message
        data (dict, optional): Additional data
    """
    try:
        async_to_sync(notify_user_async)(user_id, message, data)
    except Exception as e:
        logger.error(f"Failed to send sync notification to user {user_id}: {str(e)}")


# Bulk notification functions
async def notify_multiple_users_async(user_ids, message, data=None):
    """
    Send notifications to multiple users.
    Args:
        user_ids (list): List of user IDs
        message (str): Notification message
        data (dict, optional): Additional data
    """
    for user_id in user_ids:
        await notify_user_async(user_id, message, data)


def notify_multiple_users(user_ids, message, data=None):
    """
    Synchronously send notifications to multiple users.
    Args:
        user_ids (list): List of user IDs
        message (str): Notification message
        data (dict, optional): Additional data
    """
    try:
        async_to_sync(notify_multiple_users_async)(user_ids, message, data)
    except Exception as e:
        logger.error(f"Failed to send bulk notifications: {str(e)}")


# Connection monitoring
async def ping_user_connection(user_id):
    """
    Send a ping to check if user's WebSocket connection is active.
    Args:
        user_id (str or int): User ID to ping
    """
    try:
        await WebSocketNotificationService.send_to_group(
            f"profile_{user_id}",
            "ping",
            {}
        )
    except Exception as e:
        logger.error(f"Failed to ping user {user_id}: {str(e)}")


def ping_user_connection_sync(user_id):
    """
    Synchronously ping user's WebSocket connection.
    Args:
        user_id (str or int): User ID to ping
    """
    try:
        async_to_sync(ping_user_connection)(user_id)
    except Exception as e:
        logger.error(f"Failed to ping user {user_id} synchronously: {str(e)}")


# Password reset notification functions
async def notify_profile_password_reset_async(user_id, device_id=None):
    """
    Asynchronously sends a profile password reset event to all WebSocket clients in the
    user's group.
    This should trigger logout on all connected devices except the one that initiated the
    reset.
    Args:
        user_id (str or int): The ID of the user whose password was reset
        device_id (str, optional): Device ID to exclude from receiving the update
    """
    try:
        await WebSocketNotificationService.send_to_group(
            f"profile_{user_id}",
            "profile_password_reset",
            {
                "password_reset": True,
                "action": "logout_required",
                "device_id": device_id,
            }
        )
    except Exception as e:
        logger.error("Failed to send profile password reset notification for "
                     f"user {user_id}: {str(e)}")



def notify_profile_password_reset(user_id, device_id=None):
    """
    Synchronously sends a profile password reset event to all WebSocket clients in the
    user's group.
    This wraps the async version for use in non-async code.
    Args:
        user_id (str or int): The ID of the user whose password was reset
        device_id (str, optional): Device ID to exclude from receiving the update
    """
    try:
        async_to_sync(notify_profile_password_reset_async)(user_id, device_id)
    except Exception as e:
        logger.error(
            f"Failed to send sync profile password reset notification for user {user_id}:"
            f" {str(e)}")
