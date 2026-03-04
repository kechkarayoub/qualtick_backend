# pylint: disable=unnecessary-pass
"""
Custom exceptions for the backend project.
"""


class BackendBaseException(Exception):
    """Base exception for all backend-related exceptions."""
    pass


class GeolocationException(BackendBaseException):
    """Exception raised when geolocation services fail."""
    pass


class FileUploadException(BackendBaseException):
    """Exception raised when file upload fails."""
    pass


class MessageSendException(BackendBaseException):
    """Exception raised when message sending fails."""
    pass


class PhoneNumberException(BackendBaseException):
    """Exception raised for phone number related issues."""
    pass


class EmailException(BackendBaseException):
    """Exception raised for email related issues."""
    pass


class ValidationException(BackendBaseException):
    """Exception raised for validation failures."""
    pass
