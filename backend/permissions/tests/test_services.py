"""Tests for permissions services."""
from django.test import TestCase

from accounts.models import User
from permissions.constants import PERMISSION_CODENAMES
from permissions.models import UserPermission
from permissions.services import PermissionService


class PermissionServiceTest(TestCase):
	"""Service tests for permissions logic."""

	def setUp(self):
		# Regular user under test.
		self.user = User.objects.create_user(
			username='service_user',
			email='service_user@example.com',
			password='password123',
		)
		# User that grants permissions in audit fields.
		self.granter = User.objects.create_user(
			username='service_granter',
			email='service_granter@example.com',
			password='password123',
		)
		# Superuser for implicit-permission behavior checks.
		self.superuser = User.objects.create_superuser(
			username='service_superuser',
			email='service_superuser@example.com',
			password='password123',
		)

	def test_get_user_permissions_for_superuser_returns_all(self):
		"""Superuser implicitly has all permissions."""
		# Superusers should not depend on stored UserPermission rows.
		perms = PermissionService.get_user_permissions(self.superuser, db_alias='default')
		self.assertCountEqual(perms, PERMISSION_CODENAMES)

	def test_get_user_permissions_for_regular_user(self):
		"""Regular user returns only granted codenames."""
		# Build one granted and one denied permission for filtering check.
		allowed = PERMISSION_CODENAMES[0]
		blocked = PERMISSION_CODENAMES[1]
		UserPermission.objects.create(
			user=self.user,
			codename=allowed,
			granted=True,
			granted_by=self.granter,
		)
		UserPermission.objects.create(
			user=self.user,
			codename=blocked,
			granted=False,
			granted_by=self.granter,
		)

		# Service should return only granted code(s).
		perms = PermissionService.get_user_permissions(self.user, db_alias='default')
		self.assertEqual(perms, [allowed])

	def test_has_permission_has_any_and_has_all(self):
		"""Single/any/all permission checks work as expected."""
		# Give user one permission and verify all three check methods.
		code_a = PERMISSION_CODENAMES[0]
		code_b = PERMISSION_CODENAMES[1]
		UserPermission.objects.create(
			user=self.user,
			codename=code_a,
			granted=True,
			granted_by=self.granter,
		)

		self.assertTrue(PermissionService.has_permission(self.user, code_a, db_alias='default'))
		self.assertFalse(PermissionService.has_permission(self.user, code_b, db_alias='default'))
		self.assertTrue(
			PermissionService.has_any_permission(self.user, [code_b, code_a], db_alias='default')
		)
		self.assertFalse(
			PermissionService.has_all_permissions(self.user, [code_a, code_b], db_alias='default')
		)

	def test_set_user_permissions_replaces_existing_and_filters_invalid(self):
		"""set_user_permissions deletes old rows and keeps only valid codenames."""
		# Existing permission should be removed after replacement.
		old_code = PERMISSION_CODENAMES[0]
		new_code = PERMISSION_CODENAMES[2]
		UserPermission.objects.create(
			user=self.user,
			codename=old_code,
			granted=True,
			granted_by=self.granter,
		)

		# Includes duplicate + invalid codename to verify sanitization.
		result = PermissionService.set_user_permissions(
			target_user=self.user,
			codenames=[new_code, 'invalid_codename', new_code],
			granted_by=self.granter,
			db_alias='default',
		)

		# Final state should contain only the valid replacement code.
		self.assertEqual(result, [new_code])
		self.assertFalse(
			UserPermission.objects.filter(user=self.user, codename=old_code).exists()
		)
		self.assertTrue(
			UserPermission.objects.filter(user=self.user, codename=new_code, granted=True).exists()
		)

	def test_grant_permission_create_then_update(self):
		"""grant_permission returns True on create, False on update."""
		# First call creates the row.
		code = PERMISSION_CODENAMES[0]
		created = PermissionService.grant_permission(
			target_user=self.user,
			codename=code,
			granted_by=self.granter,
			db_alias='default',
		)
		# Second call updates existing row metadata and returns False.
		created_again = PermissionService.grant_permission(
			target_user=self.user,
			codename=code,
			granted_by=self.superuser,
			db_alias='default',
		)

		# Assert create/update semantics and granted_by overwrite.
		self.assertTrue(created)
		self.assertFalse(created_again)
		row = UserPermission.objects.get(user=self.user, codename=code)
		self.assertTrue(row.granted)
		self.assertEqual(row.granted_by, self.superuser)

	def test_grant_permission_invalid_codename(self):
		"""grant_permission rejects unknown codename."""
		# Unknown code must short-circuit with no DB writes.
		created = PermissionService.grant_permission(
			target_user=self.user,
			codename='not_allowed',
			granted_by=self.granter,
			db_alias='default',
		)

		self.assertFalse(created)
		self.assertEqual(UserPermission.objects.filter(user=self.user).count(), 0)

	def test_revoke_permission(self):
		"""revoke_permission returns True only when a row existed."""
		# Seed one granted row to revoke.
		code = PERMISSION_CODENAMES[0]
		UserPermission.objects.create(
			user=self.user,
			codename=code,
			granted=True,
			granted_by=self.granter,
		)

		# First revoke should delete; second should report nothing deleted.
		deleted = PermissionService.revoke_permission(self.user, code, db_alias='default')
		deleted_again = PermissionService.revoke_permission(self.user, code, db_alias='default')

		self.assertTrue(deleted)
		self.assertFalse(deleted_again)

