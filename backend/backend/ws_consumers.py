# pylint: disable=attribute-defined-outside-init,broad-exception-caught,logging-fstring-interpolation
"""
WebSocket consumers for real-time functionality.
"""

import json
import logging
import time

from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser
from django.utils.translation import gettext_lazy as _


logger = logging.getLogger(__name__)


class BaseConsumer(AsyncWebsocketConsumer):
    """Base WebSocket consumer with common functionality."""

    async def connect(self):
        """Handle WebSocket connection."""
        await self.accept()
        logger.info(f"WebSocket connection established: {self.channel_name}")

    async def disconnect(self, code):
        """Handle WebSocket disconnection."""
        logger.info(f"WebSocket disconnected: {self.channel_name}, code: {code}")

    async def send_error(self, message, code="error"):
        """Send error message to client."""
        await self.send(text_data=json.dumps({
            "type": "error",
            "code": code,
            "message": str(message)
        }))

    async def send_success(self, data, message="Success"):
        """Send success message to client."""
        await self.send(text_data=json.dumps({
            "type": "success",
            "message": str(message),  # Convert to string to handle lazy translations
            "data": data
        }))


class ProfileConsumer(BaseConsumer):
    """WebSocket consumer for profile-related real-time updates."""

    async def connect(self):
        """
        Handle WebSocket connection for profile updates.
        Authenticates user and adds them to their profile group.
        """
        self.user = self.scope.get('user')
        self.user_id = self.scope['url_route']['kwargs']['user_id']
        self.auth_error = self.scope.get('auth_error')
        # Always accept the connection first, then handle auth errors
        await self.accept()
        # Check authentication errors first
        if self.auth_error:
            # Send error message before closing to ensure frontend receives the error
            # reason
            if self.auth_error == "token_expired":
                await self.send(text_data=json.dumps({
                    "type": "auth_error",
                    "error": "token_expired",
                    "message": "Token has expired"
                }))
                await self.close(code=4001, reason="token_expired")
            elif self.auth_error == "token_blacklisted":
                await self.send(text_data=json.dumps({
                    "type": "auth_error",
                    "error": "token_blacklisted",
                    "message": "Token has been blacklisted"
                }))
                await self.close(code=4002, reason="token_blacklisted")
            elif self.auth_error == "invalid_token":
                await self.send(text_data=json.dumps({
                    "type": "auth_error",
                    "error": "invalid_token",
                    "message": "Invalid token"
                }))
                await self.close(code=4002, reason="invalid_token")
            elif self.auth_error == "user_not_found":
                await self.send(text_data=json.dumps({
                    "type": "auth_error",
                    "error": "user_not_found",
                    "message": "User not found"
                }))
                await self.close(code=4003, reason="user_not_found")
            elif self.auth_error == "no_token":
                await self.send(text_data=json.dumps({
                    "type": "auth_error",
                    "error": "no_token",
                    "message": "No token provided"
                }))
                await self.close(code=4004, reason="no_token")
            else:
                await self.send(text_data=json.dumps({
                    "type": "auth_error",
                    "error": "auth_error",
                    "message": "Authentication error"
                }))
                await self.close(code=4005, reason="auth_error")
            return
        # Check if user is authenticated
        if isinstance(self.user, AnonymousUser):
            await self.send(text_data=json.dumps({
                "type": "auth_error",
                "error": "unauthenticated",
                "message": "User not authenticated"
            }))
            await self.close(code=4001, reason="unauthenticated")
            return
        # Check if user can access this profile
        if str(self.user.id) != str(self.user_id):
            await self.send(text_data=json.dumps({
                "type": "auth_error",
                "error": "access_denied",
                "message": "Access denied to this profile"
            }))
            await self.close(code=4003, reason="access_denied")
            return
        self.group_name = f"profile_{self.user_id}"
        # Add this channel to the user's group
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        logger.info(f"WebSocket client added to group '{self.group_name}', "
                    f"channel: {self.channel_name}")
        # Store connection time for debugging
        self.connected_at = time.time()
        # Don't call super().connect() since we already accepted above
        # Send confirmation message
        await self.send_success({
            "connected": True,
            "user_id": self.user_id,
            "group": self.group_name
        }, _("Connected to profile updates"))

    async def disconnect(self, code):
        """
        Handle WebSocket disconnection.
        Removes the channel from the user's group.
        """
        # Calculate connection duration
        if hasattr(self, 'connected_at'):
            duration = time.time() - self.connected_at
            logger.info(f"WebSocket was connected for {duration:.2f} seconds") # pylint: disable=logging-fstring-interpolation
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
            logger.info(f"WebSocket client removed from group '{self.group_name}', "
                        f"channel: {self.channel_name}")
        await super().disconnect(code)

    async def receive(self, text_data, *args):
        """
        Handle messages received from the client.
        Currently handles ping/pong for connection monitoring.
        """
        logger.info(f"ProfileConsumer.receive called with data: {text_data}")
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            if message_type == 'ping':
                logger.info("Received ping from client, sending pong")
                await self.send(text_data=json.dumps({
                    "type": "pong",
                    "timestamp": data.get('timestamp')
                }))
            else:
                await self.send_error(_("Unknown message type"), "unknown_type")
        except json.JSONDecodeError:
            await self.send_error(_("Invalid JSON format"), "invalid_json")
        except Exception as e:
            logger.error(f"Error in ProfileConsumer.receive: {str(e)}")
            await self.send_error(_("Internal server error"), "internal_error")

    async def profile_update(self, event):
        """
        Handle profile update events sent to the group.
        Forwards the update to the WebSocket client.
        """
        logger.info(f"PROFILE_UPDATE METHOD CALLED for user {self.user_id} with "
                    f"event: {event}")
        try:
            # Check if this update should be sent to this specific client
            device_id = event.get('device_id')
            # if device_id and hasattr(self, 'device_id') and self.device_id == device_id:
            #     # Skip sending to the device that initiated the update
            #     return
            logger.info(f"Sending profile update to client for user {self.user_id}")
            await self.send(text_data=json.dumps({
                "type": "profile_update",
                "action": "profile_updated",
                "device_id": device_id,
                "data": event.get('new_profile_data', {}),
                "password_updated": event.get('password_updated', False),
                "timestamp": event.get('timestamp')
            }))
        except Exception as e:
            logger.error(f"Error in ProfileConsumer.profile_update: {str(e)}")
            await self.send_error(_("Error processing profile update"), "update_error")

    async def profile_password_update(self, event):
        """
        Handle profile password update events sent to the group.
        Forwards the update to the WebSocket client.
        """
        try:
            # Check if this update should be sent to this specific client
            device_id = event.get('device_id')
            # if device_id and hasattr(self, 'device_id') and self.device_id == device_id:
            #     # Skip sending to the device that initiated the update
            #     return
            await self.send(text_data=json.dumps({
                "type": "profile_password_update",
                "action": "password_changed",
                "device_id": device_id,
                "password_updated": event.get('password_updated', False),
                "timestamp": event.get('timestamp')
            }))
        except Exception as e:
            logger.error(f"Error in ProfileConsumer.profile_password_update: {str(e)}")
            await self.send_error(_("Error processing profile password update"),
                                  "update_error")

    async def profile_password_reset(self, event):
        """
        Handle profile password reset events sent to the group.
        This should trigger logout on all connected devices except the one that 
            initiated the reset.
        """
        try:
            # Check if this update should be sent to this specific client
            device_id = event.get('device_id')
            await self.send(text_data=json.dumps({
                "type": "profile_password_reset",
                "action": "logout_required",
                "device_id": device_id,
                "password_reset": event.get('password_reset', True),
                "timestamp": event.get('timestamp')
            }))
        except Exception as e:
            logger.error(f"Error in ProfileConsumer.profile_password_reset: {str(e)}")
            await self.send_error(_("Error processing profile password reset"),
                                  "reset_error")

    async def notification(self, event):
        """
        Handle general notification events.
        """
        try:
            await self.send(text_data=json.dumps({
                "type": "notification",
                "data": event.get('data', {}),
                "message": event.get('message', ''),
                "timestamp": event.get('timestamp')
            }))
        except Exception as e:
            logger.error(f"Error in ProfileConsumer.notification: {str(e)}")
            await self.send_error(_("Error processing notification"), "notification_error")

    async def default(self, event):
        """
        Default handler for any unmatched event types.
        """
        logger.warning(f"Unhandled event type '{event.get('type')}' received in "
                       f"ProfileConsumer: {event}")

    async def dispatch(self, message):
        """
        Override dispatch to add debugging for all incoming messages.
        """
        logger.info(f"ProfileConsumer.dispatch called with message: {message}")
        logger.info(f"Message type: {message.get('type')}")
        # Check if the method exists
        handler_name = message.get('type', 'default')
        if hasattr(self, handler_name):
            logger.info(f"Found handler method: {handler_name}")
        else:
            logger.warning(f"No handler method found for: {handler_name}")
        try:
            result = await super().dispatch(message)
            logger.info(f"Dispatch completed successfully for type: {message.get('type')}")
            return result
        except Exception as e:
            logger.error(f"Dispatch failed for type {message.get('type')}: {str(e)}")
            raise
