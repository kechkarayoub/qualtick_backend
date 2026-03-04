"""
Test suite for backend views.

This module contains tests for views defined in backend/views.py,
including geolocation, health check, and API info endpoints.
Also includes environment and configuration tests that relate to backend setup.
"""

import json
import os
from unittest.mock import patch

from decouple import config
from django.conf import settings
from django.test import TestCase, RequestFactory
from django.utils.translation import gettext_lazy as _
from rest_framework import status

from backend.exceptions import GeolocationException
from backend.views import get_geolocation, health_check, api_info


class EnvFileTest(TestCase):
    """Test if .env file exists and contains required environment variables."""

    def test_env_file_exists(self):
        """Test that the .env file exists in the project root."""
        env_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
        self.assertTrue(os.path.exists(env_path), "⚠️ .env file is missing!")

    def test_required_env_variables(self):
        """Test that all required environment variables are set."""
        required_vars = [
            "ALLOWED_HOSTS",
            "API_BURST_LIMIT",
            "API_RATE_LIMIT",
            "BACKEND_ENDPOINT",
            "CORS_ALLOW_ALL_ORIGINS",
            "CORS_ALLOWED_ORIGINS",
            "DB_CONTAINER_EXTERNAL_PORT",
            "DB_CONTAINER_INTERNAL_PORT",
            "DB_IP",
            "DB_NAME",
            "DB_ROOT_PASSWORD",
            "DB_USER_NM",
            "DB_USER_PW",
            "DEFAULT_FROM_EMAIL",
            "DJANGO_CONTAINER_EXTERNAL_PORT",
            "DJANGO_CONTAINER_INTERNAL_PORT",
            "DJANGO_SECRET_KEY",
            "EMAIL_HOST",
            "EMAIL_PORT",
            "EMAIL_HOST_PASSWORD",
            "EMAIL_HOST_USER",
            "EMAIL_USE_TLS",
            "ENABLE_EMAIL_VERIFICATION",
            "ENABLE_PHONE_NUMBER_VERIFICATION",
            "FIREBASE_PROJECT_ID",
            "FIREBASE_VAPID_KEY",
            "FRONTEND_ENDPOINT",
            "PERFORMANCE_MONITORING",
            "PIPLINE",
            "REDIS_CONTAINER_EXTERNAL_PORT",
            "REDIS_CONTAINER_INTERNAL_PORT",
            "REDIS_URL",
            "TECHNICAL_SERVICE_EMAIL",
            "USE_DEBUG_TOOLBAR",
            "WHATSAPP_INSTANCE_ID",
            "WHATSAPP_INSTANCE_TOKEN",
            "WHATSAPP_INSTANCE_URL",
            "WS_EXTERNAL_PORT",
            "WS_INTERNAL_PORT",
        ]

        missing_vars = [var for var in required_vars if not config(var, None)]
        self.assertEqual(
            missing_vars, [],
            f"⚠️ Missing environment variables: {', '.join(missing_vars)}"
        )


class BackendConfigTest(TestCase):
    """Test backend app configuration settings."""

    def test_firebase_credentials_path(self):
        """Test that FIREBASE_CREDENTIALS_PATH is correctly set."""
        self.assertEqual(
            str(settings.FIREBASE_CREDENTIALS_PATH),
            os.path.join(settings.PARENT_DIR, "firebase-service-account.json")
        )
        self.assertTrue(os.path.exists(settings.FIREBASE_CREDENTIALS_PATH))


class ViewsTestCase(TestCase):
    """Test view functions from backend/views.py."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()

    @patch('backend.views.GeolocationService.get_client_ip')
    @patch('backend.views.GeolocationService.get_geolocation_data')
    def test_get_geolocation_success(self, mock_geo_data, mock_get_ip):
        """Test successful geolocation request."""
        mock_get_ip.return_value = '192.168.1.1'
        mock_geo_data.return_value = {
            'country': 'France',
            'countryCode': 'FR'
        }
        request = self.factory.get('/geolocation/', {
            'requested_info': 'country,countryCode',
            'selected_language': 'fr'
        })
        response = get_geolocation(request)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['country'], 'France')
        self.assertEqual(data['countryCode'], 'FR')

    @patch('backend.views.GeolocationService.get_client_ip')
    def test_get_geolocation_failure(self, mock_get_ip):
        """Test geolocation request failure."""
        mock_get_ip.side_effect = GeolocationException("IP not found")
        request = self.factory.get('/geolocation/')
        response = get_geolocation(request)
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn('error', data)

    def test_health_check(self):
        """Test health check endpoint."""
        request = self.factory.get('/health/')
        response = health_check(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'healthy')
        self.assertNotIn('timestamp', response.data)
        self.assertNotIn('environment', response.data)

    def test_api_info(self):
        """Test API info endpoint."""
        request = self.factory.get('/api/info/')
        response = api_info(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['application'], settings.APPLICATION_NAME)
        self.assertEqual(response.data['environment'], settings.ENVIRONMENT)
        self.assertIn('version', response.data)


class GeolocationViewTests(TestCase):
    """Test the geolocation view with additional test scenarios."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()

    @patch("requests.get")
    def test_success(self, mock_get):
        """Test the successful retrieval of geolocation data."""
        # Mock API response
        mock_get.return_value.json.return_value = {
            "country": "France",
            "countryCode": "FR",
        }
        # Simulate request
        request = self.factory.get("/geolocation/")
        response = get_geolocation(request)
        data = json.loads(response.content.decode('utf-8'))
        # Assertions
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(data.get("countryCode"), "FR")
        self.assertEqual(data.get("country"), "France")

    @patch("requests.get")
    def test_invalid_ip(self, _mock_get):
        """Test handling of an invalid IP address."""
        # Simulate missing IP
        request = self.factory.get("/geolocation/?selected_language=fr", REMOTE_ADDR=None)
        response = get_geolocation(request)
        data = json.loads(response.content.decode('utf-8'))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            data.get("error"),
            _('Geolocation service unavailable. Try again later.')
        )
