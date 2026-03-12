# pylint: disable=broad-exception-caught,too-many-locals,too-many-branches,too-many-return-statements
"""Accounts related views"""
import datetime
import logging

from django.contrib.auth.tokens import default_token_generator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.http import urlsafe_base64_decode
from django.utils.timezone import now
from django.utils.translation import activate
from django.utils.translation import gettext_lazy as _

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
import firebase_config  # pylint: disable=unused-import


from accounts.models import User
from accounts.repositories import UserRepository
from accounts.services import EmailVerificationService
from backend.utils import get_db_alias

# Get a logger instance
logger = logging.getLogger(__name__)


class SendVerificationEmailLinkView(APIView):
    """
    API endpoint to send a verification email link.
    This allows a user to request a new verification link if they haven't validated
        their email.
    """
    permission_classes = [AllowAny]
    # noinspection PyMethodMayBeStatic
    def post(self, request):
        """
        Handles POST request to send email verification link.

        Request Body:
        - user_id (int): The user's ID.
        - selected_language (str, optional): The language preference.

        Response:
        - Success: Email sent confirmation.
        - Failure: Appropriate error messages.
        """
        db_alias = get_db_alias(request=request)
        user_id = request.data.get("user_id")
        current_language = request.data.get("selected_language") or 'fr'
        activate(current_language)
        if not user_id:
            return Response(
                {"message": _("User id is required"), "success": False},
                status=status.HTTP_400_BAD_REQUEST
            )
        # Fetch the user or return 400 error if not found
        user_qs = User.objects.using(db_alias or None)
        user = get_object_or_404(user_qs, pk=user_id)
        if user.is_user_email_validated is True:
            return Response(
                {
                    "message": _("Your email is already verified. Try to sign in."),
                    "already_verified": True,
                    "success": False,
                },
                status=status.HTTP_401_UNAUTHORIZED
            )
        code_response, _uid_token = EmailVerificationService.send_verification_email(user)
        # Check if email was successfully sent
        if code_response != 200:
            return Response({
                "message": _("Email not sent. Please contact the technical team to "
                             "resolve your issue."),
                "success": False
            }, status=status.HTTP_400_BAD_REQUEST)
        return Response({
            "message": _("A new verification link has been sent to your email address. "
                         "Please verify your email before logging in."),
            "success": True,
        }, status=status.HTTP_200_OK)



def verify_user_email(uid, token_, resend_verification_email=False, db_alias=''):
    """
    Verifies the email token for a user.

    Args:
        uid (str): Base64 encoded user ID.
        token_ (str): Token for email verification.
        resend_verification_email (bool): resend the verification email for the user 
            if True.
        db_alias (str): Database alias to use.

    Returns:
        tuple: (
            (True if verification is successful, False otherwise),
            (True if already verified, False otherwise),
            (True if not verified and expired, False otherwise),
            (True if not a new verification email sent, False otherwise),
        ).
    """
    # Get user's token and timestamp str from the token in request
    token_date = token_.split("_*_")
    token = token_date[0]
    # Convert timestamp str to float if exists
    timestamp = len(token_date) == 2 and float(token_date[1])
    # Get date of token creation
    date_token = timestamp and datetime.datetime.fromtimestamp(timestamp)
    # Decode the user's coded id
    uid = urlsafe_base64_decode(uid).decode()
    user = UserRepository.get_by_id(uid, db_alias=db_alias)
    # The email is already validated
    if user.is_user_email_validated:
        return True, True, False, False
    # The resend_verification_email is True or the token is expired (not the same day)
    if resend_verification_email:
        code_status, _ = EmailVerificationService.send_verification_email(user)
        return False, False, False, code_status == 200
    if (
        date_token and date_token.strftime("%Y-%m-%d") != now().strftime("%Y-%m-%d")
    ):
        return False, False, True, False
    # If the token is valid, the email address will be validated
    if default_token_generator.check_token(user, token):
        user.is_user_email_validated = True
        user.save(using=db_alias or None)
        return True, False, False, False
    # If the token is not valid, the email address will not be validated
    return False, False, False, False


def verify_email(request):
    """
    Handles the email verification endpoint.

    Args:
        request (HttpRequest): The HTTP request object.

    Returns:
        JsonResponse: A response indicating the result of the verification.
    """
    db_alias = get_db_alias(request=request)
    uid = request.GET.get('uid')
    token = request.GET.get('token')
    # If uid or token aren't exists in the request, return an error message
    if not uid or not token:
        return JsonResponse({"message": _("Missing required parameters.")}, status=400)
    resend_verification_email = request.GET.get('resend_verification_email') in [True,
                                                                                 "true"]
    uid_ = urlsafe_base64_decode(uid).decode()
    user = UserRepository.get_by_id(uid_, db_alias=db_alias)
    selected_language = request.GET.get('selected_language') or user.current_language or 'en'
    # Activate user's current language for translations
    activate(selected_language)
    try:
        (verified, already_verified, expired_token,
         new_verification_email_sent) = verify_user_email(uid, token,
            resend_verification_email=resend_verification_email, db_alias=db_alias)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist) as e:
        # Save error in the log
        logger.error("Error while verifying email: %s", str(e), exc_info=True)
        return JsonResponse({"message": _("Invalid verification link.")}, status=400)
    if verified:
        if already_verified:
            return JsonResponse({"message": _("Email already verified."),
                                 "already_verified": True})
        return JsonResponse({"message": _("Email verified successfully.")})
    if resend_verification_email and new_verification_email_sent:
        return JsonResponse({
            "message": _("A new verification email has been sent."),
            "new_verification_email_sent": True
        }, status=400)
    if expired_token:
        return JsonResponse({
            "message": _("Expired token. Send a new verification email to "
                            "your email address."),
            "expired": True
        }, status=400)
    return JsonResponse({"message": _("Invalid token.")}, status=400)

