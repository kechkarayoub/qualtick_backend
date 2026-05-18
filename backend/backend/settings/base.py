"""
Base Django settings for backend project.
This file contains settings that are common to all environments.
"""

import sys
from datetime import timedelta
from pathlib import Path
from decouple import config

from django.utils.translation import gettext_lazy as _


def get_secret(secret_id, backup=None):
    """
    Get secret from environment variables with fallback.
    
    Args:
        secret_id (str): The environment variable name
        backup: Default value if environment variable is not set
        
    Returns:
        The environment variable value or backup
    """
    return config(secret_id, default=backup)


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent
PARENT_DIR = BASE_DIR

# Check if we're running tests
TEST = 'test' in sys.argv


# Application definition
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'corsheaders',
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'channels',
]

LOCAL_APPS = [
    'accounts',
    'i18n_switcher',
    'backend',
    'permissions',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS


# Middleware
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'accounts.middleware.TimezoneMiddleware',
    'backend.middleware.audit_log_middleware.AuditLogMiddleware',
]

# URL configuration
ROOT_URLCONF = 'backend.urls'

# Templates
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'templates',
            BASE_DIR / 'accounts' / 'templates',
            BASE_DIR / 'backend' / 'templates',
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.i18n',
            ],
        },
    },
]

# WSGI/ASGI
WSGI_APPLICATION = 'backend.wsgi.application'
ASGI_APPLICATION = 'backend.asgi.application'

# Custom user model
AUTH_USER_MODEL = 'accounts.User'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en'
TIME_ZONE = 'Africa/Casablanca'
USE_I18N = True
USE_TZ = True

LANGUAGES = [
    ('ar', _('Arabic')),
    ('en', _('English')),
    ('fr', _('French')),
]

# Directory for language files
LOCALE_PATHS = [
    BASE_DIR / 'accounts' / 'locale',
    BASE_DIR / 'i18n_switcher' / 'locale',
    BASE_DIR / 'backend' / 'locale',
]

BACKEND_ENDPOINT = get_secret("BACKEND_ENDPOINT")
FRONTEND_ENDPOINT = get_secret("FRONTEND_ENDPOINT", "")

# Google OAuth settings
GOOGLE_SIGN_IN_WEB_CLIENT_ID = get_secret("GOOGLE_SIGN_IN_WEB_CLIENT_ID", "")

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files
MEDIA_URL = '/media/'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'accounts.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.MultiPartParser',
        'rest_framework.parsers.FormParser',
    ],
}

# JWT Configuration
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
    'JTI_CLAIM': 'jti',
    'SLIDING_TOKEN_REFRESH_EXP_CLAIM': 'refresh_exp',
    'SLIDING_TOKEN_LIFETIME': timedelta(minutes=5),
    'SLIDING_TOKEN_REFRESH_LIFETIME': timedelta(days=1),
}

# CORS Configuration
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
    'x-device-id',
]

# Application constants
COMPANY_ADDRESS = get_secret("COMPANY_ADDRESS", "")
APPLICATION_NAME = "QUALTICK"
DEFAULT_PHONE_NUMBER_COUNTRY_CODE = "MA"
MINIMUM_AGE_ALLOWED_FOR_USERS = 12

# Phone number verification settings
PHONE_NUMBER_VERIFICATION_REQUIRED = True
NUMBER_MINUTES_BEFORE_PHONE_NUMBER_VERIFICATION_CODE_EXPIRATION = 60
PHONE_NUMBER_VERIFICATION_CODE_QUOTA = 3

# Logging configuration
def get_logging_config():
    """Get logging configuration."""
    log_dir = BASE_DIR / 'logs'
    log_dir.mkdir(exist_ok=True)
    return {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'verbose': {
                'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
                'style': '{',
            },
            'simple': {
                'format': '{levelname} {message}',
                'style': '{',
            },
        },
        'handlers': {
            'console': {
                'level': 'INFO',
                'class': 'logging.StreamHandler',
                'formatter': 'simple',
            },
            'file': {
                'level': 'WARNING',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': log_dir / 'application.log',
                'maxBytes': 1024 * 1024 * 5,  # 5 MB
                'backupCount': 10,
                'formatter': 'verbose',
            },
            'error_file': {
                'level': 'ERROR',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': log_dir / 'errors.log',
                'maxBytes': 1024 * 1024 * 5,  # 5 MB
                'backupCount': 10,
                'formatter': 'verbose',
            },
        },
        'loggers': {
            'django': {
                'handlers': ['console', 'file'],
                'level': 'INFO',
                'propagate': True,
            },
            'backend': {
                'handlers': ['console', 'file', 'error_file'],
                'level': 'DEBUG',
                'propagate': False,
            },
        },
    }

LOGGING = get_logging_config()

# Firebase configuration
FIREBASE_CREDENTIALS_PATH = PARENT_DIR / "firebase-service-account.json"

# Performance monitoring
# This should be False in normal production
PERFORMANCE_MONITORING = get_secret("PERFORMANCE_MONITORING", "false").lower() == "true"

# API Rate limiting
API_RATE_LIMIT = get_secret("API_RATE_LIMIT", "1500/hour")  # requests per hour
API_BURST_LIMIT = get_secret("API_BURST_LIMIT", "15/second")  # burst requests

# Default cookie settings (can be overridden in environment-specific files)
# These will be overridden in local.py and production.py

# Default database alias
DEFAULT_DB_ALIAS = 'default'

