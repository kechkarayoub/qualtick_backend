
"""Accounts related urls"""
from django.urls import path

from .jwt_views import TokenObtainPairView, TokenRefreshView
from .views import (FCMTokenView, ForgotPasswordView, LogoutView, ResetPasswordView,
                    SendVerificationEmailLinkView, SignInThirdPartyView,
                    SignInView, SignUpThirdPartyView, SignUpView,
                    UpdateProfileView, UpdateSettingsView, verify_email,
                    verify_phone_number)

urlpatterns = [
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('send-verification-email-link/', SendVerificationEmailLinkView.as_view(),
         name='send-verification-email-link'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('sign-in/', SignInView.as_view(), name='sign-in'),
    path('sign-in-third-party/', SignInThirdPartyView.as_view(), name='sign-in-third-party'),
    path('sign-up/', SignUpView.as_view(), name='sign-up'),
    path('sign-up-third-party/', SignUpThirdPartyView.as_view(), name='sign-up-third-party'),
    path('verify-email/', verify_email, name='verify_email'),
    path('verify-phone-number/', verify_phone_number, name='verify_phone_number'),
    path('update-profile/', UpdateProfileView.as_view(), name='update-profile'),
    path('update-settings/', UpdateSettingsView.as_view(), name='update-settings'),
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot-password'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset-password'),
    path('fcm-token/', FCMTokenView.as_view(), name='fcm-token'),
]
