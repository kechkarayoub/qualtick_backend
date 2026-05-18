"""Permissions app configuration."""
from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class PermissionsConfig(AppConfig):
    # Keep PK strategy aligned with the rest of the project.
    default_auto_field = 'django.db.models.BigAutoField'
    # Django app label/path.
    name = 'permissions'
    # Human-readable label shown in Django admin.
    verbose_name = _('Permissions')
