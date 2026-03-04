"""Test phone number verification views."""
import datetime
import json

from django.conf import settings
from django.test import TestCase

from accounts.models import User
from accounts.repositories import UserRepository
from accounts.utils import send_phone_number_verification_code
from accounts.views import verify_user_phone_number
from backend.utils import get_db_alias


class PhoneNumberVerificationTests(TestCase):
    """Test phone number verification views."""
    def setUp(self):
        db_alias = get_db_alias()
        self.user = UserRepository.create_user(
            username='testuser', email='test@example.com', password='password123',
            user_phone_number_to_verify='+212612505257',
            db_alias=db_alias)
        if settings.ENABLE_PHONE_NUMBER_VERIFICATION is False:
            return
        self.user_ar = UserRepository.create_user(username='testuser_ar',
            email='test_ar@example.com', password='password123',
            current_language='ar', user_phone_number_to_verify='+212612505257',
            db_alias=db_alias)
        self.user_en = UserRepository.create_user(username='testuser_en',
            email='test_en@example.com', password='password123',
            current_language='en', user_phone_number_to_verify='+212612505257',
            db_alias=db_alias)
        self.user_fr = UserRepository.create_user(username='testuser_fr',
            email='test_fr@example.com', password='password123',
            current_language='fr', user_phone_number_to_verify='+212612505257',
            db_alias=db_alias)
    def test_verify_user_phone_number_valid(self):
        """Test verifying user phone number with valid code."""
        db_alias = get_db_alias()
        if settings.ENABLE_PHONE_NUMBER_VERIFICATION is False:
            self.assertEqual(2, 1 + 1)
            return
        _, (uid, verification_code) = send_phone_number_verification_code(self.user)
        (
            verified, already_verified, expired_verification_code, quota_exceeded
        ) = verify_user_phone_number(uid, verification_code, db_alias=db_alias)
        self.assertTrue(verified)
        self.assertFalse(already_verified)
        self.assertFalse(expired_verification_code)
        self.assertFalse(quota_exceeded)
        self.user = UserRepository.get_user_by_id(self.user.id, db_alias=db_alias)
        self.assertTrue(self.user.is_user_phone_number_validated)
        self.assertEqual(self.user.user_phone_number,
                         self.user.user_phone_number_to_verify)
        self.assertEqual(self.user.nbr_phone_number_verification_code_used, 1)
        (
            verified, already_verified, expired_verification_code, quota_exceeded
        ) = verify_user_phone_number(uid, verification_code, db_alias=db_alias)
        self.assertTrue(verified)
        self.assertTrue(already_verified)
        self.assertFalse(expired_verification_code)
        self.assertFalse(quota_exceeded)

    def test_verify_user_phone_number_invalid(self):
        """Test verifying user phone number with invalid code."""
        db_alias = get_db_alias()
        if settings.ENABLE_PHONE_NUMBER_VERIFICATION is False:
            self.assertEqual(2, 1 + 1)
            return
        _, (uid, _verification_code) = send_phone_number_verification_code(self.user)
        self.user.user_phone_number = None
        self.user.is_user_phone_number_validated = False
        self.user.save(using=db_alias or None)
        self.user = UserRepository.get_user_by_id(self.user.id, db_alias=db_alias)
        (
            verified, already_verified, expired_verification_code, quota_exceeded
        ) = verify_user_phone_number(uid, "verification_code", db_alias=db_alias)
        self.assertFalse(verified)
        self.assertFalse(already_verified)
        self.assertFalse(expired_verification_code)
        self.assertFalse(quota_exceeded)

    def test_verify_user_phone_number_expired(self):
        """Test verifying user phone number with expired code."""
        db_alias = get_db_alias()
        if settings.ENABLE_PHONE_NUMBER_VERIFICATION is False:
            self.assertEqual(2, 1 + 1)
            return
        _, (uid, verification_code) = send_phone_number_verification_code(self.user)
        self.user = UserRepository.get_user_by_id(self.user.id, db_alias=db_alias)
        self.user.user_phone_number = None
        self.user.is_user_phone_number_validated = False
        self.user.user_phone_number_verification_code_generated_at = self.user.user_phone_number_verification_code_generated_at - datetime.timedelta(minutes=settings.NUMBER_MINUTES_BEFORE_PHONE_NUMBER_VERIFICATION_CODE_EXPIRATION + 2) # pylint: disable=line-too-long
        self.user.save(using=db_alias or None)
        (
            verified, already_verified, expired_verification_code, quota_exceeded
        ) = verify_user_phone_number(uid, verification_code, db_alias=db_alias)
        self.assertFalse(verified)
        self.assertFalse(already_verified)
        self.assertTrue(expired_verification_code)
        self.assertFalse(quota_exceeded)

    def test_verify_user_phone_number_quota_exceeded(self):
        """Test verifying user phone number with quota exceeded."""
        db_alias = get_db_alias()
        if settings.ENABLE_PHONE_NUMBER_VERIFICATION is False:
            self.assertEqual(2, 1 + 1)
            return
        _, (uid, _verification_code) = send_phone_number_verification_code(self.user)
        self.user = UserRepository.get_user_by_id(self.user.id, db_alias=db_alias)
        self.user.user_phone_number = None
        self.user.is_user_phone_number_validated = False
        self.user.save(using=db_alias or None)
        _, (uid, _verification_code) = send_phone_number_verification_code(self.user)
        (
            verified, already_verified, expired_verification_code, quota_exceeded
        ) = verify_user_phone_number(
            uid, 'verification_code', resend_verification_phone_number_code=True,
            db_alias=db_alias)
        self.assertFalse(verified)
        self.assertFalse(already_verified)
        self.assertFalse(expired_verification_code)
        self.assertFalse(quota_exceeded)
        _, (uid, _verification_code) = send_phone_number_verification_code(self.user)
        (
            verified, already_verified, expired_verification_code, quota_exceeded
        ) = verify_user_phone_number(uid, 'verification_code',
            resend_verification_phone_number_code=True, db_alias=db_alias)
        self.assertFalse(verified)
        self.assertFalse(already_verified)
        self.assertFalse(expired_verification_code)
        self.assertTrue(quota_exceeded)

    def test_verify_phone_number_view(self):
        """Test verifying user phone number view."""
        db_alias = get_db_alias()
        if settings.ENABLE_PHONE_NUMBER_VERIFICATION is False:
            self.assertEqual(2, 1 + 1)
            return
        _, (uid, verification_code) = send_phone_number_verification_code(self.user_fr)
        response = self.client.get('/accounts/verify-phone-number/',
                                   {'uid': uid, 'verification_code': verification_code})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content.decode('utf-8'))
        message = data.get("message")
        self.assertEqual(message, "Numéro de téléphone vérifié avec succès.")
        response = self.client.get('/accounts/verify-phone-number/',
                                   {'uid': uid, 'verification_code': verification_code})
        data = json.loads(response.content.decode('utf-8'))
        message = data.get("message")
        self.assertEqual(message, "Numéro de téléphone déjà vérifié.")
        _, (uid, verification_code) = send_phone_number_verification_code(self.user_fr)
        UserRepository.filter(pk=self.user_fr.id).update(
            user_phone_number=None, is_user_phone_number_validated=False,
            user_phone_number_verification_code_generated_at=self.user_fr.user_phone_number_verification_code_generated_at - datetime.timedelta(minutes=settings.NUMBER_MINUTES_BEFORE_PHONE_NUMBER_VERIFICATION_CODE_EXPIRATION + 2), # pylint: disable=line-too-long
            db_alias=db_alias
        )
        response = self.client.get('/accounts/verify-phone-number/',
                                   {'uid': uid, 'verification_code': verification_code})
        data = json.loads(response.content.decode('utf-8'))
        message = data.get("message")
        self.assertEqual(message, "Code de vérification expiré.")
        response = self.client.get('/accounts/verify-phone-number/',
            {'uid': uid, 'verification_code': verification_code,
             'resend_verification_phone_number_code': "true"})
        data = json.loads(response.content.decode('utf-8'))
        message = data.get("message")
        self.assertEqual(message, "Un nouveau code de vérification sera envoyé à "
                         "votre numéro de téléphone.")
        _, (uid, verification_code) = send_phone_number_verification_code(self.user_fr)
        response = self.client.get('/accounts/verify-phone-number/',
                                   {'uid': uid, 'verification_code': 'verification_code'})
        data = json.loads(response.content.decode('utf-8'))
        message = data.get("message")
        self.assertEqual(message, "Code invalide.")

    def test_verify_phone_number_view_en(self):
        """Test the phone number verification view for English."""
        db_alias = get_db_alias()
        if settings.ENABLE_PHONE_NUMBER_VERIFICATION is False:
            self.assertEqual(2, 1 + 1)
            return
        _, (uid, verification_code) = send_phone_number_verification_code(self.user_en)
        response = self.client.get('/accounts/verify-phone-number/',
                                   {'uid': uid, 'verification_code': verification_code})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content.decode('utf-8'))
        message = data.get("message")
        self.assertEqual(message, "Phone number verified successfully.")
        response = self.client.get('/accounts/verify-phone-number/',
                                   {'uid': uid, 'verification_code': verification_code})
        data = json.loads(response.content.decode('utf-8'))
        message = data.get("message")
        self.assertEqual(message, "Phone number already verified.")
        _, (uid, verification_code) = send_phone_number_verification_code(self.user_en)
        UserRepository.filter(pk=self.user_en.id).update(
            user_phone_number=None, is_user_phone_number_validated=False,
            user_phone_number_verification_code_generated_at=self.user_en.user_phone_number_verification_code_generated_at - datetime.timedelta(minutes=settings.NUMBER_MINUTES_BEFORE_PHONE_NUMBER_VERIFICATION_CODE_EXPIRATION + 2), # pylint: disable=line-too-long
            db_alias=db_alias
        )
        response = self.client.get('/accounts/verify-phone-number/',
                                   {'uid': uid, 'verification_code': verification_code})
        data = json.loads(response.content.decode('utf-8'))
        message = data.get("message")
        self.assertEqual(message, "Expired verification code.")
        response = self.client.get('/accounts/verify-phone-number/',
            {'uid': uid, 'verification_code': verification_code,
             'resend_verification_phone_number_code': "true"})
        data = json.loads(response.content.decode('utf-8'))
        message = data.get("message")
        self.assertEqual(message, "A new verification code will be sent to "
                         "your phone number.")
        _, (uid, verification_code) = send_phone_number_verification_code(self.user_en)
        response = self.client.get('/accounts/verify-phone-number/',
                                   {'uid': uid, 'verification_code': 'verification_code'})
        data = json.loads(response.content.decode('utf-8'))
        message = data.get("message")
        self.assertEqual(message, "Invalid code.")

    def test_verify_phone_number_view_ar(self):
        """Test the phone number verification view for Arabic."""
        db_alias = get_db_alias()
        if settings.ENABLE_PHONE_NUMBER_VERIFICATION is False:
            self.assertEqual(2, 1 + 1)
            return
        _, (uid, verification_code) = send_phone_number_verification_code(self.user_ar)
        response = self.client.get('/accounts/verify-phone-number/',
                                   {'uid': uid, 'verification_code': verification_code})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content.decode('utf-8'))
        message = data.get("message")
        self.assertEqual(message, "تم التحقق من رقم الهاتف بنجاح.")
        response = self.client.get('/accounts/verify-phone-number/',
        {'uid': uid, 'verification_code': verification_code})
        data = json.loads(response.content.decode('utf-8'))
        message = data.get("message")
        self.assertEqual(message, "رقم الهاتف تم التحقق منه بالفعل.")
        _, (uid, verification_code) = send_phone_number_verification_code(self.user_ar)
        UserRepository.filter(pk=self.user_ar.id).update(
            user_phone_number=None, is_user_phone_number_validated=False,
            user_phone_number_verification_code_generated_at=self.user_ar.user_phone_number_verification_code_generated_at - datetime.timedelta(minutes=settings.NUMBER_MINUTES_BEFORE_PHONE_NUMBER_VERIFICATION_CODE_EXPIRATION + 2), # pylint: disable=line-too-long
            db_alias=db_alias
        )
        response = self.client.get('/accounts/verify-phone-number/',
                                   {'uid': uid, 'verification_code': verification_code})
        data = json.loads(response.content.decode('utf-8'))
        message = data.get("message")
        self.assertEqual(message, "رمز التحقق منتهي الصلاحية.")
        response = self.client.get('/accounts/verify-phone-number/',
            {'uid': uid, 'verification_code': verification_code,
             'resend_verification_phone_number_code': "true"})
        data = json.loads(response.content.decode('utf-8'))
        message = data.get("message")
        self.assertEqual(message, "سيتم إرسال رمز تحقق جديد إلى رقم هاتفك.")
        _, (uid, verification_code) = send_phone_number_verification_code(self.user_ar)
        response = self.client.get('/accounts/verify-phone-number/',
                                   {'uid': uid, 'verification_code': 'verification_code'})
        data = json.loads(response.content.decode('utf-8'))
        message = data.get("message")
        self.assertEqual(message, "رمز غير صالح.")

    def test_verify_phone_number_view_missing_params(self):
        """Test missing parameters"""
        if settings.ENABLE_PHONE_NUMBER_VERIFICATION is False:
            self.assertEqual(2, 1 + 1)
            return
        response = self.client.get('/accounts/verify-phone-number/', {})
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content.decode('utf-8'))
        message = data.get("message")
        self.assertEqual(message, "Paramètres requis manquants.")
        response = self.client.get('/accounts/verify-phone-number/', {'uid': "uid"})
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content.decode('utf-8'))
        message = data.get("message")
        self.assertEqual(message, "Paramètres requis manquants.")
        response = self.client.get('/accounts/verify-phone-number/',
                                   {'verification_code': "verification_code"})
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content.decode('utf-8'))
        message = data.get("message")
        self.assertEqual(message, "Paramètres requis manquants.")
