"""
ASGI config for backend project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/asgi/
"""

import os

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

import backend.ws_routing
from backend.middleware.channels_jwt_middleware import query_auth_middleware_stack

# Set the default Django settings module for the 'asgi' application
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

# ✅ Initialize Django before importing any routing/consumers
django_asgi_app = get_asgi_application()

# Define the ASGI application with support for both HTTP and WebSocket protocols
application = ProtocolTypeRouter({
    # Route traditional HTTP requests to Django's ASGI application
    "http": django_asgi_app,
    # Route WebSocket requests to the custom JWT AuthMiddleware and URLRouter
    "websocket": query_auth_middleware_stack(
        URLRouter(
            backend.ws_routing.websocket_urlpatterns # WebSocket URL patterns
        )
    ),
})
