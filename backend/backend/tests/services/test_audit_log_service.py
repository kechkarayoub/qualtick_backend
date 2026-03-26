"""Tests for AuditLogService."""
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.test import RequestFactory, TestCase
from django.utils import timezone

from accounts.repositories import UserRepository
from backend.models import AuditLog
from backend.repositories import AuditLogRepository
from backend.services.audit_log_service import AuditLogService, _sanitize
from backend.utils import get_db_alias


class SanitizeTest(TestCase):

    def test_redacts_password(self):
        result = _sanitize({'password': 'secret123', 'email': 'a@b.com'})
        self.assertEqual(result['password'], '[redacted]')
        self.assertEqual(result['email'], 'a@b.com')

    def test_redacts_token(self):
        result = _sanitize({'access_token': 'tok', 'name': 'John'})
        self.assertEqual(result['access_token'], '[redacted]')
        self.assertEqual(result['name'], 'John')

    def test_nested_redaction(self):
        result = _sanitize({'user': {'password': 'abc', 'id': 1}})
        self.assertEqual(result['user']['password'], '[redacted]')
        self.assertEqual(result['user']['id'], 1)

    def test_list_of_dicts(self):
        result = _sanitize([{'password': 'x'}, {'name': 'y'}])
        self.assertEqual(result[0]['password'], '[redacted]')
        self.assertEqual(result[1]['name'], 'y')

    def test_max_depth_truncation(self):
        deep = {'a': {'b': {'c': {'d': 'val'}}}}
        result = _sanitize(deep, max_depth=2)
        self.assertEqual(result['a']['b'], '[truncated]')

    def test_non_dict_passthrough(self):
        self.assertEqual(_sanitize('hello'), 'hello')
        self.assertEqual(_sanitize(42), 42)
        self.assertIsNone(_sanitize(None))

    def test_case_insensitive_key(self):
        result = _sanitize({'PASSWORD': 'secret'})
        self.assertEqual(result['PASSWORD'], '[redacted]')


