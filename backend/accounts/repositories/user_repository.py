"""
Repository for User model data access operations.
"""
from typing import Optional, List
from django.db.models import QuerySet, Q
from django.utils import timezone
from datetime import timedelta
from django.db.models.functions import Lower

from accounts.models import User
from .base_repository import BaseRepository


class UserRepository(BaseRepository):
    """Repository for User data access."""
    
    model = User
    
    @classmethod
    def get_by_username(cls, username: str, db_alias: str = '') -> Optional[User]:
        """
        Get user by username (case-insensitive).
        
        Args:
            username: Username to search for
            db_alias: Database alias to use
            
        Returns:
            User object or None
        """
        return cls.model.objects.using(db_alias or None).get(username__iexact=username)
    
    @classmethod
    def get_by_email(cls, email: str, db_alias: str = '') -> Optional[User]:
        """
        Get user by email (case-insensitive).
        
        Args:
            email: Email to search for
            db_alias: Database alias to use
            
        Returns:
            User object or None
        """
        return cls.model.objects.using(db_alias or None).get(email__iexact=email)
    
    @classmethod
    def get_by_phone_number(cls, phone_number: str, db_alias: str = '') -> Optional[User]:
        """
        Get user by phone number.
        
        Args:
            phone_number: Phone number to search for
            db_alias: Database alias to use
            
        Returns:
            User object or None
        """
        try:
            return cls.model.objects.using(db_alias or None).get(user_phone_number=phone_number)
        except cls.model.DoesNotExist:
            return None
    
    @classmethod
    def get_by_cin(cls, cin: str, db_alias: str = '') -> Optional[User]:
        """
        Get user by CIN (national ID).
        
        Args:
            cin: CIN to search for
            db_alias: Database alias to use
            
        Returns:
            User object or None
        """
        try:
            return cls.model.objects.using(db_alias or None).get(user_cin=cin)
        except cls.model.DoesNotExist:
            return None
    
    @classmethod
    def get_active_users(cls, db_alias: str = '') -> QuerySet:
        """
        Get all active users.
        
        Args:
            db_alias: Database alias to use
            
        Returns:
            QuerySet of active users
        """
        return cls.filter(is_active=True, is_user_deleted=False, db_alias=db_alias)
    
    @classmethod
    def get_inactive_users(cls, db_alias: str = '') -> QuerySet:
        """
        Get all inactive or deleted users.
        
        Args:
            db_alias: Database alias to use
            
        Returns:
            QuerySet of inactive/deleted users
        """
        return cls.filter(Q(is_active=False) | Q(is_user_deleted=True), db_alias=db_alias)
    
    @classmethod
    def get_verified_email_users(cls, db_alias: str = '') -> QuerySet:
        """
        Get users with verified emails.
        
        Args:
            db_alias: Database alias to use
            
        Returns:
            QuerySet of users with verified emails
        """
        return cls.filter(is_user_email_validated=True, db_alias=db_alias)
    
    @classmethod
    def get_unverified_email_users(cls, db_alias: str = '') -> QuerySet:
        """
        Get users with unverified emails.
        
        Args:
            db_alias: Database alias to use
            
        Returns:
            QuerySet of users with unverified emails
        """
        return cls.filter(is_user_email_validated=False, is_active=True, db_alias=db_alias)
    
    @classmethod
    def get_verified_phone_users(cls, db_alias: str = '') -> QuerySet:
        """
        Get users with verified phone numbers.
        
        Args:
            db_alias: Database alias to use
            
        Returns:
            QuerySet of users with verified phone numbers
        """
        return cls.filter(is_user_phone_number_validated=True, db_alias=db_alias)
    
    @classmethod
    def get_by_country(cls, country: str, db_alias: str = '') -> QuerySet:
        """
        Get users by country.
        
        Args:
            country: Country code or name
            db_alias: Database alias to use
            
        Returns:
            QuerySet of users from the country
        """
        return cls.filter(user_country=country, db_alias=db_alias)
    
    @classmethod
    def get_by_gender(cls, gender: str, db_alias: str = '') -> QuerySet:
        """
        Get users by gender.
        
        Args:
            gender: Gender value
            db_alias: Database alias to use
            
        Returns:
            QuerySet of users with the gender
        """
        return cls.filter(user_gender=gender, db_alias=db_alias)
    
    @classmethod
    def get_recent_registrations(cls, days: int = 7, db_alias: str = '') -> QuerySet:
        """
        Get users registered within specified days.
        
        Args:
            days: Number of days to look back
            db_alias: Database alias to use
            
        Returns:
            QuerySet of recently registered users
        """
        date_threshold = timezone.now() - timedelta(days=days)
        return cls.filter(date_joined__gte=date_threshold, db_alias=db_alias)
    
    @classmethod
    def get_recent_logins(cls, days: int = 7, db_alias: str = '') -> QuerySet:
        """
        Get users who logged in within specified days.
        
        Args:
            days: Number of days to look back
            db_alias: Database alias to use
            
        Returns:
            QuerySet of users with recent logins
        """
        date_threshold = timezone.now() - timedelta(days=days)
        return cls.filter(last_login__gte=date_threshold, db_alias=db_alias)
    
    @classmethod
    def search_users(cls, query: str, db_alias: str = '') -> QuerySet:
        """
        Search users by username, email, first name, or last name.
        
        Args:
            query: Search query string
            db_alias: Database alias to use
            
        Returns:
            QuerySet of matching users
        """
        return cls.model.objects.using(db_alias or None).filter(
            Q(username__icontains=query) |
            Q(email__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        )
    
    @classmethod
    def username_exists(cls, username: str, db_alias: str = '') -> bool:
        """
        Check if username exists (case-insensitive).
        
        Args:
            username: Username to check
            db_alias: Database alias to use
            
        Returns:
            True if exists, False otherwise
        """
        return cls.model.objects.using(db_alias or None).filter(username__iexact=username).exists()
    
    @classmethod
    def email_exists(cls, email: str, db_alias: str = '') -> bool:
        """
        Check if email exists (case-insensitive).
        
        Args:
            email: Email to check
            db_alias: Database alias to use
            
        Returns:
            True if exists, False otherwise
        """
        return cls.model.objects.using(db_alias or None).filter(email__iexact=email).exists()
    
    @classmethod
    def phone_number_exists(cls, phone_number: str, db_alias: str = '') -> bool:
        """
        Check if phone number exists.
        
        Args:
            phone_number: Phone number to check
            db_alias: Database alias to use
            
        Returns:
            True if exists, False otherwise
        """
        return cls.exists(user_phone_number=phone_number, db_alias=db_alias)
    
    @classmethod
    def cin_exists(cls, cin: str, db_alias: str = '') -> bool:
        """
        Check if CIN exists.
        
        Args:
            cin: CIN to check
            db_alias: Database alias to use
            
        Returns:
            True if exists, False otherwise
        """
        return cls.exists(user_cin=cin, db_alias=db_alias)
    
    @classmethod
    def create_user(cls, username: str, email: str, password: str, db_alias: str = '', **extra_fields) -> User:
        """
        Create a new user with password hashing.
        
        Args:
            username: Username
            email: Email address
            password: Plain text password (will be hashed)
            db_alias: Database alias to use
            **extra_fields: Additional user fields
            
        Returns:
            Created user instance
        """
        manager = cls.model.objects.db_manager(db_alias) if db_alias else cls.model.objects
        return manager.create_user(
            username=username,
            email=email,
            password=password,
            **extra_fields
        )
    
    @classmethod
    def create_superuser(cls, username: str, email: str, password: str, db_alias: str = '', **extra_fields) -> User:
        """
        Create a new superuser.
        
        Args:
            username: Username
            email: Email address
            password: Plain text password (will be hashed)
            db_alias: Database alias to use
            **extra_fields: Additional user fields
            
        Returns:
            Created superuser instance
        """
        manager = cls.model.objects.db_manager(db_alias) if db_alias else cls.model.objects
        return manager.create_superuser(
            username=username,
            email=email,
            password=password,
            **extra_fields
        )
    
    @classmethod
    def update_last_login(cls, user_id: int, db_alias: str = '') -> Optional[User]:
        """
        Update user's last login timestamp.
        
        Args:
            user_id: User ID
            db_alias: Database alias to use
            
        Returns:
            Updated user or None
        """
        return cls.update(user_id, last_login=timezone.now(), db_alias=db_alias)
    
    @classmethod
    def update_verification_code(cls, user_id: int, code: str, db_alias: str = '') -> Optional[User]:
        """
        Update user's phone verification code.
        
        Args:
            user_id: User ID
            code: Verification code
            db_alias: Database alias to use
            
        Returns:
            Updated user or None
        """
        return cls.update(
            user_id,
            user_phone_number_verification_code=code,
            user_phone_number_verification_code_generated_at=timezone.now(),
            db_alias=db_alias
        )
    
    @classmethod
    def verify_email(cls, user_id: int, db_alias: str = '') -> Optional[User]:
        """
        Mark user's email as verified.
        
        Args:
            user_id: User ID
            db_alias: Database alias to use
            
        Returns:
            Updated user or None
        """
        return cls.update(user_id, is_user_email_validated=True, db_alias=db_alias)
    
    @classmethod
    def verify_phone_number(cls, user_id: int, verified_by: str = '', db_alias: str = '') -> Optional[User]:
        """
        Mark user's phone number as verified.
        
        Args:
            user_id: User ID
            verified_by: Verification method (sms, whatsapp, etc.)
            db_alias: Database alias to use
            
        Returns:
            Updated user or None
        """
        user = cls.get_by_id(user_id, db_alias=db_alias)
        data = {
            'is_user_phone_number_validated': True,
            'user_phone_number': user.user_phone_number_to_verify,
            'user_phone_number_to_verify': '',
            'user_phone_number_verification_code': '',
        }
        if verified_by:
            data['user_phone_number_verified_by'] = verified_by
        return cls.update(user_id, db_alias=db_alias, **data)
    
    @classmethod
    def soft_delete(cls, user_id: int, db_alias: str = '') -> Optional[User]:
        """
        Soft delete a user (mark as deleted and inactive).
        
        Args:
            user_id: User ID
            db_alias: Database alias to use
            
        Returns:
            Updated user or None
        """
        return cls.update(user_id, is_user_deleted=True, is_active=False, db_alias=db_alias)
    
    @classmethod
    def activate_user(cls, user_id: int, db_alias: str = '') -> Optional[User]:
        """
        Activate a user account.
        
        Args:
            user_id: User ID
            db_alias: Database alias to use
            
        Returns:
            Updated user or None
        """
        return cls.update(user_id, is_active=True, is_user_deleted=False, db_alias=db_alias)
    
    @classmethod
    def deactivate_user(cls, user_id: int, db_alias: str = '') -> Optional[User]:
        """
        Deactivate a user account.
        
        Args:
            user_id: User ID
            db_alias: Database alias to use
            
        Returns:
            Updated user or None
        """
        return cls.update(user_id, is_active=False, db_alias=db_alias)
    
    @classmethod
    def get_statistics(cls, db_alias: str = '') -> dict:
        """
        Get user statistics.
        
        Args:
            db_alias: Database alias to use
            
        Returns:
            Dictionary with various statistics
        """
        return {
            'total_users': cls.count(db_alias=db_alias),
            'active_users': cls.count(is_active=True, is_user_deleted=False, db_alias=db_alias),
            'inactive_users': cls.get_inactive_users(db_alias=db_alias).count(),
            'verified_emails': cls.count(is_user_email_validated=True, db_alias=db_alias),
            'unverified_emails': cls.count(is_user_email_validated=False, db_alias=db_alias),
            'verified_phones': cls.count(is_user_phone_number_validated=True, db_alias=db_alias),
            'recent_registrations_7d': cls.get_recent_registrations(7, db_alias=db_alias).count(),
            'recent_registrations_30d': cls.get_recent_registrations(30, db_alias=db_alias).count(),
            'recent_logins_7d': cls.get_recent_logins(7, db_alias=db_alias).count(),
            'recent_logins_30d': cls.get_recent_logins(30, db_alias=db_alias).count(),
        }
