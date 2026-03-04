# pylint: disable=unused-wildcard-import,wildcard-import,R0801
"""
Production settings for backend project.
"""

from .base import *


# Security settings
SECRET_KEY = get_secret("DJANGO_SECRET_KEY")
DEBUG = False
ALLOWED_HOSTS = get_secret("ALLOWED_HOSTS", "").split(",")
ALLOWED_HOSTS = [host for host in ALLOWED_HOSTS if host]

# Security middleware settings
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# CORS settings
CORS_ALLOWED_ORIGINS = get_secret("CORS_ALLOWED_ORIGINS", "").split(",")
CORS_ALLOWED_ORIGINS = [origin for origin in CORS_ALLOWED_ORIGINS if origin]
CORS_ALLOW_CREDENTIALS = True

# CSRF settings for production
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = False  # Allow JavaScript access for admin
CSRF_COOKIE_SAMESITE = 'Lax'  # Less restrictive for admin panel
CSRF_TRUSTED_ORIGINS = get_secret("CORS_ALLOWED_ORIGINS", "").split(",")
CSRF_TRUSTED_ORIGINS = [origin for origin in CSRF_TRUSTED_ORIGINS if origin]

# Session cookie settings for production
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'  # Less restrictive for admin panel
SESSION_COOKIE_AGE = 3600  # 1 hour

# Language cookie settings for production
LANGUAGE_COOKIE_SECURE = True
LANGUAGE_COOKIE_HTTPONLY = False
LANGUAGE_COOKIE_SAMESITE = 'Lax'

# Redis and Channel Layers
REDIS_URL = get_secret("REDIS_URL")
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [REDIS_URL],
            "capacity": 1500,
            "expiry": 10,
        },
    },
}

# Endpoints
BACKEND_ENDPOINT = get_secret("BACKEND_ENDPOINT", "")
FRONTEND_ENDPOINT = get_secret("FRONTEND_ENDPOINT", "")


# Technical service email
TECHNICAL_SERVICE_EMAIL = get_secret("TECHNICAL_SERVICE_EMAIL", "")

# Feature flags
ENABLE_EMAIL_VERIFICATION = get_secret("ENABLE_EMAIL_VERIFICATION",
                                       "false").lower() == "true"
ENABLE_PHONE_NUMBER_VERIFICATION = get_secret("ENABLE_PHONE_NUMBER_VERIFICATION",
                                              "false").lower() == "true"

# Media configuration
MEDIA_ROOT = PARENT_DIR / 'media'


# Database configuration
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': get_secret("DB_NAME"),
        'USER': get_secret("DB_USER_NM"),
        'PASSWORD': get_secret("DB_USER_PW"),
        'HOST': get_secret("DB_IP"),
        'PORT': get_secret("DB_CONTAINER_INTERNAL_PORT"),
        'OPTIONS': {
            'connect_timeout': 10,
            'sslmode': 'require',
        },
        'CONN_MAX_AGE': 60,
    }
}

# Email configuration
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = get_secret("EMAIL_HOST")
EMAIL_PORT = int(get_secret("EMAIL_PORT", 587))
EMAIL_USE_TLS = get_secret("EMAIL_USE_TLS", "true").lower() == "true"
EMAIL_HOST_USER = get_secret("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = get_secret("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = get_secret("DEFAULT_FROM_EMAIL")
EMAIL_TIMEOUT = 10

# Environment
ENVIRONMENT = "production"

# WhatsApp configuration
WHATSAPP_INSTANCE_ID = get_secret("WHATSAPP_INSTANCE_ID")
WHATSAPP_INSTANCE_TOKEN = get_secret("WHATSAPP_INSTANCE_TOKEN")
WHATSAPP_INSTANCE_URL = get_secret("WHATSAPP_INSTANCE_URL")

# Caching configuration
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': REDIS_URL,
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'KEY_PREFIX': 'backend_prod',
        'TIMEOUT': 300,
    }
}

# Session configuration
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'

# Override logging for production
LOGGING['handlers']['console']['level'] = 'WARNING'
LOGGING['handlers']['file']['level'] = 'INFO'
