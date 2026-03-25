# pylint: disable=broad-exception-caught,logging-fstring-interpolation
"""FCM device token registration/deregistration endpoints."""

import logging

from django.utils.translation import gettext_lazy as _
from backend.utils import get_db_alias
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.repositories.fcm_token_repository import FCMTokenRepository

logger = logging.getLogger(__name__)

VALID_PLATFORMS = {"android", "ios", "web"}


class FCMTokenView(APIView):
    """
    POST   /accounts/fcm-token/  — register or refresh a device FCM token.
    DELETE /accounts/fcm-token/  — deactivate a device FCM token (e.g. on logout).
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Register (or refresh) an FCM token for the authenticated user.

        Request body:
            token    (str, required)  — FCM registration token from the device/browser.
            platform (str, required)  — 'android', 'ios', or 'web'.
            device_id (str, optional) — Client device identifier.
        """
        token = request.data.get("token", "").strip()
        platform = request.data.get("platform", "").strip().lower()
        device_id = request.data.get("device_id", "").strip()
        db_alias = get_db_alias(request=request)

        if not token:
            return Response(
                {"message": _("token is required"), "success": False},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if platform not in VALID_PLATFORMS:
            return Response(
                {
                    "message": _("platform must be one of: android, ios, web"),
                    "success": False,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            FCMTokenRepository.upsert(
                user_id=request.user.id,
                token=token,
                platform=platform,
                device_id=device_id or None,
                db_alias=db_alias,
            )
            return Response(
                {"message": _("FCM token registered successfully"), "success": True},
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            logger.error(f"Failed to register FCM token for user {request.user.id}: {e}")
            return Response(
                {"message": _("Failed to register FCM token"), "success": False},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request):
        """
        Deactivate an FCM token for the authenticated user.

        Request body:
            token (str, required) — The FCM token to deactivate.
        """
        token = request.data.get("token", "").strip()
        if not token:
            return Response(
                {"message": _("token is required"), "success": False},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            db_alias = get_db_alias(request=request)
            FCMTokenRepository.delete_by_token(token, db_alias=db_alias)
            return Response(
                {"message": _("FCM token deactivated successfully"), "success": True},
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            logger.error(f"Failed to deactivate FCM token for user {request.user.id}: {e}")
            return Response(
                {"message": _("Failed to deactivate FCM token"), "success": False},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
