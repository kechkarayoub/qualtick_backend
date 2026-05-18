"""Permissions models."""
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from permissions.constants import AVAILABLE_PERMISSIONS, PERMISSION_CODENAMES

PERMISSION_CHOICES = [(code, label) for code, label in AVAILABLE_PERMISSIONS]


class UserPermission(models.Model):
    """
    Stores explicit permission grants for a user.

    A user has a permission if a row exists here with granted=True.
    Rows with granted=False act as explicit denials (useful audit trail).
    """

    class Meta:
        # Explicit table name keeps schema stable.
        db_table = 'permissions_user_permission'
        # One row per (user, codename).
        unique_together = [('user', 'codename')]
        # Predictable default ordering in admin/querysets.
        ordering = ['user', 'codename']
        verbose_name = _('User permission')
        verbose_name_plural = _('User permissions')
        # Query helpers for common filters.
        indexes = [
            models.Index(fields=['user', 'granted']),
            models.Index(fields=['codename']),
        ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='custom_permissions',
        verbose_name=_('User'),
    )
    codename = models.CharField(
        max_length=100,
        choices=PERMISSION_CHOICES,
        db_index=True,
        verbose_name=_('Permission'),
    )
    granted = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name=_('Granted'),
    )
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='permissions_granted',
        verbose_name=_('Granted by'),
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Created at'))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_('Updated at'))

    def __str__(self) -> str:
        # Human-readable format used in admin/logging.
        status = 'GRANT' if self.granted else 'DENY'
        return f'{status} {self.codename} → {self.user_id}'
