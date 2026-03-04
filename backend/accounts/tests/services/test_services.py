"""
    Test services
"""
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils.encoding import force_bytes
from django.utils import timezone
from django.utils.http import urlsafe_base64_encode

from accounts.exceptions import (AuthenticationException, ProfileImageException,
                                 SMSException, TokenValidationException,
                                 UserRegistrationException,
                                 UserValidationException,
                                 VerificationCodeException)
from accounts.models import User
from accounts.services import (EmailVerificationService, EmailSendingException,
                               PhoneVerificationService, ProfileImageService,
                                 UserService, UserValidationService)
from accounts.repositories.user_repository import UserRepository
from backend.utils import get_db_alias


class UserServiceTest(TestCase):
    """Test cases for UserService."""
    def setUp(self):
        self.user_service = UserService
        self.user_data = {
            'username': 'servicetest',
            'email': 'servicetest@example.com',
            'password': 'testpassword123',
            'first_name': 'Service',
            'last_name': 'Test',
            'current_language': 'en',
            'user_country': 'US',
            'user_gender': 'male'
        }
    def test_create_user_service_success(self):
        """Test successful user creation through service."""
        db_alias = get_db_alias()
        user = self.user_service.create_user(self.user_data, db_alias=db_alias)
        self.assertEqual(user.username, 'servicetest')
        self.assertEqual(user.email, 'servicetest@example.com')
        self.assertEqual(user.first_name, 'Service')
        self.assertEqual(user.last_name, 'Test')
        self.assertTrue(user.check_password('testpassword123'))
        # Email validation status depends on ENABLE_EMAIL_VERIFICATION setting
        if hasattr(settings,
                   'ENABLE_EMAIL_VERIFICATION') and settings.ENABLE_EMAIL_VERIFICATION:
            self.assertFalse(user.is_user_email_validated)
        else:
            self.assertTrue(user.is_user_email_validated)
        # Phone validation status depends on ENABLE_PHONE_NUMBER_VERIFICATION setting
        if hasattr(
            settings, 'ENABLE_PHONE_NUMBER_VERIFICATION'
            ) and settings.ENABLE_PHONE_NUMBER_VERIFICATION:
            self.assertFalse(user.is_user_phone_number_validated)
        else:
            self.assertTrue(user.is_user_phone_number_validated)
    def test_create_user_service_missing_fields(self):
        """Test user creation with missing required fields."""
        db_alias = get_db_alias()
        incomplete_data = {'username': 'servicetest'}
        with self.assertRaises(UserRegistrationException):
            self.user_service.create_user(incomplete_data, db_alias=db_alias)
    def test_create_user_service_duplicate_username(self):
        """Test user creation with existing username."""
        db_alias = get_db_alias()
        self.user_service.create_user(self.user_data, db_alias=db_alias)
        with self.assertRaises(UserRegistrationException):
            self.user_service.create_user(self.user_data, db_alias=db_alias)
    def test_update_user_service_success(self):
        """Test successful user update through service."""
        db_alias = get_db_alias()
        user = self.user_service.create_user(self.user_data, db_alias=db_alias)
        update_data = {
            'first_name': 'UpdatedService',
            'user_country': 'CA'
        }
        updated_user = self.user_service.update_user(user, update_data, db_alias=db_alias)
        self.assertEqual(updated_user.first_name, 'UpdatedService')
        self.assertEqual(updated_user.user_country, 'CA')
    def test_authenticate_user_service_success(self):
        """Test successful user authentication through service."""
        db_alias = get_db_alias()
        user = self.user_service.create_user(self.user_data, db_alias=db_alias)
        authenticated_user = self.user_service.authenticate_user(
            'servicetest', 'testpassword123', db_alias=db_alias)
        self.assertEqual(authenticated_user.id, user.id)
    def test_authenticate_user_service_with_email(self):
        """Test user authentication with email through service."""
        db_alias = get_db_alias()
        user = self.user_service.create_user(self.user_data, db_alias=db_alias)
        authenticated_user = self.user_service.authenticate_user(
            'servicetest@example.com', 'testpassword123', db_alias=db_alias)
        self.assertEqual(authenticated_user.id, user.id)
    def test_authenticate_user_service_invalid_credentials(self):
        """Test authentication with invalid credentials through service."""
        db_alias = get_db_alias()
        self.user_service.create_user(self.user_data, db_alias=db_alias)
        with self.assertRaises(AuthenticationException):
            self.user_service.authenticate_user('servicetest', 'wrongpassword',
                                                db_alias=db_alias)
    def test_delete_user_service_soft_delete(self):
        """Test soft user deletion through service."""
        db_alias = get_db_alias()
        user = self.user_service.create_user(self.user_data, db_alias=db_alias)
        result = self.user_service.delete_user(user, soft_delete=True, db_alias=db_alias)
        self.assertTrue(result)
        user.refresh_from_db(using=db_alias)
        self.assertFalse(user.is_active)
        self.assertTrue(user.is_user_deleted)
    def test_generate_unique_username_basic(self):
        """Test basic username generation."""
        db_alias = get_db_alias()
        UserRepository.create_user(username="SmithJohn", email="sj@example.com",
                                password="pw", first_name="John", last_name="Smith",
                                db_alias=db_alias)
        username = UserService.generate_unique_username(email="sj@example.com",
                                first_name="John", last_name="Smith", db_alias=db_alias)
        self.assertNotEqual(username, "SmithJohn")
        self.assertTrue(isinstance(username, str))
        self.assertFalse(UserRepository.filter(username=username, db_alias=db_alias).exists())
    def test_generate_unique_username_email_only(self):
        """Test username generation with email only."""
        db_alias = get_db_alias()
        username = UserService.generate_unique_username(email="uniqueuser@example.com",
                                                        db_alias=db_alias)
        self.assertEqual(username, "uniqueuser")
    def test_generate_unique_username_fallback(self):
        """Test username generation fallback."""
        db_alias = get_db_alias()
        taken = [f"username_{i}" for i in range(1, 21)]
        for uname in taken:
            UserRepository.create_user(username=uname, email=f"{uname}@example.com",
                                       password="pw", db_alias=db_alias)
        UserRepository.create_user(username="fallback", email="xxx@example.com",
                                   password="pw", db_alias=db_alias)
        username = UserService.generate_unique_username(email="fallback@example.com",
                                                        db_alias=db_alias)
        self.assertTrue(username)
        self.assertNotIn(username, taken)


