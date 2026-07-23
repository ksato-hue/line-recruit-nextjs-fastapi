import copy
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from tests.support import load_backend_main


main = load_backend_main()


class TenantQuery:
    def __init__(self, database, table_name: str):
        self.database = database
        self.table_name = table_name
        self.equal_filters: list[tuple[str, object]] = []
        self.not_equal_filters: list[tuple[str, object]] = []
        self.insert_data: dict | list[dict] | None = None
        self.update_data: dict | None = None
        self.order_column: str | None = None
        self.order_desc = False
        self.row_limit: int | None = None

    def select(self, _columns: str):
        return self

    def insert(self, data: dict | list[dict]):
        self.insert_data = copy.deepcopy(data)
        return self

    def update(self, data: dict):
        self.update_data = copy.deepcopy(data)
        return self

    def eq(self, column: str, value: object):
        self.equal_filters.append((column, value))
        return self

    def neq(self, column: str, value: object):
        self.not_equal_filters.append((column, value))
        return self

    def order(self, column: str, desc: bool = False):
        self.order_column = column
        self.order_desc = desc
        return self

    def limit(self, value: int):
        self.row_limit = value
        return self

    def execute(self):
        operation = "insert" if self.insert_data is not None else "update" if self.update_data is not None else "select"
        self.database.executed.append({
            "table": self.table_name,
            "operation": operation,
            "eq": copy.deepcopy(self.equal_filters),
            "neq": copy.deepcopy(self.not_equal_filters),
        })

        rows = self.database.rows[self.table_name]
        if self.insert_data is not None:
            values = self.insert_data if isinstance(self.insert_data, list) else [self.insert_data]
            inserted = []
            for value in values:
                row = {"id": f"inserted-{self.table_name}-{len(rows) + 1}", **value}
                rows.append(copy.deepcopy(row))
                self.database.inserted[self.table_name].append(copy.deepcopy(row))
                inserted.append(copy.deepcopy(row))
            return SimpleNamespace(data=inserted)

        matched = [
            row for row in rows
            if all(row.get(column) == value for column, value in self.equal_filters)
            and all(row.get(column) != value for column, value in self.not_equal_filters)
        ]
        if self.order_column:
            matched.sort(
                key=lambda row: str(row.get(self.order_column) or ""),
                reverse=self.order_desc,
            )
        if self.row_limit is not None:
            matched = matched[:self.row_limit]
        if self.update_data is not None:
            for row in matched:
                row.update(self.update_data)
        return SimpleNamespace(data=[copy.deepcopy(row) for row in matched])


