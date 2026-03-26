"""Middleware that automatically writes an AuditLog entry for every API request."""
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

_SKIP_PATHS = frozenset({
    '/api/health/',
    '/api/info/',
    '/static/',
    '/media/',
    '/__debug__/',
    '/favicon.ico',
})

_WRITE_METHODS = frozenset({'POST', 'PUT', 'PATCH', 'DELETE'})

_ACTION_MAP = {
    'POST':   'create',
    'PUT':    'update',
    'PATCH':  'update',
    'DELETE': 'delete',
    'GET':    'read',
    'HEAD':   'read',
}

_PATH_ACTION_OVERRIDES = {
    '/accounts/sign-in/':             'login',
    '/accounts/sign-in-third-party/': 'login',
    '/accounts/sign-up/':             'create',
    '/accounts/sign-up-third-party/': 'create',
    '/accounts/logout/':              'logout',
    '/accounts/forgot-password/':     'password_reset',
    '/accounts/reset-password/':      'password_reset',
    '/accounts/verify-email/':        'email_verify',
    '/accounts/verify-phone-number/': 'phone_verify',
}

_EXPLICIT_LOG_PATHS = frozenset({
    '/accounts/sign-in/',
    '/accounts/sign-in-third-party/',
    '/accounts/logout/',
    '/accounts/update-profile/',
})


def _should_skip(path: str) -> bool:
    for prefix in _SKIP_PATHS:
        if path.startswith(prefix):
            return True
    return False


class AuditLogMiddleware:
    """
    Automatic request-level audit logging.

    Only write-method requests (POST/PUT/PATCH/DELETE) are logged by default
    to avoid flooding the table with GET reads.  Set
    ``AUDIT_LOG_ALL_METHODS = True`` in settings to log every request.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.log_all_methods = getattr(settings, 'AUDIT_LOG_ALL_METHODS', False)

    def __call__(self, request):
        response = self.get_response(request)
        try:
            self._maybe_log(request, response)
        except Exception:
            logger.exception("AuditLogMiddleware: unexpected error")
        return response

    def _maybe_log(self, request, response):
        if _should_skip(request.path):
            return
        if not self.log_all_methods and request.method not in _WRITE_METHODS:
            return
        if request.path in _EXPLICIT_LOG_PATHS:
            return

        from backend.services.audit_log_service import AuditLogService
        from backend.models import AuditLog

        user = request.user if request.user.is_authenticated else None
        outcome = (
            AuditLog.OUTCOME_SUCCESS
            if response.status_code < 400
            else AuditLog.OUTCOME_FAILURE
        )
        action = _PATH_ACTION_OVERRIDES.get(
            request.path, _ACTION_MAP.get(request.method, AuditLog.ACTION_OTHER))

        AuditLogService.log(
            action=action,
            outcome=outcome,
            user=user,
            description=f"{request.method} {request.path} → {response.status_code}",
            request=request,
        )
