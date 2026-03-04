"""Firebase configuration and initialization for the backend."""
import firebase_admin
from firebase_admin import credentials

from django.conf import settings

# Initialize Firebase Admin SDK

# Check if Firebase is already initialized (prevents duplicate initialization errors)
if not firebase_admin._apps: # pylint: disable=protected-access
    # Load Firebase service account credentials from the JSON file
    cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
    # Initialize Firebase Admin SDK with the loaded credentials
    firebase_admin.initialize_app(cred)
