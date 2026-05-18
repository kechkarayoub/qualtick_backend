"""Permission codenames and human-readable labels.

Each entry: (codename, label)
Add new permissions here — they are automatically available
in the admin UI and the API.
"""
from django.utils.translation import gettext_lazy as _

AVAILABLE_PERMISSIONS = [
    # Admin/authorization permissions.
    ('manage_permissions',  _('Manage user permissions')),
    ('view_audit_logs',     _('View audit logs')),
    ('manage_users',        _('Manage users')),
    # Product-level feature access permissions.
    ('view_dashboard',      _('View dashboard')),
    ('manage_contact_messages', _('Manage contact messages')),
]

# Convenience flat list used by services/serializers.
PERMISSION_CODENAMES = [p[0] for p in AVAILABLE_PERMISSIONS]
