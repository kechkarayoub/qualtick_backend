"""Service layer for permission business logic."""
from typing import Iterable, Optional

from django.conf import settings
from django.db import transaction

from permissions.constants import PERMISSION_CODENAMES
from permissions.models import UserPermission


class PermissionService:
    """Central service for checking and managing user permissions."""

    @staticmethod
    def get_user_permissions(user, db_alias: str = '') -> list[str]:
        """Return the list of granted codenames for *user*.

        Superusers implicitly hold every permission.
        """
        if user.is_superuser:
            # Superusers implicitly own all codenames.
            return list(PERMISSION_CODENAMES)
        # Empty alias means default database.
        using = db_alias or None
        qs = UserPermission.objects.using(using).filter(user=user, granted=True).values_list(
            'codename', flat=True
        )
        return list(qs)

    @staticmethod
    def has_permission(user, codename: str, db_alias: str = '') -> bool:
        """Return True if *user* holds *codename*."""
        if user.is_superuser:
            return True
        # Keep query routed to request/user-specific DB.
        using = db_alias or None
        return UserPermission.objects.using(using).filter(
            user=user, codename=codename, granted=True
        ).exists()

    @staticmethod
    def has_any_permission(user, codenames: Iterable[str], db_alias: str = '') -> bool:
        """Return True if *user* holds at least one of *codenames*."""
        if user.is_superuser:
            return True
        # Convert iterables once before ORM filtering.
        using = db_alias or None
        return UserPermission.objects.using(using).filter(
            user=user, codename__in=list(codenames), granted=True
        ).exists()

    @staticmethod
    def has_all_permissions(user, codenames: Iterable[str], db_alias: str = '') -> bool:
        """Return True if *user* holds ALL of *codenames*."""
        if user.is_superuser:
            return True
        # Compare granted count against requested count.
        codename_list = list(codenames)
        using = db_alias or None
        count = UserPermission.objects.using(using).filter(
            user=user, codename__in=codename_list, granted=True
        ).count()
        return count == len(codename_list)

    @staticmethod
    @transaction.atomic
    def set_user_permissions(
        target_user,
        codenames: Iterable[str],
        granted_by,
        db_alias: str = '',
    ) -> list[str]:
        """Replace the full permission set for *target_user*.

        Codenames present in *codenames* → granted=True.
        Codenames previously granted but absent from *codenames* → deleted.
        Returns the final list of granted codenames.
        """
        codename_set = set(codenames) & set(PERMISSION_CODENAMES)
        # Normalize alias for Django `.using(...)`.
        db_alias = db_alias or None

        # Full replacement strategy: clear then bulk-create.
        UserPermission.objects.using(db_alias).filter(user=target_user).delete()

        rows = [
            UserPermission(
                user=target_user,
                codename=code,
                granted=True,
                granted_by=granted_by,
            )
            for code in codename_set
        ]
        UserPermission.objects.using(db_alias).bulk_create(rows, ignore_conflicts=True)
        return list(codename_set)

    @staticmethod
    @transaction.atomic
    def grant_permission(target_user, codename: str, granted_by, db_alias: str = '') -> bool:
        """Grant a single permission. Returns True if newly created."""
        if codename not in PERMISSION_CODENAMES:
            return False
        # Normalize alias and upsert permission row.
        db_alias = db_alias or None
        obj, created = UserPermission.objects.using(db_alias).update_or_create(
            user=target_user,
            codename=codename,
            defaults={'granted': True, 'granted_by': granted_by},
        )
        return created

    @staticmethod
    @transaction.atomic
    def revoke_permission(target_user, codename: str, db_alias: str = '') -> bool:
        """Revoke a single permission. Returns True if it existed."""
        # Normalize alias and delete if present.
        db_alias = db_alias or None
        deleted, _ = UserPermission.objects.using(db_alias).filter(
            user=target_user, codename=codename
        ).delete()
        return deleted > 0
