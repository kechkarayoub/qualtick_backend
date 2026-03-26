"""Serializers for contact messages and audit logs."""
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from backend.models import ContactMessage, AuditLog
from backend.repositories.contact_message_repository import ContactMessageRepository
from backend.utils import get_db_alias


class ContactMessageSerializer(serializers.ModelSerializer):
    """
    Serializer for contact messages
    """
    class Meta:
        model = ContactMessage
        fields = [
            'id',
            'name',
            'email', 
            'subject',
            'message',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    def validate_message(self, value):
        """
        Validate that the message has minimum length
        """
        if len(value.strip()) < 10:
            raise serializers.ValidationError(
                _('Message must be at least 10 characters long')
            )
        return value.strip()

    def validate_name(self, value):
        """
        Validate that the name is not empty
        """
        if not value.strip():
            raise serializers.ValidationError(
                _('Name is required')
            )
        return value.strip()

    def create(self, validated_data):
        """
        Create a new contact message, optionally linking to authenticated user
        """
        # Get the current user from the request context if available
        request = self.context.get('request')
        db_alias = get_db_alias(request=request)
        if request and request.user.is_authenticated:
            validated_data['user'] = request.user
        return ContactMessageRepository.create(db_alias=db_alias, **validated_data)


class ContactMessageListSerializer(serializers.ModelSerializer):
    """
    Serializer for listing contact messages (admin view)
    """
    subject_display = serializers.CharField(source='get_subject_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = ContactMessage
        fields = [
            'id',
            'name',
            'email',
            'subject',
            'subject_display',
            'status',
            'status_display',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class AuditLogSerializer(serializers.ModelSerializer):
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    outcome_display = serializers.CharField(source='get_outcome_display', read_only=True)
    user_id = serializers.IntegerField(source='user.id', read_only=True, default=None)

    class Meta:
        model = AuditLog
        fields = [
            'id',
            'timestamp',
            'user_id',
            'actor_username',
            'action',
            'action_display',
            'outcome',
            'outcome_display',
            'resource_type',
            'resource_id',
            'description',
            'ip_address',
            'user_agent',
            'request_method',
            'request_path',
            'extra_data',
        ]
        read_only_fields = fields
