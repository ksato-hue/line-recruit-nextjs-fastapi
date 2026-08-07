import unittest

from inquiry_response import (
    InquiryReasonCode,
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


if __name__ == "__main__":
    unittest.main()
