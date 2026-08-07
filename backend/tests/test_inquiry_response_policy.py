import unittest
from uuid import UUID

from pydantic import ValidationError

from inquiry_response import (
    InquiryReplyRequest,
    InquiryReasonCode,
    InquiryStatus,
    InquiryUpdateRequest,
    extract_default_assignee_name,
    mask_line_destination,
    normalize_assignee_name,
    validate_operator_status_transition,
)


class InquiryResponsePolicyTests(unittest.TestCase):
    def test_extract_default_assignee_name_returns_first_space_delimited_name(self):
        self.assertEqual("佐藤", extract_default_assignee_name(" 佐藤 太郎 "))
        self.assertEqual("佐藤", extract_default_assignee_name("佐藤　太郎"))
        self.assertEqual("佐藤", extract_default_assignee_name("佐藤   太郎"))

    def test_extract_default_assignee_name_keeps_single_token_and_rejects_blank_value(self):
        self.assertEqual("佐藤太郎", extract_default_assignee_name("佐藤太郎"))
        self.assertEqual("", extract_default_assignee_name(" \u3000 "))
        self.assertEqual("", extract_default_assignee_name(None))

    def test_normalize_assignee_name_preserves_manual_inner_spacing(self):
        self.assertEqual("田中 花子", normalize_assignee_name(" 田中 花子 "))
        self.assertEqual("田中　花子", normalize_assignee_name("\u3000田中　花子\u3000"))

    def test_normalize_assignee_name_rejects_blank_or_too_long_values(self):
        with self.assertRaises(ValueError):
            normalize_assignee_name(" \u3000 ")
        with self.assertRaises(ValueError):
            normalize_assignee_name("あ" * 81)

    def test_operator_status_transition_allows_start_and_reopen(self):
        self.assertTrue(validate_operator_status_transition("未対応", "対応中").allowed)
        self.assertTrue(validate_operator_status_transition("対応済み", "対応中").allowed)

    def test_operator_status_transition_allows_idempotent_noop(self):
        decision = validate_operator_status_transition("対応中", "対応中")

        self.assertTrue(decision.allowed)
        self.assertIsNone(decision.reason_code)

    def test_operator_status_transition_rejects_finalization_and_unknown_values(self):
        completed = validate_operator_status_transition("対応中", "対応済み")
        unknown = validate_operator_status_transition("unknown", "対応中")

        self.assertFalse(completed.allowed)
        self.assertEqual(InquiryReasonCode.INVALID_STATUS_TRANSITION, completed.reason_code)
        self.assertFalse(unknown.allowed)
        self.assertEqual(InquiryReasonCode.INVALID_STATUS_TRANSITION, unknown.reason_code)

    def test_mask_line_destination_does_not_return_raw_destination(self):
        destination = "Uabcdefghijklmnopqrstuvwxyz1234"

        self.assertEqual("Uabcd…1234", mask_line_destination(destination))
        self.assertNotEqual(destination, mask_line_destination(destination))
        self.assertEqual("…", mask_line_destination("U123"))


