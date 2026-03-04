# pylint: disable=unused-wildcard-import,wildcard-import,R0801
"""
Development settings for backend project.
"""

from .base import *


# Security settings (relaxed for development)
SECRET_KEY = get_secret("DJANGO_SECRET_KEY", "dev-secret-key-change-in-production")
DEBUG = True
ALLOWED_HOSTS = ["*"]


# Endpoints
BACKEND_ENDPOINT = get_secret("BACKEND_ENDPOINT")
FRONTEND_ENDPOINT = get_secret("FRONTEND_ENDPOINT")

# CORS settings (more permissive for development)
CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'http://localhost:8082',
    'http://127.0.0.1:3000',
    'http://127.0.0.1:8082',
    FRONTEND_ENDPOINT,
]
CORS_ALLOWED_ORIGINS = [origin for origin in CORS_ALLOWED_ORIGINS if origin]
CORS_ALLOW_ALL_ORIGINS = get_secret("CORS_ALLOW_ALL_ORIGINS", "false").lower() == "true"
CORS_ALLOW_CREDENTIALS = True

# CSRF settings for development (more permissive)
CSRF_COOKIE_SECURE = False  # Allow HTTP for development
CSRF_COOKIE_HTTPONLY = False  # Allow JavaScript access
CSRF_COOKIE_SAMESITE = 'Lax'  # Less restrictive
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:3000',
    'http://localhost:8082',
    'http://localhost:8080',
    'http://127.0.0.1:3000',
    'http://127.0.0.1:8082',
    'http://127.0.0.1:8080',
    FRONTEND_ENDPOINT,
    BACKEND_ENDPOINT,
]
CSRF_TRUSTED_ORIGINS = [origin for origin in CSRF_TRUSTED_ORIGINS if origin]

# Session cookie settings for development
SESSION_COOKIE_SECURE = False  # Allow HTTP for development
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 3600  # 1 hour

# Language cookie settings for development
LANGUAGE_COOKIE_SECURE = False  # Allow HTTP for development
LANGUAGE_COOKIE_HTTPONLY = False
LANGUAGE_COOKIE_SAMESITE = 'Lax'

# Redis and Channel Layers (using Redis for reliable group messaging)
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [("redis", 6379)],  # Use Redis container name in Docker
        },
    },
}

# Database configuration
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': get_secret("DB_NAME"),
        'USER': get_secret("DB_USER_NM"),
        'PASSWORD': get_secret("DB_USER_PW"),
        'HOST': get_secret("DB_IP", "localhost"),
        'PORT': get_secret("DB_CONTAINER_INTERNAL_PORT", "5432"),
        'OPTIONS': {
            'connect_timeout': 10,
        },
    }
}

# Email configuration (console backend for development)
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
EMAIL_HOST = get_secret("EMAIL_HOST")
EMAIL_PORT = int(get_secret("EMAIL_PORT", 587))
EMAIL_USE_TLS = get_secret("EMAIL_USE_TLS", "true").lower() == "true"
EMAIL_HOST_USER = get_secret("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = get_secret("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = get_secret("DEFAULT_FROM_EMAIL")


# Technical service email
TECHNICAL_SERVICE_EMAIL = get_secret("TECHNICAL_SERVICE_EMAIL", "")

# Feature flags
ENABLE_EMAIL_VERIFICATION = get_secret("ENABLE_EMAIL_VERIFICATION",
                                       "false").lower() == "true"
ENABLE_PHONE_NUMBER_VERIFICATION = get_secret("ENABLE_PHONE_NUMBER_VERIFICATION",
                                              "false").lower() == "true"

# Environment
ENVIRONMENT = "development"

# WhatsApp configuration
WHATSAPP_INSTANCE_ID = get_secret("WHATSAPP_INSTANCE_ID")
WHATSAPP_INSTANCE_TOKEN = get_secret("WHATSAPP_INSTANCE_TOKEN")
WHATSAPP_INSTANCE_URL = get_secret("WHATSAPP_INSTANCE_URL")

# Media configuration
MEDIA_ROOT = PARENT_DIR / 'media_dev'

# Development logging adjustments
LOGGING['handlers']['console']['level'] = 'DEBUG'
LOGGING['handlers']['file']['level'] = 'INFO'

# Debug toolbar for development (optional)
USE_DEBUG_TOOLBAR = get_secret("USE_DEBUG_TOOLBAR", "false").lower() == "true"
if DEBUG and USE_DEBUG_TOOLBAR and not TEST:
    INSTALLED_APPS += ['debug_toolbar']
    MIDDLEWARE = ['debug_toolbar.middleware.DebugToolbarMiddleware'] + MIDDLEWARE
    INTERNAL_IPS = ['127.0.0.1', 'localhost']

# Caching configuration (local memory cache for development)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
        'TIMEOUT': 300,  # 5 minutes
        'OPTIONS': {
            'MAX_ENTRIES': 1000,
            'CULL_FREQUENCY': 3,
        }
    }
}
