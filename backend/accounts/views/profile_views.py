# pylint: disable=broad-exception-caught,too-many-locals,too-many-branches,too-many-return-statements
"""Accounts related views"""
import logging

from django.conf import settings
from django.contrib.auth import authenticate
from django.http import QueryDict
from django.utils.translation import activate
from django.utils.translation import gettext_lazy as _

from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
import firebase_config  # pylint: disable=unused-import

from backend.utils import (generate_random_code, get_all_timezones, get_db_alias, remove_file, upload_file)
from backend.ws_utils import (notify_profile_password_update,
                              notify_profile_update)
from backend.models import AuditLog
from backend.services.audit_log_service import AuditLogService

from accounts.models import THEME_CHOICES
from accounts.serializers import UserSerializer
from accounts.tokens import RefreshToken
from accounts.utils import (blacklist_user_tokens, format_phone_number)

# Get a logger instance
logger = logging.getLogger(__name__)


class UpdateProfileView(APIView):
    """
    A view to handle updating the user's profile information, including personal data
    and optional image and password updates.

    This view:
    - Requires the user to be authenticated.
    - Allows updating of basic profile information such as name, gender, and birthday.
    - Handles the optional upload of a profile image.
    - Optionally, allows the user to update their password if the correct current
        password is provided.

    Methods:
        put: Handles the PUT request to update the user profile.
    """
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)

    # noinspection PyMethodMayBeStatic
    def put(self, request, *args, **kwargs):  # pylint: disable=too-many-statements,too-many-branches,line-too-long
        """
        Handles the logic for updating the user's profile.
        This includes updating their basic profile fields, profile image (if provided),
        and optionally updating the password.

        Args:
            request (Request): The request object containing the user's data and files.

        Returns:
            Response: The response containing the updated user data, any relevant tokens,
                and success/failure message.
        """
        db_alias = get_db_alias(request=request)
        user = request.user
        data = QueryDict('', mutable=True)
        data.update(request.data)
        # Get selected language or default to French
        current_language = data.get('current_language') or 'fr'
        activate(current_language)
        action = data.get('action')
        if action in ['update_profile']:
            # Generate a unique prefix to avoid email/username uniqueness validation
            # errors
            random_prefix = generate_random_code()
            data['email'] = random_prefix + data.get('email', '')
            data['username'] = random_prefix + data.get('username', '')
            user_phone_number = data.get('user_phone_number')
            user_cin = data.get('user_cin')
            if user_cin and user_cin == user.user_cin:
                data['user_cin'] = ""
            formatted_user_phone_number = format_phone_number(user_phone_number)
            if user.user_phone_number and user.user_phone_number == formatted_user_phone_number:
                data['user_phone_number'] = ""
            # Create a dummy serializer for validation purposes only
            serializer = UserSerializer(data=data)
            if not serializer.is_valid():
                message = _(
                    "Your profile could not be updated due to the errors listed "
                    "above. Please correct them and try again.")
                AuditLogService.log(
                    action=AuditLog.ACTION_PROFILE_UPDATE,
                    outcome=AuditLog.OUTCOME_FAILURE,
                    user=user,
                    resource_type='accounts.User',
                    resource_id=user.id,
                    description=f"Profile update failed for '{user.username}' (validation error)",
                    extra_data={
                        'errors': serializer.errors,
                        'fields_attempted': {
                            k: data.get(k) for k in (
                                'first_name', 'last_name', 'user_phone_number',
                                'user_cin', 'user_country', 'user_gender',
                                'user_birthday', 'user_address',
                            )
                        },
                    },
                    request=request,
                    db_alias=db_alias,
                )
                return Response(
                    {'message': message, 'errors': serializer.errors, 'success': False},
                    status=status.HTTP_409_CONFLICT
                )
            # Retrieve additional profile data
            profile_image = request.FILES.get('profile_image')
            image_updated = data.get('image_updated') in [True, 'true']
            update_password = data.get('update_password') in [True, 'true']
            user_image_url = user.user_image_url
            # Handle profile image update
            if image_updated:
                user_image_url = None
                if profile_image:
                    try:
                        user_image_url, file_path = upload_file(request, profile_image,
                            'profile_images', prefix="profile_")
                        logger.info("file_path: %s", file_path)
                    except Exception as e:
                        logger.error("Image upload failed: %s", str(e))
                        return Response({'message': _("Image upload failed."),
                                         'success': False}, status=500)
                if user.user_image_url:
                    remove_file(request, user.user_image_url)
            # Update user fields
            user.current_language = current_language
            user.first_name = data.get('first_name')
            user.last_name = data.get('last_name')
            user.user_address = data.get('user_address')
            user.user_birthday = data.get('user_birthday')
            user.user_cin = data.get('user_cin')
            user.user_country = data.get('user_country')
            user.user_gender = data.get('user_gender')
            user.user_image_url = user_image_url
            user.user_initials_bg_color = data.get('user_initials_bg_color')
            user.user_phone_number = user_phone_number
            user.save(using=db_alias or None)
            # Handle password update
            wrong_password = False
            access_token = None
            refresh_token = None
            if update_password:
                authenticated_user = authenticate(request, username=user.username,
                                                  password=data.get('current_password'))
                if authenticated_user is not None:
                    user.set_password(data.get('new_password'))
                    user.save(using=db_alias or None)
                    refresh = RefreshToken.for_user(user)
                    access_token = str(refresh.access_token)
                    refresh_token = str(refresh)
                else:
                    wrong_password = True
            # Prepare response
            user_data = user.to_login_dict()
            message = _('Your profile has been updated successfully.')
            # Get device ID from request headers or data to exclude from WebSocket
            # updates
            device_id = request.headers.get('X-Device-ID')
            # Notify all connected clients (via WebSocket) that the user's profile has
            # changed
            logger.info(
                "Sending profile update notification for user %s from device %s",
                user.id, device_id)
            notify_profile_update(
                user.id, user_data,
                password_updated=access_token is not None,
                device_id=device_id)
            AuditLogService.log(
                action=AuditLog.ACTION_PROFILE_UPDATE,
                outcome=AuditLog.OUTCOME_SUCCESS,
                user=user,
                resource_type='accounts.User',
                resource_id=user.id,
                description=f"Profile updated for '{user.username}'"
                            + (' (password changed)' if access_token else ''),
                extra_data={
                    'updated_fields': {
                        k: data.get(k) for k in (
                            'first_name', 'last_name', 'user_phone_number',
                            'user_cin', 'user_country', 'user_gender',
                            'user_birthday', 'user_address', 'current_language',
                        )
                    },
                    'image_updated': image_updated,
                    'password_updated': bool(access_token),
                },
                request=request,
                db_alias=db_alias,
            )
            return Response({
                    'message': message,
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "success": True,
                    "user": user_data,
                    "wrong_password": wrong_password,
                }, status=status.HTTP_200_OK,
            )
        if action in ['update_password']:
            # Handle password update
            current_password = data.get('current_password')
            new_password = data.get('new_password')
            wrong_password = False
            access_token = None
            refresh_token = None
            authenticated_user = authenticate(request, username=user.username,
                                              password=current_password)
            if authenticated_user is not None:
                # Blacklist all existing tokens for this user before setting new password
                blacklist_user_tokens(user, db_alias=db_alias)
                # Set new password and generate new tokens
                user.set_password(new_password)
                user.save(using=db_alias or None)
                refresh = RefreshToken.for_user(user)
                access_token = str(refresh.access_token)
                refresh_token = str(refresh)
                message = _('Your password has been updated successfully.')
            else:
                message = _(
                    'Your password update failed. Please check your current '
                    'password and try again.')
                wrong_password = True
            # Prepare response
            if not wrong_password:
                device_id = request.headers.get('X-Device-ID')
                notify_profile_password_update(user.id, device_id=device_id)
            AuditLogService.log(
                action=AuditLog.ACTION_PASSWORD_CHANGE,
                outcome=AuditLog.OUTCOME_FAILURE if wrong_password else AuditLog.OUTCOME_SUCCESS,
                user=user,
                resource_type='accounts.User',
                resource_id=user.id,
                description=f"Password change {'failed' if wrong_password else 'succeeded'}"
                            f" for '{user.username}'",
                request=request,
                db_alias=db_alias,
            )
            return Response({
                    'message': message,
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "success": True,
                    "wrong_password": wrong_password,
                }, status=status.HTTP_200_OK,
            )
        return Response({'message': _("Action not exists."), 'success': False}, status=500)



