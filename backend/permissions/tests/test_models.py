"""Tests for permissions models."""
from django.db import IntegrityError, transaction
from django.test import TestCase

from accounts.models import User
from permissions.constants import PERMISSION_CODENAMES
from permissions.models import UserPermission


class UserPermissionModelTest(TestCase):
	"""Model tests for UserPermission."""

	def setUp(self):
		# Shared actors used by all model scenarios.
		self.user = User.objects.create_user(
			username='model_user',
			email='model_user@example.com',
			password='password123',
		)
		self.admin = User.objects.create_user(
			username='model_admin',
			email='model_admin@example.com',
			password='password123',
		)

	def test_string_representation_for_grant_and_deny(self):
		"""__str__ returns GRANT/DENY format."""
		# Create one granted and one denied row to verify both formats.
		granted = UserPermission.objects.create(
			user=self.user,
			codename=PERMISSION_CODENAMES[0],
			granted=True,
			granted_by=self.admin,
		)
		denied = UserPermission.objects.create(
			user=self.user,
			codename=PERMISSION_CODENAMES[1],
			granted=False,
			granted_by=self.admin,
		)

		# Assert exact output contract expected by admins/debug logs.
		self.assertEqual(str(granted), f'GRANT {PERMISSION_CODENAMES[0]} → {self.user.id}')
		self.assertEqual(str(denied), f'DENY {PERMISSION_CODENAMES[1]} → {self.user.id}')

	def test_unique_together_on_user_and_codename(self):
		"""Cannot create two rows with same (user, codename)."""
		# First insert succeeds.
		UserPermission.objects.create(
			user=self.user,
			codename=PERMISSION_CODENAMES[0],
			granted=True,
			granted_by=self.admin,
		)

		# Duplicate insert must fail due to unique_together constraint.
		with self.assertRaises(IntegrityError):
			with transaction.atomic():
				UserPermission.objects.create(
					user=self.user,
					codename=PERMISSION_CODENAMES[0],
					granted=False,
					granted_by=self.admin,
				)

