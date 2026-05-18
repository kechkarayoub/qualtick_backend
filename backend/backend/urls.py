"""
URL configuration for backend project.
"""

from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from .views import (
    get_geolocation, 
    health_check, 
    api_info, 
    contact_message_create,
    contact_message_list,
    contact_message_detail,
    contact_message_update_status,
    contact_message_statistics,
    audit_log_list,
    audit_log_detail,
    audit_log_statistics,
)


# API endpoints (no i18n)
api_patterns = [
    path('api/health/', health_check, name='health_check'),
    path('api/info/', api_info, name='api_info'),
    path('api/geolocation/', get_geolocation, name="geolocation_info"),
    path('api/contact/', contact_message_create, name='contact_message_create'),
    path('api/contact/messages/', contact_message_list, name='contact_message_list'),
    path('api/contact/messages/<int:message_id>/', contact_message_detail, name='contact_message_detail'),
    path('api/contact/messages/<int:message_id>/status/', contact_message_update_status, name='contact_message_update_status'),
    path('api/contact/statistics/', contact_message_statistics, name='contact_message_statistics'),
    path('api/audit-logs/', audit_log_list, name='audit_log_list'),
    path('api/audit-logs/statistics/', audit_log_statistics, name='audit_log_statistics'),
    path('api/audit-logs/<int:log_id>/', audit_log_detail, name='audit_log_detail'),
    path('accounts/', include('accounts.urls')),
    path('api/permissions/', include('permissions.urls')),
]

# Main URL patterns
urlpatterns = [
    path('', include(api_patterns)),
    path('i18n/', include('django.conf.urls.i18n')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Internationalized patterns
urlpatterns += i18n_patterns(
    re_path(r'^admin/', admin.site.urls),
    prefix_default_language=True
)

# Add debug toolbar URLs in development
if settings.DEBUG and hasattr(settings, 'INTERNAL_IPS') and\
    'debug_toolbar' in settings.INSTALLED_APPS:
    try:
        import debug_toolbar
        urlpatterns = [
            path('__debug__/', include(debug_toolbar.urls)),
        ] + urlpatterns
    except ImportError:
        pass
