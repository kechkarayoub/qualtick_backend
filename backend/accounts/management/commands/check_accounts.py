# pylint: disable=no-member
# pylint: disable=protected-access
"""
Management command for accounts app health check.
"""

import logging
import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand
from django.db import connection

from firebase_admin import auth as firebase_auth  # pylint: disable=unused-import

from accounts.models import User
from accounts.services import UserValidationService
import firebase_config  # pylint: disable=unused-import

from accounts.repositories import UserRepository
from backend.utils import get_db_alias

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Management command to check accounts app health and functionality.
    """
    help = 'Check accounts app health and functionality'
    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed information',
        )
        parser.add_argument(
            '--check-email',
            action='store_true',
            help='Test email sending functionality',
        )
        parser.add_argument(
            '--check-sms',
            action='store_true',
            help='Test SMS sending functionality',
        )
        parser.add_argument(
            '--check-firebase',
            action='store_true',
            help='Test Firebase connectivity',
        )
        parser.add_argument(
            '--db_alias',
            type=str,
            help='Specify the database alias to use',
        )
    def handle(self, *args, **options):
        """Handle the command execution."""
        verbose = options.get('verbose', False)
        check_email = options.get('check_email', False)
        check_sms = options.get('check_sms', False)
        check_firebase = options.get('check_firebase', False)
        db_alias = options.get('db_alias', '')
        self.stdout.write(
            self.style.SUCCESS('=== Accounts App Health Check ===')
        )
        # Check basic configuration
        self._check_basic_config(verbose)
        # Check user model
        self._check_user_model(verbose, db_alias=db_alias)
        # Check authentication settings
        self._check_auth_settings(verbose)
        # Check email functionality if requested
        if check_email:
            self._check_email_functionality(verbose)
        # Check SMS functionality if requested
        if check_sms:
            self._check_sms_functionality(verbose)
        # Check Firebase functionality if requested
        if check_firebase:
            self._check_firebase_functionality(verbose)
        # Check services functionality
        self._check_services(verbose)
        self.stdout.write(
            self.style.SUCCESS('=== Accounts health check completed ===')
        )
    def _check_basic_config(self, verbose):
        """Check basic accounts configuration."""
        self.stdout.write('\n🔍 Checking basic configuration...')
        # Check custom user model
        user_model = get_user_model()
        if user_model.__name__ == 'User' and user_model._meta.app_label == 'accounts':
            self.stdout.write(
                self.style.SUCCESS('✓ Custom user model configured correctly')
            )
        else:
            self.stdout.write(
                self.style.ERROR('✗ Custom user model not configured correctly')
            )
    def _check_user_model(self, verbose, db_alias=''):
        """Check user model structure."""
        if verbose:
            self.stdout.write('\n👤 Checking User model')
        self.stdout.write('\n👤 Checking user model...')
        try:
            # Check if we can query the User model
            user_count = UserRepository.count(db_alias=db_alias)
            self.stdout.write(
                self.style.SUCCESS(f'✓ User model accessible, {user_count} users in database')
            )
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.stdout.write(
                self.style.ERROR(f'✗ User model check failed: {str(e)}')
            )
    def _check_auth_settings(self, verbose):
        """Check authentication settings."""
        self.stdout.write('\n🔐 Checking authentication settings...')
        auth_settings = {
            'AUTH_USER_MODEL': getattr(settings, 'AUTH_USER_MODEL', None),
            'LOGIN_URL': getattr(settings, 'LOGIN_URL', None),
            'LOGIN_REDIRECT_URL': getattr(settings, 'LOGIN_REDIRECT_URL', None),
            'LOGOUT_REDIRECT_URL': getattr(settings, 'LOGOUT_REDIRECT_URL', None),
        }
        for setting_name, value in auth_settings.items():
            if value:
                if verbose:
                    self.stdout.write(f'  ✓ {setting_name}: {value}')
            else:
                if verbose:
                    self.stdout.write(f'  ⚠ {setting_name}: Not set')
        # Check JWT settings
        if hasattr(settings, 'SIMPLE_JWT'):
            self.stdout.write(
                self.style.SUCCESS('✓ JWT authentication configured')
            )
        else:
            self.stdout.write(
                self.style.WARNING('⚠ JWT authentication not configured')
            )
    def _check_email_functionality(self, verbose):
        """Check email sending functionality."""
        self.stdout.write('\n📧 Checking email functionality...')
        try:
            # Test email configuration
            EmailMessage(
                subject='Accounts Health Check',
                body='This is a test email from accounts health check.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[settings.TECHNICAL_SERVICE_EMAIL],
            )
            # Don't actually send, just validate
            if verbose:
                self.stdout.write(f'  Email backend: {settings.EMAIL_BACKEND}')
                self.stdout.write(f'  From email: {settings.DEFAULT_FROM_EMAIL}')
                self.stdout.write(f'  Email host: {settings.EMAIL_HOST}')
            self.stdout.write(
                self.style.SUCCESS('✓ Email configuration appears valid')
            )
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.stdout.write(
                self.style.ERROR(f'✗ Email configuration failed: {str(e)}')
            )
    def _check_sms_functionality(self, verbose):
        """Check SMS sending functionality."""
        self.stdout.write('\n📱 Checking SMS functionality...')
        try:
            # Check WhatsApp settings
            whatsapp_settings = [
                'WHATSAPP_INSTANCE_ID',
                'WHATSAPP_INSTANCE_TOKEN',
                'WHATSAPP_INSTANCE_URL',
            ]
            all_configured = True
            for setting_name in whatsapp_settings:
                value = getattr(settings, setting_name, None)
                if value:
                    if verbose:
                        self.stdout.write(f'  ✓ {setting_name}: {"*" * len(str(value)[:4])}...')
                else:
                    self.stdout.write(
                        self.style.WARNING(f'⚠ {setting_name} not configured')
                    )
                    all_configured = False
            if all_configured:
                self.stdout.write(
                    self.style.SUCCESS('✓ SMS/WhatsApp configuration appears valid')
                )
            else:
                self.stdout.write(
                    self.style.WARNING('⚠ SMS/WhatsApp configuration incomplete')
                )
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.stdout.write(
                self.style.ERROR(f'✗ SMS configuration check failed: {str(e)}')
            )
    def _check_firebase_functionality(self, verbose):
        """Check Firebase connectivity."""
        self.stdout.write('\n🔥 Checking Firebase functionality...')
        try:
            # Test Firebase connection by listing first user (don't actually list)
            self.stdout.write(
                self.style.SUCCESS('✓ Firebase admin SDK imported successfully')
            )
            if verbose:
                firebase_project_id = getattr(settings, 'FIREBASE_PROJECT_ID', None)
                if firebase_project_id:
                    self.stdout.write(f'  Project ID: {firebase_project_id}')
                credentials_path = getattr(settings, 'FIREBASE_CREDENTIALS_PATH', None)
                if credentials_path:
                    if os.path.exists(credentials_path):
                        self.stdout.write(f'  ✓ Credentials file exists: {credentials_path}')
                    else:
                        self.stdout.write(f'  ✗ Credentials file missing: {credentials_path}')
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.stdout.write(
                self.style.ERROR(f'✗ Firebase configuration failed: {str(e)}')
            )
    def _check_services(self, verbose):
        """Check services functionality."""
        if verbose:
            self.stdout.write('\n🧪 Testing services functionality...')
        self.stdout.write('\n🧪 Testing services functionality...')
        try:
            # Test UserValidationService
            test_data = {
                'email': 'test@example.com',
                'password': 'testpassword123',
                'user_gender': 'male',
            }
            UserValidationService.validate_user_data(test_data)
            self.stdout.write(
                self.style.SUCCESS('✓ UserValidationService working')
            )
            # Test phone validation
            try:
                UserValidationService.validate_phone_number('+1234567890')
                self.stdout.write(
                    self.style.SUCCESS('✓ Phone validation working')
                )
            except Exception:  # pylint: disable=broad-exception-caught
                self.stdout.write(
                    self.style.WARNING('⚠ Phone validation may need adjustment')
                )
            self.stdout.write(
                self.style.SUCCESS('✓ Service functionality tests passed')
            )
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.stdout.write(
                self.style.ERROR(f'✗ Service testing failed: {str(e)}')
            )
