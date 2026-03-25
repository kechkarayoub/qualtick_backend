# pylint: disable=too-few-public-methods
"""
Tests for FCMService and FCMTokenRepository.
"""

from unittest.mock import MagicMock, patch

from django.test import TestCase

from accounts.models import FCMToken
from backend.services.fcm_service import FCMService
from backend.repositories.fcm_token_repository import FCMTokenRepository
from backend.utils import get_db_alias


class TestFCMTokenRepository(TestCase):
    """Tests for FCMTokenRepository using a real in-memory SQLite DB via TransactionTestCase."""

    def _create_user(self, suffix="a"):
        from accounts.repositories import UserRepository
        return UserRepository.create_user(
            email=f"fcmtest_{suffix}@example.com",
            username=f"fcmtest_{suffix}",
            password="pass123",
            first_name="FCM",
            last_name="Test",
            db_alias=get_db_alias(),
        )

    def test_upsert_creates_new_token(self):
        user = self._create_user("b")
        db_alias = get_db_alias()
        FCMTokenRepository.upsert(user.id, "token_android_1", "android", "dev_1", db_alias=db_alias)
        self.assertTrue(FCMToken.objects.using(db_alias or None).filter(token="token_android_1", user=user).exists())

    def test_upsert_updates_existing_token(self):
        user = self._create_user("c")
        db_alias = get_db_alias()
        FCMTokenRepository.upsert(user.id, "token_ios_1", "ios", "dev_a", db_alias=db_alias)
        FCMTokenRepository.upsert(user.id, "token_ios_1", "ios", "dev_b", db_alias=db_alias)
        self.assertEqual(FCMToken.objects.using(db_alias or None).filter(token="token_ios_1").count(), 1)
        self.assertEqual(FCMToken.objects.using(db_alias or None).get(token="token_ios_1").device_id, "dev_b")

    def test_get_tokens_for_user_returns_active_tokens(self):
        user = self._create_user("d")
        db_alias = get_db_alias()
        FCMTokenRepository.upsert(user.id, "tok1", "android", "d1", db_alias=db_alias)
        FCMTokenRepository.upsert(user.id, "tok2", "ios", "d2", db_alias=db_alias)
        tokens = FCMTokenRepository.get_tokens_for_user(user.id, db_alias=db_alias)
        self.assertIn("tok1", tokens)
        self.assertIn("tok2", tokens)

    def test_get_tokens_filters_by_platform(self):
        user = self._create_user("e")
        db_alias = get_db_alias()
        FCMTokenRepository.upsert(user.id, "tok_and", "android", "d1", db_alias=db_alias)
        FCMTokenRepository.upsert(user.id, "tok_web", "web", "d2", db_alias=db_alias)
        android_tokens = FCMTokenRepository.get_tokens_for_user(user.id, platform="android", db_alias=db_alias)
        self.assertEqual(android_tokens, ["tok_and"])

    def test_delete_by_token_soft_deletes(self):
        user = self._create_user("f")
        db_alias = get_db_alias()
        FCMTokenRepository.upsert(user.id, "tok_del", "web", db_alias=db_alias)
        FCMTokenRepository.delete_by_token("tok_del", db_alias=db_alias)
        self.assertFalse(FCMToken.objects.using(db_alias or None).get(token="tok_del").is_active)

    def test_deactivate_for_user_deactivates_all(self):
        user = self._create_user("g")
        db_alias = get_db_alias()
        FCMTokenRepository.upsert(user.id, "tok_all_1", "android", db_alias=db_alias)
        FCMTokenRepository.upsert(user.id, "tok_all_2", "ios", db_alias=db_alias)
        FCMTokenRepository.deactivate_for_user(user.id, db_alias=db_alias)
        tokens = FCMTokenRepository.get_tokens_for_user(user.id, db_alias=db_alias)
        self.assertEqual(tokens, [])

    def test_deactivate_for_user_by_device_id(self):
        user = self._create_user("h")
        db_alias = get_db_alias()
        FCMTokenRepository.upsert(user.id, "tok_d1", "android", "dev_keep", db_alias=db_alias)
        FCMTokenRepository.upsert(user.id, "tok_d2", "ios", "dev_remove", db_alias=db_alias)
        FCMTokenRepository.deactivate_for_user(user.id, device_id="dev_remove", db_alias=db_alias)
        remaining = FCMTokenRepository.get_tokens_for_user(user.id, db_alias=db_alias)
        self.assertIn("tok_d1", remaining)
        self.assertNotIn("tok_d2", remaining)


