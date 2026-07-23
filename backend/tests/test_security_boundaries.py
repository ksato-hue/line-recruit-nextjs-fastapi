import base64
import hashlib
import hmac
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from tests.support import load_backend_main


main = load_backend_main()


class LineSignatureTests(unittest.TestCase):
    def setUp(self):
        self.body = b'{"events":[]}'
        self.secret = "test-line-channel-secret"

    def signature(self) -> str:
        digest = hmac.new(self.secret.encode("utf-8"), self.body, hashlib.sha256).digest()
        return base64.b64encode(digest).decode("ascii")

    def test_accepts_valid_signature(self):
        with patch.object(main, "LINE_CHANNEL_SECRET", self.secret):
            self.assertIsNone(main._verify_line_signature(self.body, self.signature()))

    def test_rejects_missing_signature(self):
        with patch.object(main, "LINE_CHANNEL_SECRET", self.secret):
            with self.assertRaises(HTTPException) as raised:
                main._verify_line_signature(self.body, None)
        self.assertEqual(401, raised.exception.status_code)

    def test_rejects_invalid_signature(self):
        with patch.object(main, "LINE_CHANNEL_SECRET", self.secret):
            with self.assertRaises(HTTPException) as raised:
                main._verify_line_signature(self.body, "invalid")
        self.assertEqual(401, raised.exception.status_code)

    def test_rejects_when_channel_secret_is_not_configured(self):
        with patch.object(main, "LINE_CHANNEL_SECRET", None):
            with self.assertRaises(HTTPException) as raised:
                main._verify_line_signature(self.body, "anything")
        self.assertEqual(503, raised.exception.status_code)


class AdminApiKeyTests(unittest.TestCase):
    def test_accepts_matching_admin_key(self):
        with patch.object(main, "ADMIN_API_KEY", "server-secret"):
            self.assertIsNone(main.require_admin("server-secret"))

    def test_rejects_missing_request_key(self):
        with patch.object(main, "ADMIN_API_KEY", "server-secret"):
            with self.assertRaises(HTTPException) as raised:
                main.require_admin(None)
        self.assertEqual(401, raised.exception.status_code)

    def test_rejects_mismatched_request_key(self):
        with patch.object(main, "ADMIN_API_KEY", "server-secret"):
            with self.assertRaises(HTTPException) as raised:
                main.require_admin("wrong-secret")
        self.assertEqual(401, raised.exception.status_code)

    def test_rejects_when_server_key_is_not_configured(self):
        with patch.object(main, "ADMIN_API_KEY", None):
            with self.assertRaises(HTTPException) as raised:
                main.require_admin("anything")
        self.assertEqual(503, raised.exception.status_code)


if __name__ == "__main__":
    unittest.main()
