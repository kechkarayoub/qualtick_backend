"""
Admin configuration for Contact Messages and Audit Logs
"""
from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import ContactMessage, AuditLog


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    """
    Admin interface for Contact Messages
    """
    list_display = [
        'name',
        'email', 
        'subject',
        'status',
        'created_at',
        'updated_at'
    ]
    list_filter = [
        'status',
        'subject',
        'created_at',
        'updated_at'
    ]
    search_fields = [
        'name',
        'email',
        'message',
        'admin_notes'
    ]
    readonly_fields = [
        'created_at',
        'updated_at',
        'user'
    ]
    fields = [
        'name',
        'email',
        'subject',
        'message',
        'status',
        'admin_notes',
        'user',
        'created_at',
        'updated_at'
    ]
    ordering = ['-created_at']
    list_per_page = 25

    def get_queryset(self, request, db_alias=''):
        """
        Optimize queryset to include related user data
        """
        queryset = super().get_queryset(request).using(db_alias or None)
        return queryset.select_related('user')

    def has_delete_permission(self, request, obj=None):
        """
        Only superusers can delete contact messages
        """
        return request.user.is_superuser

    actions = ['mark_as_in_progress', 'mark_as_resolved', 'mark_as_closed']

    def mark_as_in_progress(self, request, queryset):
        """
        Mark selected messages as in progress
        """
        updated = queryset.update(status='in_progress')
        self.message_user(
            request,
            _('%(count)d message(s) marked as in progress.') % {'count': updated}
        )

    mark_as_in_progress.short_description = _('Mark as in progress')

    def mark_as_resolved(self, request, queryset):
        """
        Mark selected messages as resolved
        """
        updated = queryset.update(status='resolved')
        self.message_user(
            request,
            _('%(count)d message(s) marked as resolved.') % {'count': updated}
        )

    mark_as_resolved.short_description = _('Mark as resolved')

    def mark_as_closed(self, request, queryset):
        """
        Mark selected messages as closed
        """
        updated = queryset.update(status='closed')
        self.message_user(
            request,
            _('%(count)d message(s) marked as closed.') % {'count': updated}
        )

    mark_as_closed.short_description = _('Mark as closed')


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = [
        'timestamp',
        'actor_username',
        'action',
        'outcome',
        'resource_type',
        'resource_id',
        'ip_address',
        'request_method',
        'request_path',
    ]
    list_filter = [
        'action',
        'outcome',
        'resource_type',
        'request_method',
        ('timestamp', admin.DateFieldListFilter),
    ]
    search_fields = [
        'actor_username',
        'description',
        'ip_address',
        'request_path',
        'resource_id',
    ]
    readonly_fields = [
        'timestamp',
        'user',
        'actor_username',
        'action',
        'outcome',
        'resource_type',
        'resource_id',
        'description',
        'ip_address',
        'user_agent',
        'request_method',
        'request_path',
        'extra_data',
    ]
    ordering = ['-timestamp']
    list_per_page = 50
    date_hierarchy = 'timestamp'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