class TestFCMServiceSendToToken(TestCase):
    """Unit tests for FCMService.send_to_token."""

    @patch("backend.services.fcm_service.messaging.send")
    def test_send_to_token_success(self, mock_send):
        mock_send.return_value = "projects/test/messages/1"
        db_alias = get_db_alias()
        result = FCMService.send_to_token("valid_token", "Title", "Body", db_alias=db_alias)
        self.assertTrue(result)
        mock_send.assert_called_once()

    @patch("backend.services.fcm_service.FCMTokenRepository.delete_by_token")
    @patch("backend.services.fcm_service.messaging.send")
    def test_send_to_token_removes_unregistered(self, mock_send, mock_delete):
        from firebase_admin import messaging as fb_messaging
        mock_send.side_effect = fb_messaging.UnregisteredError("Not registered")
        db_alias = get_db_alias()
        result = FCMService.send_to_token("dead_token", "Title", "Body", db_alias=db_alias)
        self.assertFalse(result)
        mock_delete.assert_called_once_with("dead_token", db_alias=db_alias)

    @patch("backend.services.fcm_service.messaging.send")
    def test_send_to_token_generic_error_returns_false(self, mock_send):
        mock_send.side_effect = Exception("Network error")
        db_alias = get_db_alias()
        result = FCMService.send_to_token("some_token", "Title", "Body", db_alias=db_alias)
        self.assertFalse(result)

    @patch("backend.services.fcm_service.messaging.send")
    def test_send_to_token_passes_data_as_strings(self, mock_send):
        mock_send.return_value = "msg_id"
        db_alias = get_db_alias()
        FCMService.send_to_token("tok", "T", "B", data={"count": 5, "flag": True}, db_alias=db_alias)
        call_args = mock_send.call_args[0][0]
        self.assertEqual(call_args.data, {"count": "5", "flag": "True"})


class TestFCMServiceSendToUser(TestCase):
    """Unit tests for FCMService.send_to_user."""

    @patch("backend.services.fcm_service.FCMService.send_to_token")
    @patch("backend.services.fcm_service.FCMTokenRepository.get_tokens_for_user")
    def test_send_to_user_sends_to_all_tokens(self, mock_get_tokens, mock_send_token):
        mock_get_tokens.return_value = ["tok1", "tok2", "tok3"]
        mock_send_token.return_value = True
        db_alias = get_db_alias()
        result = FCMService.send_to_user(1, "Hello", "World", db_alias=db_alias)
        self.assertEqual(result, {"sent": 3, "failed": 0})
        self.assertEqual(mock_send_token.call_count, 3)

    @patch("backend.services.fcm_service.FCMService.send_to_token")
    @patch("backend.services.fcm_service.FCMTokenRepository.get_tokens_for_user")
    def test_send_to_user_counts_failures(self, mock_get_tokens, mock_send_token):
        mock_get_tokens.return_value = ["tok1", "tok2"]
        mock_send_token.side_effect = [True, False]
        db_alias = get_db_alias()
        result = FCMService.send_to_user(1, "Hello", "World", db_alias=db_alias)
        self.assertEqual(result, {"sent": 1, "failed": 1})

    @patch("backend.services.fcm_service.FCMTokenRepository.get_tokens_for_user")
    def test_send_to_user_no_tokens_returns_zeros(self, mock_get_tokens):
        mock_get_tokens.return_value = []
        db_alias = get_db_alias()
        result = FCMService.send_to_user(99, "Hello", "World", db_alias=db_alias)
        self.assertEqual(result, {"sent": 0, "failed": 0})

    @patch("backend.services.fcm_service.FCMService.send_to_token")
    @patch("backend.services.fcm_service.FCMTokenRepository.get_tokens_for_user")
    def test_send_to_user_filters_by_platform(self, mock_get_tokens, mock_send_token):
        mock_get_tokens.return_value = ["ios_tok"]
        mock_send_token.return_value = True
        db_alias = get_db_alias()
        FCMService.send_to_user(1, "T", "B", platform="ios", db_alias=db_alias)
        mock_get_tokens.assert_called_once_with(1, platform="ios", db_alias=db_alias)


class TestFCMServiceSendToMultipleUsers(TestCase):
    """Unit tests for FCMService.send_to_multiple_users."""

    @patch("backend.services.fcm_service.FCMService.send_to_user")
    def test_send_to_multiple_users_aggregates(self, mock_send_to_user):
        mock_send_to_user.side_effect = [
            {"sent": 2, "failed": 0},
            {"sent": 1, "failed": 1},
            {"sent": 0, "failed": 2},
        ]
        db_alias = get_db_alias()
        result = FCMService.send_to_multiple_users([1, 2, 3], "Broadcast", "Msg", db_alias=db_alias)
        self.assertEqual(result, {"sent": 3, "failed": 3})
        self.assertEqual(mock_send_to_user.call_count, 3)


