# pylint: disable=broad-exception-caught,logging-fstring-interpolation
"""
Repository for FCM device tokens — data-access layer only.
"""

import logging

logger = logging.getLogger(__name__)


class FCMTokenRepository:
    """Data-access helpers for the FCMToken model."""

    @staticmethod
    def get_tokens_for_user(user_id: int, platform: str | None = None, db_alias: str = '') -> list[str]:
        """Return all active FCM tokens for a user, optionally filtered by platform."""
        from accounts.models import FCMToken
        qs = FCMToken.objects.using(db_alias or None).filter(user_id=user_id, is_active=True)
        if platform:
            qs = qs.filter(platform=platform)
        return list(qs.values_list("token", flat=True))

    @staticmethod
    def upsert(user_id: int, token: str, platform: str, device_id: str | None = None, db_alias: str = '') -> None:
        """
        Create or update an FCM token for a user.
        If the same token already exists for another user, it is reassigned.
        """
        from accounts.models import FCMToken
        FCMToken.objects.using(db_alias or None).update_or_create(
            token=token,
            defaults={
                "user_id": user_id,
                "platform": platform,
                "device_id": device_id or "",
                "is_active": True,
            },
        )

    @staticmethod
    def delete_by_token(token: str, db_alias: str = '') -> None:
        """Mark a specific FCM token as inactive (soft-delete)."""
        from accounts.models import FCMToken
        FCMToken.objects.using(db_alias or None).filter(token=token).update(is_active=False)

    @staticmethod
    def deactivate_for_user(user_id: int, device_id: str | None = None, db_alias: str = '') -> None:
        """
        Deactivate FCM tokens for a user, optionally limited to a specific device.
        Called on logout so stale tokens are not targeted.
        """
        from accounts.models import FCMToken
        qs = FCMToken.objects.using(db_alias or None).filter(user_id=user_id, is_active=True)
        if device_id:
            qs = qs.filter(device_id=device_id)
        qs.update(is_active=False)
