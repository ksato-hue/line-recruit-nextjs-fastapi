import base64
import copy
import hashlib
import hmac
import json
import unittest
from datetime import datetime
from unittest.mock import patch

from fastapi.testclient import TestClient

from tests.support import load_backend_main
from tests.test_interview_message_tenant_scope import TenantQuery, TenantSupabase


main = load_backend_main()


class SchemaAwareRoutingQuery(TenantQuery):
    def execute(self):
        operation = "insert" if self.insert_data is not None else "update" if self.update_data is not None else "select"
        if self.table_name == "interview_slots" and operation == "select":
            slot_value = next(
                (value for column, value in self.equal_filters if column == "slot_datetime"),
                None,
            )
            if slot_value is not None:
                normalized = str(slot_value).replace("T", " ")
                formats = ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S")
                if not any(self._matches_datetime(normalized, date_format) for date_format in formats):
                    raise ValueError("synthetic invalid timestamptz input")
            if self.database.fail_interview_select:
                raise RuntimeError("synthetic interview_slots select failure")
        return super().execute()

    @staticmethod
    def _matches_datetime(value: str, date_format: str) -> bool:
        try:
            datetime.strptime(value, date_format)
            return True
        except ValueError:
            return False


class SchemaAwareRoutingSupabase(TenantSupabase):
    def __init__(self):
        super().__init__()
        self.fail_interview_select = False
        self.rows.update({
            "application_sessions": [],
            "app_settings": [],
            "question_tree_settings": [],
            "applicant_status_settings": [],
            "faq_settings": [],
            "faq_categories": [],
            "faqs": [],
            "inquiries": [],
        })
        self.rows["interview_slots"].extend([
            {
                "id": "own-expired-slot",
                "company_id": "tenant-a",
                "applicant_id": "own-applicant",
                "line_user_id": "shared-line",
                "slot_datetime": "2026-08-05 10:00",
                "status": "期限切れ",
                "interview_type": "1次面接",
                "created_at": "2026-07-23T18:00:00+00:00",
            },
            {
                "id": "own-selected-slot",
                "company_id": "tenant-a",
                "applicant_id": "own-applicant",
                "line_user_id": "shared-line",
                "slot_datetime": "2026-08-06 10:00",
                "status": "選択済み",
                "interview_type": "1次面接",
                "created_at": "2026-07-23T19:00:00+00:00",
            },
        ])
        for applicant in self.rows["applicants"]:
            if applicant["company_id"] == "tenant-a":
                applicant["status"] = "面接調整中"
                applicant["interview_status"] = "面接調整中"
        self.inserted = {table_name: [] for table_name in self.rows}

    def table(self, name: str):
        if name not in self.rows:
            raise AssertionError(f"Unexpected table access: {name}")
        return SchemaAwareRoutingQuery(self, name)


class InterviewRoutingRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.database = SchemaAwareRoutingSupabase()
        self.patches = [
            patch.object(main, "supabase", self.database),
            patch.object(main, "COMPANY_ID", "tenant-a"),
            patch.object(main, "user_states", {}),
            patch.object(main, "applicants", {}),
            patch.object(main, "interview_confirmations", {}),
            patch.object(main, "faq_sessions", {}),
            patch.object(main, "application_tree_sessions", {}),
        ]
        for active_patch in self.patches:
            active_patch.start()

    def tearDown(self):
        for active_patch in reversed(self.patches):
            active_patch.stop()

    def assert_all_conversation_memory_is_empty(self):
        self.assertEqual({}, main.user_states)
        self.assertEqual({}, main.applicants)
        self.assertEqual({}, main.interview_confirmations)
        self.assertEqual({}, main.faq_sessions)
        self.assertEqual({}, main.application_tree_sessions)

    def assert_not_interview_error(self, response):
        text = response.get("text") or response.get("body") or ""
        self.assertNotIn("面接候補日の確認中にエラー", text)

    def test_menu_works_after_restart_with_pending_database_slot(self):
        self.assert_all_conversation_memory_is_empty()
        self.assertTrue(any(row["status"] == "確認待ち" for row in self.database.rows["interview_slots"]))

        response = main.handle_message("shared-line", "メニュー")

        self.assertEqual("知りたい内容を選んでください。", response["text"])

    def test_apply_works_after_restart_with_empty_memory(self):
        self.assert_all_conversation_memory_is_empty()

        response = main.handle_message("shared-line", "応募")

        self.assert_not_interview_error(response)
        self.assertIn("応募", response["text"])

    def test_faq_works_after_restart_with_empty_memory(self):
        self.assert_all_conversation_memory_is_empty()

        response = main.handle_message("shared-line", "よくある質問")

        self.assert_not_interview_error(response)
        self.assertIn("よくある質問", response["text"])

    def test_inquiry_command_escapes_broken_interview_confirmation(self):
        main.user_states["shared-line"] = "confirming_interview_slot"
        main.interview_confirmations["shared-line"] = {
            "slot_id": "own-sibling",
            "applicant_id": "own-applicant",
            "slot_datetime": "2026-08-01 11:00",
            "company_id": "tenant-a",
        }

        response = main.handle_message("shared-line", "お問い合わせ")

        self.assertIn("お問い合わせ内容を入力してください", response["text"])
        self.assertEqual("waiting_inquiry", main.user_states["shared-line"])
        self.assertNotIn("shared-line", main.interview_confirmations)
        self.assertEqual(
            "候補",
            self.database.row("interview_slots", "own-sibling", "tenant-a")["status"],
        )

    def test_cancel_clears_interview_confirmation_for_only_that_user(self):
        main.user_states.update({
            "shared-line": "confirming_interview_slot",
            "other-user": "confirming_interview_slot",
        })
        main.interview_confirmations.update({
            "shared-line": {
                "slot_id": "own-sibling",
                "applicant_id": "own-applicant",
                "slot_datetime": "2026-08-01 11:00",
                "company_id": "tenant-a",
            },
            "other-user": {"slot_id": "other-user-slot", "company_id": "tenant-a"},
        })

        response = main.handle_message("shared-line", "キャンセル")

        self.assertIn("入力をキャンセルしました", response["text"])
        self.assertIsNone(main.user_states["shared-line"])
        self.assertNotIn("shared-line", main.interview_confirmations)
        self.assertEqual(
            "候補",
            self.database.row("interview_slots", "own-sibling", "tenant-a")["status"],
        )
        self.assertEqual("confirming_interview_slot", main.user_states["other-user"])
        self.assertIn("other-user", main.interview_confirmations)

    def test_cancel_after_restart_resets_persisted_pending_slot(self):
        self.assert_all_conversation_memory_is_empty()

        response = main.handle_message("pending-line", "キャンセル")

        self.assertIn("入力をキャンセルしました", response["text"])
        self.assertEqual(
            "候補",
            self.database.row("interview_slots", "own-pending", "tenant-a")["status"],
        )

    def test_unrelated_text_is_not_treated_as_interview_candidate(self):
        response = main.handle_message("shared-line", "営業時間を教えてください")

        self.assert_not_interview_error(response)
        self.assertEqual("お問い合わせ案内", response["title"])

    def test_valid_candidate_text_enters_confirmation(self):
        response = main.handle_message("shared-line", "2026-08-01 10:00")

        self.assertEqual("confirming_interview_slot", main.user_states["shared-line"])
        self.assertEqual("own-slot", main.interview_confirmations["shared-line"]["slot_id"])
        self.assertIn("確定しますか", response["text"])
        selected_query = self.database.last_query("interview_slots", "select")
        self.assertIn(("status", "候補"), selected_query["eq"])

    def test_nonexistent_candidate_identifier_is_safely_rejected(self):
        response = main.handle_message("shared-line", "slot-does-not-exist")

        self.assert_not_interview_error(response)
        self.assertEqual("お問い合わせ案内", response["title"])
        self.assertNotIn("shared-line", main.interview_confirmations)

    def test_selected_candidate_is_not_selectable(self):
        response = main.handle_message("shared-line", "2026-08-06 10:00")

        self.assertEqual("お問い合わせ案内", response["title"])
        self.assertNotIn("shared-line", main.interview_confirmations)

    def test_expired_candidate_status_is_not_selectable(self):
        response = main.handle_message("shared-line", "2026-08-05 10:00")

        self.assertEqual("お問い合わせ案内", response["title"])
        self.assertNotIn("shared-line", main.interview_confirmations)

    def test_database_error_does_not_lock_next_menu_command(self):
        self.database.fail_interview_select = True

        failed = main.handle_message("shared-line", "2026-08-01 10:00")
        recovered = main.handle_message("shared-line", "メニュー")

        self.assertIn("面接候補日の確認中にエラー", failed["text"])
        self.assertEqual("知りたい内容を選んでください。", recovered["text"])

    def test_database_error_clears_only_affected_users_temporary_state(self):
        self.database.fail_interview_select = True
        main.interview_confirmations.update({
            "shared-line": {"slot_id": "stale-own", "company_id": "tenant-a"},
            "other-user": {"slot_id": "stale-other", "company_id": "tenant-a"},
        })

        main.handle_message("shared-line", "2026-08-01 10:00")

        self.assertNotIn("shared-line", main.interview_confirmations)
        self.assertIn("other-user", main.interview_confirmations)

    def test_replayed_confirmation_event_does_not_confirm_twice(self):
        main.handle_message("shared-line", "2026-08-01 10:00", "slot-event")
        main.handle_message("shared-line", "確定する", "confirm-event")
        main.handle_message("shared-line", "確定する", "confirm-event")

        own_slot_updates = [
            query for query in self.database.executed
            if query["table"] == "interview_slots"
            and query["operation"] == "update"
            and ("id", "own-slot") in query["eq"]
        ]
        self.assertEqual(2, len(own_slot_updates))
        self.assertEqual("選択済み", self.database.row("interview_slots", "own-slot", "tenant-a")["status"])

    def test_same_datetime_in_other_company_is_not_selectable(self):
        other_before = copy.deepcopy(
            self.database.row("interview_slots", "other-sibling", "tenant-b")
        )

        response = main.handle_message("shared-line", "2026-08-01 13:00")

        self.assertEqual("お問い合わせ案内", response["title"])
        self.assertEqual(
            other_before,
            self.database.row("interview_slots", "other-sibling", "tenant-b"),
        )

    def test_slot_lookup_error_log_contains_no_raw_user_or_message(self):
        self.database.fail_interview_select = True

        with self.assertLogs("line_recruit", level="INFO") as captured:
            main.handle_message("shared-line", "2026-08-01 10:00")

        log_text = "\n".join(captured.output)
        self.assertIn('"event":"interview.slot.select"', log_text)
        self.assertIn('"error":"RuntimeError"', log_text)
        self.assertNotIn("shared-line", log_text)
        self.assertNotIn("2026-08-01 10:00", log_text)

    def test_webhook_returns_200_when_candidate_lookup_error_is_converted_to_reply(self):
        self.database.fail_interview_select = True
        secret = "local-test-secret"
        body = json.dumps({
            "events": [{
                "type": "message",
                "source": {"userId": "shared-line"},
                "message": {"type": "text", "text": "2026-08-01 10:00"},
                "replyToken": "",
                "webhookEventId": "webhook-event",
            }]
        }).encode("utf-8")
        signature = base64.b64encode(
            hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
        ).decode("ascii")

        with (
            patch.object(main, "LINE_CHANNEL_SECRET", secret),
            patch.object(main, "LINE_ACCESS_TOKEN", None),
        ):
            response = TestClient(main.app).post(
                "/webhook",
                content=body,
                headers={"X-Line-Signature": signature, "Content-Type": "application/json"},
            )

        self.assertEqual(200, response.status_code)
        self.assertEqual({"status": "ok"}, response.json())


if __name__ == "__main__":
    unittest.main()
