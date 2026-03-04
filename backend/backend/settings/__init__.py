"""
Django settings module initialization.
Automatically loads the appropriate settings based on the environment.
"""

from decouple import config

# Import base settings
from .base import *

# Load environment-specific settings
pipeline = get_secret("PIPLINE", "development")

if pipeline == "production":
    from .production import *
else:
    # Default to development settings
    from .local import *
    # Adjust logging for development
    if not TEST:
        LOGGING['handlers']['file']['level'] = 'INFO'
        LOGGING['loggers']['django']['handlers'] = ['console', 'file']
        LOGGING['loggers']['backend']['handlers'] = ['console', 'file']
