"""Tests for AuditLogMiddleware."""
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings

from accounts.repositories import UserRepository
from backend.middleware.audit_log_middleware import AuditLogMiddleware, _should_skip
from backend.models import AuditLog
from backend.repositories import AuditLogRepository
from backend.utils import get_db_alias


def _make_response(status_code=200):
    response = HttpResponse()
    response.status_code = status_code
    return response


class ShouldSkipTest(TestCase):

    def test_health_check_skipped(self):
        self.assertTrue(_should_skip('/api/health/'))

    def test_api_info_skipped(self):
        self.assertTrue(_should_skip('/api/info/'))

    def test_static_skipped(self):
        self.assertTrue(_should_skip('/static/css/main.css'))

    def test_media_skipped(self):
        self.assertTrue(_should_skip('/media/images/photo.jpg'))

    def test_favicon_skipped(self):
        self.assertTrue(_should_skip('/favicon.ico'))

    def test_regular_api_not_skipped(self):
        self.assertFalse(_should_skip('/api/accounts/profile/'))

    def test_audit_logs_endpoint_not_skipped(self):
        self.assertFalse(_should_skip('/api/audit-logs/'))


class AuditLogMiddlewareTest(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        db_alias = get_db_alias()
        suffix = uuid4().hex[:8]
        self.user = UserRepository.create_user(
            username=f'mwuser_{suffix}',
            email=f'mwuser_{suffix}@example.com',
            password='testpass123',
            db_alias=db_alias,
        )

    def _middleware(self, response=None, all_methods=False):
        resp = response or _make_response(200)
        mw = AuditLogMiddleware(get_response=lambda r: resp)
        mw.log_all_methods = all_methods
        return mw

    def test_post_request_creates_log(self):
        db_alias = get_db_alias()
        initial = AuditLogRepository.count(db_alias=db_alias)
        request = self.factory.post('/api/contact/')
        request.user = self.user
        self._middleware().__call__(request)
        self.assertEqual(AuditLogRepository.count(db_alias=db_alias), initial + 1)

    def test_delete_request_creates_log(self):
        db_alias = get_db_alias()
        initial = AuditLogRepository.count(db_alias=db_alias)
        request = self.factory.delete('/api/accounts/profile/')
        request.user = self.user
        self._middleware()._maybe_log(request, _make_response(204))
        self.assertEqual(AuditLogRepository.count(db_alias=db_alias), initial + 1)

    def test_get_request_skipped_by_default(self):
        db_alias = get_db_alias()
        initial = AuditLogRepository.count(db_alias=db_alias)
        request = self.factory.get('/api/accounts/profile/')
        request.user = self.user
        self._middleware()._maybe_log(request, _make_response(200))
        self.assertEqual(AuditLogRepository.count(db_alias=db_alias), initial)

    def test_get_request_logged_when_all_methods_enabled(self):
        db_alias = get_db_alias()
        initial = AuditLogRepository.count(db_alias=db_alias)
        request = self.factory.get('/api/accounts/profile/')
        request.user = self.user
        self._middleware(all_methods=True)._maybe_log(request, _make_response(200))
        self.assertEqual(AuditLogRepository.count(db_alias=db_alias), initial + 1)

    def test_health_check_always_skipped(self):
        db_alias = get_db_alias()
        initial = AuditLogRepository.count(db_alias=db_alias)
        request = self.factory.post('/api/health/')
        request.user = self.user
        self._middleware(all_methods=True)._maybe_log(request, _make_response(200))
        self.assertEqual(AuditLogRepository.count(db_alias=db_alias), initial)

    def test_outcome_success_on_2xx(self):
        db_alias = get_db_alias()
        request = self.factory.post('/api/contact/')
        request.user = self.user
        AuditLogRepository.all(db_alias=db_alias).delete()
        self._middleware(_make_response(201))._maybe_log(request, _make_response(201))
        log = AuditLogRepository.all(db_alias=db_alias).first()
        self.assertEqual(log.outcome, AuditLog.OUTCOME_SUCCESS)

    def test_outcome_failure_on_4xx(self):
        db_alias = get_db_alias()
        request = self.factory.post('/api/contact/')
        request.user = self.user
        AuditLogRepository.all(db_alias=db_alias).delete()
        self._middleware(_make_response(400))._maybe_log(request, _make_response(400))
        log = AuditLogRepository.all(db_alias=db_alias).first()
        self.assertEqual(log.outcome, AuditLog.OUTCOME_FAILURE)

    def test_outcome_failure_on_5xx(self):
        db_alias = get_db_alias()
        request = self.factory.post('/api/contact/')
        request.user = self.user
        AuditLogRepository.all(db_alias=db_alias).delete()
        self._middleware(_make_response(500))._maybe_log(request, _make_response(500))
        log = AuditLogRepository.all(db_alias=db_alias).first()
        self.assertEqual(log.outcome, AuditLog.OUTCOME_FAILURE)

    def test_action_mapped_correctly_post(self):
        db_alias = get_db_alias()
        request = self.factory.post('/api/contact/')
        request.user = self.user
        AuditLogRepository.all(db_alias=db_alias).delete()
        self._middleware()._maybe_log(request, _make_response(201))
        log = AuditLogRepository.all(db_alias=db_alias).first()
        self.assertEqual(log.action, AuditLog.ACTION_CREATE)

    def test_action_mapped_correctly_delete(self):
        db_alias = get_db_alias()
        request = self.factory.delete('/api/accounts/profile/')
        request.user = self.user
        AuditLogRepository.all(db_alias=db_alias).delete()
        self._middleware()._maybe_log(request, _make_response(204))
        log = AuditLogRepository.all(db_alias=db_alias).first()
        self.assertEqual(log.action, AuditLog.ACTION_DELETE)

    def test_anonymous_user_no_user_on_log(self):
        db_alias = get_db_alias()
        request = self.factory.post('/api/contact/')
        anon = MagicMock()
        anon.is_authenticated = False
        request.user = anon
        AuditLogRepository.all(db_alias=db_alias).delete()
        self._middleware()._maybe_log(request, _make_response(200))
        log = AuditLogRepository.all(db_alias=db_alias).first()
        self.assertIsNone(log.user)

    def test_middleware_does_not_break_on_service_exception(self):
        expected = _make_response(200)
        request = self.factory.post('/api/contact/')
        request.user = self.user
        with patch('backend.services.audit_log_service.AuditLogService.log',
                   side_effect=Exception('boom')):
            mw = AuditLogMiddleware(get_response=lambda r: expected)
            result = mw(request)
        self.assertIs(result, expected)

    def test_call_returns_response_unchanged(self):
        expected = _make_response(201)
        request = self.factory.post('/api/contact/')
        anon = MagicMock()
        anon.is_authenticated = False
        request.user = anon
        mw = AuditLogMiddleware(get_response=lambda r: expected)
        result = mw(request)
        self.assertIs(result, expected)