class EmailVerificationServiceTest(TestCase):
    """Test cases for EmailVerificationService."""
    def setUp(self):
        db_alias = get_db_alias()
        self.email_service = EmailVerificationService
        self.user = UserRepository.create_user(
            username='emailtest',
            email='emailtest@example.com',
            password='testpassword123',
            first_name='Email',
            last_name='Test',
            db_alias=db_alias,
        )
    @patch('accounts.services.EmailMultiAlternatives.send')
    def test_send_verification_email_service_success(self, mock_send):
        """Test successful email verification sending through service."""
        mock_send.return_value = True
        code_status, _ = self.email_service.send_verification_email(self.user)
        self.assertTrue(code_status == 200)
        mock_send.assert_called_once()
    @patch('accounts.services.EmailMultiAlternatives.send')
    def test_send_verification_email_service_failure(self, mock_send):
        """Test email verification sending failure through service."""
        mock_send.side_effect = Exception("SMTP Error")
        with self.assertRaises(EmailSendingException):
            self.email_service.send_verification_email(self.user)
    def test_verify_email_token_service_success(self):
        """Test successful email token verification through service."""
        db_alias = get_db_alias()
        token = default_token_generator.make_token(self.user)
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        verified_user = self.email_service.verify_email_token(uid, token, db_alias=db_alias)
        self.assertEqual(verified_user.id, self.user.id)
        self.assertTrue(verified_user.is_user_email_validated)
    def test_verify_email_token_service_invalid(self):
        """Test email token verification with invalid token through service."""
        db_alias = get_db_alias()
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        invalid_token = "invalid-token"
        with self.assertRaises(TokenValidationException):
            self.email_service.verify_email_token(uid, invalid_token, db_alias=db_alias)