class TenantSupabase:
    def __init__(self):
        self.rows = {
            "applicants": [
                {
                    "id": "own-applicant", "company_id": "tenant-a", "line_user_id": "shared-line",
                    "status": "新規応募", "interview_status": "未設定", "interview_date": None,
                },
                {
                    "id": "own-applicant", "company_id": "tenant-b", "line_user_id": "shared-line",
                    "status": "新規応募", "interview_status": "未設定", "interview_date": None,
                },
                {
                    "id": "other-applicant", "company_id": "tenant-b", "line_user_id": "other-line",
                    "status": "新規応募", "interview_status": "未設定", "interview_date": None,
                },
            ],
            "interview_slots": [
                {
                    "id": "own-slot", "company_id": "tenant-a", "applicant_id": "own-applicant",
                    "line_user_id": "shared-line", "slot_datetime": "2026-08-01 10:00",
                    "status": "候補", "interview_type": "1次面接", "created_at": "2026-07-23T10:00:00+00:00",
                },
                {
                    "id": "own-sibling", "company_id": "tenant-a", "applicant_id": "own-applicant",
                    "line_user_id": "shared-line", "slot_datetime": "2026-08-01 11:00",
                    "status": "確認待ち", "interview_type": "1次面接", "created_at": "2026-07-23T11:00:00+00:00",
                },
                {
                    "id": "other-overlap", "company_id": "tenant-b", "applicant_id": "own-applicant",
                    "line_user_id": "shared-line", "slot_datetime": "2026-08-01 10:00",
                    "status": "候補", "interview_type": "他社面接", "created_at": "2026-07-23T12:00:00+00:00",
                },
                {
                    "id": "other-sibling", "company_id": "tenant-b", "applicant_id": "own-applicant",
                    "line_user_id": "shared-line", "slot_datetime": "2026-08-01 13:00",
                    "status": "候補", "interview_type": "他社面接", "created_at": "2026-07-23T13:00:00+00:00",
                },
                {
                    "id": "own-sibling", "company_id": "tenant-b", "applicant_id": "other-applicant",
                    "line_user_id": "other-line", "slot_datetime": "2026-08-02 11:00",
                    "status": "確認待ち", "interview_type": "他社面接", "created_at": "2026-07-23T14:00:00+00:00",
                },
                {
                    "id": "own-pending", "company_id": "tenant-a", "applicant_id": "own-applicant",
                    "line_user_id": "pending-line", "slot_datetime": "2026-08-03 10:00",
                    "status": "確認待ち", "interview_type": "1次面接", "created_at": "2026-07-23T15:00:00+00:00",
                },
                {
                    "id": "other-pending", "company_id": "tenant-b", "applicant_id": "other-applicant",
                    "line_user_id": "pending-line", "slot_datetime": "2026-08-03 12:00",
                    "status": "確認待ち", "interview_type": "他社面接", "created_at": "2026-07-23T16:00:00+00:00",
                },
                {
                    "id": "other-slot", "company_id": "tenant-b", "applicant_id": "other-applicant",
                    "line_user_id": "other-line", "slot_datetime": "2026-08-04 10:00",
                    "status": "候補", "interview_type": "他社面接", "created_at": "2026-07-23T17:00:00+00:00",
                },
            ],
            "line_message_logs": [
                {
                    "id": "own-message", "company_id": "tenant-a", "line_user_id": "shared-line",
                    "message": "own", "direction": "inbound", "message_type": "reply",
                    "created_at": "2026-07-23T10:00:00+00:00",
                },
                {
                    "id": "other-shared-message", "company_id": "tenant-b", "line_user_id": "shared-line",
                    "message": "other shared", "direction": "inbound", "message_type": "reply",
                    "created_at": "2026-07-23T11:00:00+00:00",
                },
                {
                    "id": "other-only-message", "company_id": "tenant-b", "line_user_id": "other-only-line",
                    "message": "other only", "direction": "outbound", "message_type": "manual",
                    "created_at": "2026-07-23T12:00:00+00:00",
                },
            ],
        }
        self.executed: list[dict] = []
        self.inserted = {table_name: [] for table_name in self.rows}

    def table(self, name: str):
        if name not in self.rows:
            raise AssertionError(f"Unexpected table access: {name}")
        return TenantQuery(self, name)

    def row(self, table_name: str, row_id: str, company_id: str):
        return next(
            row for row in self.rows[table_name]
            if row["id"] == row_id and row["company_id"] == company_id
        )

    def last_query(self, table_name: str, operation: str):
        return next(
            query for query in reversed(self.executed)
            if query["table"] == table_name and query["operation"] == operation
        )


class TenantScopeTestCase(unittest.TestCase):
    def setUp(self):
        self.database = TenantSupabase()
        self.patches = [
            patch.object(main, "supabase", self.database),
            patch.object(main, "COMPANY_ID", "tenant-a"),
            patch.object(main, "user_states", {}),
            patch.object(main, "interview_confirmations", {}),
            patch.object(main, "get_app_settings", return_value={
                "interview_slots_message": "候補日を選択してください",
                "interview_confirmed_message": "確定しました",
            }),
            patch.object(main, "get_status_name", side_effect=lambda _key, fallback: fallback),
        ]
        for active_patch in self.patches:
            active_patch.start()

    def tearDown(self):
        for active_patch in reversed(self.patches):
            active_patch.stop()

    def assert_last_query_is_scoped(self, table_name: str, operation: str):
        query = self.database.last_query(table_name, operation)
        self.assertIn(("company_id", "tenant-a"), query["eq"])