class AuditLogServiceLogTest(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        db_alias = get_db_alias()
        suffix = uuid4().hex[:8]
        self.user = UserRepository.create_user(
            username=f'svcuser_{suffix}',
            email=f'svcuser_{suffix}@example.com',
            password='testpass123',
            db_alias=db_alias,
        )

    def _make_request(self, path='/api/test/', method='POST', user=None):
        request = self.factory.generic(method, path)
        request.META['HTTP_USER_AGENT'] = 'TestAgent/1.0'
        request.META['REMOTE_ADDR'] = '127.0.0.1'
        if user is not None:
            request.user = user
        else:
            request.user = MagicMock(is_authenticated=False)
        return request

    def test_log_creates_record(self):
        db_alias = get_db_alias()
        initial = AuditLogRepository.count(db_alias=db_alias)
        AuditLogService.log(action=AuditLog.ACTION_LOGIN, db_alias=db_alias)
        self.assertEqual(AuditLogRepository.count(db_alias=db_alias), initial + 1)

    def test_log_extracts_ip_from_request(self):
        db_alias = get_db_alias()
        request = self._make_request()
        log = AuditLogService.log(
            action=AuditLog.ACTION_CREATE, request=request, db_alias=db_alias)
        self.assertEqual(log.ip_address, '127.0.0.1')

    def test_log_extracts_x_forwarded_for(self):
        db_alias = get_db_alias()
        request = self._make_request()
        request.META['HTTP_X_FORWARDED_FOR'] = '203.0.113.5, 10.0.0.1'
        log = AuditLogService.log(
            action=AuditLog.ACTION_READ, request=request, db_alias=db_alias)
        self.assertEqual(log.ip_address, '203.0.113.5')

    def test_log_extracts_user_agent(self):
        db_alias = get_db_alias()
        request = self._make_request()
        log = AuditLogService.log(
            action=AuditLog.ACTION_READ, request=request, db_alias=db_alias)
        self.assertEqual(log.user_agent, 'TestAgent/1.0')

    def test_log_extracts_method_and_path(self):
        db_alias = get_db_alias()
        request = self._make_request(path='/api/profile/', method='PATCH')
        log = AuditLogService.log(
            action=AuditLog.ACTION_UPDATE, request=request, db_alias=db_alias)
        self.assertEqual(log.request_method, 'PATCH')
        self.assertEqual(log.request_path, '/api/profile/')

    def test_log_picks_up_authenticated_user_from_request(self):
        db_alias = get_db_alias()
        request = self._make_request(user=self.user)
        log = AuditLogService.log(
            action=AuditLog.ACTION_LOGIN, request=request, db_alias=db_alias)
        self.assertEqual(log.user_id, self.user.id)

    def test_log_sanitizes_extra_data(self):
        db_alias = get_db_alias()
        log = AuditLogService.log(
            action=AuditLog.ACTION_UPDATE,
            extra_data={'password': 'abc', 'name': 'John'},
            db_alias=db_alias,
        )
        self.assertEqual(log.extra_data['password'], '[redacted]')
        self.assertEqual(log.extra_data['name'], 'John')

    def test_log_outcome_failure(self):
        db_alias = get_db_alias()
        log = AuditLogService.log(
            action=AuditLog.ACTION_LOGIN_FAILED,
            outcome=AuditLog.OUTCOME_FAILURE,
            db_alias=db_alias,
        )
        self.assertEqual(log.outcome, AuditLog.OUTCOME_FAILURE)

    def test_log_returns_none_on_exception(self):
        db_alias = get_db_alias()
        with patch('backend.services.audit_log_service.AuditLogRepository.create_log',
                   side_effect=Exception('forced error')):
            log = AuditLogService.log(action=AuditLog.ACTION_READ, db_alias=db_alias)
        self.assertIsNone(log)


class AuditLogServiceGetLogsTest(TestCase):

    def setUp(self):
        db_alias = get_db_alias()
        suffix = uuid4().hex[:8]
        self.user = UserRepository.create_user(
            username=f'filteruser_{suffix}',
            email=f'filteruser_{suffix}@example.com',
            password='testpass123',
            db_alias=db_alias,
        )
        AuditLogService.log(
            action=AuditLog.ACTION_LOGIN, user=self.user, db_alias=db_alias)
        AuditLogService.log(
            action=AuditLog.ACTION_LOGOUT, user=self.user, db_alias=db_alias)
        AuditLogService.log(
            action=AuditLog.ACTION_LOGIN_FAILED,
            outcome=AuditLog.OUTCOME_FAILURE,
            db_alias=db_alias,
        )

    def test_filter_by_user_id(self):
        db_alias = get_db_alias()
        qs = AuditLogService.get_logs(user_id=self.user.id, db_alias=db_alias)
        for log in qs:
            self.assertEqual(log.user_id, self.user.id)
        self.assertEqual(qs.count(), 2)

    def test_filter_by_action(self):
        db_alias = get_db_alias()
        qs = AuditLogService.get_logs(action=AuditLog.ACTION_LOGIN, db_alias=db_alias)
        for log in qs:
            self.assertEqual(log.action, AuditLog.ACTION_LOGIN)

    def test_filter_by_outcome(self):
        db_alias = get_db_alias()
        qs = AuditLogService.get_logs(
            outcome=AuditLog.OUTCOME_FAILURE, db_alias=db_alias)
        for log in qs:
            self.assertEqual(log.outcome, AuditLog.OUTCOME_FAILURE)

    def test_filter_by_date_from(self):
        db_alias = get_db_alias()
        future = timezone.now() + timezone.timedelta(days=1)
        qs = AuditLogService.get_logs(date_from=future, db_alias=db_alias)
        self.assertEqual(qs.count(), 0)

    def test_filter_by_date_to(self):
        db_alias = get_db_alias()
        past = timezone.now() - timezone.timedelta(days=1)
        qs = AuditLogService.get_logs(date_to=past, db_alias=db_alias)
        self.assertEqual(qs.count(), 0)

    def test_filter_by_resource_type_and_id(self):
        db_alias = get_db_alias()
        AuditLogService.log(
            action=AuditLog.ACTION_UPDATE,
            resource_type='accounts.User',
            resource_id='77',
            db_alias=db_alias,
        )
        qs = AuditLogService.get_logs(
            resource_type='accounts.User', resource_id='77', db_alias=db_alias)
        self.assertEqual(qs.count(), 1)

    def test_no_filters_returns_all(self):
        db_alias = get_db_alias()
        total = AuditLogRepository.count(db_alias=db_alias)
        qs = AuditLogService.get_logs(db_alias=db_alias)
        self.assertEqual(qs.count(), total)


class AuditLogServiceStatisticsTest(TestCase):

    def setUp(self):
        db_alias = get_db_alias()
        AuditLogRepository.all(db_alias=db_alias).delete()
        AuditLogService.log(action=AuditLog.ACTION_LOGIN, db_alias=db_alias)
        AuditLogService.log(action=AuditLog.ACTION_LOGIN, db_alias=db_alias)
        AuditLogService.log(
            action=AuditLog.ACTION_LOGIN_FAILED,
            outcome=AuditLog.OUTCOME_FAILURE,
            db_alias=db_alias,
        )

    def test_statistics_total(self):
        db_alias = get_db_alias()
        stats = AuditLogService.get_statistics(db_alias=db_alias)
        self.assertEqual(stats['total'], 3)

    def test_statistics_last_24h(self):
        db_alias = get_db_alias()
        stats = AuditLogService.get_statistics(db_alias=db_alias)
        self.assertEqual(stats['last_24h'], 3)

    def test_statistics_by_action_keys(self):
        db_alias = get_db_alias()
        stats = AuditLogService.get_statistics(db_alias=db_alias)
        self.assertIn('by_action', stats)
        actions = [entry['action'] for entry in stats['by_action']]
        self.assertIn(AuditLog.ACTION_LOGIN, actions)

    def test_statistics_by_outcome_keys(self):
        db_alias = get_db_alias()
        stats = AuditLogService.get_statistics(db_alias=db_alias)
        self.assertIn('by_outcome', stats)
        outcomes = [entry['outcome'] for entry in stats['by_outcome']]
        self.assertIn(AuditLog.OUTCOME_SUCCESS, outcomes)
        self.assertIn(AuditLog.OUTCOME_FAILURE, outcomes)

    def test_statistics_has_time_buckets(self):
        db_alias = get_db_alias()
        stats = AuditLogService.get_statistics(db_alias=db_alias)
        for key in ('last_24h', 'last_7d', 'last_30d'):
            self.assertIn(key, stats)
