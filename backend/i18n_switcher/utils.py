# pylint: disable=broad-exception-caught
"""
Utility functions for i18n_switcher app.
"""

import logging

from django.utils import translation
from django.utils.translation import get_language_info

from .services import LanguageSwitchService


logger = logging.getLogger(__name__)


def get_language_display_info(language_code=None):
    """
    Get comprehensive display information for a language.
    Args:
        language_code (str): Language code. If None, uses current language.
    Returns:
        dict: Language display information
    """
    if not language_code:
        language_code = translation.get_language()
    try:
        # Get Django's language info
        lang_info = get_language_info(language_code)
        # Get our custom info
        language_names = LanguageSwitchService.get_language_names()
        return {
            'code': language_code,
            'name': language_names.get(language_code, lang_info.get('name', language_code)),
            'name_local': lang_info.get('name_local', language_code),
            'name_translated': lang_info.get('name_translated', language_code),
            'bidi': lang_info.get('bidi', False),
            'is_rtl': lang_info.get('bidi', False),
            'text_direction': 'rtl' if lang_info.get('bidi', False) else 'ltr'
        }
    except Exception as e:
        logger.warning("Could not get language info for %s: %s", language_code, str(e))
        return {
            'code': language_code,
            'name': language_code,
            'name_local': language_code,
            'name_translated': language_code,
            'bidi': False,
            'is_rtl': False,
            'text_direction': 'ltr'
        }


def get_all_languages_info():
    """
    Get display information for all supported languages.

    Returns:
        list: List of language information dictionaries
    """
    languages_info = []
    supported_languages = LanguageSwitchService.get_supported_languages()
    for lang_code in supported_languages:
        languages_info.append(get_language_display_info(lang_code))
    return languages_info


def format_language_name(language_code, format_type='name'):
    """
    Format a language name according to the specified format.
    Args:
        language_code (str): Language code
        format_type (str): Format type ('name', 'local', 'translated', 'code')
    Returns:
        str: Formatted language name
    """
    lang_info = get_language_display_info(language_code)
    format_map = {
        'name': lang_info['name'],
        'local': lang_info['name_local'],
        'translated': lang_info['name_translated'],
        'code': lang_info['code']
    }
    return format_map.get(format_type, lang_info['name'])


def is_language_rtl(language_code=None):
    """
    Check if a language is right-to-left.
    Args:
        language_code (str): Language code. If None, uses current language.
    Returns:
        bool: True if language is RTL
    """
    if not language_code:
        language_code = translation.get_language()
    lang_info = get_language_display_info(language_code)
    return lang_info['is_rtl']


def get_text_direction(language_code=None):
    """
    Get text direction for a language.
    Args:
        language_code (str): Language code. If None, uses current language.
    Returns:
        str: 'rtl' or 'ltr'
    """
    if not language_code:
        language_code = translation.get_language()
    lang_info = get_language_display_info(language_code)
    return lang_info['text_direction']


def build_language_context(request=None, current_path=None):
    """
    Build comprehensive language context for templates.
    Args:
        request: Django request object (optional)
        current_path (str): Current URL path (optional)
    Returns:
        dict: Language context dictionary
    """
    if request and not current_path:
        current_path = request.path
    current_language = translation.get_language()
    context = {
        'current_language': current_language,
        'current_language_info': get_language_display_info(current_language),
        'supported_languages': LanguageSwitchService.get_supported_languages(),
        'all_languages_info': get_all_languages_info(),
        'is_rtl': is_language_rtl(current_language),
        'text_direction': get_text_direction(current_language),
    }
    if current_path:
        try:
            context['language_urls'] = LanguageSwitchService.build_language_switch_urls(
                current_path)
            context['current_path'] = current_path
            context['path_language'] = LanguageSwitchService.get_current_language_from_path(
                current_path)
        except Exception as e:
            logger.warning("Could not build language URLs for %s: %s", current_path, str(e))
            context['language_urls'] = {}
    return context


class LanguageContextProcessor: # pylint: disable=too-few-public-methods
    """
    Context processor to add language information to all templates.
    """
    def __call__(self, request):
        """
        Add language context to template context.
        Args:
            request: Django request object
        Returns:
            dict: Context variables for templates
        """
        return {
            'language_context': build_language_context(request),
            'LANGUAGE_CODE': translation.get_language(),
            'LANGUAGE_BIDI': translation.get_language_bidi(),
            'TEXT_DIRECTION': 'rtl' if translation.get_language_bidi() else 'ltr',
        }
