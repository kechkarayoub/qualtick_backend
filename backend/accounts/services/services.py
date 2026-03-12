"""
Service layer for accounts app.
"""

import datetime
import logging
import os
from smtplib import (SMTPAuthenticationError, SMTPDataError, SMTPException,
                     SMTPRecipientsRefused, SMTPSenderRefused)

import phonenumbers
from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.tokens import default_token_generator
from django.core.files.storage import default_storage
from django.core.mail import EmailMultiAlternatives
from django.db.models.functions import Lower
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.timezone import now
from django.utils.translation import activate
from django.utils.translation import gettext_lazy as _
from firebase_admin import auth as firebase_auth
import firebase_config  # pylint: disable=unused-import
from backend.utils import (generate_random_code, generate_random_string,
                           get_email_base_context, send_phone_message)

from accounts.constants import GENDERS_CHOICES
from accounts.exceptions import (AuthenticationException, EmailSendingException,
                         FirebaseException,
                         PhoneVerificationException,
                         ProfileImageException, SMSException,
                         TokenValidationException, UserDeleteException,
                         UserNotActiveException, UserRegistrationException,
                         UserUpdateException, UserValidationException,
                         VerificationCodeException)
from accounts.models import User
from accounts.utils import format_phone_number
from accounts.repositories import UserRepository

logger = logging.getLogger(__name__)


