"""Accounts related utils"""
import logging
from smtplib import (SMTPAuthenticationError, SMTPDataError, SMTPException,
                     SMTPRecipientsRefused, SMTPSenderRefused)

import phonenumbers

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from rest_framework_simplejwt.token_blacklist.models import (BlacklistedToken,
                                                             OutstandingToken)

from backend.utils import (generate_random_code, get_db_alias, get_email_base_context,
                           send_phone_message)

# Get a logger instance
logger = logging.getLogger(__name__)



def format_phone_number(user_phone_number):
    """
        Convert user_phone_number to a standard format

        Args:
            user_phone_number (String): the phone number.

        Returns:
            user_phone_number: formatted phone number.
    """
    try:
        parsed_number = phonenumbers.parse(user_phone_number,
                                           settings.DEFAULT_PHONE_NUMBER_COUNTRY_CODE)
        user_phone_number = phonenumbers.format_number(
            parsed_number, phonenumbers.PhoneNumberFormat.E164
        )
    except phonenumbers.NumberParseException:
        pass
    return user_phone_number


def send_phone_number_verification_code(user,
        handle_send_phone_number_verification_sms_error=False, do_not_mock_api=False):
    """
    Sends a phone number verification code to the user.

    Args:
        user (User): The user object to send the email to.
        handle_send_phone_number_verification_sms_error (bool): Flag to simulate an 
            intentional error for testing.
        do_not_mock_api (bool): Flag to api even if it is for testing.

    Returns:
        tuple: A tuple containing the status code (int) and code verification data (tuple).
    """
    db_alias = get_db_alias(user=user)
    # Generate user's verification code (6-digit)
    verification_code = generate_random_code()
    # Encode user's id
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    # Build the sms content
    context = {'verification_code': verification_code}
    # Plain text fallback
    message_content = render_to_string("sms_verification.txt", context)
    # Send the email
    try:
        if settings.DEBUG:
            print("message_content")
            print(message_content)
        # This is for testing send sms error from third party
        if handle_send_phone_number_verification_sms_error:
            _err = int("text")
        receivers_numbers = [user.user_phone_number_to_verify]
        response = send_phone_message(message_content, receivers_numbers,
                                      do_not_mock_api=do_not_mock_api)
        if not response.get('all_verification_codes_sent'):
            return 500, (uid, verification_code)
    except (  # pylint: disable=broad-exception-caught
        UnicodeEncodeError, TypeError, ValueError, OverflowError, Exception
    ) as e:
        # Save the error in the log
        logger.error("Error while sending phone number verification code: %s", str(e),
                     exc_info=True)
        return 500, (uid, verification_code)
    # Save verification code && generation date to user
    user.user_phone_number_verification_code = verification_code
    user.user_phone_number_verification_code_generated_at = now()
    # If whatsapp message sent, we're updating nbr_phone_number_verification_code_used
    # values of users with the receiver_number's number
    user.nbr_phone_number_verification_code_used += 1
    user.save(using=db_alias or None)
    return 200, (uid, verification_code)


