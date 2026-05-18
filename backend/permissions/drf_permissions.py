"""DRF permission classes for the permissions app."""
from backend.utils import get_db_alias
from rest_framework.permissions import BasePermission

from permissions.services import PermissionService


class HasPermission(BasePermission):
    """DRF permission class: requires the authenticated user to hold *codename*.

    Usage::

        class MyView(APIView):
            permission_classes = [IsAuthenticated, HasPermission]
            required_permission = 'view_dashboard'
    """

    def has_permission(self, request, view):
        # Reject anonymous requests early.
        if not request.user or not request.user.is_authenticated:
            return False
        # Views can opt-in by setting `required_permission`.
        codename = getattr(view, 'required_permission', None)
        if not codename:
            return True
        # Resolve DB alias from request context for multi-DB safety.
        db_alias = get_db_alias(request=request)
        return PermissionService.has_permission(request.user, codename, db_alias=db_alias)


def require_permission(codename: str):
    """Return a DRF permission class that enforces *codename*.

    Usage::

        class MyView(APIView):
            permission_classes = [IsAuthenticated, require_permission('view_audit_logs')]
    """
    class _Perm(BasePermission):
        # Default DRF error message for denied access.
        message = f"Permission required: {codename}"

        def has_permission(self, request, view):
            # Keep behavior consistent with HasPermission.
            if not request.user or not request.user.is_authenticated:
                return False
            # Use request-derived database alias for permission checks.
            db_alias = get_db_alias(request=request)
            return PermissionService.has_permission(request.user, codename, db_alias=db_alias)

    # Improves readability in debugging and DRF introspection.
    _Perm.__name__ = f'HasPerm_{codename}'
    return _Perm
