"""
Management commands for i18n_switcher app.
"""
# pylint: disable=broad-exception-caught
import os

from django.core.management.base import BaseCommand
from django.conf import settings

from i18n_switcher.services import LanguageSwitchService


class Command(BaseCommand):
    """
    Management command to check and validate language configuration.
    """

    help = 'Check and validate i18n_switcher configuration'

    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed information',
        )
        parser.add_argument(
            '--check-translations',
            action='store_true',
            help='Check for missing translation files',
        )

    def handle(self, *args, **options):
        """Handle the command execution."""
        verbose = options.get('verbose', False)
        check_translations = options.get('check_translations', False)

        self.stdout.write(
            self.style.SUCCESS('=== i18n_switcher Configuration Check ===')
        )

        # Check basic configuration
        self._check_basic_config(verbose)

        # Check supported languages
        self._check_supported_languages(verbose)

        # Check language cookie settings
        self._check_cookie_settings(verbose)

        # Check translation files if requested
        if check_translations:
            self._check_translation_files(verbose)

        # Test service functionality
        self._test_services(verbose)
        self.stdout.write(
            self.style.SUCCESS('=== Configuration check completed ===')
        )

    def _check_basic_config(self, verbose):
        """Check basic Django i18n configuration."""
        self.stdout.write('\n🔍 Checking basic configuration...')

        # Check USE_I18N
        if getattr(settings, 'USE_I18N', False):
            self.stdout.write(
                self.style.SUCCESS('✓ USE_I18N is enabled')
            )
        else:
            self.stdout.write(
                self.style.ERROR('✗ USE_I18N is not enabled')
            )

        # Check LANGUAGE_CODE
        language_code = getattr(settings, 'LANGUAGE_CODE', None)
        if language_code:
            self.stdout.write(
                self.style.SUCCESS(f'✓ LANGUAGE_CODE: {language_code}')
            )
        else:
            self.stdout.write(
                self.style.ERROR('✗ LANGUAGE_CODE is not set')
            )

        # Check LOCALE_PATHS
        locale_paths = getattr(settings, 'LOCALE_PATHS', [])
        if locale_paths:
            self.stdout.write(
                self.style.SUCCESS(f'✓ LOCALE_PATHS configured: {len(locale_paths)} paths')
            )
            if verbose:
                for path in locale_paths:
                    self.stdout.write(f'    - {path}')
        else:
            self.stdout.write(
                self.style.WARNING('⚠ LOCALE_PATHS is not configured')
            )

    def _check_supported_languages(self, verbose):
        """Check supported languages configuration."""
        self.stdout.write('\n🌍 Checking supported languages...')

        try:
            supported_languages = LanguageSwitchService.get_supported_languages()
            language_names = LanguageSwitchService.get_language_names()

            self.stdout.write(
                self.style.SUCCESS(f'✓ Found {len(supported_languages)} supported languages')
            )

            if verbose:
                for lang_code in supported_languages:
                    lang_name = language_names.get(lang_code, lang_code)
                    self.stdout.write(f'    - {lang_code}: {lang_name}')

            # Check if default language is supported
            default_lang = getattr(settings, 'LANGUAGE_CODE', 'en')
            if LanguageSwitchService.is_language_supported(default_lang):
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Default language ({default_lang}) is supported')
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f'✗ Default language ({default_lang}) is not in LANGUAGES')
                )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'✗ Error checking languages: {str(e)}')
            )

    def _check_cookie_settings(self, verbose):
        """Check language cookie settings."""
        self.stdout.write('\n🍪 Checking cookie settings...')

        cookie_settings = {
            'LANGUAGE_COOKIE_NAME': getattr(settings, 'LANGUAGE_COOKIE_NAME', 'django_language'),
            'LANGUAGE_COOKIE_AGE': getattr(settings, 'LANGUAGE_COOKIE_AGE', None),
            'LANGUAGE_COOKIE_DOMAIN': getattr(settings, 'LANGUAGE_COOKIE_DOMAIN', None),
            'LANGUAGE_COOKIE_PATH': getattr(settings, 'LANGUAGE_COOKIE_PATH', '/'),
            'LANGUAGE_COOKIE_SECURE': getattr(settings, 'LANGUAGE_COOKIE_SECURE', False),
            'LANGUAGE_COOKIE_HTTPONLY': getattr(settings, 'LANGUAGE_COOKIE_HTTPONLY', False),
            'LANGUAGE_COOKIE_SAMESITE': getattr(settings, 'LANGUAGE_COOKIE_SAMESITE', None),
        }

        for setting_name, value in cookie_settings.items():
            if verbose or value is not None:
                self.stdout.write(f'  {setting_name}: {value}')

        self.stdout.write(
            self.style.SUCCESS('✓ Cookie settings checked')
        )

    def _check_translation_files(self, verbose):
        """Check for translation files."""
        self.stdout.write('\n📁 Checking translation files...')

        try:
            supported_languages = LanguageSwitchService.get_supported_languages()
            locale_paths = getattr(settings, 'LOCALE_PATHS', [])

            if not locale_paths:
                self.stdout.write(
                    self.style.WARNING('⚠ No LOCALE_PATHS configured, skipping file check')
                )
                return

            for locale_path in locale_paths:
                self.stdout.write(f'\n📂 Checking locale path: {locale_path}')

                if not os.path.exists(locale_path):
                    self.stdout.write(
                        self.style.ERROR(f'✗ Locale path does not exist: {locale_path}')
                    )
                    continue

                for lang_code in supported_languages:
                    lang_dir = os.path.join(locale_path, lang_code, 'LC_MESSAGES')
                    po_file = os.path.join(lang_dir, 'django.po')
                    mo_file = os.path.join(lang_dir, 'django.mo')

                    if os.path.exists(po_file):
                        if os.path.exists(mo_file):
                            self.stdout.write(
                                self.style.SUCCESS(f'✓ {lang_code}: Complete translation files')
                            )
                        else:
                            self.stdout.write(
                                self.style.WARNING(
                                    f'⚠ {lang_code}: .po file exists but .mo is missing '
                                    '(run compilemessages)'
                                )
                            )
                    else:
                        if verbose:
                            self.stdout.write(
                                self.style.ERROR(f'✗ {lang_code}: No translation files found')
                            )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'✗ Error checking translation files: {str(e)}')
            )

    def _test_services(self, verbose):
        """Test service functionality."""
        self.stdout.write('\n🧪 Testing service functionality...')

        try:
            # Test path switching
            test_paths = [
                ('/', 'en'),
                ('/fr/test/', 'en'),
                ('/test/', 'fr'),
            ]

            for path, language in test_paths:
                try:
                    result = LanguageSwitchService.switch_language_in_path(path, language)
                    if verbose:
                        self.stdout.write(f'  Switch {path} -> {language}: {result}')
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f'✗ Path switching failed for {path} -> {language}: {str(e)}'
                        )
                    )
                    return

            self.stdout.write(
                self.style.SUCCESS('✓ Service functionality tests passed')
            )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'✗ Service testing failed: {str(e)}')
            )
