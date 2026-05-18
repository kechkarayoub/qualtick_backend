"""Tests for permissions API views."""
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import User
from permissions.constants import AVAILABLE_PERMISSIONS, PERMISSION_CODENAMES
from permissions.models import UserPermission


class PermissionsViewsTest(TestCase):
	"""API tests for permissions endpoints."""

	def setUp(self):
		# DRF client used across all endpoint tests.
		self.client = APIClient()

		# User with manage_permissions for admin endpoints.
		self.manager = User.objects.create_user(
			username='perm_manager',
			email='perm_manager@example.com',
			password='password123',
			first_name='Manager',
			last_name='Alpha',
		)
		# Normal user whose permissions are queried/updated.
		self.target = User.objects.create_user(
			username='perm_target',
			email='perm_target@example.com',
			password='password123',
			first_name='Target',
			last_name='Bravo',
		)
		# Soft-deleted user used to verify list filtering.
		self.deleted_user = User.objects.create_user(
			username='perm_deleted',
			email='perm_deleted@example.com',
			password='password123',
			first_name='Deleted',
			last_name='Charlie',
			is_user_deleted=True,
		)

		# Seed baseline permission rows for authorization and serialization tests.
		UserPermission.objects.create(
			user=self.manager,
			codename='manage_permissions',
			granted=True,
			granted_by=self.manager,
		)
		UserPermission.objects.create(
			user=self.target,
			codename='view_dashboard',
			granted=True,
			granted_by=self.manager,
		)
		UserPermission.objects.create(
			user=self.target,
			codename='manage_users',
			granted=False,
			granted_by=self.manager,
		)

	def test_my_permissions_requires_authentication(self):
		"""GET /api/permissions/me/ returns 401 without auth."""
		# Endpoint is IsAuthenticated-protected.
		response = self.client.get('/api/permissions/me/')
		self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

	def test_my_permissions_returns_current_user_permissions(self):
		"""GET /api/permissions/me/ returns the caller's granted permissions."""
		# Authenticate as regular target user.
		self.client.force_authenticate(user=self.target)

		response = self.client.get('/api/permissions/me/')

		# Response should include granted permissions only.
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertTrue(response.data['success'])
		self.assertEqual(response.data['permissions'], ['view_dashboard'])
		self.assertFalse(response.data['is_superuser'])

	def test_available_permissions_returns_all_constants(self):
		"""GET /api/permissions/available/ returns all available permission entries."""
		# Any authenticated user can fetch available permission catalog.
		self.client.force_authenticate(user=self.target)

		response = self.client.get('/api/permissions/available/')

		# Returned codenames should match constants exactly.
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertTrue(response.data['success'])
		returned_codenames = [entry['codename'] for entry in response.data['permissions']]
		self.assertCountEqual(returned_codenames, [item[0] for item in AVAILABLE_PERMISSIONS])

	def test_user_permissions_list_requires_manage_permissions(self):
		"""GET /api/permissions/users/ returns 403 without manage_permissions."""
		# Target user lacks manage_permissions grant.
		self.client.force_authenticate(user=self.target)

		response = self.client.get('/api/permissions/users/')

		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

	def test_user_permissions_list_returns_active_users_with_permissions(self):
		"""GET /api/permissions/users/ excludes deleted users and includes permission list."""
		# Manager has access to list endpoint.
		self.client.force_authenticate(user=self.manager)

		response = self.client.get('/api/permissions/users/')

		# Deleted users should be excluded from listing.
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertTrue(response.data['success'])
		users = response.data['users']
		returned_usernames = [row['username'] for row in users]

		self.assertIn(self.manager.username, returned_usernames)
		self.assertIn(self.target.username, returned_usernames)
		self.assertNotIn(self.deleted_user.username, returned_usernames)

		# Permissions field must include only granted rows.
		target_payload = next(row for row in users if row['id'] == self.target.id)
		self.assertEqual(target_payload['permissions'], ['view_dashboard'])

	def test_user_permissions_detail_not_found(self):
		"""GET /api/permissions/users/<id>/ returns 404 for missing user."""
		# Manager is authenticated and authorized.
		self.client.force_authenticate(user=self.manager)

		response = self.client.get('/api/permissions/users/999999/')

		self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
		self.assertFalse(response.data['success'])

	def test_user_permissions_detail_success(self):
		"""GET /api/permissions/users/<id>/ returns single user with permissions."""
		# Happy path for detail endpoint.
		self.client.force_authenticate(user=self.manager)

		response = self.client.get(f'/api/permissions/users/{self.target.id}/')

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertTrue(response.data['success'])
		self.assertEqual(response.data['user']['id'], self.target.id)
		self.assertEqual(response.data['user']['permissions'], ['view_dashboard'])

	def test_put_user_permissions_without_user_id_returns_bad_request(self):
		"""PUT /api/permissions/users/ returns 400 when user_id is missing."""
		# Endpoint requires user_id in URL.
		self.client.force_authenticate(user=self.manager)

		response = self.client.put('/api/permissions/users/', {'permissions': []}, format='json')

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

	def test_put_user_permissions_invalid_payload(self):
		"""PUT /api/permissions/users/<id>/ returns 400 for invalid permission code."""
		# Invalid codename should fail serializer validation.
		self.client.force_authenticate(user=self.manager)

		response = self.client.put(
			f'/api/permissions/users/{self.target.id}/',
			{'permissions': ['invalid_permission']},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertFalse(response.data['success'])
		self.assertIn('errors', response.data)

	def test_put_user_permissions_replaces_existing_permissions(self):
		"""PUT /api/permissions/users/<id>/ replaces permission set for target user."""
		# Manager can replace all target permissions in one call.
		self.client.force_authenticate(user=self.manager)
		new_permissions = ['manage_users', 'view_audit_logs']

		response = self.client.put(
			f'/api/permissions/users/{self.target.id}/',
			{'permissions': new_permissions},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertTrue(response.data['success'])
		self.assertCountEqual(response.data['permissions'], new_permissions)

		# DB should reflect the new set only.
		saved_codes = list(
			UserPermission.objects.filter(user=self.target, granted=True).values_list(
				'codename', flat=True
			)
		)
		self.assertCountEqual(saved_codes, new_permissions)

	def test_put_user_permissions_returns_404_for_missing_user(self):
		"""PUT /api/permissions/users/<id>/ returns 404 when target user doesn't exist."""
		# Authorized requester, non-existing target ID.
		self.client.force_authenticate(user=self.manager)

		response = self.client.put(
			'/api/permissions/users/999999/',
			{'permissions': [PERMISSION_CODENAMES[0]]},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
		self.assertFalse(response.data['success'])

