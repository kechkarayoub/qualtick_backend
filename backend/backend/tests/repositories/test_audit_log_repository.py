"""Tests for AuditLogRepository."""
from uuid import uuid4

from django.test import TestCase

from accounts.repositories import UserRepository
from backend.models import AuditLog
from backend.repositories import AuditLogRepository
from backend.utils import get_db_alias


class AuditLogRepositoryTest(TestCase):

    def setUp(self):
        db_alias = get_db_alias()
        suffix = uuid4().hex[:8]
        self.user = UserRepository.create_user(
            username=f'repouser_{suffix}',
            email=f'repouser_{suffix}@example.com',
            password='testpass123',
            db_alias=db_alias,
        )

    def test_create_log_minimal(self):
        db_alias = get_db_alias()
        log = AuditLogRepository.create_log(action=AuditLog.ACTION_READ, db_alias=db_alias)
        self.assertIsNotNone(log.pk)
        self.assertEqual(log.action, AuditLog.ACTION_READ)
        self.assertEqual(log.outcome, AuditLog.OUTCOME_SUCCESS)
        self.assertEqual(log.actor_username, '')

    def test_create_log_with_user_sets_actor_username(self):
        db_alias = get_db_alias()
        log = AuditLogRepository.create_log(
            action=AuditLog.ACTION_LOGIN,
            user=self.user,
            db_alias=db_alias,
        )
        self.assertEqual(log.actor_username, self.user.username)

    def test_create_log_explicit_actor_username_overrides(self):
        db_alias = get_db_alias()
        log = AuditLogRepository.create_log(
            action=AuditLog.ACTION_LOGIN,
            user=self.user,
            actor_username='custom_name',
            db_alias=db_alias,
        )
        self.assertEqual(log.actor_username, 'custom_name')

    def test_create_log_all_fields(self):
        db_alias = get_db_alias()
        log = AuditLogRepository.create_log(
            action=AuditLog.ACTION_DELETE,
            outcome=AuditLog.OUTCOME_FAILURE,
            user=self.user,
            resource_type='accounts.User',
            resource_id=str(self.user.id),
            description='Deleted user account',
            ip_address='10.0.0.1',
            user_agent='Mozilla/5.0',
            request_method='DELETE',
            request_path='/accounts/profile/',
            extra_data={'reason': 'test'},
            db_alias=db_alias,
        )
        self.assertEqual(log.outcome, AuditLog.OUTCOME_FAILURE)
        self.assertEqual(log.resource_type, 'accounts.User')
        self.assertEqual(log.resource_id, str(self.user.id))
        self.assertEqual(log.ip_address, '10.0.0.1')
        self.assertEqual(log.request_method, 'DELETE')
        self.assertEqual(log.extra_data, {'reason': 'test'})

    def test_get_by_id_existing(self):
        db_alias = get_db_alias()
        log = AuditLogRepository.create_log(action=AuditLog.ACTION_READ, db_alias=db_alias)
        fetched = AuditLogRepository.get_by_id(log.pk, db_alias=db_alias)
        self.assertEqual(fetched.pk, log.pk)

    def test_get_by_id_missing(self):
        db_alias = get_db_alias()
        result = AuditLogRepository.get_by_id(999999, db_alias=db_alias)
        self.assertIsNone(result)

    def test_get_for_user(self):
        db_alias = get_db_alias()
        AuditLogRepository.create_log(
            action=AuditLog.ACTION_LOGIN, user=self.user, db_alias=db_alias)
        AuditLogRepository.create_log(
            action=AuditLog.ACTION_LOGOUT, user=self.user, db_alias=db_alias)
        AuditLogRepository.create_log(action=AuditLog.ACTION_READ, db_alias=db_alias)

        qs = AuditLogRepository.get_for_user(self.user.id, db_alias=db_alias)
        self.assertEqual(qs.count(), 2)
        for log in qs:
            self.assertEqual(log.user_id, self.user.id)

    def test_get_for_resource(self):
        db_alias = get_db_alias()
        AuditLogRepository.create_log(
            action=AuditLog.ACTION_UPDATE,
            resource_type='accounts.User',
            resource_id='42',
            db_alias=db_alias,
        )
        AuditLogRepository.create_log(
            action=AuditLog.ACTION_UPDATE,
            resource_type='accounts.User',
            resource_id='99',
            db_alias=db_alias,
        )
        qs = AuditLogRepository.get_for_resource('accounts.User', '42', db_alias=db_alias)
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().resource_id, '42')

    def test_get_recent_limits_results(self):
        db_alias = get_db_alias()
        for _ in range(10):
            AuditLogRepository.create_log(action=AuditLog.ACTION_READ, db_alias=db_alias)
        recent = AuditLogRepository.get_recent(limit=5, db_alias=db_alias)
        self.assertEqual(len(list(recent)), 5)

    def test_filter_by_action(self):
        db_alias = get_db_alias()
        AuditLogRepository.create_log(action=AuditLog.ACTION_LOGIN, db_alias=db_alias)
        AuditLogRepository.create_log(action=AuditLog.ACTION_LOGOUT, db_alias=db_alias)
        logins = AuditLogRepository.filter(db_alias=db_alias, action=AuditLog.ACTION_LOGIN)
        self.assertEqual(logins.count(), 1)

    def test_filter_by_outcome(self):
        db_alias = get_db_alias()
        AuditLogRepository.create_log(
            action=AuditLog.ACTION_LOGIN, outcome=AuditLog.OUTCOME_FAILURE, db_alias=db_alias)
        AuditLogRepository.create_log(
            action=AuditLog.ACTION_LOGIN, outcome=AuditLog.OUTCOME_SUCCESS, db_alias=db_alias)
        failures = AuditLogRepository.filter(
            db_alias=db_alias, outcome=AuditLog.OUTCOME_FAILURE)
        self.assertEqual(failures.count(), 1)

    def test_count(self):
        db_alias = get_db_alias()
        initial = AuditLogRepository.count(db_alias=db_alias)
        AuditLogRepository.create_log(action=AuditLog.ACTION_READ, db_alias=db_alias)
        AuditLogRepository.create_log(action=AuditLog.ACTION_READ, db_alias=db_alias)
        self.assertEqual(AuditLogRepository.count(db_alias=db_alias), initial + 2)
