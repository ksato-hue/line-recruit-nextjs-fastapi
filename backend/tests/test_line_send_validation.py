import unittest
from unittest.mock import call, patch

from fastapi.testclient import TestClient
from pydantic import ValidationError

from line_send_validation import (
    LineSendRequest,
    utf16_code_unit_length,
    validate_line_message_text,
)
from tests.support import load_backend_main


main = load_backend_main()
VALID_LINE_USER_ID = "U" + ("0" * 32)


class Utf16CodeUnitLengthTests(unittest.TestCase):
    def test_empty_string_has_zero_code_units(self):
        self.assertEqual(0, utf16_code_unit_length(""))

    def test_ascii_uses_one_code_unit_per_character(self):
        self.assertEqual(3, utf16_code_unit_length("abc"))

    def test_japanese_bmp_characters_use_one_code_unit_each(self):
        self.assertEqual(2, utf16_code_unit_length("採用"))

    def test_newline_uses_one_code_unit(self):
        self.assertEqual(3, utf16_code_unit_length("a\nb"))

    def test_emoji_uses_two_code_units(self):
        self.assertEqual(2, utf16_code_unit_length("😀"))

    def test_mixed_text_counts_bmp_and_supplementary_characters(self):
        self.assertEqual(4, utf16_code_unit_length("採用😀"))

    def test_helper_does_not_count_a_byte_order_mark(self):
        self.assertEqual(1, utf16_code_unit_length("a"))

    def test_isolated_surrogate_is_rejected(self):
        with self.assertRaises(UnicodeEncodeError):
            utf16_code_unit_length("\ud800")


class LineUserIdValidationTests(unittest.TestCase):
    def assert_invalid(self, value):
        with self.assertRaises(ValidationError):
            LineSendRequest(line_user_id=value, message="連絡です")

    def test_accepts_exact_line_user_id(self):
        request = LineSendRequest(
            line_user_id="U0123456789abcdef0123456789abcdef",
            message="連絡です",
        )

        self.assertEqual("U0123456789abcdef0123456789abcdef", request.line_user_id)

    def test_rejects_empty_line_user_id(self):
        self.assert_invalid("")

    def test_rejects_missing_line_user_id(self):
        with self.assertRaises(ValidationError):
            LineSendRequest(message="連絡です")

    def test_rejects_null_line_user_id(self):
        self.assert_invalid(None)

    def test_rejects_numeric_line_user_id(self):
        self.assert_invalid(123)

    def test_rejects_leading_whitespace(self):
        self.assert_invalid(" " + VALID_LINE_USER_ID)

    def test_rejects_trailing_whitespace(self):
        self.assert_invalid(VALID_LINE_USER_ID + " ")

    def test_rejects_lowercase_u_prefix(self):
        self.assert_invalid("u" + ("0" * 32))

    def test_rejects_c_prefix(self):
        self.assert_invalid("C" + ("0" * 32))

    def test_rejects_r_prefix(self):
        self.assert_invalid("R" + ("0" * 32))

    def test_rejects_31_character_body(self):
        self.assert_invalid("U" + ("0" * 31))

    def test_rejects_33_character_body(self):
        self.assert_invalid("U" + ("0" * 33))

    def test_rejects_uppercase_hexadecimal_body(self):
        self.assert_invalid("U" + ("0" * 31) + "A")

    def test_rejects_non_hexadecimal_body(self):
        self.assert_invalid("U" + ("0" * 31) + "g")

    def test_rejects_human_search_line_id(self):
        self.assert_invalid("recruit_example")


