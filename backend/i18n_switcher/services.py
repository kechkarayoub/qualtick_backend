"""
Service layer for i18n_switcher app.
"""
import logging

from django.conf import settings
from django.utils.translation import get_language_from_request

from .exceptions import (InvalidPathException, UnsupportedLanguageException,
                         LanguageDetectionException)


logger = logging.getLogger(__name__)


class LanguageSwitchService:
    """Service for handling language switching operations."""

    @staticmethod
    def get_supported_languages():
        """
        Get list of supported language codes.
        Returns:
            list: List of supported language codes
        """
        return [code for code, name in settings.LANGUAGES]

    @staticmethod
    def get_language_names():
        """
        Get dictionary of language codes to names.
        Returns:
            dict: Dictionary mapping language codes to names
        """
        return dict(settings.LANGUAGES)

    @staticmethod
    def is_language_supported(language_code):
        """
        Check if a language code is supported.
        Args:
            language_code (str): Language code to check
        Returns:
            bool: True if language is supported
        """
        return language_code in LanguageSwitchService.get_supported_languages()

    @staticmethod
    def validate_path(path):
        """
        Validate URL path.
        Args:
            path (str): URL path to validate
        Raises:
            InvalidPathException: If path is invalid
        """
        if not path:
            raise InvalidPathException("URL path for language switch is empty")
        if not path.startswith('/'):
            raise InvalidPathException('URL path for language switch does not start with '
                                       '"/"')

    @staticmethod
    def validate_language(language_code):
        """
        Validate language code.
        Args:
            language_code (str): Language code to validate
        Raises:
            UnsupportedLanguageException: If language is not supported
        """
        if not LanguageSwitchService.is_language_supported(language_code):
            raise UnsupportedLanguageException(f'{language_code} is not a supported '
                                               'language code')
    @staticmethod
    def switch_language_in_path(path, new_language):
        """
        Switch language in URL path.
        Args:
            path (str): Current URL path
            new_language (str): New language code
        Returns:
            str: Path with new language prefix
        Raises:
            InvalidPathException: If path is invalid
            UnsupportedLanguageException: If language is not supported
        """
        # Validate inputs
        LanguageSwitchService.validate_path(path)
        LanguageSwitchService.validate_language(new_language)
        # Get supported language codes
        supported_languages = LanguageSwitchService.get_supported_languages()
        # Split the path parts
        parts = path.split('/')
        # Check if first part (after initial /) is a language code
        if len(parts) > 1 and parts[1] in supported_languages:
            # Replace existing language prefix
            parts[1] = new_language
        else:
            # Add new language prefix
            parts.insert(1, new_language)
        # Join and return the new path
        new_path = '/'.join(parts)
        logger.debug(
            "Language switch: %s -> %s (language: %s)", path, new_path, new_language)
        return new_path

    @staticmethod
    def detect_language_from_request(request):
        """
        Detect language from request headers and settings.
        Args:
            request (HttpRequest): Django request object
        Returns:
            str: Detected language code
        Raises:
            LanguageDetectionException: If language detection fails
        """
        try:
            # Try to get language from Django's built-in detection
            detected_language = get_language_from_request(request)
            # Ensure it's supported
            if LanguageSwitchService.is_language_supported(detected_language):
                return detected_language
            # Fallback to default language
            default_language = settings.LANGUAGE_CODE
            if LanguageSwitchService.is_language_supported(default_language):
                return default_language
            # Fallback to first supported language
            supported_languages = LanguageSwitchService.get_supported_languages()
            if supported_languages:
                return supported_languages[0]
            raise LanguageDetectionException("No supported languages configured")
        except Exception as e:
            logger.error("Language detection failed: %s", str(e))
            raise LanguageDetectionException(
                f"Language detection failed: {str(e)}") from e

    @staticmethod
    def get_current_language_from_path(path):
        """
        Extract current language from URL path.
        Args:
            path (str): URL path
        Returns:
            str: Current language code or None if not found
        """
        if not path or not path.startswith('/'):
            return None
        parts = path.split('/')
        if len(parts) > 1:
            potential_language = parts[1]
            if LanguageSwitchService.is_language_supported(potential_language):
                return potential_language
        return None

    @staticmethod
    def remove_language_from_path(path):
        """
        Remove language prefix from URL path.
        Args:
            path (str): URL path with language prefix
        Returns:
            str: Path without language prefix
        """
        current_language = LanguageSwitchService.get_current_language_from_path(path)
        if current_language:
            # Remove the language prefix
            parts = path.split('/')
            if len(parts) > 1 and parts[1] == current_language:
                parts.pop(1)
                return '/'.join(parts) if len(parts) > 1 else '/'
        return path

    @staticmethod
    def build_language_switch_urls(current_path):
        """
        Build URLs for all supported languages.
        Args:
            current_path (str): Current URL path
        Returns:
            dict: Dictionary mapping language codes to URLs
        """
        language_urls = {}
        supported_languages = LanguageSwitchService.get_supported_languages()
        language_names = LanguageSwitchService.get_language_names()
        for lang_code in supported_languages:
            try:
                new_url = LanguageSwitchService.switch_language_in_path(
                    current_path, lang_code)
                language_urls[lang_code] = {
                    'url': new_url,
                    'name': language_names.get(lang_code, lang_code),
                    'code': lang_code
                }
            except (InvalidPathException, UnsupportedLanguageException) as e:
                logger.warning("Failed to build URL for language %s: %s", lang_code, str(e))
                continue
        return language_urls


class LanguagePreferenceService:
    """Service for handling user language preferences."""

    @staticmethod
    def set_language_preference(request, response, language_code):
        """
        Set language preference in cookie.
        Args:
            request (HttpRequest): Django request object
            response (HttpResponse): Django response object
            language_code (str): Language code to set
        """
        if LanguageSwitchService.is_language_supported(language_code):
            response.set_cookie(
                settings.LANGUAGE_COOKIE_NAME,
                language_code,
                max_age=settings.LANGUAGE_COOKIE_AGE,
                path=settings.LANGUAGE_COOKIE_PATH,
                domain=settings.LANGUAGE_COOKIE_DOMAIN,
                secure=settings.LANGUAGE_COOKIE_SECURE,
                httponly=settings.LANGUAGE_COOKIE_HTTPONLY,
                samesite=settings.LANGUAGE_COOKIE_SAMESITE,
            )
            logger.info("Language preference set to %s", language_code)

    @staticmethod
    def get_language_preference(request):
        """
        Get language preference from cookie.
        Args:
            request (HttpRequest): Django request object
        Returns:
            str: Language code or None if not set
        """
        return request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)