class PhoneVerificationServiceTest(TestCase):
    """Test cases for PhoneVerificationService."""
    def setUp(self):
        db_alias = get_db_alias()
        self.phone_service = PhoneVerificationService
        self.user = UserRepository.create_user(
            username='phonetest',
            email='phonetest@example.com',
            password='testpassword123',
            first_name='Phone',
            last_name='Test',
            user_phone_number='+1234567890',
            db_alias=db_alias,
        )
    @patch('accounts.services.send_phone_message')
    def test_send_verification_code_service_success(self, mock_send_sms):
        """Test successful verification code sending through service."""
        db_alias = get_db_alias()
        mock_send_sms.return_value = True
        code = self.phone_service.send_verification_code(self.userl, db_alias=db_alias)
        self.assertIsInstance(code, str)
        self.assertEqual(len(code), 6)  # Assuming 6-digit codes
        mock_send_sms.assert_called_once()
    def test_send_verification_code_service_no_phone(self):
        """Test verification code sending without phone number through service."""
        db_alias = get_db_alias()
        self.user.user_phone_number = ''
        self.user.save(using=db_alias or None)
        with self.assertRaises(SMSException):
            self.phone_service.send_verification_code(self.user, db_alias=db_alias)
    def test_verify_phone_code_service_success(self):
        """Test successful phone code verification through service."""
        db_alias = get_db_alias()
        # Set up verification code
        self.user.user_phone_number_verification_code = '123456'
        self.user.user_phone_number_verification_code_timestamp = timezone.now()
        self.user.save(using=db_alias or None)
        result = self.phone_service.verify_phone_code(self.user, '123456', db_alias=db_alias)
        self.assertTrue(result)
        self.user.refresh_from_db(using=db_alias or None)
        self.assertTrue(self.user.is_user_phone_number_validated)
    def test_verify_phone_code_service_invalid(self):
        """Test phone code verification with invalid code through service."""
        db_alias = get_db_alias()
        self.user.user_phone_number_verification_code = '123456'
        self.user.save(using=db_alias or None)
        with self.assertRaises(VerificationCodeException):
            self.phone_service.verify_phone_code(self.user, '654321', db_alias=db_alias)


class ProfileImageServiceTest(TestCase):
    """Test cases for ProfileImageService."""
    def setUp(self):
        db_alias = get_db_alias()
        self.image_service = ProfileImageService
        self.user = UserRepository.create_user(
            username='imagetest',
            email='imagetest@example.com',
            password='testpassword123',
            db_alias=db_alias,
        )
    def test_upload_profile_image_service_success(self):
        """Test successful profile image upload through service."""
        db_alias = get_db_alias()
        # Create a test image file
        image_content = b"fake image content"
        image_file = SimpleUploadedFile(
            "test.jpg", image_content, content_type="image/jpeg"
        )
        with patch('accounts.services.default_storage.save') as mock_save, \
             patch('accounts.services.default_storage.url') as mock_url:
            mock_save.return_value = 'profile_images/test.jpg'
            mock_url.return_value = '/media/profile_images/test.jpg'
            image_url = self.image_service.upload_profile_image(self.user, image_file,
                                                                 db_alias=db_alias)
            self.assertEqual(image_url, '/media/profile_images/test.jpg')
            mock_save.assert_called_once()
    def test_upload_profile_image_service_invalid_type(self):
        """Test profile image upload with invalid file type through service."""
        db_alias = get_db_alias()
        text_file = SimpleUploadedFile(
            "test.txt", b"text content", content_type="text/plain"
        )
        with self.assertRaises(ProfileImageException):
            self.image_service.upload_profile_image(self.user, text_file, db_alias=db_alias)
    def test_delete_profile_image_service_success(self):
        """Test successful profile image deletion through service."""
        db_alias = get_db_alias()
        self.user.user_image_url = '/media/profile_images/test.jpg'
        self.user.save(using=db_alias or None)
        with patch('accounts.services.default_storage.exists') as mock_exists, \
             patch('accounts.services.default_storage.delete') as mock_delete:
            mock_exists.return_value = True
            result = self.image_service.delete_profile_image(self.user, db_alias=db_alias)
            self.assertTrue(result)
            self.user.refresh_from_db(using=db_alias or None)
            self.assertIsNone(self.user.user_image_url)
            mock_delete.assert_called_once()


