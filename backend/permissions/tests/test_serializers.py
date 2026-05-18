"""Tests for permissions serializers."""
from django.test import TestCase

from accounts.models import User
from permissions.constants import PERMISSION_CODENAMES
from permissions.models import UserPermission
from permissions.serializers import (
	SetUserPermissionsSerializer,
	UserPermissionSerializer,
	UserWithPermissionsSerializer,
)


class PermissionsSerializersTest(TestCase):
	"""Serializer tests for the permissions app."""

	def setUp(self):
		# Primary user plus acting admin for granted_by checks.
		self.user = User.objects.create_user(
			username='serializer_user',
			email='serializer_user@example.com',
			password='password123',
		)
		self.admin = User.objects.create_user(
			username='serializer_admin',
			email='serializer_admin@example.com',
			password='password123',
		)

	def test_user_permission_serializer_returns_granted_by_username(self):
		"""granted_by_username is populated when granted_by exists."""
		# Arrange a permission record granted by an admin user.
		row = UserPermission.objects.create(
			user=self.user,
			codename=PERMISSION_CODENAMES[0],
			granted=True,
			granted_by=self.admin,
		)

		# Serializer should expose the username helper field.
		serializer = UserPermissionSerializer(row)
		self.assertEqual(serializer.data['granted_by_username'], self.admin.username)

	def test_user_permission_serializer_granted_by_username_is_none(self):
		"""granted_by_username is None when granted_by is null."""
		# Arrange a permission row without granted_by.
		row = UserPermission.objects.create(
			user=self.user,
			codename=PERMISSION_CODENAMES[0],
			granted=True,
			granted_by=None,
		)

		# Helper field should be null-safe.
		serializer = UserPermissionSerializer(row)
		self.assertIsNone(serializer.data['granted_by_username'])

	def test_set_user_permissions_serializer_valid(self):
		"""List of known codenames is valid."""
		# Known codename should pass choice validation.
		serializer = SetUserPermissionsSerializer(data={'permissions': [PERMISSION_CODENAMES[0]]})
		self.assertTrue(serializer.is_valid(), serializer.errors)

	def test_set_user_permissions_serializer_invalid_codename(self):
		"""Unknown codename is rejected."""
		# Unknown codename must trigger a field-level validation error.
		serializer = SetUserPermissionsSerializer(data={'permissions': ['unknown_permission']})
		self.assertFalse(serializer.is_valid())
		self.assertIn('permissions', serializer.errors)

	def test_user_with_permissions_serializer_only_returns_granted(self):
		"""UserWithPermissionsSerializer returns granted codenames only."""
		# One granted + one denied row for the same user.
		granted_code = PERMISSION_CODENAMES[0]
		denied_code = PERMISSION_CODENAMES[1]
		UserPermission.objects.create(
			user=self.user,
			codename=granted_code,
			granted=True,
			granted_by=self.admin,
		)
		UserPermission.objects.create(
			user=self.user,
			codename=denied_code,
			granted=False,
			granted_by=self.admin,
		)

		# Serializer should return granted entries only.
		serializer = UserWithPermissionsSerializer(self.user, context={'db_alias': 'default'})
		self.assertEqual(serializer.data['permissions'], [granted_code])

