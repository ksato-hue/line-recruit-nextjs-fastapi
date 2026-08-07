import json
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch
from uuid import UUID

import requests

import inquiry_response
from inquiry_response import LinePushDisposition, LinePushResult
from tests.support import load_backend_main


main = load_backend_main()
LINE_USER_ID = "U0123456789abcdef0123456789abcdef"
MESSAGE = "Thank you for your inquiry."
LINE_RETRY_KEY = UUID("12345678-1234-5678-1234-567812345678")
LINE_ACCESS_TOKEN = "test-line-access-token"


def line_response(status_code: int, headers: dict[str, str] | None = None) -> requests.Response:
    response = requests.Response()
    response.status_code = status_code
    response.headers.update(headers or {})
    response._content = b'{"message":"provider response must not be logged"}'
    return response


class InquiryReplyLineTransportTests(unittest.TestCase):
    def setUp(self):
        self.access_token_patch = patch.object(
            main,
            "LINE_ACCESS_TOKEN",
            LINE_ACCESS_TOKEN,
        )
        self.access_token_patch.start()

    def tearDown(self):
        self.access_token_patch.stop()

    def push_with(self, *, response=None, side_effect=None):
        with patch.object(
            main.requests,
            "post",
            return_value=response,
            side_effect=side_effect,
        ) as post:
            result = main._push_inquiry_reply(
                LINE_USER_ID,
                MESSAGE,
                LINE_RETRY_KEY,
            )
        return result, post

    def test_two_hundred_and_two_is_accepted(self):
        result, _post = self.push_with(response=line_response(202))

        self.assertEqual(
            LinePushResult(LinePushDisposition.ACCEPTED, 202),
            result,
        )

    def test_every_two_xx_boundary_is_accepted(self):
        for status_code in (200, 201, 204, 299):
            with self.subTest(status_code=status_code):
                result, _post = self.push_with(response=line_response(status_code))

                self.assertEqual(LinePushDisposition.ACCEPTED, result.disposition)
                self.assertEqual(status_code, result.http_status)

    def test_accepted_retry_key_conflict_is_already_accepted(self):
        result, _post = self.push_with(
            response=line_response(
                409,
                {"X-Line-Accepted-Request-Id": "accepted-request-id"},
            )
        )

        self.assertEqual(
            LinePushResult(LinePushDisposition.ALREADY_ACCEPTED, 409),
            result,
        )

    def test_conflict_without_accepted_request_header_is_rejected(self):
        result, _post = self.push_with(response=line_response(409))

        self.assertEqual(
            LinePushResult(LinePushDisposition.REJECTED, 409),
            result,
        )

    def test_known_client_rejections_are_rejected(self):
        for status_code in (400, 401, 403, 404, 429):
            with self.subTest(status_code=status_code):
                result, _post = self.push_with(response=line_response(status_code))

                self.assertEqual(LinePushDisposition.REJECTED, result.disposition)
                self.assertEqual(status_code, result.http_status)

    def test_server_errors_are_unknown_and_are_not_automatically_retried(self):
        for status_code in (500, 502, 503, 599):
            with self.subTest(status_code=status_code):
                result, post = self.push_with(response=line_response(status_code))

                self.assertEqual(LinePushDisposition.UNKNOWN, result.disposition)
                self.assertEqual(status_code, result.http_status)
                post.assert_called_once()

    def test_timeout_and_connection_error_are_unknown_without_retry(self):
        for error in (requests.Timeout("timeout"), requests.ConnectionError("offline")):
            with self.subTest(error=type(error).__name__):
                result, post = self.push_with(side_effect=error)

                self.assertEqual(
                    LinePushResult(LinePushDisposition.UNKNOWN, None),
                    result,
                )
                post.assert_called_once()

    def test_request_preserves_destination_message_retry_key_and_timeout(self):
        result, post = self.push_with(response=line_response(200))

        self.assertEqual(LinePushDisposition.ACCEPTED, result.disposition)
        post.assert_called_once_with(
            "https://api.line.me/v2/bot/message/push",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {LINE_ACCESS_TOKEN}",
                "X-Line-Retry-Key": str(LINE_RETRY_KEY),
            },
            json={
                "to": LINE_USER_ID,
                "messages": [{"type": "text", "text": MESSAGE}],
            },
            timeout=10,
        )

    def test_explicit_same_operation_retry_reuses_the_identical_retry_header(self):
        with patch.object(
            main.requests,
            "post",
            side_effect=[
                line_response(503),
                line_response(
                    409,
                    {"x-line-accepted-request-id": "accepted-request-id"},
                ),
            ],
        ) as post:
            first = main._push_inquiry_reply(LINE_USER_ID, MESSAGE, LINE_RETRY_KEY)
            second = main._push_inquiry_reply(LINE_USER_ID, MESSAGE, LINE_RETRY_KEY)

        self.assertEqual(LinePushDisposition.UNKNOWN, first.disposition)
        self.assertEqual(LinePushDisposition.ALREADY_ACCEPTED, second.disposition)
        self.assertEqual(2, post.call_count)
        self.assertEqual(
            [str(LINE_RETRY_KEY), str(LINE_RETRY_KEY)],
            [call.kwargs["headers"]["X-Line-Retry-Key"] for call in post.call_args_list],
        )

    def test_response_log_contains_only_safe_delivery_fields(self):
        with (
            patch.object(main.requests, "post", return_value=line_response(400)),
            patch.object(main.logger, "info") as info,
        ):
            result = main._push_inquiry_reply(LINE_USER_ID, MESSAGE, LINE_RETRY_KEY)

        self.assertEqual(LinePushDisposition.REJECTED, result.disposition)
        info.assert_called_once()
        record = json.loads(info.call_args.args[0])
        self.assertEqual(
            {
                "event": "inquiry.reply.push",
                "result": "rejected",
                "subject_id": "0acba02590b4",
                "http_status": 400,
            },
            record,
        )
        serialized = info.call_args.args[0]
        for forbidden in (
            LINE_USER_ID,
            MESSAGE,
            LINE_RETRY_KEY.hex,
            str(LINE_RETRY_KEY),
            LINE_ACCESS_TOKEN,
            "provider response must not be logged",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_transport_error_log_is_safe_and_records_exception_type(self):
        with (
            patch.object(
                main.requests,
                "post",
                side_effect=requests.Timeout("secret timeout details"),
            ),
            patch.object(main.logger, "info") as info,
        ):
            result = main._push_inquiry_reply(LINE_USER_ID, MESSAGE, LINE_RETRY_KEY)

        self.assertEqual(LinePushDisposition.UNKNOWN, result.disposition)
        info.assert_called_once()
        self.assertEqual(
            {
                "event": "inquiry.reply.push",
                "result": "unknown",
                "subject_id": "0acba02590b4",
                "error": "Timeout",
            },
            json.loads(info.call_args.args[0]),
        )
        serialized = info.call_args.args[0]
        for forbidden in (
            LINE_USER_ID,
            MESSAGE,
            str(LINE_RETRY_KEY),
            LINE_ACCESS_TOKEN,
            "secret timeout details",
        ):
            self.assertNotIn(forbidden, serialized)


class InquiryReplyRecoveryPolicyTests(unittest.TestCase):
    def test_unknown_retry_window_expires_at_exactly_twenty_four_hours(self):
        retry_allowed = getattr(inquiry_response, "inquiry_reply_retry_allowed", None)
        self.assertIsNotNone(
            retry_allowed,
            "production recovery policy helper is missing",
        )
        now = datetime(2026, 8, 7, 12, 0, tzinfo=timezone.utc)

        self.assertTrue(retry_allowed(now - timedelta(hours=24, microseconds=-1), now))
        self.assertFalse(retry_allowed(now - timedelta(hours=24), now))
        self.assertFalse(retry_allowed(now + timedelta(seconds=1), now))

    def test_sending_attempt_is_active_only_during_the_recovery_lease(self):
        attempt_active = getattr(inquiry_response, "inquiry_reply_attempt_active", None)
        self.assertIsNotNone(
            attempt_active,
            "production active-attempt policy helper is missing",
        )
        now = datetime(2026, 8, 7, 12, 0, tzinfo=timezone.utc)

        self.assertTrue(attempt_active(now - timedelta(minutes=1, microseconds=-1), now, 60))
        self.assertFalse(attempt_active(now - timedelta(minutes=1), now, 60))


if __name__ == "__main__":
    unittest.main()
