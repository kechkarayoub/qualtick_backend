"""Tests for audit log API views."""
from uuid import uuid4

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from accounts.repositories import UserRepository
from backend.models import AuditLog
from backend.repositories import AuditLogRepository
from backend.utils import get_db_alias


def _create_tokens(user):
    from accounts.tokens import RefreshToken
    refresh = RefreshToken.for_user(user)
    return str(refresh.access_token)


class AuditLogListViewTest(TestCase):

    def setUp(self):
        db_alias = get_db_alias()
        suffix = uuid4().hex[:8]
        self.client = APIClient()
        self.admin = UserRepository.create_superuser(
            db_alias=db_alias,
            username=f'admin_{suffix}',
            email=f'admin_{suffix}@example.com',
            password='adminpass123',
        )
        self.admin.is_staff = True
        self.admin.save(using=db_alias or None)
        self.regular_user = UserRepository.create_user(
            username=f'regular_{suffix}',
            email=f'regular_{suffix}@example.com',
            password='userpass123',
            db_alias=db_alias,
        )
        AuditLogRepository.all(db_alias=db_alias).delete()
        AuditLogRepository.create_log(
            action=AuditLog.ACTION_LOGIN, user=self.admin, db_alias=db_alias)
        AuditLogRepository.create_log(
            action=AuditLog.ACTION_LOGOUT, user=self.regular_user, db_alias=db_alias)
        AuditLogRepository.create_log(
            action=AuditLog.ACTION_LOGIN_FAILED,
            outcome=AuditLog.OUTCOME_FAILURE,
            db_alias=db_alias,
        )

    def _auth_admin(self):
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {_create_tokens(self.admin)}')

    def _auth_regular(self):
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {_create_tokens(self.regular_user)}')

    def test_list_requires_authentication(self):
        self.client.credentials()
        response = self.client.get('/api/audit-logs/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_requires_admin(self):
        self._auth_regular()
        response = self.client.get('/api/audit-logs/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_returns_logs_for_admin(self):
        self._auth_admin()
        response = self.client.get('/api/audit-logs/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertIn('logs', response.data)
        self.assertIn('total', response.data)

    def test_list_filter_by_action(self):
        self._auth_admin()
        response = self.client.get('/api/audit-logs/', {'action': AuditLog.ACTION_LOGIN})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for log in response.data['logs']:
            self.assertEqual(log['action'], AuditLog.ACTION_LOGIN)

    def test_list_filter_by_outcome(self):
        self._auth_admin()
        response = self.client.get(
            '/api/audit-logs/', {'outcome': AuditLog.OUTCOME_FAILURE})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for log in response.data['logs']:
            self.assertEqual(log['outcome'], AuditLog.OUTCOME_FAILURE)

    def test_list_filter_by_user_id(self):
        self._auth_admin()
        response = self.client.get(
            '/api/audit-logs/', {'user_id': self.admin.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for log in response.data['logs']:
            self.assertEqual(log['user_id'], self.admin.id)

    def test_list_pagination_page_size(self):
        self._auth_admin()
        response = self.client.get('/api/audit-logs/', {'page_size': 2})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertLessEqual(len(response.data['logs']), 2)

    def test_list_pagination_page_and_total(self):
        self._auth_admin()
        response = self.client.get('/api/audit-logs/', {'page': 1, 'page_size': 1})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['page'], 1)
        self.assertEqual(response.data['page_size'], 1)
        self.assertGreaterEqual(response.data['total'], 1)

    def test_list_page_size_capped_at_200(self):
        self._auth_admin()
        response = self.client.get('/api/audit-logs/', {'page_size': 9999})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['page_size'], 200)

    def test_list_serializer_fields(self):
        self._auth_admin()
        response = self.client.get('/api/audit-logs/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        if response.data['logs']:
            log = response.data['logs'][0]
            for field in ('id', 'timestamp', 'action', 'outcome', 'actor_username'):
                self.assertIn(field, log)

    def test_list_filter_by_date_from_future_returns_empty(self):
        self._auth_admin()
        response = self.client.get(
            '/api/audit-logs/', {'date_from': '2099-01-01T00:00:00Z'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total'], 0)


class AuditLogDetailViewTest(TestCase):

    def setUp(self):
        db_alias = get_db_alias()
        suffix = uuid4().hex[:8]
        self.client = APIClient()
        self.admin = UserRepository.create_superuser(
            db_alias=db_alias,
            username=f'admin_{suffix}',
            email=f'admin_{suffix}@example.com',
            password='adminpass123',
        )
        self.admin.is_staff = True
        self.admin.save(using=db_alias or None)
        self.regular_user = UserRepository.create_user(
            username=f'regular_{suffix}',
            email=f'regular_{suffix}@example.com',
            password='userpass123',
            db_alias=db_alias,
        )
        self.log = AuditLogRepository.create_log(
            action=AuditLog.ACTION_LOGIN,
            user=self.admin,
            db_alias=db_alias,
        )

    def _auth_admin(self):
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {_create_tokens(self.admin)}')

    def _auth_regular(self):
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {_create_tokens(self.regular_user)}')

    def test_detail_requires_authentication(self):
        self.client.credentials()
        response = self.client.get(f'/api/audit-logs/{self.log.pk}/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_detail_requires_admin(self):
        self._auth_regular()
        response = self.client.get(f'/api/audit-logs/{self.log.pk}/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_detail_returns_log_for_admin(self):
        self._auth_admin()
        response = self.client.get(f'/api/audit-logs/{self.log.pk}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['log']['id'], self.log.pk)

    def test_detail_not_found(self):
        self._auth_admin()
        response = self.client.get('/api/audit-logs/999999/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(response.data['success'])

    def test_detail_serializer_fields(self):
        self._auth_admin()
        response = self.client.get(f'/api/audit-logs/{self.log.pk}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        log = response.data['log']
        for field in ('id', 'timestamp', 'action', 'outcome', 'actor_username',
                      'resource_type', 'resource_id', 'ip_address', 'extra_data'):
            self.assertIn(field, log)


class AuditLogStatisticsViewTest(TestCase):

    def setUp(self):
        db_alias = get_db_alias()
        suffix = uuid4().hex[:8]
        self.client = APIClient()
        self.admin = UserRepository.create_superuser(
            db_alias=db_alias,
            username=f'admin_{suffix}',
            email=f'admin_{suffix}@example.com',
            password='adminpass123',
        )
        self.admin.is_staff = True
        self.admin.save(using=db_alias or None)
        self.regular_user = UserRepository.create_user(
            username=f'regular_{suffix}',
            email=f'regular_{suffix}@example.com',
            password='userpass123',
            db_alias=db_alias,
        )
        AuditLogRepository.all(db_alias=db_alias).delete()
        AuditLogRepository.create_log(action=AuditLog.ACTION_LOGIN, db_alias=db_alias)
        AuditLogRepository.create_log(
            action=AuditLog.ACTION_LOGIN_FAILED,
            outcome=AuditLog.OUTCOME_FAILURE,
            db_alias=db_alias,
        )

    def _auth_admin(self):
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {_create_tokens(self.admin)}')

    def _auth_regular(self):
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {_create_tokens(self.regular_user)}')

    def test_statistics_requires_authentication(self):
        self.client.credentials()
        response = self.client.get('/api/audit-logs/statistics/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_statistics_requires_admin(self):
        self._auth_regular()
        response = self.client.get('/api/audit-logs/statistics/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_statistics_returns_data_for_admin(self):
        self._auth_admin()
        response = self.client.get('/api/audit-logs/statistics/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        stats = response.data['statistics']
        for key in ('total', 'last_24h', 'last_7d', 'last_30d',
                    'by_action', 'by_outcome'):
            self.assertIn(key, stats)

    def test_statistics_total_correct(self):
        self._auth_admin()
        response = self.client.get('/api/audit-logs/statistics/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['statistics']['total'], 2)

    def test_statistics_by_outcome_includes_both(self):
        self._auth_admin()
        response = self.client.get('/api/audit-logs/statistics/')
        outcomes = [
            e['outcome'] for e in response.data['statistics']['by_outcome']]
        self.assertIn(AuditLog.OUTCOME_SUCCESS, outcomes)
        self.assertIn(AuditLog.OUTCOME_FAILURE, outcomes)