class InterviewTenantScopeTests(TenantScopeTestCase):
    def test_interview_list_excludes_other_company(self):
        result = main.api_get_interview_slots("own-applicant")

        self.assertEqual(
            ["own-slot", "own-sibling", "own-pending"],
            [row["id"] for row in result],
        )
        self.assert_last_query_is_scoped("interview_slots", "select")

    def test_active_slot_lookup_returns_only_own_company_slot(self):
        result = main._find_active_interview_slot("shared-line", "2026-08-01 10:00")

        self.assertEqual("own-slot", result["id"])
        self.assert_last_query_is_scoped("interview_slots", "select")

    def test_pending_confirmation_lookup_returns_only_own_company_slot(self):
        result = main._get_pending_interview_confirmation("pending-line")

        self.assertEqual("own-pending", result["slot_id"])
        self.assertEqual("tenant-a", result["company_id"])
        self.assert_last_query_is_scoped("interview_slots", "select")

    def test_internal_slot_lookup_returns_not_found_for_other_company(self):
        self.assertTrue(
            hasattr(main, "_get_interview_slot_or_404"),
            "企業スコープ済みの面接候補取得ヘルパーが未実装です",
        )
        with self.assertRaises(HTTPException) as raised:
            main._get_interview_slot_or_404("other-slot")

        self.assertEqual(404, raised.exception.status_code)
        self.assert_last_query_is_scoped("interview_slots", "select")

    def _assert_other_company_patch_is_rejected(self, payload):
        before = copy.deepcopy(self.database.row("interview_slots", "other-slot", "tenant-b"))

        with self.assertRaises(HTTPException) as raised:
            main.api_update_interview_slot("other-slot", payload)

        self.assertEqual(404, raised.exception.status_code)
        self.assertEqual(before, self.database.row("interview_slots", "other-slot", "tenant-b"))

    def test_other_company_slot_cannot_be_updated(self):
        self._assert_other_company_patch_is_rejected(
            main.InterviewSlotUpdate(interview_type="変更後"),
        )

    def test_other_company_slot_cannot_be_confirmed(self):
        self._assert_other_company_patch_is_rejected(
            main.InterviewSlotUpdate(status="選択済み"),
        )

    def test_other_company_slot_cannot_be_cancelled(self):
        self._assert_other_company_patch_is_rejected(
            main.InterviewSlotUpdate(status="キャンセル"),
        )

    def test_own_company_patch_update_query_is_scoped(self):
        result = main.api_update_interview_slot(
            "own-slot",
            main.InterviewSlotUpdate(interview_type="更新後面接"),
        )

        self.assertEqual("更新後面接", result["interview_type"])
        update_query = self.database.last_query("interview_slots", "update")
        self.assertIn(("id", "own-slot"), update_query["eq"])
        self.assertIn(("company_id", "tenant-a"), update_query["eq"])

    def test_interview_create_sets_company_id_explicitly(self):
        with (
            patch.object(main, "push_line_message"),
            patch.object(main, "try_insert_line_message_log"),
        ):
            main.api_create_interview_slots(
                "own-applicant",
                main.InterviewSlotCreate(slots=["2026-08-10T10:00", "2026-08-10T11:00"]),
            )

        inserted = self.database.inserted["interview_slots"]
        self.assertEqual(2, len(inserted))
        self.assertTrue(all(row.get("company_id") == "tenant-a" for row in inserted))
        self.assert_last_query_is_scoped("applicants", "update")

    def test_interview_create_rejects_other_company_applicant_before_side_effects(self):
        with (
            patch.object(main, "push_line_message") as push,
            patch.object(main, "try_insert_line_message_log") as log,
            self.assertRaises(HTTPException) as raised,
        ):
            main.api_create_interview_slots(
                "other-applicant",
                main.InterviewSlotCreate(slots=["2026-08-10T10:00", "2026-08-10T11:00"]),
            )

        self.assertEqual(404, raised.exception.status_code)
        self.assertEqual([], self.database.inserted["interview_slots"])
        push.assert_not_called()
        log.assert_not_called()

    def test_webhook_slot_selection_updates_only_own_company(self):
        other_before = copy.deepcopy(self.database.row("interview_slots", "other-overlap", "tenant-b"))

        response = main.handle_interview_slot_selection("shared-line", "2026-08-01 10:00")

        self.assertIsNotNone(response)
        self.assertEqual("確認待ち", self.database.row("interview_slots", "own-slot", "tenant-a")["status"])
        self.assertEqual(other_before, self.database.row("interview_slots", "other-overlap", "tenant-b"))
        self.assert_last_query_is_scoped("interview_slots", "update")

    def test_webhook_confirmation_updates_and_cancels_only_own_company(self):
        main.interview_confirmations["shared-line"] = {
            "slot_id": "own-slot",
            "applicant_id": "own-applicant",
            "slot_datetime": "2026-08-01 10:00",
            "interview_type": "1次面接",
            "company_id": "tenant-a",
        }
        other_slot_before = copy.deepcopy(self.database.row("interview_slots", "other-overlap", "tenant-b"))
        other_applicant_before = copy.deepcopy(self.database.row("applicants", "own-applicant", "tenant-b"))

        main._finish_interview_confirmation("shared-line")

        self.assertEqual("選択済み", self.database.row("interview_slots", "own-slot", "tenant-a")["status"])
        self.assertEqual("キャンセル", self.database.row("interview_slots", "own-sibling", "tenant-a")["status"])
        self.assertEqual(other_slot_before, self.database.row("interview_slots", "other-overlap", "tenant-b"))
        self.assertEqual(other_applicant_before, self.database.row("applicants", "own-applicant", "tenant-b"))
        update_queries = [
            query for query in self.database.executed
            if query["operation"] == "update" and query["table"] in {"interview_slots", "applicants"}
        ]
        self.assertTrue(update_queries)
        self.assertTrue(all(("company_id", "tenant-a") in query["eq"] for query in update_queries))

    def test_webhook_reset_updates_and_returns_only_own_company_slots(self):
        main.interview_confirmations["shared-line"] = {
            "slot_id": "own-sibling",
            "applicant_id": "own-applicant",
            "slot_datetime": "2026-08-01 11:00",
            "interview_type": "1次面接",
            "company_id": "tenant-a",
        }
        other_same_id_before = copy.deepcopy(self.database.row("interview_slots", "own-sibling", "tenant-b"))

        response = main._reset_interview_confirmation("shared-line")

        self.assertEqual("候補", self.database.row("interview_slots", "own-sibling", "tenant-a")["status"])
        self.assertEqual(other_same_id_before, self.database.row("interview_slots", "own-sibling", "tenant-b"))
        self.assertNotIn("2026-08-01 13:00", response.get("buttons") or [])
        self.assert_last_query_is_scoped("interview_slots", "select")


class LineMessageTenantScopeTests(TenantScopeTestCase):
    def test_message_list_excludes_other_company(self):
        result = main.api_line_messages()

        self.assertEqual(["own-message"], [row["id"] for row in result])
        self.assert_last_query_is_scoped("line_message_logs", "select")

    def test_shared_line_user_history_returns_only_own_company(self):
        result = main.api_line_messages("shared-line")

        self.assertEqual(["own-message"], [row["id"] for row in result])
        query = self.database.last_query("line_message_logs", "select")
        self.assertIn(("company_id", "tenant-a"), query["eq"])
        self.assertIn(("line_user_id", "shared-line"), query["eq"])

    def test_other_company_user_history_returns_empty_array(self):
        result = main.api_line_messages("other-only-line")

        self.assertEqual([], result)
        self.assert_last_query_is_scoped("line_message_logs", "select")

    def test_message_log_insert_sets_company_id_explicitly(self):
        main.try_insert_line_message_log("shared-line", "new message", "outbound", "manual")

        inserted = self.database.inserted["line_message_logs"]
        self.assertEqual(1, len(inserted))
        self.assertEqual("tenant-a", inserted[0].get("company_id"))


if __name__ == "__main__":
    unittest.main()
