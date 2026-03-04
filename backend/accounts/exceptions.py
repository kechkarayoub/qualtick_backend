"""
Custom exceptions for accounts app.
"""
# pylint: disable=unnecessary-pass


class AccountsException(Exception):
    """Base exception for accounts app."""
    pass


class UserValidationException(AccountsException):
    """Exception raised when user validation fails."""
    pass


class EmailVerificationException(AccountsException):
    """Exception raised when email verification fails."""
    pass


class PhoneVerificationException(AccountsException):
    """Exception raised when phone number verification fails."""
    pass


class AuthenticationException(AccountsException):
    """Exception raised when authentication fails."""
    pass


class PasswordValidationException(AccountsException):
    """Exception raised when password validation fails."""
    pass


class ProfileImageException(AccountsException):
    """Exception raised when profile image operations fail."""
    pass


class UserRegistrationException(AccountsException):
    """Exception raised when user registration fails."""
    pass


class UserUpdateException(AccountsException):
    """Exception raised when user update fails."""
    pass


class TokenValidationException(AccountsException):
    """Exception raised when token validation fails."""
    pass


class PermissionException(AccountsException):
    """Exception raised when permission checks fail."""
    pass


class FirebaseException(AccountsException):
    """Exception raised when Firebase operations fail."""
    pass


class SMSException(AccountsException):
    """Exception raised when SMS operations fail."""
    pass


class EmailSendingException(AccountsException):
    """Exception raised when email sending fails."""
    pass


class UserNotActiveException(AccountsException):
    """Exception raised when user account is not active."""
    pass


class VerificationCodeException(AccountsException):
    """Exception raised when verification code operations fail."""
    pass


class UserDeleteException(AccountsException):
    """Exception raised when user deletion fails."""
    pass


class ProfileException(AccountsException):
    """Exception raised when profile operations fail."""
    pass
