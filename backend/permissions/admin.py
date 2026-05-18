"""Admin configuration for the permissions app."""
from django.contrib import admin

from permissions.models import UserPermission


@admin.register(UserPermission)
class UserPermissionAdmin(admin.ModelAdmin):
    # Core columns for quick audit in admin list view.
    list_display = ['user', 'codename', 'granted', 'granted_by', 'created_at']
    # Common filters used by support/admin teams.
    list_filter = ['codename', 'granted']
    # Useful lookup fields for large user bases.
    search_fields = ['user__username', 'user__email', 'codename']
    # FK widgets optimized for large related tables.
    raw_id_fields = ['user', 'granted_by']
    # Stable ordering improves scanability.
    ordering = ['user__username', 'codename']