class MessageValidationTests(unittest.TestCase):
    def assert_invalid(self, value):
        with self.assertRaises(ValidationError):
            LineSendRequest(line_user_id=VALID_LINE_USER_ID, message=value)

    def test_accepts_normal_japanese_message(self):
        request = LineSendRequest(
            line_user_id=VALID_LINE_USER_ID,
            message="ご応募ありがとうございます。",
        )

        self.assertEqual("ご応募ありがとうございます。", request.message)

    def test_accepts_one_character_message(self):
        request = LineSendRequest(line_user_id=VALID_LINE_USER_ID, message="a")

        self.assertEqual("a", request.message)

    def test_rejects_empty_message(self):
        self.assert_invalid("")

    def test_rejects_space_only_message(self):
        self.assert_invalid("   ")

    def test_rejects_newline_only_message(self):
        self.assert_invalid("\n\r\n")

    def test_rejects_missing_message(self):
        with self.assertRaises(ValidationError):
            LineSendRequest(line_user_id=VALID_LINE_USER_ID)

    def test_rejects_null_message(self):
        self.assert_invalid(None)

    def test_rejects_numeric_message(self):
        self.assert_invalid(123)

    def test_rejects_list_message(self):
        self.assert_invalid(["連絡です"])

    def test_accepts_5000_ascii_code_units(self):
        request = LineSendRequest(
            line_user_id=VALID_LINE_USER_ID,
            message="a" * 5000,
        )

        self.assertEqual(5000, utf16_code_unit_length(request.message))

    def test_rejects_5001_ascii_code_units(self):
        self.assert_invalid("a" * 5001)

    def test_accepts_2500_emoji_as_5000_code_units(self):
        request = LineSendRequest(
            line_user_id=VALID_LINE_USER_ID,
            message="😀" * 2500,
        )

        self.assertEqual(5000, utf16_code_unit_length(request.message))

    def test_rejects_2501_emoji_as_5002_code_units(self):
        self.assert_invalid("😀" * 2501)

    def test_accepts_mixed_japanese_and_emoji(self):
        request = LineSendRequest(
            line_user_id=VALID_LINE_USER_ID,
            message="面接😀\nご案内",
        )

        self.assertEqual("面接😀\nご案内", request.message)

    def test_accepts_mixed_message_at_exact_limit(self):
        request = LineSendRequest(
            line_user_id=VALID_LINE_USER_ID,
            message=("a" * 4998) + "😀",
        )

        self.assertEqual(5000, utf16_code_unit_length(request.message))

    def test_preserves_valid_newlines(self):
        message = "1行目\n2行目\n"
        request = LineSendRequest(line_user_id=VALID_LINE_USER_ID, message=message)

        self.assertEqual(message, request.message)

    def test_preserves_leading_and_trailing_whitespace(self):
        message = "  本文\n"
        request = LineSendRequest(line_user_id=VALID_LINE_USER_ID, message=message)

        self.assertEqual(message, request.message)

    def test_rejects_isolated_surrogate_as_validation_error(self):
        self.assert_invalid("\ud800")


class SharedMessageValidationTests(unittest.TestCase):
    def test_shared_validator_preserves_valid_whitespace_and_newlines(self):
        message = "  First line\nSecond line\n"

        self.assertEqual(message, validate_line_message_text(message))

    def test_shared_validator_rejects_non_string_values(self):
        for value in (None, 123, ["message"]):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    validate_line_message_text(value)

    def test_shared_validator_rejects_empty_or_whitespace_only_messages(self):
        for value in ("", "  ", "\n\r\n"):
            with self.subTest(value=repr(value)):
                with self.assertRaises(ValueError):
                    validate_line_message_text(value)

    def test_shared_validator_enforces_utf16_limit_for_ascii(self):
        self.assertEqual("a" * 5000, validate_line_message_text("a" * 5000))

        with self.assertRaises(ValueError):
            validate_line_message_text("a" * 5001)

    def test_shared_validator_enforces_utf16_limit_for_emoji(self):
        emoji = "\U0001f600"
        self.assertEqual(emoji * 2500, validate_line_message_text(emoji * 2500))

        with self.assertRaises(ValueError):
            validate_line_message_text(emoji * 2501)

    def test_shared_validator_rejects_an_isolated_surrogate(self):
        with self.assertRaises(ValueError):
            validate_line_message_text("\ud800")


class RequestShapeValidationTests(unittest.TestCase):
    def test_accepts_exact_two_field_request(self):
        request = LineSendRequest(
            line_user_id=VALID_LINE_USER_ID,
            message="面接のご案内です",
        )

        self.assertEqual(
            {
                "line_user_id": VALID_LINE_USER_ID,
                "message": "面接のご案内です",
            },
            request.model_dump(),
        )

    def test_rejects_unknown_field(self):
        with self.assertRaises(ValidationError):
            LineSendRequest(
                line_user_id=VALID_LINE_USER_ID,
                message="面接のご案内です",
                applicant_id="example",
            )

    def test_reports_both_invalid_fields(self):
        with self.assertRaises(ValidationError) as raised:
            LineSendRequest(line_user_id="invalid", message="")

        self.assertGreaterEqual(len(raised.exception.errors()), 2)

    def test_rejects_empty_object(self):
        with self.assertRaises(ValidationError) as raised:
            LineSendRequest()

        self.assertEqual(2, len(raised.exception.errors()))


