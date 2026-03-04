"""
URL configuration for i18n_switcher app.
"""

from django.urls import path
from . import views

app_name = 'i18n_switcher'

urlpatterns = [
    # Legacy endpoint for backward compatibility
    path('switch/', views.switch_language, name='switch_language'),

    # API endpoints
    path('api/languages/', views.LanguageApiView.as_view(), name='api_languages'),
    path('api/detect/', views.LanguageDetectionView.as_view(), name='api_detect'),
    path('api/info/', views.language_info, name='api_info'),
]