class UpdateSettingsView(APIView):
    """
    API endpoint for updating user settings (language, timezone, theme).
    """
    permission_classes = [IsAuthenticated]

    def put(self, request):
        """
        Update user settings including language, timezone, and theme.
        
        Request Body:
        - current_language (str, optional): User's preferred language
        - user_timezone (str, optional): User's timezone
        - user_theme (str, optional): User's preferred theme (light, dark, auto)
        - selected_language (str, optional): Language for response messages
        
        Response:
        - Success: Updated user data
        - Failure: Error messages with proper status codes
        """
        db_alias = get_db_alias(request=request)
        try:
            current_language = request.data.get("selected_language") or \
            request.user.current_language or 'en'
            activate(current_language)
            user = request.user
            updated_fields = []
            # Update current language
            new_language = request.data.get("current_language")
            if new_language and new_language != user.current_language:
                if new_language in [lang[0] for lang in settings.LANGUAGES]:
                    user.current_language = new_language
                    updated_fields.append("current_language")
                else:
                    return Response({
                        "message": _("Invalid language selection"),
                        "success": False
                    }, status=status.HTTP_400_BAD_REQUEST)
            # Update timezone
            new_timezone = request.data.get("user_timezone")
            if new_timezone and new_timezone != user.user_timezone:
                # Validate timezone
                valid_timezones = [tz[0] for tz in get_all_timezones()]
                if new_timezone in valid_timezones:
                    user.user_timezone = new_timezone
                    updated_fields.append("user_timezone")
                else:
                    return Response({
                        "message": _("Invalid timezone selection"),
                        "success": False
                    }, status=status.HTTP_400_BAD_REQUEST)
            # Update theme
            new_theme = request.data.get("user_theme")
            if new_theme and new_theme != user.user_theme:
                valid_themes = [theme[0] for theme in THEME_CHOICES]
                if new_theme in valid_themes:
                    user.user_theme = new_theme
                    updated_fields.append("user_theme")
                else:
                    return Response({
                        "message": _("Invalid theme selection"),
                        "success": False
                    }, status=status.HTTP_400_BAD_REQUEST)
            if not updated_fields:
                return Response({
                    "message": _("No changes detected"),
                    "success": False
                }, status=status.HTTP_400_BAD_REQUEST)
            # Save the user
            user.save(update_fields=updated_fields, using=db_alias or None)
            # Get device ID for WebSocket notification
            device_id = request.headers.get('X-Device-ID')
            # Notify other devices about settings update
            user_data = user.to_login_dict()
            notify_profile_update(user.id, user_data, device_id=device_id)
            logger.info("Settings updated for user %s: %s",
                        user.username, ', '.join(updated_fields))
            return Response({
                "message": _("Settings updated successfully"),
                "success": True,
                "user": user_data
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error("Error updating settings for user %s: %s",
                         request.user.id if request.user else 'unknown', str(e))
            return Response({
                "message": _("An error occurred while updating settings"),
                "success": False
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

