"""Tests for permissions DRF permission classes."""
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from accounts.models import User
from permissions.drf_permissions import HasPermission, require_permission


class DummyView:
	"""Simple dummy view for permission class tests."""
	# By default this dummy does not require a specific codename.
	required_permission = None


class DRFPermissionsTest(TestCase):
	"""Tests for HasPermission and require_permission."""

	def setUp(self):
		# APIRequestFactory lets us test permission classes directly.
		self.factory = APIRequestFactory()
		self.user = User.objects.create_user(
			username='drf_user',
			email='drf_user@example.com',
			password='password123',
		)

	def test_has_permission_rejects_unauthenticated_user(self):
		"""HasPermission denies anonymous requests."""
		# Anonymous user should always fail permission checks.
		request = self.factory.get('/api/permissions/users/')
		request.user = AnonymousUser()

		allowed = HasPermission().has_permission(request, DummyView())
		self.assertFalse(allowed)

	def test_has_permission_allows_when_view_has_no_required_permission(self):
		"""HasPermission allows authenticated access when required_permission is missing."""
		# Authenticated request with no required codename should pass.
		request = self.factory.get('/api/permissions/users/')
		request.user = self.user

		allowed = HasPermission().has_permission(request, DummyView())
		self.assertTrue(allowed)

	@patch('permissions.drf_permissions.PermissionService.has_permission')
	@patch('permissions.drf_permissions.get_db_alias')
	def test_has_permission_uses_view_required_permission_and_db_alias(
		self,
		mock_get_db_alias,
		mock_has_permission,
	):
		"""HasPermission forwards codename and db_alias to service."""
		# Mock resolution path to verify delegation arguments exactly.
		mock_get_db_alias.return_value = 'default'
		mock_has_permission.return_value = True

		class ViewWithPermission:
			required_permission = 'manage_permissions'

		request = self.factory.get('/api/permissions/users/')
		request.user = self.user

		# Should call service with view.required_permission.
		allowed = HasPermission().has_permission(request, ViewWithPermission())

		self.assertTrue(allowed)
		mock_has_permission.assert_called_once_with(
			self.user,
			'manage_permissions',
			db_alias='default',
		)

	def test_require_permission_class_denies_unauthenticated(self):
		"""Class returned by require_permission denies anonymous user."""
		# Factory-generated permission class should match HasPermission auth behavior.
		perm_class = require_permission('manage_permissions')
		request = self.factory.get('/api/permissions/users/')
		request.user = AnonymousUser()

		allowed = perm_class().has_permission(request, DummyView())
		self.assertFalse(allowed)

	@patch('permissions.drf_permissions.PermissionService.has_permission')
	@patch('permissions.drf_permissions.get_db_alias')
	def test_require_permission_class_uses_codename_and_db_alias(
		self,
		mock_get_db_alias,
		mock_has_permission,
	):
		"""Class returned by require_permission forwards codename and db alias."""
		# Mock helpers so we can assert codename/db_alias handoff.
		mock_get_db_alias.return_value = 'default'
		mock_has_permission.return_value = True

		perm_class = require_permission('view_dashboard')
		request = self.factory.get('/api/permissions/users/')
		request.user = self.user

		# Generated class should enforce the provided codename.
		allowed = perm_class().has_permission(request, DummyView())

		self.assertTrue(allowed)
		self.assertEqual(perm_class.message, 'Permission required: view_dashboard')
		mock_has_permission.assert_called_once_with(
			self.user,
			'view_dashboard',
			db_alias='default',
		)