class UserService:
    """Service for user-related operations."""
    @staticmethod
    def create_user(user_data, db_alias=''):
        """
        Create a new user account.
        
        Args:
            user_data (dict): User data for registration
            db_alias (str): Database alias to use
            
        Returns:
            User: Created user instance
            
        Raises:
            UserRegistrationException: If user creation fails
        """
        try:
            # Validate required fields
            required_fields = ['username', 'email', 'first_name', 'last_name', 'password']
            missing_fields = [
                field for field in required_fields if not user_data.get(field)]
            if missing_fields:
                raise UserValidationException(
                    f"Missing required fields: {', '.join(missing_fields)}")
            
            # Check if user already exists using repository
            if UserRepository.username_exists(user_data['username'], db_alias=db_alias):
                raise UserRegistrationException("Username already exists")
            if UserRepository.email_exists(user_data['email'], db_alias=db_alias):
                raise UserRegistrationException("Email already exists")
            
            # Create user through repository
            user = UserRepository.create_user(
                username=user_data['username'],
                email=user_data['email'],
                password=user_data['password'],
                first_name=user_data['first_name'],
                last_name=user_data['last_name'],
                current_language=user_data.get('current_language', settings.LANGUAGE_CODE),
                user_country=user_data.get('user_country', ''),
                user_gender=user_data.get('user_gender', ''),
                user_birthday=user_data.get('user_birthday'),
                user_address=user_data.get('user_address', ''),
                user_phone_number=user_data.get('user_phone_number', ''),
                user_timezone=user_data.get('user_timezone', 'UTC'),
                db_alias=db_alias,
            )
            logger.info("User created successfully: %s", user.username)
            return user
        except Exception as e:
            logger.error("User creation failed: %s", str(e))
            raise UserRegistrationException(f"User creation failed: {str(e)}") from e
    @staticmethod
    def generate_unique_username(email="", first_name="", last_name="", db_alias=""):  # pylint: disable=too-many-branches
        """
        Generate a unique username based on user information.

        Args:
            email (str): User email address
            first_name (str): User first name
            last_name (str): User last name
            db_alias (str): Database alias to use

        Returns:
            str: Generated unique username

        This method tries to generate a username using combinations of first name,
            last name, and email prefix.
        It checks for uniqueness in the database and appends numbers or random strings
            if needed.
        """
        email = email.strip().lower()
        first_name = first_name.strip().lower()
        last_name = last_name.strip().lower()
        # Build possible username candidates from user info
        possible_usernames_base = []
        if last_name and first_name:
            possible_usernames_base.extend([
                f"{last_name}{first_name}",
                f"{first_name}{last_name}",
                f"{last_name}.{first_name}",
                f"{first_name}.{last_name}",
                f"{last_name[0]}{first_name}",
                f"{first_name[0]}{last_name}",
                f"{last_name[0]}.{first_name}",
                f"{first_name[0]}.{last_name}",
                f"{last_name}",
                f"{first_name}",
            ])
        elif last_name:
            possible_usernames_base.append(f"{last_name}")
        elif first_name:
            possible_usernames_base.append(f"{first_name}")
        if email:
            possible_usernames_base.append(email.split('@')[0])
        # Try base candidates
        candidates = list(possible_usernames_base)
        if candidates:
            exists = set(User.objects.using(db_alias or None).annotate(username_lower=Lower('username')).filter(
                username_lower__in=candidates).values_list('username', flat=True))
            # If all taken, try with '1' and '2' suffixes
            if len(exists) == len(candidates):
                candidates = [pu + "1" for pu in possible_usernames_base]
                exists = set(User.objects.using(db_alias or None).annotate(username_lower=Lower('username'))
                .filter(username_lower__in=candidates).values_list('username', flat=True))
                if len(exists) == len(candidates):
                    candidates = [pu + "2" for pu in possible_usernames_base]
                    exists = set(User.objects.using(db_alias or None).annotate(username_lower=Lower('username'))
                    .filter(username_lower__in=candidates).values_list(
                        'username', flat=True))
            for candidate in candidates:
                if candidate not in exists:
                    return candidate
        # Fallback: username_1 to username_20
        for i in range(1, 21):
            candidate = f"username_{i}"
            if not UserRepository.username_exists(candidate, db_alias=db_alias):
                return candidate
        # Last resort: random string usernames
        for _ in range(20):
            candidate = generate_random_string()
            if not UserRepository.username_exists(candidate, db_alias=db_alias):
                return candidate
        return email
    @staticmethod
    def update_user(user, update_data, db_alias=''):
        """
        Update user profile information.
        Args:
            user (User): User instance to update
            update_data (dict): Data to update
            db_alias (str): Database alias to use
        Returns:
            User: Updated user instance
        Raises:
            UserUpdateException: If update fails
        """
        try:
            # Fields that can be updated
            updatable_fields = [
                'first_name', 'last_name', 'current_language',
                'user_country', 'user_gender', 'user_birthday', 'user_address',
                'user_phone_number', 'user_timezone', 'user_cin', 'user_image_url',
                'user_phone_number_to_verify'
            ]
            # Filter only updatable fields
            filtered_data = {k: v for k, v in update_data.items() if k in updatable_fields}
            
            # Update through repository
            updated_user = UserRepository.update(user.id, db_alias=db_alias, **filtered_data)
            if not updated_user:
                raise UserUpdateException("User not found")
            
            logger.info("User updated successfully: %s", updated_user.username)
            return updated_user
        except Exception as e:
            logger.error("User update failed: %s", str(e))
            raise UserUpdateException(f"User update failed: {str(e)}") from e
    @staticmethod
    def authenticate_user(username, password, db_alias=''):
        """
        Authenticate user credentials.
        
        Args:
            username (str): Username or email
            password (str): User password
            db_alias (str): Database alias to use
            
        Returns:
            User: Authenticated user instance
            
        Raises:
            AuthenticationException: If authentication fails
        """
        try:
            # Try authentication with username first
            user = authenticate(username=username, password=password)
            # If failed, try with email using repository
            if not user:
                user_obj = UserRepository.get_by_email(username, db_alias=db_alias)
                if user_obj:
                    user = authenticate(username=user_obj.username, password=password)
            
            if not user:
                raise AuthenticationException("Invalid credentials")
            if not user.is_active:
                raise UserNotActiveException("User account is inactive")
            
            # Update last login through repository
            UserRepository.update_last_login(user.id, db_alias=db_alias)
            
            logger.info("User authenticated successfully: %s", user.username)
            return user
        except Exception as e:
            logger.warning("Authentication failed for %s: %s", username, str(e))
            raise AuthenticationException(f"Authentication failed: {str(e)}") from e
    @staticmethod
    def delete_user(user, soft_delete=True, db_alias=''):
        """
        Delete or deactivate user account.
        
        Args:
            user (User): User instance to delete
            soft_delete (bool): Whether to soft delete (deactivate) or hard delete
            db_alias (str): Database alias to use
            
        Returns:
            bool: True if successful
            
        Raises:
            UserDeleteException: If deletion fails
        """
        try:
            if soft_delete:
                UserRepository.soft_delete(user.id, db_alias=db_alias)
                logger.info("User soft deleted: %s", user.username)
            else:
                username = user.username
                UserRepository.delete(user.id, db_alias=db_alias)
                logger.info("User hard deleted: %s", username)
            return True
        except Exception as e:
            logger.error("User deletion failed: %s", str(e))
            raise UserDeleteException(f"User deletion failed: {str(e)}") from e
    
    @staticmethod
    def get_user_by_id(user_id, db_alias=''):
        """Get user by ID."""
        return UserRepository.get_by_id(user_id, db_alias=db_alias)
    
    @staticmethod
    def get_user_by_username(username, db_alias=''):
        """Get user by username."""
        return UserRepository.get_by_username(username, db_alias=db_alias)
    
    @staticmethod
    def get_user_by_email(email, db_alias=''):
        """Get user by email."""
        return UserRepository.get_by_email(email, db_alias=db_alias)
    
    @staticmethod
    def get_user_by_phone(phone_number, db_alias=''):
        """Get user by phone number."""
        return UserRepository.get_by_phone_number(phone_number, db_alias=db_alias)
    
    @staticmethod
    def search_users(query, db_alias=''):
        """Search users by username, email, or name."""
        return UserRepository.search_users(query, db_alias=db_alias)
    
    @staticmethod
    def get_active_users(db_alias=''):
        """Get all active users."""
        return UserRepository.get_active_users(db_alias=db_alias)
    
    @staticmethod
    def get_user_statistics(db_alias=''):
        """Get user statistics."""
        return UserRepository.get_statistics(db_alias=db_alias)

    
    @staticmethod
    def send_emails_verifications_links(email=None, db_alias=''):
        """
        This function send emails verification links to unverified users emails
        :param email: Not required, but used if you need to send email to a specific user
        :param db_alias: Database alias to use
        :return: A message describe what happen in the functions
        """
        if settings.ENABLE_EMAIL_VERIFICATION is False:
            return 'ENABLE_EMAIL_VERIFICATION is False!!.'
        kwargs = {'is_active': True, 'is_user_email_validated': False, }
        if email:
            kwargs['email'] = email
        nbr_verifications_emails_links_sent = 0
        nbr_verifications_emails_links_not_sent = 0
        for user in UserRepository.filter(db_alias=db_alias, **kwargs):
            status, _items = EmailVerificationService.send_verification_email(user)
            if status == 200:
                nbr_verifications_emails_links_sent += 1
                print(f'Verification email sent to: {user.email}.')
            else:
                nbr_verifications_emails_links_not_sent += 1
                print("An error has occurred, the verification email isn't sent "
                      f"to: {user.email}!")
        if (email and nbr_verifications_emails_links_sent == 0 and
            nbr_verifications_emails_links_not_sent == 0):
            return f'There is any user with this email: {email}, or it is already verified!'
        if (nbr_verifications_emails_links_sent == 0 and
            nbr_verifications_emails_links_not_sent == 0):
            return 'There is no user with not email verified yet!'
        return f"{nbr_verifications_emails_links_sent} verification email are sent, " \
               f"{nbr_verifications_emails_links_not_sent} are not."


