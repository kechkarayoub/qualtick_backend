
"""Accounts serializers"""
from datetime import date

import phonenumbers
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from accounts.models import User


class UserSerializer(serializers.ModelSerializer):
    """Serializer for the User model."""
    class Meta:
        model = User
        fields = [
            "user_address", "user_birthday", "user_cin", "user_country", "current_language",
            "date_joined", "email",
            "first_name", "user_gender", "user_phone_number_verification_code",
            "user_phone_number_verification_code_generated_at",
            "id", "user_image_url", "user_initials_bg_color", "is_active",
            "is_user_email_validated", "is_user_deleted", "is_user_phone_number_validated",
            "last_name", "user_phone_number", "user_phone_number_to_verify",
            "user_phone_number_verified_by",
            "username", "nbr_phone_number_verification_code_used", "user_timezone",
        ]
        read_only_fields = ["id", "date_joined"]
    # noinspection PyMethodMayBeStatic
    def validate_user_phone_number(self, value):
        """Validate phone number starts with +, country code, and contains only digits."""
        if value is None or value == "":
            return value
        try:
            # Parse and format the phone number
            parsed_number = phonenumbers.parse(
                value, settings.DEFAULT_PHONE_NUMBER_COUNTRY_CODE)
            if phonenumbers.is_valid_number(parsed_number):
                return phonenumbers.format_number(
                    parsed_number, phonenumbers.PhoneNumberFormat.E164)
            raise serializers.ValidationError(
                _("Invalid phone number.")
            )
        except phonenumbers.NumberParseException as exc:
            raise serializers.ValidationError(
                _("Phone number must start with a '+' followed by the country code "
                  "and the phone number.")
            ) from exc
    # noinspection PyMethodMayBeStatic
    def validate_user_phone_number_to_verify(self, value):
        """Validate phone number to verify starts with +, country code, and contains 
        only digits."""
        if value is None or value == "":
            return value
        try:
            # Parse and format the phone number
            parsed_number = phonenumbers.parse(
                value, settings.DEFAULT_PHONE_NUMBER_COUNTRY_CODE)
            if phonenumbers.is_valid_number(parsed_number):
                return phonenumbers.format_number(
                    parsed_number, phonenumbers.PhoneNumberFormat.E164)
            raise serializers.ValidationError(
                _("Invalid phone number.")
            )
        except phonenumbers.NumberParseException as exc:
            raise serializers.ValidationError(
                _("Phone number must start with a '+' followed by the country code "
                  "and the phone number.")
            ) from exc
    # noinspection PyMethodMayBeStatic
    def validate_user_birthday(self, value):
        """Validate user_birthday is at least MINIMUM_AGE_ALLOWED_FOR_USERS years 
        before today."""
        if value is None:
            return None
        today = date.today()
        min_date = date(
            today.year - settings.MINIMUM_AGE_ALLOWED_FOR_USERS, today.month, today.day
        )
        if value >= min_date:
            raise serializers.ValidationError(
                _("The minimum age allowed for users is: ") + str(
                    settings.MINIMUM_AGE_ALLOWED_FOR_USERS
                )
            )
        return value