def send_password_reset_email(user, handle_send_email_error=False, do_not_mock_api=False):
    """
    Sends a password reset email to the user.

    Args:
        user (User): The user object to send the email to.
        handle_send_email_error (bool): Flag to simulate an intentional error for testing.
        do_not_mock_api (bool): Flag to api even if it is for testing.

    Returns:
        tuple: A tuple containing the status code (int) and token data (tuple).
    """
    # Generate user's token
    token_ = default_token_generator.make_token(user)
    # Get current timestamp as str
    timestamp_str = str(now().timestamp())
    # Generate final token that contains timestamp for expiration validation
    token = token_ + "_*_" + timestamp_str
    # Encode user's id
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    # Build the password reset URL
    # This url is for frontend and it not the backend url: accounts/reset-password
    reset_url = f"{settings.FRONTEND_ENDPOINT}/auth/reset-password?uid={uid}&token={token}"
    # Render the email content
    subject = _("Password Reset Request")
    # Get emails common context
    context = get_email_base_context()
    # Add custom context to password reset email
    context.update({
        "email_title": _("Password Reset Request"), "user": user, "reset_url": reset_url,
    })
    text_content = render_to_string("password_reset.txt", context)  # Plain text fallback
    html_content = render_to_string("password_reset.html", context)  # HTML content
    # Send the email
    try:
        if settings.DEBUG or settings.TEST:
            print("html_content")
            print(html_content)
        # This is for testing send email's error from third party
        if handle_send_email_error:
            _err = int("text")
        if settings.TEST and do_not_mock_api is False:
            return 200, (uid, token)
        email = EmailMultiAlternatives(subject, text_content, context.get('from_email'),
                                       [user.email])
        email.attach_alternative(html_content, "text/html")
        email.send()
    except (  # pylint: disable=broad-exception-caught
        SMTPAuthenticationError, SMTPSenderRefused, SMTPRecipientsRefused, SMTPDataError,
        SMTPException, UnicodeEncodeError, TypeError, ValueError, OverflowError, Exception
    ) as e:
        # Save the error in the log
        logger.error("Error while sending password reset email: %s", str(e), exc_info=True)
        return 500, (uid, token)
    return 200, (uid, token)


def validate_password_reset_token(uid, token, db_alias=''): # pylint: disable=too-many-return-statements
    """
    Validates a password reset token.

    Args:
        uid (str): The base64 encoded user ID.
        token (str): The password reset token.
        db_alias (str): Database alias to use.

    Returns:
        tuple: (is_valid, user, error_message)
    """
    from accounts.repositories import UserRepository
    User = get_user_model()
    try:
        # Decode user id
        user_id = urlsafe_base64_decode(uid).decode()
        user = UserRepository.get_by_id(user_id, db_alias=db_alias)
    except (TypeError, ValueError, OverflowError, UnicodeDecodeError, User.DoesNotExist):
        return False, None, "Invalid user"
    # Check if user is active
    if not user.is_active:
        return False, None, "User account is disabled"
    # Split token to get the actual token and timestamp
    try:
        token_parts = token.split("_*_")
        if len(token_parts) != 2:
            return False, None, "Invalid token format"
        actual_token, timestamp_str = token_parts
        timestamp = float(timestamp_str)
    except (ValueError, IndexError):
        return False, None, "Invalid token format"
    # Check if token is expired (24 hours)
    current_timestamp = now().timestamp()
    token_age_hours = (current_timestamp - timestamp) / 3600
    if token_age_hours > 24:  # 24 hours expiration
        return False, None, _("Token has expired")
    # Verify the token
    if not default_token_generator.check_token(user, actual_token):
        return False, None, "Invalid token"
    return True, user, None

def blacklist_user_tokens(user, db_alias: str = ''):
    """
    Blacklist all existing tokens for the user
    Args:
        user (User): The ouner of tokens to be blacklisted.
        token (str): The password reset token.

    Returns:
        tuple: (is_valid, user, error_message)
    """
    nbr_tokens_blacklisted = 0
    try:
        outstanding_tokens = OutstandingToken.objects.using(db_alias or None).filter(user=user)
        for outstanding_token in outstanding_tokens:
            if not BlacklistedToken.objects.using(db_alias or None).filter(
                token=outstanding_token).exists():
                BlacklistedToken.objects.using(db_alias or None).create(token=outstanding_token)
                nbr_tokens_blacklisted += 1
        logger.info("Blacklisted %d tokens for user %s due to password change",
            nbr_tokens_blacklisted, user.username)
    except Exception as e: # pylint: disable=broad-exception-caught
        logger.error("Error blacklisting tokens during password change for "
            "user %s: %s", user.username, str(e))
    return nbr_tokens_blacklisted