class EmailVerificationService:
    """Service for email verification operations."""
    @staticmethod
    def send_verification_email(user, handle_send_email_error=False, language=None):
        """
        Send email verification link to user.
        
        Args:
            user (User): User instance
            handle_send_email_error (bool): Flag to simulate an intentional error for testing.
            language (str): Language for email template
            
        Returns:
            bool: True if email sent successfully
            
        Raises:
            EmailSendingException: If email sending fails
        """
        try:
            if not language:
                language = user.current_language or settings.LANGUAGE_CODE
            # Activate language for email template
            activate(language)
            # Generate verification token
            token = default_token_generator.make_token(user)
            timestamp = datetime.datetime.now().timestamp()
            token += "_*_" + str(timestamp)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            # Build verification URL
            verification_url = f"{settings.FRONTEND_ENDPOINT}/accounts/verify-email/{uid}/{token}/"
            # Prepare email context
            context = get_email_base_context()
            context.update({
                "email_title": _("Verify Your Email Address"),
                'user': user,
                'verification_url': verification_url,
                'site_name': settings.APPLICATION_NAME,
            })
            # Render email templates
            subject = _('Verify your email address')
            html_content = render_to_string('email_verification.html', context)
            text_content = render_to_string('email_verification.txt', context)
            # Send the email
            try:
                if settings.DEBUG or settings.TEST:
                    print("html_content")
                    print(html_content)
                # This is for testing send email's error from third party
                if handle_send_email_error:
                    _err = int("text")
                email = EmailMultiAlternatives(subject, text_content, context.get('from_email'),
                                            [user.email])
                email.attach_alternative(html_content, "text/html")
                email.send()
                logger.info("Verification email sent to: %s", user.email)
                return 200, (uid, token)
            except (  # pylint: disable=broad-exception-caught
                SMTPAuthenticationError, SMTPSenderRefused, SMTPRecipientsRefused, SMTPDataError,
                SMTPException, UnicodeEncodeError, TypeError, ValueError, OverflowError, Exception
            ) as e:
                # Save the error in the log
                logger.error("Error while sending verification email: %s", str(e), exc_info=True)
                return 500, (uid, token)
        except Exception as e:
            logger.error("Failed to send verification email: %s", str(e))
            return 500, (uid, token)

    @staticmethod
    def verify_email_token(uid, token, db_alias=''):
        """
        Verify email verification token.
        
        Args:
            uid (str): Base64 encoded user ID
            token (str): Verification token
            db_alias (str): Database alias to use
            
        Returns:
            User: Verified user instance
            
        Raises:
            TokenValidationException: If token is invalid
        """
        try:
            # Decode user ID
            user_id = urlsafe_base64_decode(uid).decode()
            user = UserRepository.get_by_id(int(user_id), db_alias=db_alias)
            
            if not user:
                raise TokenValidationException("User not found")
            
            # Verify token
            if not default_token_generator.check_token(user, token):
                raise TokenValidationException("Invalid or expired token")
            
            # Mark email as verified through repository
            user = UserRepository.verify_email(user.id, db_alias=db_alias)
            
            logger.info("Email verified for user: %s", user.username)
            return user
        except Exception as e:
            logger.error("Email verification failed: %s", str(e))
            raise TokenValidationException(f"Email verification failed: {str(e)}") from e


