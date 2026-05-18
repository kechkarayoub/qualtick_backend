"""Serializers for the permissions app."""
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from accounts.models import User
from permissions.constants import AVAILABLE_PERMISSIONS, PERMISSION_CODENAMES
from permissions.models import UserPermission

CODENAME_CHOICES = [p[0] for p in AVAILABLE_PERMISSIONS]


class UserPermissionSerializer(serializers.ModelSerializer):
    # Convenience field for admin UIs to avoid nested objects.
    granted_by_username = serializers.SerializerMethodField()

    class Meta:
        model = UserPermission
        fields = ['id', 'codename', 'granted', 'granted_by', 'granted_by_username',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'granted_by', 'created_at', 'updated_at']

    def get_granted_by_username(self, obj):
        # Null-safe helper for rows created without explicit granter.
        if obj.granted_by_id:
            return obj.granted_by.username
        return None


class SetUserPermissionsSerializer(serializers.Serializer):
    """Used by the admin endpoint to replace a user's full permission set."""
    # Accepts a full replacement list of permission codenames.
    permissions = serializers.ListField(
        child=serializers.ChoiceField(choices=CODENAME_CHOICES),
        allow_empty=True,
    )


class UserWithPermissionsSerializer(serializers.ModelSerializer):
    """Minimal user info + their current permissions, for the admin list."""
    # Computed field to serialize effective granted codenames.
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name',
                  'is_active', 'is_superuser', 'permissions']

    def get_permissions(self, obj):
        # Prefer explicit context alias; fallback to the model instance DB.
        db_alias = self.context.get('db_alias') or getattr(obj._state, 'db', None)
        return list(
            UserPermission.objects.using(db_alias or None).filter(
                user=obj, granted=True
            ).values_list(
                'codename', flat=True
            )
        )
