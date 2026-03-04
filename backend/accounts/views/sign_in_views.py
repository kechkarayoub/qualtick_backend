# pylint: disable=broad-exception-caught,too-many-locals,too-many-branches,too-many-return-statements
"""Accounts related views"""
import logging

from django.conf import settings
from django.contrib.auth import authenticate
from django.utils.translation import activate
from django.utils.translation import gettext_lazy as _
from google.auth.transport import requests
from google.oauth2 import id_token

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
import firebase_config  # pylint: disable=unused-import


from accounts.models import User
from accounts.repositories import UserRepository
from accounts.tokens import RefreshToken
from backend.utils import get_db_alias

# Get a logger instance
logger = logging.getLogger(__name__)


class SignInView(APIView):
    """
    API endpoint for user authentication.
    If credentials are valid, returns JWT tokens (access & refresh).
    """
    permission_classes = [AllowAny]
    # noinspection PyMethodMayBeStatic
    def post(self, request):
        """
        Handles user login authentication.

        Request Body:
        - email_or_username (str): User's email or username.
        - password (str): User's password.
        - selected_language (str, optional): Language preference.

        Response:
        - Success: JWT tokens and user data.
        - Failure: Error messages with proper status codes.
        """
        db_alias = get_db_alias(request=request)
        email_or_username = request.data.get("email_or_username")
        current_language = request.data.get("selected_language") or 'fr'
        password = request.data.get("password")

        activate(current_language)

        if not email_or_username or not password:
            return Response(
                {"message": _("Email/Username and password are required"),
                 "success": False},
                status=status.HTTP_400_BAD_REQUEST
            )
        if "@" in email_or_username:
            user = UserRepository.filter(
                email=email_or_username, is_active=True, db_alias=db_alias
            ).first() or UserRepository.filter(email=email_or_username, db_alias=db_alias).first()
        else:
            user = UserRepository.filter(username=email_or_username, db_alias=db_alias).first()
        if user is not None:
            # Generate JWT tokens
            if user.is_user_deleted is True:
                return Response(
                    {
                        "message": _("Your account is deleted. Please contact the "
                                     "technical team to resolve your issue."),
                        "success": False,
                    },
                    status=status.HTTP_401_UNAUTHORIZED
                )
            if user.is_active is False:
                return Response(
                    {
                        "message": _("Your account is inactive. Please contact the "
                                     "technical team to resolve your issue."),
                        "success": False,
                    },
                    status=status.HTTP_401_UNAUTHORIZED
                )
            user = authenticate(request, username=user.username, password=password)
            if user is not None:
                if user.is_user_email_validated is False:
                    if getattr(settings, 'ENABLE_EMAIL_VERIFICATION', False):
                        return Response(
                            {
                                "message": _("Your email is not yet verified. Please verify "
                                            "your email address before sign in."),
                                "success": False,
                                "user_id": user.id,
                                "email": user.email,
                                "email_verification_required": True,
                            },
                            status=status.HTTP_403_FORBIDDEN
                        )
                    else:
                        user.is_user_email_validated = True
                        user.save(using=db_alias or None)
                if user.current_language != current_language:
                    activate(user.current_language)
                refresh = RefreshToken.for_user(user)
                user_data = user.to_login_dict()
                return Response({
                    "access_token": str(refresh.access_token),
                    "refresh_token": str(refresh),
                    "success": True,
                    "user": user_data,
                }, status=status.HTTP_200_OK)
            return Response({"message": _("Invalid credentials"), "success": False},
                                status=status.HTTP_400_BAD_REQUEST)
        return Response({"message": _("Invalid credentials"), "success": False},
                        status=status.HTTP_400_BAD_REQUEST)
class SignInThirdPartyView(APIView):
    """
    API endpoint for user authentication using third party.
    If credentials are valid, returns JWT tokens (access & refresh).
    """
    permission_classes = [AllowAny]
    # noinspection PyMethodMayBeStatic
    def post(self, request, user=None):
        """
        Handles user login authentication.

        Request Body:
        - email (str): User's email.
        - selected_language (str, optional): Language preference.
        - type_third_party (str): Type third party (Apple, facebook, google, ...).

        Returns:
        - 200 OK: If authentication is successful (JWT tokens and user data).
        - 400 Bad Request: If required fields are missing or credentials are invalid.
        - 401 Unauthorized: If the user is deleted or inactive.
        """
        db_alias = get_db_alias(request=request)
        email = request.data.get("email")
        current_language = request.data.get("selected_language") or 'fr'
        token_value = request.data.get("id_token")
        type_third_party = request.data.get("type_third_party")
        _from_platform = request.data.get("from_platform") or 'web'
        activate(current_language)
        if user is None:
            if not email or not type_third_party or not token_value:
                return Response(
                    {"message": _("Email, Id token and Third party type are required"),
                     "success": False},
                    status=status.HTTP_400_BAD_REQUEST
                )
            try:
                # For Google OAuth, validate the token using Google OAuth verification
                if type_third_party == "google":
                    try:
                        # The token you receive is a Google OAuth ID token,
                        # not a Firebase token
                        # Use Google OAuth verification instead of Firebase
                        request_adapter = requests.Request()
                        # Your Google OAuth client ID (the audience in the token)
                        google_client_id = getattr(
                            settings, 'GOOGLE_SIGN_IN_WEB_CLIENT_ID', None)
                        # Verify the Google OAuth ID token
                        idinfo = id_token.verify_oauth2_token(
                            token_value, request_adapter, google_client_id)
                        # Check if the token is valid and email matches
                        verified_email = idinfo.get('email')
                        email_verified = idinfo.get('email_verified', False)
                        if verified_email == email and email_verified:
                            email = verified_email
                            logger.info(
                                "Successfully verified Google OAuth token for email: %s",
                                email)
                        else:
                            logger.warning(
                                "Email mismatch or not verified: provided=%s, "
                                "token=%s, verified=%s", email, verified_email, 
                                email_verified)
                            email = None
                    except Exception as google_error:
                        logger.error(
                            "Google OAuth token verification failed: %s", 
                            str(google_error))
                        email = None
                else:
                    # For other third-party providers, implement similar verification
                    logger.warning(
                        "Third-party provider '%s' not implemented yet", 
                        type_third_party)
                    email = None
            except Exception as e:
                logger.error("Unexpected error during token verification: %s", str(e))
                email = None
            user = UserRepository.filter(email=email, db_alias=db_alias).first()
        if user is not None:
            if user.is_user_deleted is True:
                return Response(
                    {
                        "message": _("Your account is deleted. Please contact the "
                                     "technical team to resolve your issue."),
                        "success": False,
                    },
                    status=status.HTTP_401_UNAUTHORIZED
                )
            if user.is_active is False:
                return Response(
                    {
                        "message": _("Your account is inactive. Please contact the "
                                     "technical team to resolve your issue."),
                        "success": False,
                    },
                    status=status.HTTP_401_UNAUTHORIZED
                )
            if user.is_user_email_validated is False:
                user.is_user_email_validated = True
                user.save(using=db_alias or None)
            if user.current_language != current_language:
                activate(user.current_language)
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            user_data = user.to_login_dict()
            return Response({
                "access_token": str(refresh.access_token),
                "refresh_token": str(refresh),
                "success": True,
                "user": user_data,
            }, status=status.HTTP_200_OK)
        return Response({"message": _("Invalid credentials"), "success": False},
                        status=status.HTTP_400_BAD_REQUEST)

