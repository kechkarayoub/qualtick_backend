# pylint: disable=line-too-long
"""Account-related signals."""
import phonenumbers
from django.conf import settings
from django.db.models.signals import pre_save
from django.dispatch import receiver

from .models import User


@receiver(pre_save, sender=User)
def format_phone_numbers(sender, instance, **kwargs): # pylint: disable=unused-argument
    """Format phone numbers before saving the user instance."""
    if instance.user_phone_number:
        if not instance.is_user_phone_number_validated and settings.ENABLE_PHONE_NUMBER_VERIFICATION:
            instance.user_phone_number = None
        else:
            try:
                parsed_number = phonenumbers.parse(
                    instance.user_phone_number, settings.DEFAULT_PHONE_NUMBER_COUNTRY_CODE)
                instance.user_phone_number = phonenumbers.format_number(
                    parsed_number, phonenumbers.PhoneNumberFormat.E164
                )
            except phonenumbers.NumberParseException:
                instance.user_phone_number = None
    if instance.user_phone_number_to_verify:
        try:
            parsed_number = phonenumbers.parse(
                instance.user_phone_number_to_verify,
                settings.DEFAULT_PHONE_NUMBER_COUNTRY_CODE)
            instance.user_phone_number_to_verify = phonenumbers.format_number(
                parsed_number, phonenumbers.PhoneNumberFormat.E164
            )
        except phonenumbers.NumberParseException:
            instance.user_phone_number_to_verify = None
    if settings.ENABLE_PHONE_NUMBER_VERIFICATION is False:
        if not instance.is_user_phone_number_validated:
            instance.is_user_phone_number_validated = True
        if not instance.user_phone_number_verified_by:
            instance.user_phone_number_verified_by = "default"
        if instance.user_phone_number_to_verify and not instance.user_phone_number:
            instance.user_phone_number = instance.user_phone_number_to_verify
    if settings.ENABLE_EMAIL_VERIFICATION is False:
        if not instance.is_user_email_validated:
            instance.is_user_email_validated = True
