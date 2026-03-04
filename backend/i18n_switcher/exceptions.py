"""
Custom exceptions for the i18n_switcher app.
"""
# pylint: disable=unnecessary-pass


class I18nSwitcherBaseException(Exception):
    """Base exception for i18n_switcher app."""
    pass


class InvalidPathException(I18nSwitcherBaseException):
    """Exception raised when URL path is invalid."""
    pass


class UnsupportedLanguageException(I18nSwitcherBaseException):
    """Exception raised when language code is not supported."""
    pass


class LanguageDetectionException(I18nSwitcherBaseException):
    """Exception raised when language detection fails."""
    pass
