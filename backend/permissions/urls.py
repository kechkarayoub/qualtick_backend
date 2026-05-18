"""URL configuration for the permissions app."""
from django.urls import path

from permissions.views import (
    AvailablePermissionsView,
    MyPermissionsView,
    UserPermissionsView,
)

urlpatterns = [
    # Current authenticated user's effective permissions.
    path('me/', MyPermissionsView.as_view(), name='my-permissions'),
    # Catalog of all available codenames.
    path('available/', AvailablePermissionsView.as_view(), name='available-permissions'),
    # Admin list endpoint (all active users + their permissions).
    path('users/', UserPermissionsView.as_view(), name='user-permissions-list'),
    # Admin detail/update endpoint for one user.
    path('users/<int:user_id>/', UserPermissionsView.as_view(), name='user-permissions-detail'),
]
