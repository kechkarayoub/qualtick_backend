"""Service layer for AuditLog business logic."""
import logging
from typing import Optional, Any

from django.db.models import QuerySet, Count
from django.utils import timezone

from backend.models import AuditLog
from backend.repositories import AuditLogRepository

logger = logging.getLogger(__name__)

_SENSITIVE_KEYS = frozenset({
    'password', 'new_password', 'old_password', 'confirm_password',
    'token', 'access_token', 'refresh_token', 'id_token',
    'secret', 'authorization', 'credit_card', 'cvv',
})


def _sanitize(data: Any, max_depth: int = 3) -> Any:
    if max_depth <= 0:
        return '[truncated]'
    if isinstance(data, dict):
        return {
            k: '[redacted]' if k.lower() in _SENSITIVE_KEYS else _sanitize(v, max_depth - 1)
            for k, v in data.items()
        }
    if isinstance(data, (list, tuple)):
        return [_sanitize(item, max_depth - 1) for item in data]
    return data


class AuditLogService:
    """Central service for creating and querying audit log records."""

    @staticmethod
    def log(
        *,
        action: str,
        outcome: str = AuditLog.OUTCOME_SUCCESS,
        user=None,
        actor_username: str = '',
        resource_type: str = '',
        resource_id: Any = '',
        description: str = '',
        request=None,
        extra_data: Optional[dict] = None,
        db_alias: str = '',
    ) -> Optional[AuditLog]:
        ip_address = None
        user_agent = ''
        request_method = ''
        request_path = ''

        if request is not None:
            ip_address = AuditLogService._get_client_ip(request)
            user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
            request_method = request.method or ''
            request_path = request.path or ''
            if user is None and request.user.is_authenticated:
                user = request.user

        sanitized_extra = _sanitize(extra_data) if extra_data else None

        try:
            return AuditLogRepository.create_log(
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
                extra_data=sanitized_extra,
                db_alias=db_alias,
            )
        except Exception:
            logger.exception("Failed to write audit log [action=%s]", action)
            return None

    @staticmethod
    def _get_client_ip(request) -> Optional[str]:
        forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR', '')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR') or None

    @staticmethod
    def get_logs(
        *,
        user_id: Optional[int] = None,
        action: Optional[str] = None,
        outcome: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        date_from=None,
        date_to=None,
        db_alias: str = '',
    ) -> QuerySet:
        qs = AuditLogRepository.all(db_alias=db_alias).select_related('user')
        if user_id is not None:
            qs = qs.filter(user_id=user_id)
        if action:
            qs = qs.filter(action=action)
        if outcome:
            qs = qs.filter(outcome=outcome)
        if resource_type:
            qs = qs.filter(resource_type=resource_type)
        if resource_id:
            qs = qs.filter(resource_id=resource_id)
        if date_from:
            qs = qs.filter(timestamp__gte=date_from)
        if date_to:
            qs = qs.filter(timestamp__lte=date_to)
        return qs

    @staticmethod
    def get_statistics(db_alias: str = '') -> dict:
        qs = AuditLogRepository.all(db_alias=db_alias)
        now = timezone.now()
        last_24h = now - timezone.timedelta(hours=24)
        last_7d  = now - timezone.timedelta(days=7)
        last_30d = now - timezone.timedelta(days=30)

        by_action = list(
            qs.values('action').annotate(count=Count('id')).order_by('-count')
        )
        by_outcome = list(
            qs.values('outcome').annotate(count=Count('id')).order_by('-count')
        )

        return {
            'total': qs.count(),
            'last_24h': qs.filter(timestamp__gte=last_24h).count(),
            'last_7d':  qs.filter(timestamp__gte=last_7d).count(),
            'last_30d': qs.filter(timestamp__gte=last_30d).count(),
            'by_action': by_action,
            'by_outcome': by_outcome,
        }