class TestFCMServiceMulticast(TestCase):
    """Unit tests for FCMService.send_multicast."""

    @patch("backend.services.fcm_service.messaging.send_each_for_multicast")
    def test_multicast_success(self, mock_multicast):
        db_alias = get_db_alias()
        mock_response = MagicMock()
        mock_response.success_count = 3
        mock_response.failure_count = 0
        mock_response.responses = [
            MagicMock(success=True, exception=None),
            MagicMock(success=True, exception=None),
            MagicMock(success=True, exception=None),
        ]
        mock_multicast.return_value = mock_response
        result = FCMService.send_multicast(["t1", "t2", "t3"], "Title", "Body", db_alias=db_alias)
        self.assertEqual(result, {"sent": 3, "failed": 0})

    @patch("backend.services.fcm_service.FCMTokenRepository.delete_by_token")
    @patch("backend.services.fcm_service.messaging.send_each_for_multicast")
    def test_multicast_removes_unregistered_tokens(self, mock_multicast, mock_delete):
        from firebase_admin import messaging as fb_messaging
        mock_response = MagicMock()
        mock_response.success_count = 1
        mock_response.failure_count = 1
        mock_response.responses = [
            MagicMock(success=True, exception=None),
            MagicMock(success=False, exception=fb_messaging.UnregisteredError("dead")),
        ]
        mock_multicast.return_value = mock_response
        db_alias = get_db_alias()
        FCMService.send_multicast(["good_tok", "dead_tok"], "Title", "Body", db_alias=db_alias)
        mock_delete.assert_called_once_with("dead_tok", db_alias=db_alias)

    @patch("backend.services.fcm_service.messaging.send_each_for_multicast")
    def test_multicast_error_returns_all_failed(self, mock_multicast):
        db_alias = get_db_alias()
        mock_multicast.side_effect = Exception("FCM error")
        result = FCMService.send_multicast(["t1", "t2"], "Title", "Body", db_alias=db_alias)
        self.assertEqual(result, {"sent": 0, "failed": 2})

    def test_multicast_empty_tokens_returns_zeros(self):
        db_alias = get_db_alias()
        result = FCMService.send_multicast([], "Title", "Body", db_alias=db_alias)
        self.assertEqual(result, {"sent": 0, "failed": 0})


class TestFCMTokenView(TestCase):
    """Tests for the FCMTokenView API endpoint."""

    def _create_user_and_login(self, suffix="view"):
        from accounts.repositories import UserRepository
        from accounts.tokens import RefreshToken
        user = UserRepository.create_user(
            email=f"fcmview_{suffix}@example.com",
            username=f"fcmview_{suffix}",
            password="pass123",
            first_name="FCM",
            last_name="View",
            db_alias=get_db_alias(),
        )
        refresh = RefreshToken.for_user(user)
        return user, str(refresh.access_token)

    def _auth_headers(self, token):
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    @patch("accounts.views.fcm_token_views.FCMTokenRepository.upsert")
    def test_post_registers_token(self, mock_upsert):
        _, access_token = self._create_user_and_login("post1")
        response = self.client.post(
            "/accounts/fcm-token/",
            data={"token": "fcm_tok_123", "platform": "android", "device_id": "dev_1"},
            content_type="application/json",
            **self._auth_headers(access_token),
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        mock_upsert.assert_called_once()

    def test_post_missing_token_returns_400(self):
        _, access_token = self._create_user_and_login("post2")
        response = self.client.post(
            "/accounts/fcm-token/",
            data={"platform": "ios"},
            content_type="application/json",
            **self._auth_headers(access_token),
        )
        self.assertEqual(response.status_code, 400)

    def test_post_invalid_platform_returns_400(self):
        _, access_token = self._create_user_and_login("post3")
        response = self.client.post(
            "/accounts/fcm-token/",
            data={"token": "tok", "platform": "windows"},
            content_type="application/json",
            **self._auth_headers(access_token),
        )
        self.assertEqual(response.status_code, 400)

    def test_post_unauthenticated_returns_401(self):
        response = self.client.post(
            "/accounts/fcm-token/",
            data={"token": "tok", "platform": "web"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    @patch("accounts.views.fcm_token_views.FCMTokenRepository.delete_by_token")
    def test_delete_deactivates_token(self, mock_delete):
        _, access_token = self._create_user_and_login("del1")
        response = self.client.delete(
            "/accounts/fcm-token/",
            data={"token": "fcm_tok_del"},
            content_type="application/json",
            **self._auth_headers(access_token),
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        mock_delete.assert_called_once_with("fcm_tok_del", db_alias=get_db_alias())

    def test_delete_missing_token_returns_400(self):
        _, access_token = self._create_user_and_login("del2")
        response = self.client.delete(
            "/accounts/fcm-token/",
            data={},
            content_type="application/json",
            **self._auth_headers(access_token),
        )
        self.assertEqual(response.status_code, 400)
