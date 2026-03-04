"""
Enhanced tests for i18n_switcher app.
"""

from django.conf import settings
from django.http import HttpRequest
from django.test import TestCase, RequestFactory

from .services import LanguageSwitchService, LanguagePreferenceService
from .exceptions import InvalidPathException, UnsupportedLanguageException
from .views import switch_lang_code
from .templatetags.i18n_switcher import switch_i18n, switch_i18n_prefix


class LanguageSwitchServiceTest(TestCase):
    """Test cases for LanguageSwitchService."""

    def setUp(self):
        self.service = LanguageSwitchService()

    def test_get_supported_languages(self):
        """Test getting supported languages."""
        languages = LanguageSwitchService.get_supported_languages()
        self.assertIsInstance(languages, list)
        self.assertIn('en', languages)

    def test_get_language_names(self):
        """Test getting language names."""
        names = LanguageSwitchService.get_language_names()
        self.assertIsInstance(names, dict)
        self.assertIn('en', names)

    def test_is_language_supported(self):
        """Test language support validation."""
        self.assertTrue(LanguageSwitchService.is_language_supported('en'))
        self.assertFalse(LanguageSwitchService.is_language_supported('xx'))

    def test_validate_path_valid(self):
        """Test path validation with valid paths."""
        # Should not raise exception
        LanguageSwitchService.validate_path('/')
        LanguageSwitchService.validate_path('/en/test/')

    def test_validate_path_invalid(self):
        """Test path validation with invalid paths."""
        with self.assertRaises(InvalidPathException):
            LanguageSwitchService.validate_path('')
        with self.assertRaises(InvalidPathException):
            LanguageSwitchService.validate_path('invalid')

    def test_validate_language_valid(self):
        """Test language validation with valid languages."""
        # Should not raise exception
        LanguageSwitchService.validate_language('en')

    def test_validate_language_invalid(self):
        """Test language validation with invalid languages."""
        with self.assertRaises(UnsupportedLanguageException):
            LanguageSwitchService.validate_language('xx')

    def test_switch_language_in_path(self):
        """Test language switching in URL paths."""
        # Test adding language prefix
        result = LanguageSwitchService.switch_language_in_path('/', 'en')
        self.assertEqual(result, '/en/')
        # Test replacing existing language prefix
        result = LanguageSwitchService.switch_language_in_path('/fr/test/', 'en')
        self.assertEqual(result, '/en/test/')
        # Test adding to path without language prefix
        result = LanguageSwitchService.switch_language_in_path('/test/', 'en')
        self.assertEqual(result, '/en/test/')

    def test_get_current_language_from_path(self):
        """Test extracting language from path."""
        # Path with language prefix
        result = LanguageSwitchService.get_current_language_from_path('/en/test/')
        self.assertEqual(result, 'en')
        # Path without language prefix
        result = LanguageSwitchService.get_current_language_from_path('/test/')
        self.assertIsNone(result)
        # Invalid path
        result = LanguageSwitchService.get_current_language_from_path('')
        self.assertIsNone(result)

    def test_remove_language_from_path(self):
        """Test removing language prefix from path."""
        # Path with language prefix
        result = LanguageSwitchService.remove_language_from_path('/en/test/')
        self.assertEqual(result, '/test/')
        # Path without language prefix
        result = LanguageSwitchService.remove_language_from_path('/test/')
        self.assertEqual(result, '/test/')

    def test_build_language_switch_urls(self):
        """Test building language switch URLs."""
        urls = LanguageSwitchService.build_language_switch_urls('/test/')
        self.assertIsInstance(urls, dict)
        self.assertIn('en', urls)
        self.assertIn('url', urls['en'])
        self.assertIn('name', urls['en'])
        self.assertIn('code', urls['en'])


class LanguagePreferenceServiceTest(TestCase):
    """Test cases for LanguagePreferenceService."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_get_language_preference(self):
        """Test getting language preference from cookie."""
        request = self.factory.get('/')
        request.COOKIES = {settings.LANGUAGE_COOKIE_NAME: 'en'}
        preference = LanguagePreferenceService.get_language_preference(request)
        self.assertEqual(preference, 'en')

    def test_get_language_preference_none(self):
        """Test getting language preference when no cookie exists."""
        request = self.factory.get('/')
        request.COOKIES = {}
        preference = LanguagePreferenceService.get_language_preference(request)
        self.assertIsNone(preference)


class LegacyFunctionTest(TestCase):
    """Test cases for backward compatibility functions."""

    def test_switch_lang_code_legacy(self):
        """Test legacy switch_lang_code function."""
        # Test normal case
        result = switch_lang_code('/test/', 'en')
        self.assertEqual(result, '/en/test/')
        # Test with existing language
        result = switch_lang_code('/fr/test/', 'en')
        self.assertEqual(result, '/en/test/')
        # Test error cases
        with self.assertRaises(Exception):
            switch_lang_code('', 'en')
        with self.assertRaises(Exception):
            switch_lang_code('/test/', 'xx')


class I18nSwitcherTests(TestCase):
    """Legacy test cases for backward compatibility."""

    def test_switch_lang_code(self):
        """Test switch_lang_code function."""
        new_url = switch_lang_code("/fr/admin/", "fr")
        self.assertEqual("/fr/admin/", new_url)
        new_url = switch_lang_code("/fr/admin/", "ar")
        self.assertEqual("/ar/admin/", new_url)
        new_url = switch_lang_code("/admin/", "ar")
        self.assertEqual("/ar/admin/", new_url)
        self.assertRaises(Exception, switch_lang_code, "", "en")
        self.assertRaises(Exception, switch_lang_code, "ar/admin/", "ar")
        self.assertRaises(Exception, switch_lang_code, "/ar/admin/", "es")

    def test_switch_i18n_prefix(self):
        """Test switch_i18n_prefix function."""
        new_url = switch_i18n_prefix("/fr/admin/", "fr")
        self.assertEqual("/fr/admin/", new_url)
        new_url = switch_i18n_prefix("/fr/admin/", "ar")
        self.assertEqual("/ar/admin/", new_url)
        new_url = switch_i18n_prefix("/admin/", "ar")
        self.assertEqual("/ar/admin/", new_url)
        self.assertRaises(Exception, switch_i18n_prefix, "", "en")
        self.assertRaises(Exception, switch_i18n_prefix, "ar/admin/", "ar")
        self.assertRaises(Exception, switch_i18n_prefix, "/ar/admin/", "es")

    def test_switch_i18n(self):
        """test switch_i18n function"""
        request = HttpRequest()
        request.method = 'GET'
        request.path = "/fr/admin/"
        new_url = switch_i18n(request, "fr")
        self.assertEqual("/fr/admin/", new_url)
        request.path = "/fr/admin/"
        new_url = switch_i18n(request, "ar")
        self.assertEqual("/ar/admin/", new_url)
        request.path = "/admin/"
        new_url = switch_i18n(request, "ar")
        self.assertEqual("/ar/admin/", new_url)
        request.path = ""
        self.assertRaises(Exception, switch_i18n, request, "en")
        request.path = "ar/admin/"
        self.assertRaises(Exception, switch_i18n, request, "ar")
        request.path = "/fr/admin/"
        self.assertRaises(Exception, switch_i18n, request, "es")