class InquiryRequestContractTests(unittest.TestCase):
    expected_updated_at = "2026-08-06T00:00:00Z"
    idempotency_key = "2b0d4d25-74f2-48cf-8e3d-2d30b0b0099b"

    def valid_reply_payload(self):
        return {
            "assignee_name": "\u7530\u4e2d \u592a\u90ce",
            "message": "\u3054\u8fd4\u4fe1\u3042\u308a\u304c\u3068\u3046\u3054\u3056\u3044\u307e\u3059\u3002\n\u8a73\u7d30\u3092\u3054\u6848\u5185\u3057\u307e\u3059\u3002",
            "idempotency_key": self.idempotency_key,
            "expected_updated_at": self.expected_updated_at,
        }

    def test_update_accepts_status_and_timezone_aware_timestamp(self):
        request = InquiryUpdateRequest(
            status=InquiryStatus.IN_PROGRESS.value,
            expected_updated_at=self.expected_updated_at,
        )

        self.assertEqual(InquiryStatus.IN_PROGRESS, request.status)
        self.assertIsNotNone(request.expected_updated_at.tzinfo)

    def test_update_accepts_trimmed_assignee_and_preserves_inner_spacing(self):
        request = InquiryUpdateRequest(
            assignee_name="  \u7530\u4e2d  \u592a\u90ce\u3000",
            expected_updated_at=self.expected_updated_at,
        )

        self.assertEqual("\u7530\u4e2d  \u592a\u90ce", request.assignee_name)

    def test_update_accepts_an_80_character_assignee(self):
        request = InquiryUpdateRequest(
            assignee_name="a" * 80,
            expected_updated_at=self.expected_updated_at,
        )

        self.assertEqual("a" * 80, request.assignee_name)

    def test_update_rejects_empty_whitespace_or_81_character_assignee(self):
        for assignee_name in ("", " \u3000 ", "a" * 81):
            with self.subTest(assignee_name=repr(assignee_name)):
                with self.assertRaises(ValidationError):
                    InquiryUpdateRequest(
                        assignee_name=assignee_name,
                        expected_updated_at=self.expected_updated_at,
                    )

    def test_update_rejects_invalid_status(self):
        with self.assertRaises(ValidationError):
            InquiryUpdateRequest(
                status="not-a-status",
                expected_updated_at=self.expected_updated_at,
            )

    def test_update_rejects_a_request_without_mutable_fields(self):
        with self.assertRaises(ValidationError):
            InquiryUpdateRequest(expected_updated_at=self.expected_updated_at)

    def test_update_rejects_naive_timestamp_and_unknown_field(self):
        with self.assertRaises(ValidationError):
            InquiryUpdateRequest(
                status=InquiryStatus.IN_PROGRESS.value,
                expected_updated_at="2026-08-06T00:00:00",
            )
        with self.assertRaises(ValidationError):
            InquiryUpdateRequest(
                status=InquiryStatus.IN_PROGRESS.value,
                expected_updated_at=self.expected_updated_at,
                company_id="browser-controlled",
            )

    def test_reply_accepts_valid_payload_and_preserves_message_whitespace(self):
        payload = self.valid_reply_payload()
        payload["assignee_name"] = " \u3000\u7530\u4e2d \u592a\u90ce "
        payload["message"] = "  \u3054\u8fd4\u4fe1\u3042\u308a\u304c\u3068\u3046\u3054\u3056\u3044\u307e\u3059\u3002\n\u8a73\u7d30\u3092\u3054\u6848\u5185\u3057\u307e\u3059\u3002\n"

        request = InquiryReplyRequest(**payload)

        self.assertEqual("\u7530\u4e2d \u592a\u90ce", request.assignee_name)
        self.assertEqual(payload["message"], request.message)
        self.assertEqual(UUID(self.idempotency_key), request.idempotency_key)
        self.assertIsNotNone(request.expected_updated_at.tzinfo)

    def test_reply_rejects_invalid_message_bodies(self):
        emoji = "\U0001f600"
        for message in ("", " \n\u3000", "a" * 5001, emoji * 2501, "\ud800", 123):
            with self.subTest(message=repr(message)[:40]):
                payload = self.valid_reply_payload()
                payload["message"] = message
                with self.assertRaises(ValidationError):
                    InquiryReplyRequest(**payload)

    def test_reply_accepts_message_at_utf16_boundaries(self):
        emoji = "\U0001f600"
        for message in ("a" * 5000, emoji * 2500):
            with self.subTest(message_length=len(message)):
                payload = self.valid_reply_payload()
                payload["message"] = message
                self.assertEqual(message, InquiryReplyRequest(**payload).message)

    def test_reply_rejects_missing_required_fields(self):
        for missing_field in self.valid_reply_payload():
            with self.subTest(missing_field=missing_field):
                payload = self.valid_reply_payload()
                del payload[missing_field]
                with self.assertRaises(ValidationError):
                    InquiryReplyRequest(**payload)

    def test_reply_rejects_naive_timestamp_non_string_assignee_and_invalid_uuid(self):
        for field, value in (
            ("expected_updated_at", "2026-08-06T00:00:00"),
            ("assignee_name", 123),
            ("idempotency_key", "not-a-uuid"),
        ):
            with self.subTest(field=field):
                payload = self.valid_reply_payload()
                payload[field] = value
                with self.assertRaises(ValidationError):
                    InquiryReplyRequest(**payload)

    def test_reply_forbids_browser_controlled_server_fields(self):
        for field, value in (
            ("company_id", "browser-company"),
            ("line_user_id", "U" + ("0" * 32)),
            ("line_retry_key", self.idempotency_key),
            ("delivery_status", "sent"),
            ("reply_id", self.idempotency_key),
            ("actor_user_id", self.idempotency_key),
        ):
            with self.subTest(field=field):
                payload = self.valid_reply_payload()
                payload[field] = value
                with self.assertRaises(ValidationError):
                    InquiryReplyRequest(**payload)


if __name__ == "__main__":
    unittest.main()
