# pylint: disable=broad-exception-caught,too-many-locals,too-many-branches,too-many-return-statements
"""Accounts related views"""
import logging

from django.conf import settings
from django.utils.translation import activate
from django.utils.translation import gettext_lazy as _
from google.auth.transport import requests
from google.oauth2 import id_token

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
import firebase_config  # pylint: disable=unused-import


from accounts.services import UserService, EmailVerificationService
from accounts.models import User
from accounts.repositories import UserRepository
from accounts.serializers import UserSerializer
from accounts.tokens import RefreshToken
from accounts.views.sign_in_views import SignInThirdPartyView
from backend.utils import get_db_alias

# Get a logger instance
logger = logging.getLogger(__name__)


class SignUpView(APIView):
    """Handles user registration."""
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        """
        Handles user registration.
        Accepts both 'selected_language' and 'current_language' for localization.
        Normalizes user input and creates a new user if data is valid.
        Sends email verification if enabled in settings.
        """
        db_alias = get_db_alias(request=request)
        data = request.data.copy()

        # Accept both 'selected_language' and 'current_language' from frontend
        current_language = data.get('selected_language') or \
                           data.get('current_language') or 'fr'
        activate(current_language)
        # Normalize first and last name: remove extra spaces
        def normalize_name(name):
            return ' '.join(name.split()) if name else ''
        data['first_name'] = normalize_name(data.get('first_name'))
        data['last_name'] = normalize_name(data.get('last_name'))
        data['username'] = data.get('username', '').strip()
        data['email'] = data.get('email', '').strip()
        data['password'] = data.get('password', '')

        # Profile image upload is currently disabled; enable if needed
        # profile_image = request.FILES.get('profile_image')
        # image_url = None
        # if profile_image:
        #     file_path = os.path.join('profile_images', f'profile_{profile_image.name}')
        #     saved_path = default_storage.save(file_path, ContentFile(profile_image.read()))
        #     image_url = f"{request.build_absolute_uri(settings.MEDIA_URL)}{saved_path}"
        #     logger.info(f"file_path: {file_path}")
        # if image_url:
        #     data['image_url'] = image_url

        serializer = UserSerializer(data=data)
        user = None
        if serializer.is_valid():
            user = serializer.save()
            # Set password securely after user is created
            user.set_password(data['password'])
            user.save(using=db_alias or None)
            message = _('Your account is created successfully. Log in with your username '
                        'and password.')
            # Send verification email if enabled and user is not validated
            if getattr(settings, 'ENABLE_EMAIL_VERIFICATION', False) and not getattr(
                user, 'is_user_email_validated', False):
                EmailVerificationService.send_verification_email(user)
                message = _('Your account has been successfully created. You can log in '
                    'once you validate your email via the link sent to your email address.')
            return Response({
                'message': message,
                'success': True,
                'username': user.username
            }, status=status.HTTP_201_CREATED)
        # Log serializer errors for debugging
        logger.error("User registration failed: %s", serializer.errors)
        message = _("We cannot create your account due to the following errors. "
                    "Please correct them and try again.")
        return Response(
            {'message': message, 'errors': serializer.errors, 'success': False},
            status=status.HTTP_409_CONFLICT
        )


class SignUpThirdPartyView(APIView):
    """
    API endpoint for user registration using third party.
    If credentials are valid, returns JWT tokens (access & refresh).
    """
    permission_classes = [AllowAny]
    # noinspection PyMethodMayBeStatic
    def post(self, request):
        """
        Handles user registration via third-party providers (Google, etc).
        Validates the third-party token, normalizes input, and creates a new user if
            needed.
        Returns JWT tokens and user data on success.
        """
        db_alias = get_db_alias(request=request)
        current_language = request.data.get("selected_language") or 'fr'
        email = request.data.get("email")
        first_name = request.data.get("first_name")
        last_name = request.data.get("last_name")
        token_value = request.data.get("id_token")
        type_third_party = request.data.get("type_third_party")
        user_image_url = request.data.get("user_image_url") or ""
        activate(current_language)
        # Validate required fields
        if not email or not type_third_party or not token_value:
            return Response(
                {"message": _("Email, Id token and Third party type are required"),
                 "success": False},
                status=status.HTTP_400_BAD_REQUEST
            )
        email_verified = False
        # Google OAuth token validation
        if type_third_party == "google":
            try:
                request_adapter = requests.Request()
                google_client_id = getattr(
                    settings, 'GOOGLE_SIGN_IN_WEB_CLIENT_ID', None)
                idinfo = id_token.verify_oauth2_token(token_value, request_adapter,
                                                      google_client_id)
                verified_email = idinfo.get('email')
                email_verified = idinfo.get('email_verified', False)
                if verified_email == email and email_verified:
                    email = verified_email
                    logger.info(
                        "Successfully verified Google OAuth token for email: %s",
                        email)
                else:
                    logger.warning(
                        "Email mismatch or not verified: provided=%s, token=%s, "
                        "verified=%s", email, verified_email, email_verified)
                    email = None
            except Exception as google_error:
                logger.error(
                    "Google OAuth token verification failed: %s",
                    str(google_error))
                email = None
        else:
            # Placeholder for other providers
            logger.warning(
                "Third-party provider '%s' not implemented yet",
                type_third_party)
            email = None
        if not email_verified:
            return Response({
                "message": _("Unable to verify your account with the provided "
                    "third-party credentials. Please check your information or try a "
                    "different sign-up method."),
                "success": False
            }, status=status.HTTP_400_BAD_REQUEST)
        user = UserRepository.filter(email=email, db_alias=db_alias).first()
        if user is not None:
            # If user exists, delegate to sign-in logic
            return SignInThirdPartyView().post(request, user=user)
        # Create new user with normalized names and generated username
        def normalize_name(name):
            return ' '.join(name.split()) if name else ''

        username = UserService.generate_unique_username(
            email=email, first_name=first_name, last_name=last_name, db_alias=db_alias)
        data = {
            'first_name': normalize_name(first_name),
            'last_name': normalize_name(last_name),
            'username': username,
            'email': email,
            'user_image_url': user_image_url or "",
            'is_user_email_validated': True,
        }
        serializer = UserSerializer(data=data)
        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)
            user_data = user.to_login_dict()
            return Response({
                "access_token": str(refresh.access_token),
                "refresh_token": str(refresh),
                "success": True,
                "user": user_data,
                "is_new_user": True,
            }, status=status.HTTP_200_OK)
        # Log serializer errors for debugging
        logger.error("Third-party signup failed: %s", serializer.errors)
        return Response({
            "message": _(
                "Unable to create or authenticate your account with "
                "the provided third-party credentials. Please check your "
                "information or try a different sign-up method."),
            "success": False
        }, status=status.HTTP_400_BAD_REQUEST)
