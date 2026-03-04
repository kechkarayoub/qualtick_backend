# pylint: disable=broad-exception-caught
"""
Enhanced template tags for i18n_switcher app.
"""

import logging

from django import template
from django.utils import translation

from i18n_switcher.services import LanguageSwitchService, LanguagePreferenceService
from i18n_switcher.exceptions import InvalidPathException, UnsupportedLanguageException

register = template.Library()
logger = logging.getLogger(__name__)


@register.simple_tag(takes_context=True)
def switch_lang_url(context, language_code):
    """
    Generate URL for switching to a specific language.

    Usage: {% switch_lang_url 'en' %}
    """
    request = context.get('request')
    if not request:
        return '#'

    try:
        current_path = request.path
        return LanguageSwitchService.switch_language_in_path(current_path, language_code)
    except (InvalidPathException, UnsupportedLanguageException) as e:
        logger.warning("Failed to generate language switch URL: %s", str(e))
        return '#'


@register.simple_tag
def get_language_name(language_code):
    """
    Get the display name for a language code.

    Usage: {% get_language_name 'en' %}
    """
    language_names = LanguageSwitchService.get_language_names()
    return language_names.get(language_code, language_code)


@register.simple_tag
def get_supported_languages():
    """
    Get list of supported language codes.

    Usage: {% get_supported_languages %}
    """
    return LanguageSwitchService.get_supported_languages()


@register.simple_tag
def get_language_info():
    """
    Get comprehensive language information.
    Usage: {% get_language_info %}
    """
    return {
        'current': translation.get_language(),
        'supported': LanguageSwitchService.get_supported_languages(),
        'names': LanguageSwitchService.get_language_names(),
        'is_rtl': translation.get_language_bidi()
    }


@register.inclusion_tag('i18n_switcher/language_selector.html', takes_context=True)
def language_selector(context, css_class='language-selector'):
    """
    Render a language selector widget.
    Usage: {% language_selector %}
    Usage: {% language_selector 'custom-css-class' %}
    """
    request = context.get('request')
    current_language = translation.get_language()
    current_path = request.path if request else '/'

    try:
        language_urls = LanguageSwitchService.build_language_switch_urls(current_path)

        return {
            'current_language': current_language,
            'language_urls': language_urls,
            'css_class': css_class,
            'request': request
        }
    except Exception as e:
        logger.error("Error building language selector: %s", str(e))
        return {
            'current_language': current_language,
            'language_urls': {},
            'css_class': css_class,
            'request': request
        }


@register.filter
def is_rtl_language(language_code):
    """
    Check if a language is right-to-left.

    Usage: {{ 'ar'|is_rtl_language }}
    """
    rtl_languages = ['ar', 'he', 'fa', 'ur']  # Common RTL languages
    return language_code in rtl_languages


@register.filter
def language_name(language_code):
    """
    Filter to get language name from code.

    Usage: {{ 'en'|language_name }}
    """
    return get_language_name(language_code)


@register.simple_tag(takes_context=True)
def current_language_info(context):
    """
    Get current language information from request.

    Usage: {% current_language_info %}
    """
    request = context.get('request')
    current_language = translation.get_language()

    result = {
        'code': current_language,
        'name': get_language_name(current_language),
        'is_rtl': translation.get_language_bidi()
    }

    if request:
        result['preference'] = LanguagePreferenceService.get_language_preference(request)
        result['path_language'] = LanguageSwitchService.get_current_language_from_path(
            request.path)

    return result


@register.simple_tag(takes_context=True)
def language_switch_form(context, method='POST', css_class='language-switch-form'):
    """
    Generate a language switch form.

    Usage: {% language_switch_form %}
    Usage: {% language_switch_form 'GET' 'custom-form-class' %}
    """
    request = context.get('request')
    current_language = translation.get_language()
    current_path = request.path if request else '/'

    languages = []
    for lang_code in LanguageSwitchService.get_supported_languages():
        try:
            switch_url = LanguageSwitchService.switch_language_in_path(
                current_path, lang_code)
            languages.append({
                'code': lang_code,
                'name': get_language_name(lang_code),
                'url': switch_url,
                'is_current': lang_code == current_language
            })
        except Exception as e:
            logger.warning("Skipping language %s in form: %s", lang_code, str(e))
            continue

    return {
        'languages': languages,
        'current_language': current_language,
        'method': method,
        'css_class': css_class,
        'current_path': current_path
    }
