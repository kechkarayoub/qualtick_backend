# pylint: disable=broad-exception-caught,too-many-locals,too-many-branches,too-many-return-statements
"""Accounts related views"""
import logging

from django.utils.translation import activate
from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.token_blacklist.models import (BlacklistedToken,
                                                             OutstandingToken)

from accounts.tokens import RefreshToken
from accounts.utils import (blacklist_user_tokens)
from backend.repositories.fcm_token_repository import FCMTokenRepository
from backend.ws_utils import (notify_profile_password_reset)
from backend.utils import get_db_alias

# Get a logger instance
logger = logging.getLogger(__name__)


class LogoutView(APIView):
    """
    API endpoint for user logout.
    Blacklists the user's refresh token to prevent further use.
    """
    permission_classes = [IsAuthenticated]
    def post(self, request):
        """
        Logout user by blacklisting their tokens.
        
        Request Body:
        - refresh_token (str): The refresh token to blacklist
        - selected_language (str, optional): Language preference
        
        Response:
        - Success: Confirmation of logout
        - Failure: Error messages with proper status codes
        """
        try:
            current_language = request.data.get("selected_language") or 'en'
            activate(current_language)
            db_alias = get_db_alias(request=request)

            # Optional: Blacklist all tokens for this user (more secure but logs out
            # all devices)
            # You can enable this if you want to logout from all devices
            logout_all_devices = request.data.get("logout_all_devices", False)
            refresh_token = request.data.get("refresh_token")
            if not refresh_token:
                return Response({
                    "message": _("Refresh token is required"),
                    "success": False
                }, status=status.HTTP_400_BAD_REQUEST)
            try:
                # Parse the refresh token to get the JTI
                token = RefreshToken(refresh_token)
                jti = token.get('jti')
                if jti:
                    # Find the outstanding token and blacklist it
                    try:
                        outstanding_token = OutstandingToken.objects.using(db_alias or None).get(jti=jti)
                        # Check if already blacklisted
                        if not BlacklistedToken.objects.using(db_alias or None).filter(
                            token=outstanding_token).first():
                            BlacklistedToken.objects.using(db_alias or None).create(token=outstanding_token)
                            logger.info("Successfully blacklisted token for user %s",
                                        request.user.username)
                        else:
                            logger.info("Token already blacklisted for user %s",
                                        request.user.username)
                    except OutstandingToken.DoesNotExist:
                        logger.warning("Outstanding token not found for JTI %s",
                                       jti)
                        # Token might already be expired or invalid, but that's okay for
                        # logout
                else:
                    logger.warning("No JTI found in refresh token")
            except Exception as token_error:
                logger.warning("Error processing refresh token: %s",
                               str(token_error))
                # Continue with logout even if token processing fails
                if not logout_all_devices:
                    return Response({
                        "message": _("Invalid refresh token"),
                        "success": False
                    }, status=status.HTTP_400_BAD_REQUEST)
            if logout_all_devices:
                blacklist_user_tokens(request.user, db_alias=db_alias)
            # Get device ID for WebSocket notification
            device_id = request.headers.get('X-Device-ID')

            # Notify all connected devices about logout (except the current device)
            # This will trigger automatic logout on other devices if logout_all_devices
            # is True
            if logout_all_devices:
                notify_profile_password_reset(request.user.id, device_id=device_id)
            FCMTokenRepository.deactivate_for_user(
                request.user.id,
                device_id=device_id if not logout_all_devices else None,
                db_alias=db_alias,
            )
            return Response({
                "message": _("Successfully logged out"),
                "success": True
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error("Error during logout for user %s: %s",
                         request.user.id if request.user else 'unknown', str(e))
            return Response({
                "message": _("An error occurred during logout"),
                "success": False
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

