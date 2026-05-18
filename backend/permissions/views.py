"""Views for the permissions app."""
import logging

from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from backend.utils import get_db_alias
from permissions.constants import AVAILABLE_PERMISSIONS
from permissions.drf_permissions import require_permission
from permissions.serializers import (
    SetUserPermissionsSerializer,
    UserWithPermissionsSerializer,
)
from permissions.services import PermissionService

logger = logging.getLogger(__name__)


class MyPermissionsView(APIView):
    """GET /api/permissions/me/ — return the calling user's permissions."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Respect request-selected DB alias for permission lookup.
        db_alias = get_db_alias(request=request)
        perms = PermissionService.get_user_permissions(request.user, db_alias=db_alias)
        return Response({
            'success': True,
            'permissions': perms,
            'is_superuser': request.user.is_superuser,
        })


class AvailablePermissionsView(APIView):
    """GET /api/permissions/available/ — return all defined permission codenames."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Expose codename + translated label pairs.
        data = [{'codename': code, 'label': str(label)}
                for code, label in AVAILABLE_PERMISSIONS]
        return Response({'success': True, 'permissions': data})


class UserPermissionsView(APIView):
    """
    GET  /api/permissions/users/          — list all users with their permissions
    GET  /api/permissions/users/<user_id>/ — get one user's permissions
    PUT  /api/permissions/users/<user_id>/ — replace one user's permission set
    """

    permission_classes = [IsAuthenticated, require_permission('manage_permissions')]

    def get(self, request, user_id=None):
        # Route all ORM calls to the resolved database alias.
        db_alias = get_db_alias(request=request)

        if user_id is None:
            # List active users only.
            users = User.objects.using(db_alias or None).filter(
                is_user_deleted=False
            ).order_by('last_name', 'first_name')
            # Serializer includes computed permissions per user.
            serializer = UserWithPermissionsSerializer(users, many=True)
            return Response({'success': True, 'users': serializer.data})

        try:
            user = User.objects.using(db_alias or None).get(pk=user_id)
        except User.DoesNotExist:
            return Response(
                {'success': False, 'message': _('User not found.')},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = UserWithPermissionsSerializer(user)
        return Response({'success': True, 'user': serializer.data})

    def put(self, request, user_id=None):
        # URL must include target user id.
        if user_id is None:
            return Response(
                {'success': False, 'message': _('User ID is required.')},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Resolve alias once for all DB operations in this request.
        db_alias = get_db_alias(request=request)

        try:
            target_user = User.objects.using(db_alias or None).get(pk=user_id)
        except User.DoesNotExist:
            return Response(
                {'success': False, 'message': _('User not found.')},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = SetUserPermissionsSerializer(data=request.data)
        if not serializer.is_valid():
            # Return serializer errors in a consistent envelope.
            return Response(
                {'success': False, 'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Replace target user's full permission set.
        granted = PermissionService.set_user_permissions(
            target_user=target_user,
            codenames=serializer.validated_data['permissions'],
            granted_by=request.user,
            db_alias=db_alias,
        )

        logger.info(
            "User %s updated permissions for user %s: %s",
            request.user.username,
            target_user.username,
            granted,
        )

        return Response({
            'success': True,
            'message': _('Permissions updated successfully.'),
            'permissions': granted,
        })
