"""Test email verification views"""
import datetime
import json

from django.conf import settings
from django.test import TestCase
from django.utils.translation import gettext_lazy as _

from accounts.models import User
from accounts.repositories.user_repository import UserRepository
from accounts.services import EmailVerificationService
from accounts.views import verify_user_email
from backend.utils import get_db_alias


class SendVerificationEmailLinkViewTest(TestCase):
    """Test sending verification email link"""
    def setUp(self):
        db_alias = get_db_alias()
        self.user = UserRepository.create_user(
            username='testuser',
            email='kechkarayoub@gmail.com',
            password='password123',
            db_alias=db_alias
        )
        self.user2 = UserRepository.create_user(
            username='testuser2',
            email='kechkarayoub2@gmail.com',
            password='password123',
            db_alias=db_alias
        )

    def test_missing_params(self):
        """Test missing params"""
        response = self.client.post(
            '/accounts/send-verification-email-link/',
            {'selected_language': 'en'}
        )
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content.decode('utf-8'))
        message = data.get("message")
        self.assertEqual(message, "User id is required")
        self.assertFalse(data.get("success"))

    def test_send_verification_email_link_failed_invalid_credentials(self):
        """Test sending verification email link failed due to invalid credentials"""
        response = self.client.post(
            '/accounts/send-verification-email-link/',
            {'selected_language': 'en', 'user_id': 100}
        )
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(data.get("message"), None)
        self.assertFalse(data.get("success"))

    def test_send_verification_email_link_failed_activated_email(self):
        """Test sending verification email link failed due to already activated email"""
        db_alias = get_db_alias()
        self.user.is_user_email_validated = True
        self.user.save(using=db_alias or None)
        response = self.client.post(
            '/accounts/send-verification-email-link/',
            {'selected_language': 'en', 'user_id': self.user.id}
        )
        self.assertEqual(response.status_code, 401)
        data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(
            data.get("message"),
            "Your email is already verified. Try to sign in."
        )
        self.assertTrue(data.get("already_verified"))
        self.assertFalse(data.get("success"))

    def test_send_verification_email_link_success(self):
        """Test sending verification email link success"""
        db_alias = get_db_alias()
        if settings.ENABLE_EMAIL_VERIFICATION is False:
            self.assertEqual(2, 1 + 1)
            return
        self.user2.is_user_email_validated = False
        self.user2.save(using=db_alias or None)
        response = self.client.post(
            '/accounts/send-verification-email-link/',
            {'selected_language': 'en', 'user_id': self.user2.id}
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content.decode('utf-8'))
        expected_message = (
            "A new verification link has been sent to your email address. "
            "Please verify your email before logging in."
        )
        self.assertEqual(data.get("message"), expected_message)
        self.assertTrue(data.get("success"))


