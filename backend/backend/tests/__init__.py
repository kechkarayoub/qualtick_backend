"""
Test suite for the backend core application.

This test suite provides comprehensive coverage for:
- Model functionality (ContactMessage model)
- Serializer functionality (ContactMessage serializers)
- Service layer functionality (GeolocationService, MessageService, ValidationService, etc.)
- Repository layer functionality (ContactMessageRepository)
- Utility functions (utils.py)
- View endpoints (views.py)
- WebSocket consumers (ws_consumers.py)
- WebSocket utilities (ws_utils.py)
- Performance monitoring (monitoring.py)
- Custom exceptions (exceptions.py)
- Middleware (channels_jwt_middleware.py)

Test Structure:
- test_models.py: ContactMessage model, admin, and model-related tests
- test_serializers.py: ContactMessage serializers tests
- test_views.py: View endpoints and configuration tests
- test_utils.py: Utility functions tests
- test_exceptions.py: Custom exception tests
- test_monitoring.py: Performance and monitoring tests
- services/test_services.py: Service layer tests
- repositories/test_contact_message_repository.py: Repository layer tests
- websocket/test_ws_consumers.py: WebSocket consumer tests
- websocket/test_ws_utils.py: WebSocket utility tests
- middleware/test_channels_jwt_middleware.py: Middleware tests

Total test count: Approximately 150+ tests covering all major functionality
"""

# Model and serializer tests
from .test_models import *
from .test_serializers import *

# View and utility tests
from .test_views import *
from .test_utils import *

# Service and repository tests
from .services.test_services import *
from .repositories.test_contact_message_repository import *

# WebSocket tests
from .websocket.test_ws_consumers import *
from .websocket.test_ws_utils import *

# Middleware tests
from .middleware.test_channels_jwt_middleware import *

# Monitoring and exception tests
from .test_monitoring import *
from .test_exceptions import *