class UserValidationServiceTest(TestCase):
    """Test cases for UserValidationService."""
    def setUp(self):
        self.validation_service = UserValidationService
    def test_validate_user_data_service_success(self):
        """Test successful user data validation through service."""
        valid_data = {
            'email': 'validation@example.com',
            'password': 'testpassword123',
            'user_gender': 'male'
        }
        result = self.validation_service.validate_user_data(valid_data)
        self.assertTrue(result)
    def test_validate_user_data_service_invalid_email(self):
        """Test user data validation with invalid email through service."""
        invalid_data = {
            'email': 'invalid-email',
            'password': 'testpassword123'
        }
        with self.assertRaises(UserValidationException):
            self.validation_service.validate_user_data(invalid_data)
    def test_validate_user_data_service_short_password(self):
        """Test user data validation with short password through service."""
        invalid_data = {
            'email': 'validation@example.com',
            'password': '123'
        }
        with self.assertRaises(UserValidationException):
            self.validation_service.validate_user_data(invalid_data)
    def test_validate_user_data_service_invalid_gender(self):
        """Test user data validation with invalid gender through service."""
        invalid_data = {
            'email': 'validation@example.com',
            'password': 'testpassword123',
            'user_gender': 'invalid'
        }
        with self.assertRaises(UserValidationException):
            self.validation_service.validate_user_data(invalid_data)


class AccountsServiceIntegrationTest(TestCase):
    """Integration tests for accounts services."""
    def setUp(self):
        self.user_service = UserService
        self.email_service = EmailVerificationService
        self.phone_service = PhoneVerificationService
        self.user_data = {
            'username': 'integrationtest',
            'email': 'integration@example.com',
            'password': 'testpassword123',
            'first_name': 'Integration',
            'last_name': 'Test',
            'user_phone_number': '+1234567890'
        }
    def test_complete_user_service_lifecycle(self):
        """Test complete user lifecycle through services: create, verify email, 
        verify phone, update, delete."""
        # 1. Create user through service
        db_alias = get_db_alias()
        user = self.user_service.create_user(self.user_data, db_alias=db_alias)
        # Email and phone validation status depends on settings
        if hasattr(settings,
                   'ENABLE_EMAIL_VERIFICATION') and settings.ENABLE_EMAIL_VERIFICATION:
            self.assertFalse(user.is_user_email_validated)
        else:
            self.assertTrue(user.is_user_email_validated)
        if hasattr(
            settings, 'ENABLE_PHONE_NUMBER_VERIFICATION'
        ) and settings.ENABLE_PHONE_NUMBER_VERIFICATION:
            self.assertFalse(user.is_user_phone_number_validated)
        else:
            self.assertTrue(user.is_user_phone_number_validated)
        # 2. Simulate email verification
        user.is_user_email_validated = True
        user.save(using=db_alias or None)
        # 3. Simulate phone verification
        user.is_user_phone_number_validated = True
        user.save(using=db_alias or None)
        # 4. Update user through service
        update_data = {'first_name': 'UpdatedIntegration'}
        updated_user = self.user_service.update_user(user, update_data, db_alias=db_alias)
        self.assertEqual(updated_user.first_name, 'UpdatedIntegration')
        # 5. Authenticate user through service
        authenticated_user = self.user_service.authenticate_user(
            'integrationtest', 'testpassword123', db_alias=db_alias
        )
        self.assertEqual(authenticated_user.id, user.id)
        # 6. Soft delete user through service
        result = self.user_service.delete_user(user, soft_delete=True, db_alias=db_alias)
        self.assertTrue(result)
        user.refresh_from_db(using=db_alias or None)
        self.assertFalse(user.is_active)
    @patch('accounts.services.send_phone_message')
    def test_phone_verification_service_flow(self, mock_send_sms):
        """Test complete phone verification flow through services."""
        db_alias = get_db_alias()
        mock_send_sms.return_value = True
        user = self.user_service.create_user(self.user_data, db_alias=db_alias)
        # Send verification code through service
        code = self.phone_service.send_verification_code(user, db_alias=db_alias)
        self.assertIsNotNone(code)
        # Verify the code through service
        result = self.phone_service.verify_phone_code(user, code, db_alias=db_alias)
        self.assertTrue(result)
        user.refresh_from_db(using=db_alias or None)
        self.assertTrue(user.is_user_phone_number_validated)