class PhoneVerificationService:
    """Service for phone number verification operations."""
    @staticmethod
    def send_verification_code(user, db_alias=''):
        """
        Send phone verification code to user.
        
        Args:
            user (User): User instance
            db_alias (str): Database alias to use
            
        Returns:
            str: Verification code sent
            
        Raises:
            SMSException: If SMS sending fails
        """
        try:
            if not user.user_phone_number:
                raise PhoneVerificationException("No phone number provided")
            # Check quota
            if user.nbr_phone_number_verification_code_used >= settings.PHONE_NUMBER_VERIFICATION_CODE_QUOTA:  # pylint: disable=line-too-long
                raise PhoneVerificationException("Verification code quota exceeded")
            # Generate code
            verification_code = generate_random_code()
            
            # Store code and timestamp through repository
            UserRepository.update(
                user.id,
                user_phone_number_verification_code=verification_code,
                user_phone_number_verification_code_generated_at=now(),
                nbr_phone_number_verification_code_used=user.nbr_phone_number_verification_code_used + 1,
                db_alias=db_alias
            )
            
            # Send SMS
            formatted_phone = format_phone_number(user.user_phone_number)
            message = f"Your verification code is: {verification_code}"
            success = send_phone_message(message, [formatted_phone])
            if not success:
                raise SMSException("Failed to send SMS")
            logger.info("Verification code sent to: %s", formatted_phone)
            return verification_code
        except Exception as e:
            logger.error("Failed to send verification code: %s", str(e))
            raise SMSException(f"Failed to send verification code: {str(e)}") from e
    @staticmethod
    def verify_phone_code(user, code, db_alias=''):
        """
        Verify phone verification code.
        
        Args:
            user (User): User instance
            code (str): Verification code
            db_alias (str): Database alias to use
            
        Returns:
            bool: True if verification successful
            
        Raises:
            VerificationCodeException: If code verification fails
        """
        try:
            # Check if code exists
            if not user.user_phone_number_verification_code:
                raise VerificationCodeException("No verification code found")
            # Check if code matches
            if user.user_phone_number_verification_code != code:
                raise VerificationCodeException("Invalid verification code")
            # Check if code is expired
            if user.user_phone_number_verification_code_generated_at:
                expiry_time = user.user_phone_number_verification_code_generated_at + datetime.timedelta(minutes=settings.NUMBER_MINUTES_BEFORE_PHONE_NUMBER_VERIFICATION_CODE_EXPIRATION)  # pylint: disable=line-too-long
                if now() > expiry_time:
                    raise VerificationCodeException("Verification code expired")
            
            # Mark phone as verified through repository
            UserRepository.verify_phone_number(user.id, verified_by='sms', db_alias=db_alias)
            
            logger.info("Phone verified for user: %s", user.username)
            return True
        except Exception as e:
            logger.error("Phone verification failed: %s", str(e))
            raise VerificationCodeException(f"Phone verification failed: {str(e)}") from e


