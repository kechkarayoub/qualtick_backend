"""Serializers for contact messages."""
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from backend.models import ContactMessage
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
