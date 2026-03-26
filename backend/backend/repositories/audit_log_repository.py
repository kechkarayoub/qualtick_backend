"""Repository for AuditLog data-access operations."""
from typing import Optional
from django.db.models import QuerySet

from .base_repository import BaseRepository
from backend.models import AuditLog


class AuditLogRepository(BaseRepository):
    model = AuditLog

    @classmethod
    def create_log(
        cls,
        *,
        action: str,
        outcome: str = AuditLog.OUTCOME_SUCCESS,
        user=None,
        actor_username: str = '',
        resource_type: str = '',
        resource_id: str = '',
        description: str = '',
        ip_address: Optional[str] = None,
        user_agent: str = '',
        request_method: str = '',
        request_path: str = '',
        extra_data=None,
        db_alias: str = '',
    ) -> AuditLog:
        if user is not None and not actor_username:
            actor_username = getattr(user, 'username', '') or ''
        return cls.create(
            db_alias=db_alias,
            action=action,
            outcome=outcome,
            user=user,
            actor_username=actor_username,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else '',
            description=description,
            ip_address=ip_address,
            user_agent=user_agent,
            request_method=request_method,
            request_path=request_path,
            extra_data=extra_data,
        )

    @classmethod
    def get_for_user(cls, user_id: int, db_alias: str = '') -> QuerySet:
        return cls.filter(db_alias=db_alias, user_id=user_id)

    @classmethod
    def get_for_resource(cls, resource_type: str, resource_id: str,
                         db_alias: str = '') -> QuerySet:
        return cls.filter(db_alias=db_alias, resource_type=resource_type,
                          resource_id=resource_id)

    @classmethod
    def get_recent(cls, limit: int = 100, db_alias: str = '') -> QuerySet:
        return cls.all(db_alias=db_alias).select_related('user')[:limit]