class ProfileImageService:
    """Service for profile image operations."""
    @staticmethod
    def upload_profile_image(user, image_file, db_alias=''):
        """
        Upload and set user profile image.
        
        Args:
            user (User): User instance
            image_file: Image file to upload
            db_alias (str): Database alias to use
            
        Returns:
            str: URL of uploaded image
            
        Raises:
            ProfileImageException: If upload fails
        """
        try:
            # Validate file type
            allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif']
            if hasattr(image_file, 'content_type') and image_file.content_type not in allowed_types:
                raise ProfileImageException("Invalid image format")
            # Validate file size (max 5MB)
            max_size = 5 * 1024 * 1024  # 5MB
            if hasattr(image_file, 'size') and image_file.size > max_size:
                raise ProfileImageException("Image file too large (max 5MB)")
            # Generate filename
            file_extension = os.path.splitext(image_file.name)[1]
            filename = f"profile_images/{user.username}_{now().timestamp()}{file_extension}"
            # Delete old image if exists
            if user.user_image_url and default_storage.exists(user.user_image_url):
                default_storage.delete(user.user_image_url)
            # Save new image
            saved_path = default_storage.save(filename, image_file)
            image_url = default_storage.url(saved_path)
            # Update user
            user.user_image_url = image_url
            user.save(using=db_alias or None)
            logger.info("Profile image uploaded for user: %s", user.username)
            return image_url
        except Exception as e:
            logger.error("Profile image upload failed: %s", str(e))
            raise ProfileImageException(f"Profile image upload failed: {str(e)}") from e

    @staticmethod
    def delete_profile_image(user, db_alias=''):
        """
        Delete user profile image.
        
        Args:
            user (User): User instance
            db_alias (str): Database alias to use
            
        Returns:
            bool: True if successful
            
        Raises:
            ProfileImageException: If deletion fails
        """
        try:
            if user.user_image_url:
                # Delete from storage
                if default_storage.exists(user.user_image_url):
                    default_storage.delete(user.user_image_url)
                # Clear URL from user
                user.user_image_url = None
                user.save(using=db_alias or None)
                logger.info("Profile image deleted for user: %s", user.username)
            return True
        except Exception as e:
            logger.error("Profile image deletion failed: %s", str(e))
            raise ProfileImageException(f"Profile image deletion failed: {str(e)}") from e