class LineSendEndpointValidationTests(unittest.TestCase):
    def setUp(self):
        self.admin_key_patch = patch.object(main, "ADMIN_API_KEY", "test-admin-key")
        self.admin_key_patch.start()
        self.client = TestClient(main.app)
        self.headers = {"X-Admin-Key": "test-admin-key"}

    def tearDown(self):
        self.client.close()
        self.admin_key_patch.stop()

    def post(self, payload):
        return self.client.post(
            "/api/line/send",
            headers=self.headers,
            json=payload,
        )

    def test_valid_request_calls_sender_exactly_once(self):
        with (
            patch.object(main, "push_line_message") as send,
            patch.object(main, "try_insert_line_message_log"),
        ):
            response = self.post({
                "line_user_id": VALID_LINE_USER_ID,
                "message": "ご連絡です",
            })

        self.assertEqual(200, response.status_code)
        send.assert_called_once_with(VALID_LINE_USER_ID, "ご連絡です")

    def test_valid_request_writes_manual_outbound_log_exactly_once(self):
        with (
            patch.object(main, "push_line_message"),
            patch.object(main, "try_insert_line_message_log") as log,
        ):
            response = self.post({
                "line_user_id": VALID_LINE_USER_ID,
                "message": "ご連絡です",
            })

        self.assertEqual(200, response.status_code)
        log.assert_called_once_with(
            VALID_LINE_USER_ID,
            "ご連絡です",
            "outbound",
            "manual",
        )

    def test_valid_request_preserves_send_then_log_order(self):
        events = []
        with (
            patch.object(
                main,
                "push_line_message",
                side_effect=lambda *_args: events.append("send"),
            ),
            patch.object(
                main,
                "try_insert_line_message_log",
                side_effect=lambda *_args: events.append("log"),
            ),
        ):
            response = self.post({
                "line_user_id": VALID_LINE_USER_ID,
                "message": "ご連絡です",
            })

        self.assertEqual(200, response.status_code)
        self.assertEqual(["send", "log"], events)

    def test_valid_response_contract_is_unchanged(self):
        with (
            patch.object(main, "push_line_message"),
            patch.object(main, "try_insert_line_message_log"),
        ):
            response = self.post({
                "line_user_id": VALID_LINE_USER_ID,
                "message": "ご連絡です",
            })

        self.assertEqual(
            {
                "status": "sent",
                "line_user_id": VALID_LINE_USER_ID,
                "message": "ご連絡です",
            },
            response.json(),
        )

    def test_existing_frontend_payload_succeeds(self):
        payload = {
            "line_user_id": VALID_LINE_USER_ID,
            "message": "応募者へ送るメッセージ",
        }
        with (
            patch.object(main, "push_line_message"),
            patch.object(main, "try_insert_line_message_log"),
        ):
            response = self.post(payload)

        self.assertEqual(200, response.status_code)

    def test_invalid_line_user_id_returns_422_without_side_effects(self):
        with (
            patch.object(main, "push_line_message") as send,
            patch.object(main, "try_insert_line_message_log") as log,
        ):
            response = self.post({
                "line_user_id": "invalid",
                "message": "ご連絡です",
            })

        self.assertEqual(422, response.status_code)
        send.assert_not_called()
        log.assert_not_called()

    def test_empty_message_returns_422_without_side_effects(self):
        with (
            patch.object(main, "push_line_message") as send,
            patch.object(main, "try_insert_line_message_log") as log,
        ):
            response = self.post({
                "line_user_id": VALID_LINE_USER_ID,
                "message": "",
            })

        self.assertEqual(422, response.status_code)
        send.assert_not_called()
        log.assert_not_called()

    def test_5001_code_unit_message_returns_422_without_side_effects(self):
        with (
            patch.object(main, "push_line_message") as send,
            patch.object(main, "try_insert_line_message_log") as log,
        ):
            response = self.post({
                "line_user_id": VALID_LINE_USER_ID,
                "message": "a" * 5001,
            })

        self.assertEqual(422, response.status_code)
        send.assert_not_called()
        log.assert_not_called()

    def test_unknown_field_returns_422_without_side_effects(self):
        with (
            patch.object(main, "push_line_message") as send,
            patch.object(main, "try_insert_line_message_log") as log,
        ):
            response = self.post({
                "line_user_id": VALID_LINE_USER_ID,
                "message": "ご連絡です",
                "unexpected": True,
            })

        self.assertEqual(422, response.status_code)
        send.assert_not_called()
        log.assert_not_called()

    def test_missing_admin_key_remains_401(self):
        with (
            patch.object(main, "push_line_message") as send,
            patch.object(main, "try_insert_line_message_log") as log,
        ):
            response = self.client.post(
                "/api/line/send",
                json={
                    "line_user_id": VALID_LINE_USER_ID,
                    "message": "ご連絡です",
                },
            )

        self.assertEqual(401, response.status_code)
        send.assert_not_called()
        log.assert_not_called()

    def test_unconfigured_admin_key_remains_fail_closed(self):
        with (
            patch.object(main, "ADMIN_API_KEY", None),
            patch.object(main, "push_line_message") as send,
            patch.object(main, "try_insert_line_message_log") as log,
        ):
            response = self.post({
                "line_user_id": VALID_LINE_USER_ID,
                "message": "ご連絡です",
            })

        self.assertEqual(503, response.status_code)
        send.assert_not_called()
        log.assert_not_called()

    def test_sender_failure_does_not_write_success_log(self):
        with (
            patch.object(
                main,
                "push_line_message",
                side_effect=main.HTTPException(status_code=502, detail="send failed"),
            ) as send,
            patch.object(main, "try_insert_line_message_log") as log,
        ):
            response = self.post({
                "line_user_id": VALID_LINE_USER_ID,
                "message": "ご連絡です",
            })

        self.assertEqual(502, response.status_code)
        send.assert_has_calls([call(VALID_LINE_USER_ID, "ご連絡です")])
        log.assert_not_called()


if __name__ == "__main__":
    unittest.main()