class EmailVerificationTests(TestCase):
    """Test email verification"""
    def setUp(self):
        db_alias = get_db_alias()
        self.user = UserRepository.create_user(
            username='testuser', email='kechkarayoub@gmail.com', password='password123',
            db_alias=db_alias)
        self.user_ar = UserRepository.create_user(
            username='testuser_ar', email='test_ar@example.com',
            password='password123', current_language='ar', db_alias=db_alias)
        self.user_en = UserRepository.create_user(
            username='testuser_en', email='test_en@example.com',
            password='password123', current_language='en', db_alias=db_alias)

    def test_send_verification_email(self):
        """Test sending verification email"""
        if settings.ENABLE_EMAIL_VERIFICATION is False:
            self.assertEqual(2, 1 + 1)
            return
        self.assertFalse(self.user.is_user_email_validated)
        status_code, _ = EmailVerificationService.send_verification_email(self.user)
        self.assertEqual(status_code, 200)
        status_code, _ = EmailVerificationService.send_verification_email(
            self.user, handle_send_email_error=True)
        self.assertEqual(status_code, 500)

    def test_verify_user_email_valid(self):
        """Test verifying user email with valid token"""
        db_alias = get_db_alias()
        if settings.ENABLE_EMAIL_VERIFICATION is False:
            self.assertEqual(2, 1 + 1)
            return
        _, (uid, token) = EmailVerificationService.send_verification_email(self.user)
        verified, already_verified, expired_token, new_verification_email_sent = verify_user_email(uid, token, db_alias=db_alias)
        self.assertTrue(verified)
        self.assertFalse(already_verified)
        self.assertFalse(expired_token)
        self.assertFalse(new_verification_email_sent)
        self.user = UserRepository.get_by_id(self.user.id, db_alias=db_alias)
        self.assertTrue(self.user.is_user_email_validated)
        verified, already_verified, expired_token, new_verification_email_sent = verify_user_email(uid, token, db_alias=db_alias)
        self.assertTrue(verified)
        self.assertTrue(already_verified)
        self.assertFalse(expired_token)
        self.assertFalse(new_verification_email_sent)

    def test_verify_user_email_invalid(self):
        """Test verifying user email with invalid token."""
        db_alias = get_db_alias()
        if settings.ENABLE_EMAIL_VERIFICATION is False:
            self.assertEqual(2, 1 + 1)
            return
        _, (uid, _token) = EmailVerificationService.send_verification_email(self.user)
        verified, already_verified, expired_token, new_verification_email_sent = verify_user_email(uid, 'invalid-token', db_alias=db_alias)
        self.assertFalse(verified)
        self.assertFalse(already_verified)
        self.assertFalse(expired_token)
        self.assertFalse(new_verification_email_sent)

    def test_verify_user_email_expired(self):
        """Test verifying user email with expired token."""
        db_alias = get_db_alias()
        if settings.ENABLE_EMAIL_VERIFICATION is False:
            self.assertEqual(2, 1 + 1)
            return
        _, (uid, token) = EmailVerificationService.send_verification_email(self.user)
        now = datetime.datetime.now()
        token_date = token.split("_*_")
        yesterday_timestamp = (now - datetime.timedelta(days=1)).timestamp()
        token_date[1] = str(yesterday_timestamp)
        token = "_*_".join(token_date)
        verified, already_verified, expired_token, new_verification_email_sent = verify_user_email(uid, token, db_alias=db_alias)
        self.assertFalse(verified)
        self.assertFalse(already_verified)
        self.assertTrue(expired_token)
        self.assertFalse(new_verification_email_sent)

    def test_verify_user_email_resend_verification(self):
        """Test verifying user email with resend_verification_email=True."""
        db_alias = get_db_alias()
        if settings.ENABLE_EMAIL_VERIFICATION is False:
            self.assertEqual(2, 1 + 1)
            return
        _, (uid, token) = EmailVerificationService.send_verification_email(self.user)
        # Test that resend_verification_email=True sends new email and returns new_verification_email_sent=True
        verified, already_verified, expired_token, new_verification_email_sent = verify_user_email(uid, token, resend_verification_email=True, db_alias=db_alias)
        self.assertFalse(verified)
        self.assertFalse(already_verified)
        self.assertFalse(expired_token)
        self.assertTrue(new_verification_email_sent)
        # Email should still not be verified after resend
        self.user = UserRepository.get_by_id(self.user.id, db_alias=db_alias)
        self.assertFalse(self.user.is_user_email_validated)

    def test_verify_email_view(self):
        """Test the email verification view."""
        db_alias = get_db_alias()
        if settings.ENABLE_EMAIL_VERIFICATION is False:
            self.assertEqual(2, 1 + 1)
            return
        _, (uid, token) = EmailVerificationService.send_verification_email(self.user)
        response = self.client.get('/accounts/verify-email/',
                                   {'uid': uid, 'token': token})
        self.assertEqual(response.status_code, 200)
        self.user = UserRepository.get_by_id(self.user.id, db_alias=db_alias)
        self.assertTrue(self.user.is_user_email_validated)
        data = json.loads(response.content.decode('utf-8'))
        message = data.get("message")
        self.assertEqual(message, "Email verified successfully.")
        response = self.client.get('/accounts/verify-email/',
                                   {'uid': uid, 'token': token})
        self.assertEqual(response.status_code, 200)
        self.user = UserRepository.get_by_id(self.user.id, db_alias=db_alias)
        self.assertTrue(self.user.is_user_email_validated)
        data = json.loads(response.content.decode('utf-8'))
        message = data.get("message")
        self.assertEqual(message, "Email already verified.")
        self.assertTrue(data.get("already_verified"))
        UserRepository.filter(pk=self.user.id, db_alias=db_alias).update(
            is_user_email_validated=False)
        response = self.client.get('/accounts/verify-email/',
            {'uid': uid, 'token': token, 'resend_verification_email': "true"})
        self.assertEqual(response.status_code, 400)
        self.user = UserRepository.get_by_id(self.user.id, db_alias=db_alias)
        self.assertFalse(self.user.is_user_email_validated)
        data = json.loads(response.content.decode('utf-8'))
        message = data.get("message")
        self.assertEqual(message, "A new verification email has been sent.")
        self.assertTrue(data.get("new_verification_email_sent"))

    def test_verify_email_view_en(self):
        """Test the email verification view for English."""
        db_alias = get_db_alias()
        if settings.ENABLE_EMAIL_VERIFICATION is False:
            self.assertEqual(2, 1 + 1)
            return
        _, (uid, token) = EmailVerificationService.send_verification_email(self.user_en)
        response = self.client.get('/accounts/verify-email/',
                                   {'uid': uid, 'token': token})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content.decode('utf-8'))
        message = data.get("message")
        self.assertEqual(message, "Email verified successfully.")
        response = self.client.get('/accounts/verify-email/',
                                   {'uid': uid, 'token': token})
        data = json.loads(response.content.decode('utf-8'))
        message = data.get("message")
        self.assertEqual(message, "Email already verified.")
        UserRepository.filter(pk=self.user_en.id, db_alias=db_alias).update(
            is_user_email_validated=False)
        response = self.client.get('/accounts/verify-email/',
            {'uid': uid, 'token': token, 'resend_verification_email': "true"})
        data = json.loads(response.content.decode('utf-8'))
        message = data.get("message")
        self.assertEqual(message, "A new verification email has been sent.")
        self.assertTrue(data.get("new_verification_email_sent"))

    def test_verify_email_view_ar(self):
        """Test the email verification view for Arabic."""
        db_alias = get_db_alias()
        if settings.ENABLE_EMAIL_VERIFICATION is False:
            self.assertEqual(2, 1 + 1)
            return
        _, (uid, token) = EmailVerificationService.send_verification_email(self.user_ar)
        response = self.client.get('/accounts/verify-email/',
                                   {'uid': uid, 'token': token})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content.decode('utf-8'))
        message = data.get("message")
        self.assertEqual(message, "تم التحقق من البريد الإلكتروني بنجاح.")
        response = self.client.get('/accounts/verify-email/',
                                   {'uid': uid, 'token': token})
        data = json.loads(response.content.decode('utf-8'))
        message = data.get("message")
        self.assertEqual(message, "البريد الإلكتروني مُتحقق منه بالفعل.")
        UserRepository.filter(pk=self.user_ar.id, db_alias=db_alias).update(
            is_user_email_validated=False)
        response = self.client.get('/accounts/verify-email/',
            {'uid': uid, 'token': token, 'resend_verification_email': "true"})
        data = json.loads(response.content.decode('utf-8'))
        message = data.get("message")
        self.assertEqual(message, "تم إرسال بريد إلكتروني جديد للتحقق.")
        self.assertTrue(data.get("new_verification_email_sent"))

    def test_verify_email_view_missing_params(self):
        """Test missing parameters"""
        if settings.ENABLE_EMAIL_VERIFICATION is False:
            self.assertEqual(2, 1 + 1)
            return
        response = self.client.get('/accounts/verify-email/', {})
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content.decode('utf-8'))
        message = data.get("message")
        self.assertEqual(message, _("Missing required parameters."))
        response = self.client.get('/accounts/verify-email/', {'uid': "uid"})
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content.decode('utf-8'))
        message = data.get("message")
        self.assertEqual(message, _("Missing required parameters."))
        response = self.client.get('/accounts/verify-email/', {'token': "token"})
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content.decode('utf-8'))
        message = data.get("message")
        self.assertEqual(message, _("Missing required parameters."))

    def test_verify_email_view_expired_token(self):
        """Test verify_email view with expired token returns expired field."""
        if settings.ENABLE_EMAIL_VERIFICATION is False:
            self.assertEqual(2, 1 + 1)
            return
        _, (uid, token) = EmailVerificationService.send_verification_email(self.user)
        # Modify token to be expired
        now = datetime.datetime.now()
        token_date = token.split("_*_")
        yesterday_timestamp = (now - datetime.timedelta(days=1)).timestamp()
        token_date[1] = str(yesterday_timestamp)
        expired_token = "_*_".join(token_date)

        response = self.client.get('/accounts/verify-email/',
                                   {'uid': uid, 'token': expired_token})
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content.decode('utf-8'))
        message = data.get("message")
        self.assertEqual(message,"Expired token. Send a new verification email to your email"
                         " address.")
        self.assertTrue(data.get("expired"))