class FirebaseService:
    """Service for Firebase operations."""
    @staticmethod
    def create_firebase_user(user, password):
        """
        Create Firebase user account.
        
        Args:
            user (User): Django user instance
            password (str): User password
            
        Returns:
            dict: Firebase user record
            
        Raises:
            FirebaseException: If Firebase operation fails
        """
        try:
            firebase_user = firebase_auth.create_user(
                uid=str(user.id),
                email=user.email,
                password=password,
                display_name=f"{user.first_name} {user.last_name}",
                email_verified=user.is_user_email_validated
            )
            logger.info("Firebase user created: %s", user.username)
            return firebase_user
        except Exception as e:
            logger.error("Firebase user creation failed: %s", str(e))
            raise FirebaseException(f"Firebase user creation failed: {str(e)}") from e
    @staticmethod
    def delete_firebase_user(user_id):
        """
        Delete Firebase user account.
        
        Args:
            user_id (str): Firebase user ID
            
        Returns:
            bool: True if successful
            
        Raises:
            FirebaseException: If Firebase operation fails
        """
        try:
            firebase_auth.delete_user(user_id)
            logger.info("Firebase user deleted: %s", str(user_id))
            return True
        except Exception as e:
            logger.error("Firebase user deletion failed: %s", str(e))
            raise FirebaseException(f"Firebase user deletion failed: {str(e)}") from e


class UserValidationService:
    """Service for user data validation."""
    @staticmethod
    def validate_phone_number(phone_number, country_code=None):
        """
        Validate phone number format.
        
        Args:
            phone_number (str): Phone number to validate
            country_code (str): Country code for validation
            
        Returns:
            bool: True if valid
            
        Raises:
            PhoneVerificationException: If validation fails
        """
        try:
            if not country_code:
                country_code = settings.DEFAULT_PHONE_NUMBER_COUNTRY_CODE
            parsed_number = phonenumbers.parse(phone_number, country_code)
            if not phonenumbers.is_valid_number(parsed_number):
                raise PhoneVerificationException("Invalid phone number format")
            return True
        except Exception as e:
            logger.warning("Phone number validation failed: %s", str(e))
            raise PhoneVerificationException(
                f"Phone number validation failed: {str(e)}") from e
    @staticmethod
    def validate_user_data(user_data):
        """
        Validate user registration/update data.
        
        Args:
            user_data (dict): User data to validate
            
        Returns:
            bool: True if valid
            
        Raises:
            UserValidationException: If validation fails
        """
        try:
            errors = []
            # Validate email format
            if 'email' in user_data:
                email = user_data['email']
                if not email or '@' not in email:
                    errors.append("Invalid email format")
            # Validate password strength
            if 'password' in user_data:
                password = user_data['password']
                if len(password) < 8:
                    errors.append("Password must be at least 8 characters long")
            # Validate gender choice
            if 'user_gender' in user_data:
                gender = user_data['user_gender']
                valid_genders = [choice[0] for choice in GENDERS_CHOICES]
                if gender and gender not in valid_genders:
                    errors.append("Invalid gender choice")
            # Validate phone number if provided
            if 'user_phone_number' in user_data and user_data['user_phone_number']:
                UserValidationService.validate_phone_number(user_data['user_phone_number'])
            if errors:
                raise UserValidationException("; ".join(errors))
            return True
        except Exception as e:
            logger.warning("User data validation failed: %s", str(e))
            raise UserValidationException(str(e)) from e
