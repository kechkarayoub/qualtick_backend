# pylint: disable=broad-exception-caught,too-many-locals,too-many-branches,too-many-return-statements
"""Accounts related views"""
import datetime
import logging

from django.conf import settings
from django.http import JsonResponse
from django.utils.http import urlsafe_base64_decode
from django.utils.timezone import now
from django.utils.translation import activate
from django.utils.translation import gettext_lazy as _

from accounts.models import User
from accounts.repositories import UserRepository
from accounts.utils import (send_phone_number_verification_code)
from backend.utils import get_db_alias

# Get a logger instance
logger = logging.getLogger(__name__)


def verify_phone_number(request):
    """
    Handles the phone number verification endpoint.

    Args:
        request (HttpRequest): The HTTP request object.

    Returns:
        JsonResponse: A response indicating the result of the verification.
    """
    db_alias = get_db_alias(request=request)
    uid = request.GET.get('uid')
    verification_code = request.GET.get('verification_code')
    # If uid or verification_code aren't exists in the request, return an error message
    if not uid or not verification_code:
        return JsonResponse({"message": _("Missing required parameters.")}, status=400)
    resend_verification_phone_number_code = request.GET.get(
        'resend_verification_phone_number_code') in [True, "true"]
    uid_ = urlsafe_base64_decode(uid).decode()
    user = UserRepository.get(pk=uid_, db_alias=db_alias)
    # Activate user's current language for translations
    activate(user.current_language)
    if not user.is_user_phone_number_validated and not user.user_phone_number_to_verify:
        return JsonResponse({
            "message": _("You should add a phone number before validate it!")
        }, status=400)
    if not user.is_user_phone_number_validated and user.user_phone_number_to_verify and \
            UserRepository.filter(is_user_phone_number_validated=True,
                                user_phone_number=user.user_phone_number_to_verify,
                                db_alias=db_alias
    ).exists():
        return JsonResponse({
            "message": _("This phone number already verified for another user. "
                "Please contact the technical service at {technical_service_email} "
                "to resolve your problem.").format(
                    technical_service_email=settings.TECHNICAL_SERVICE_EMAIL)
        }, status=400)
    try:
        (
            verified, already_verified, expired_code, quota_exceeded
        ) = verify_user_phone_number(uid, verification_code,
            resend_verification_phone_number_code=resend_verification_phone_number_code,
            db_alias=db_alias)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist) as e:
        # Save error in the log
        logger.error("Error while verifying phone number: %s", str(e), exc_info=True)
        return JsonResponse({"message": _("Invalid verification code.")}, status=400)
    if verified:
        if already_verified:
            return JsonResponse({"message": _("Phone number already verified.")})
        return JsonResponse({"message": _("Phone number verified successfully.")})
    if expired_code:
        if resend_verification_phone_number_code:
            return JsonResponse({
                "message": _("A new verification code will be sent to your phone "
                            "number.")
            }, status=400)
        return JsonResponse({
            "message": _("Expired verification code.")
        }, status=400)
    if quota_exceeded:
        return JsonResponse({
            "message": _("Your sms verification code quota has been exceeded. "
                "Please contact the technical service at {technical_service_email} "
                "to resolve your problem.").format(
                    technical_service_email=settings.TECHNICAL_SERVICE_EMAIL)
        }, status=400)
    return JsonResponse({"message": _("Invalid code.")}, status=400)


def verify_user_phone_number(uid, verification_code_,
                             resend_verification_phone_number_code=False, db_alias=''):
    """
    Verifies the phone number code for a user.

    Args:
        uid (str): Base64 encoded user ID.
        verification_code_ (str): Code for user_phone_number verification.
        resend_verification_phone_number_code (bool): resend the phone number
            verification code for the user if True.
        db_alias (str): Database alias to use.

    Returns:
        tuple: (
            (True if verification is successful, False otherwise),
            (True if already verified, False otherwise),
            (True if not verified and expired, False otherwise),
            (True if phone number verification code sms quota exceeded, False otherwise),
        ).
    """
    # Decode the user's coded id
    uid = urlsafe_base64_decode(uid).decode()
    user = UserRepository.get_by_id(uid, db_alias=db_alias)
    # The email is already validated
    if user.is_user_phone_number_validated:
        return True, True, False, False
    # the verification_code is expired (not the same day)
    if user.user_phone_number_verification_code_generated_at and (
            user.user_phone_number_verification_code_generated_at + datetime.timedelta(
        minutes=settings.NUMBER_MINUTES_BEFORE_PHONE_NUMBER_VERIFICATION_CODE_EXPIRATION)) < now():
        return False, False, True, False
    # The resend_verification_phone_number_code is True
    if resend_verification_phone_number_code:
        if user.nbr_phone_number_verification_code_used >= settings.PHONE_NUMBER_VERIFICATION_CODE_QUOTA:   # pylint: disable=line-too-long
            return False, False, False, True
        send_phone_number_verification_code(user)
    # If the token is valid, the email address will be validated
    if user.user_phone_number_verification_code == verification_code_:
        user.is_user_phone_number_validated = True
        user.user_phone_number = user.user_phone_number_to_verify
        user.save(using=db_alias or None)
        return True, False, False, False
    # If the token is not valid, the email address will not be validated
    return False, False, False, False
