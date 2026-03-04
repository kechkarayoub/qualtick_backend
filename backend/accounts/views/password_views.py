# pylint: disable=broad-exception-caught,too-many-locals,too-many-branches,too-many-return-statements
"""Accounts related views"""
import logging

from django.utils.translation import activate
from django.utils.translation import gettext_lazy as _

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
import firebase_config  # pylint: disable=unused-import


from accounts.repositories import UserRepository
from accounts.utils import (blacklist_user_tokens,
                    send_password_reset_email,
                    validate_password_reset_token)
from backend.utils import get_db_alias
from backend.ws_utils import (notify_profile_password_reset)

# Get a logger instance
logger = logging.getLogger(__name__)


class ForgotPasswordView(APIView):
    """
    API endpoint for requesting password reset.
    Sends a password reset email to the user if the email exists.
    """
    permission_classes = [AllowAny]
    # noinspection PyMethodMayBeStatic
    def post(self, request):
        """
        Handles password reset request.

        Request Body:
        - email_or_username (str): User's email address or username.
        - selected_language (str, optional): Language preference.

        Response:
        - Success: Confirmation message (always success for security).
        - Note: For security, always returns success even if email/username doesn't exist.
        """
        db_alias = get_db_alias(request=request)
        email_or_username = request.data.get("email_or_username")
        current_language = request.data.get("selected_language") or 'fr'
        activate(current_language)
        if not email_or_username:
            return Response(
                {"message": _("Email or username is required"), "success": False},
                status=status.HTTP_400_BAD_REQUEST
            )
        # Always return success message for security
        # (don't reveal if email/username exists)
        success_message = _("If an account with this email or username exists, you will "
                            "receive a password reset link shortly.")
        try:
            # Check if user exists with this email or username
            user = None
            if "@" in email_or_username:
                # It's likely an email
                user = UserRepository.filter(email=email_or_username, is_active=True,
                                           is_user_deleted=False, db_alias=db_alias).first()
            else:
                # It's likely a username, find user by username and get their email
                user = UserRepository.filter(username=email_or_username, is_active=True,
                                           is_user_deleted=False, db_alias=db_alias).first()
            if user:
                # Set user's language for email
                if user.current_language != current_language:
                    user.current_language = current_language
                    user.save(using=db_alias or None)
                # Send password reset email
                send_password_reset_email(user)
        except Exception as e:
            # Log the error but don't expose it to the user
            logger.error("Error sending password reset email: %s", str(e))
        return Response({
            "message": success_message,
            "success": True,
        }, status=status.HTTP_200_OK)


class ResetPasswordView(APIView):
    """
    API endpoint for resetting password using the token from email.
    """
    permission_classes = [AllowAny]
    # noinspection PyMethodMayBeStatic
    def post(self, request):
        """
        Handles password reset with token.

        Request Body:
        - uid (str): Base64 encoded user ID.
        - token (str): Password reset token.
        - new_password (str): New password.
        - selected_language (str, optional): Language preference.

        Response:
        - Success: Confirmation of password reset.
        - Failure: Error messages with proper status codes.
        """
        db_alias = get_db_alias(request=request)
        uid = request.data.get("uid")
        token = request.data.get("token")
        new_password = request.data.get("new_password")
        current_language = request.data.get("selected_language") or 'fr'
        activate(current_language)
        if not uid or not token or not new_password:
            return Response(
                {"message": _("All fields are required"), "success": False},
                status=status.HTTP_400_BAD_REQUEST
            )
        # Validate the token and get user
        is_valid, user, error_message = validate_password_reset_token(uid, token, db_alias=db_alias)
        if not is_valid:
            return Response({
                "message": _(error_message) if error_message else _(
                    "Invalid or expired reset token. Please request a new password reset."),
                "success": False,
            }, status=status.HTTP_400_BAD_REQUEST)
        try:
            # Activate user's language
            activate(user.current_language)
            # Blacklist all existing tokens for this user before resetting password
            blacklist_user_tokens(user, db_alias=db_alias)
            # Reset password
            user.set_password(new_password)
            user.save(using=db_alias or None)
            # Notify all connected devices about password reset - they should logout
            # Get device ID from request headers or data to exclude from WebSocket updates
            device_id = request.headers.get('X-Device-ID')
            # No device_id provided since this is a password reset from email link
            notify_profile_password_reset(user.id, device_id=device_id)
            return Response({
                "message": _("Password has been reset successfully. You can now log "
                             "in with your new password."),
                "success": True,
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error("Error resetting password: %s", str(e))
            return Response({
                "message": _("An error occurred while resetting your password. Please "
                             "try again."),
                "success": False,
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
