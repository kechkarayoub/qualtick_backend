"""
Repository for ContactMessage model data access operations.
"""
from typing import Optional, List
from django.db.models import QuerySet, Q
from django.utils import timezone
from datetime import timedelta

from backend.models import ContactMessage
from .base_repository import BaseRepository


class ContactMessageRepository(BaseRepository):
    """Repository for ContactMessage data access."""
    
    model = ContactMessage
    
    @classmethod
    def get_by_email(cls, email: str, db_alias: str = '') -> QuerySet:
        """
        Get all contact messages from a specific email.
        
        Args:
            email: Email address to filter by
            db_alias: Database alias to use
            
        Returns:
            QuerySet of ContactMessage objects
        """
        return cls.filter(email=email, db_alias=db_alias)
    
    @classmethod
    def get_by_user(cls, user_id: int, db_alias: str = '') -> QuerySet:
        """
        Get all contact messages from a specific user.
        
        Args:
            user_id: User ID to filter by
            db_alias: Database alias to use
            
        Returns:
            QuerySet of ContactMessage objects
        """
        return cls.filter(user_id=user_id, db_alias=db_alias)
    
    @classmethod
    def get_by_status(cls, status: str, db_alias: str = '') -> QuerySet:
        """
        Get all contact messages with a specific status.
        
        Args:
            status: Status to filter by (new, in_progress, resolved, closed)
            db_alias: Database alias to use
            
        Returns:
            QuerySet of ContactMessage objects
        """
        return cls.filter(status=status, db_alias=db_alias)
    
    @classmethod
    def get_by_subject(cls, subject: str, db_alias: str = '') -> QuerySet:
        """
        Get all contact messages with a specific subject.
        
        Args:
            subject: Subject to filter by
            db_alias: Database alias to use
            
        Returns:
            QuerySet of ContactMessage objects
        """
        return cls.filter(subject=subject, db_alias=db_alias)
    
    @classmethod
    def get_recent(cls, days: int = 7, db_alias: str = '') -> QuerySet:
        """
        Get recent contact messages within specified days.
        
        Args:
            days: Number of days to look back
            db_alias: Database alias to use
            
        Returns:
            QuerySet of ContactMessage objects
        """
        date_threshold = timezone.now() - timedelta(days=days)
        return cls.filter(created_at__gte=date_threshold, db_alias=db_alias)
    
    @classmethod
    def get_pending(cls, db_alias: str = '') -> QuerySet:
        """
        Get all pending contact messages (new or in_progress).
        
        Args:
            db_alias: Database alias to use
            
        Returns:
            QuerySet of ContactMessage objects
        """
        return cls.filter(status__in=['new', 'in_progress'], db_alias=db_alias)
    
    @classmethod
    def search(cls, query: str, db_alias: str = '') -> QuerySet:
        """
        Search contact messages by name, email, or message content.
        
        Args:
            query: Search query string
            db_alias: Database alias to use
            
        Returns:
            QuerySet of ContactMessage objects
        """
        return cls.model.objects.using(db_alias or None).filter(
            Q(name__icontains=query) |
            Q(email__icontains=query) |
            Q(message__icontains=query)
        )
    
    @classmethod
    def update_status(cls, message_id: int, status: str, admin_notes: Optional[str] = None, db_alias: str = '') -> Optional[ContactMessage]:
        """
        Update the status of a contact message.
        
        Args:
            message_id: ID of the contact message
            status: New status value
            admin_notes: Optional admin notes to add
            db_alias: Database alias to use
            
        Returns:
            Updated ContactMessage or None if not found
        """
        data = {'status': status}
        if admin_notes:
            data['admin_notes'] = admin_notes
        return cls.update(message_id, db_alias=db_alias, **data)
    
    @classmethod
    def get_statistics(cls, db_alias: str = '') -> dict:
        """
        Get statistics about contact messages.
        
        Args:
            db_alias: Database alias to use
            
        Returns:
            Dictionary with various statistics
        """
        return {
            'total': cls.count(db_alias=db_alias),
            'new': cls.count(status='new', db_alias=db_alias),
            'in_progress': cls.count(status='in_progress', db_alias=db_alias),
            'resolved': cls.count(status='resolved', db_alias=db_alias),
            'closed': cls.count(status='closed', db_alias=db_alias),
            'recent_7_days': cls.get_recent(7, db_alias=db_alias).count(),
            'recent_30_days': cls.get_recent(30, db_alias=db_alias).count(),
        }
