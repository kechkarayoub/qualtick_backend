# pylint: disable=broad-exception-caught,logging-fstring-interpolation
"""
Firebase Cloud Messaging (FCM) service for sending push notifications.

Usage anywhere in the backend:
    from backend.fcm_service import FCMService

    FCMService.send_to_user(user_id=42, title="Hello", body="You have a new message")
    FCMService.send_to_token(token="...", title="Hello", body="...", data={"key": "val"})
    FCMService.send_to_multiple_users([1, 2, 3], title="Broadcast", body="...")
"""

import logging

from firebase_admin import messaging

from backend.repositories.fcm_token_repository import FCMTokenRepository

logger = logging.getLogger(__name__)


class FCMService:
    """Service for sending Firebase Cloud Messaging push notifications."""

    @staticmethod
    def send_to_token(token: str, title: str, body: str, data: dict | None = None, db_alias: str = '') -> bool:
        """
        Send a push notification to a single FCM token.

        Args:
            token: The FCM registration token.
            title: Notification title.
            body: Notification body text.
            data: Optional string key-value payload delivered alongside the notification.
            db_alias: Database alias to use for token cleanup if needed.

        Returns:
            True if the message was accepted by FCM, False otherwise.
        """
        try:
            message = messaging.Message(
                notification=messaging.Notification(title=title, body=body),
                data={k: str(v) for k, v in (data or {}).items()},
                token=token,
            )
            response = messaging.send(message)
            logger.info(f"FCM message sent successfully. Message ID: {response}")
            return True
        except messaging.UnregisteredError:
            logger.warning(f"FCM token is no longer valid, removing: {token[:20]}...")
            FCMTokenRepository.delete_by_token(token, db_alias=db_alias)
            return False
        except Exception as e:
            logger.error(f"Failed to send FCM message to token {token[:20]}...: {str(e)}")
            return False

    @staticmethod
    def send_to_user(
        user_id: int,
        title: str,
        body: str,
        data: dict | None = None,
        platform: str | None = None,
        db_alias: str = '',
    ) -> dict:
        """
        Send a push notification to all registered devices of a user.

        Args:
            user_id: The user's primary key.
            title: Notification title.
            body: Notification body text.
            data: Optional key-value data payload.
            platform: If set ('android', 'ios', 'web'), limits delivery to that platform.
            db_alias: Database alias to use for queries.

        Returns:
            dict with keys 'sent' (int) and 'failed' (int).
        """
        tokens = FCMTokenRepository.get_tokens_for_user(user_id, platform=platform, db_alias=db_alias)
        if not tokens:
            logger.info(f"No FCM tokens found for user {user_id} (platform={platform})")
            return {"sent": 0, "failed": 0}

        results = {"sent": 0, "failed": 0}
        for token in tokens:
            success = FCMService.send_to_token(token, title, body, data, db_alias=db_alias)
            if success:
                results["sent"] += 1
            else:
                results["failed"] += 1

        logger.info(
            f"FCM batch for user {user_id}: {results['sent']} sent, "
            f"{results['failed']} failed"
        )
        return results

    @staticmethod
    def send_to_multiple_users(
        user_ids: list[int],
        title: str,
        body: str,
        data: dict | None = None,
        db_alias: str = '',
    ) -> dict:
        """
        Send a push notification to multiple users.

        Args:
            user_ids: List of user primary keys.
            title: Notification title.
            body: Notification body text.
            data: Optional key-value data payload.
            db_alias: Database alias to use for queries.

        Returns:
            dict with keys 'sent' (int) and 'failed' (int).
        """
        totals = {"sent": 0, "failed": 0}
        for user_id in user_ids:
            result = FCMService.send_to_user(user_id, title, body, data, db_alias=db_alias)
            totals["sent"] += result["sent"]
            totals["failed"] += result["failed"]
        return totals

    @staticmethod
    def send_multicast(tokens: list[str], title: str, body: str, data: dict | None = None, db_alias: str = '') -> dict:
        """
        Send the same notification to up to 500 tokens in a single FCM multicast request.

        Args:
            tokens: List of FCM registration tokens (max 500).
            title: Notification title.
            body: Notification body text.
            data: Optional key-value data payload.
            db_alias: Database alias to use for token cleanup if needed.

        Returns:
            dict with keys 'sent' (int) and 'failed' (int).
        """
        if not tokens:
            return {"sent": 0, "failed": 0}

        try:
            message = messaging.MulticastMessage(
                notification=messaging.Notification(title=title, body=body),
                data={k: str(v) for k, v in (data or {}).items()},
                tokens=tokens,
            )
            response = messaging.send_each_for_multicast(message)
            invalid_tokens = [
                tokens[i]
                for i, r in enumerate(response.responses)
                if not r.success and isinstance(r.exception, messaging.UnregisteredError)
            ]
            if invalid_tokens:
                for invalid_token in invalid_tokens:
                    FCMTokenRepository.delete_by_token(invalid_token, db_alias=db_alias)
                logger.info(f"Removed {len(invalid_tokens)} expired FCM tokens")

            logger.info(
                f"FCM multicast: {response.success_count} sent, "
                f"{response.failure_count} failed"
            )
            return {"sent": response.success_count, "failed": response.failure_count}
        except Exception as e:
            logger.error(f"FCM multicast failed: {str(e)}")
            return {"sent": 0, "failed": len(tokens)}
