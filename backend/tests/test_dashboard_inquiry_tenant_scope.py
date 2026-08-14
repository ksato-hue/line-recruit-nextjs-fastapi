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
        self.database.queries.append(self)
        self.selected_columns: str | None = None
        self.filters: list[tuple[str, object]] = []
        self.in_filters: list[tuple[str, tuple[object, ...]]] = []
        self.update_data: dict | None = None
        self.insert_data: dict | None = None
        self.orders: list[tuple[str, bool]] = []
        self.row_limit: int | None = None

    def select(self, columns: str):
        self.selected_columns = columns
        return self

    def update(self, data: dict):
        self.update_data = data
        return self

    def insert(self, data: dict):
        self.insert_data = copy.deepcopy(data)
        return self

    def eq(self, column: str, value: object):
        self.filters.append((column, value))
        return self

    def order(self, column: str, desc: bool = False):
        self.orders.append((column, desc))
        return self

    def in_(self, column: str, values: list[object]):
        self.in_filters.append((column, tuple(values)))
        return self

    def limit(self, value: int):
        self.row_limit = value
        return self

    def execute(self):
        rows = self.database.rows[self.table_name]
        if self.insert_data is not None:
            inserted = {"id": f"inserted-{len(rows) + 1}", **self.insert_data}
            rows.append(inserted)
            self.database.inserted.append(copy.deepcopy(inserted))
            return SimpleNamespace(data=[copy.deepcopy(inserted)])

        matched = [
            row for row in rows
            if all(row.get(column) == value for column, value in self.filters)
            and all(row.get(column) in values for column, values in self.in_filters)
        ]
        for column, desc in reversed(self.orders):
            matched.sort(
                key=lambda row: str(row.get(column) or ""),
                reverse=desc,
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
                    "id": "own-newer", "company_id": "tenant-a", "name": "Own Newer",
                    "line_user_id": "shared-line-user",
                    "status": "新規応募", "interview_status": "面接調整中",
                    "created_at": "2026-07-22T10:00:00+00:00",
                },
                {
                    "id": "own-older", "company_id": "tenant-a", "name": "Own Older",
                    "line_user_id": "older-line-user",
                    "status": "採用", "interview_status": "面接確定",
                    "created_at": "2026-07-21T10:00:00+00:00",
                },
                {
                    "id": "other-new", "company_id": "tenant-b", "name": "Other",
                    "line_user_id": "shared-line-user",
                    "status": "新規応募", "interview_status": "面接調整中",
                    "created_at": "2026-07-23T10:00:00+00:00",
                },
            ],
            "inquiries": [
                {
                    "id": "own-inquiry-new", "company_id": "tenant-a", "status": "未対応",
                    "line_user_id": "shared-line-user", "message": "own new",
                    "created_at": "2026-07-22T10:00:00+00:00", "assignee_name": None,
                    "last_replied_at": None, "updated_at": "2026-07-22T10:00:00+00:00",
                },
                {
                    "id": "own-inquiry-old", "company_id": "tenant-a", "status": "対応済み",
                    "line_user_id": "older-line-user", "message": "own old",
                    "created_at": "2026-07-21T10:00:00+00:00", "assignee_name": "佐藤",
                    "last_replied_at": "2026-07-21T11:00:00+00:00",
                    "updated_at": "2026-07-21T11:00:00+00:00",
                },
                {
                    "id": "other-inquiry", "company_id": "tenant-b", "status": "未対応",
                    "line_user_id": "shared-line-user", "message": "other",
                    "created_at": "2026-07-23T10:00:00+00:00", "assignee_name": None,
                    "last_replied_at": None, "updated_at": "2026-07-23T10:00:00+00:00",
                },
            ],
            "inquiry_replies": [],
            "app_settings": [
                {"company_id": "tenant-a", "key": "recruiter_name", "value": "佐藤 太郎"},
            ],
            "application_sessions": [
                {
                    "id": "own-active", "company_id": "tenant-a", "status": "active",
                    "last_activity_at": "2020-01-01T00:00:00+00:00",
                },
                {
                    "id": "own-completed", "company_id": "tenant-a", "status": "completed",
                    "last_activity_at": "2026-07-22T00:00:00+00:00",
                },
                {
                    "id": "other-active", "company_id": "tenant-b", "status": "active",
                    "last_activity_at": "2020-01-01T00:00:00+00:00",
                },
                {
                    "id": "other-completed", "company_id": "tenant-b", "status": "completed",
                    "last_activity_at": "2026-07-22T00:00:00+00:00",
                },
            ],
        }
        self.inserted: list[dict] = []
        self.queries: list[TenantQuery] = []

    def table(self, name: str):
        if name not in self.rows:
            raise AssertionError(f"Unexpected table access: {name}")
        return TenantQuery(self, name)


class TenantScopeTestCase(unittest.TestCase):
    def setUp(self):
        self.database = TenantSupabase()
        status_settings = [
            {"status_key": "new", "name": "新規応募", "is_active": True},
            {"status_key": "hired", "name": "採用", "is_active": True},
        ]
        status_names = {"new": "新規応募", "hired": "採用"}
        self.patches = [
            patch.object(main, "supabase", self.database),
            patch.object(main, "COMPANY_ID", "tenant-a"),
            patch.object(main, "get_applicant_status_settings", return_value=status_settings),
            patch.object(
                main,
                "get_status_name",
                side_effect=lambda key, fallback: status_names.get(key, fallback),
            ),
        ]
        for active_patch in self.patches:
            active_patch.start()

    def tearDown(self):
        for active_patch in reversed(self.patches):
            active_patch.stop()


class DashboardTenantScopeTests(TenantScopeTestCase):
    def test_dashboard_counts_exclude_other_company(self):
        result = main.api_dashboard()

        self.assertEqual(2, result["applicant_count"])
        self.assertEqual(2, result["inquiry_count"])
        self.assertEqual(2, result["application_started_count"])
        self.assertEqual(1, result["application_completed_count"])
        self.assertEqual(1, result["in_progress_count"])
        self.assertEqual(1, result["dropout_count"])
        self.assertEqual(1, result["interview_count"])
        self.assertEqual(1, result["interview_confirmed_count"])
        self.assertEqual(1, result["unanswered_inquiry_count"])

    def test_dashboard_recent_rows_exclude_other_company(self):
        result = main.api_dashboard()

        self.assertEqual(
            ["own-newer", "own-older"],
            [row["id"] for row in result["recent_applicants"]],
        )
        self.assertEqual(
            ["own-inquiry-new", "own-inquiry-old"],
            [row["id"] for row in result["recent_inquiries"]],
        )
        recent_query = next(
            query
            for query in reversed(self.database.queries)
            if query.table_name == "inquiries" and query.row_limit == 6
        )
        self.assertEqual(
            "id,message,status,created_at,assignee_name,last_replied_at,updated_at",
            recent_query.selected_columns,
        )
        for row in result["recent_inquiries"]:
            self.assertNotIn("line_user_id", row)
            self.assertNotIn("company_id", row)


class InquiryTenantScopeTests(TenantScopeTestCase):
    def test_inquiry_list_excludes_other_company(self):
        result = main.api_inquiries()
        self.assertEqual(
            ["own-inquiry-new", "own-inquiry-old"],
            [row["id"] for row in result["items"]],
        )
        inquiry_query = next(
            query for query in self.database.queries if query.table_name == "inquiries"
        )
        self.assertIn(("company_id", "tenant-a"), inquiry_query.filters)
        self.assertTrue(all("line_user_id" not in row for row in result["items"]))

    def test_inquiry_detail_returns_own_company_record(self):
        self.assertTrue(hasattr(main, "api_inquiry_detail"), "問い合わせ詳細APIが未実装です")
        result = main.api_inquiry_detail("own-inquiry-new")
        self.assertEqual("own-inquiry-new", result["inquiry"]["id"])
        self.assertEqual(
            {"inquiry", "default_assignee_name", "masked_destination", "related_applicants", "replies", "reply_enabled"},
            set(result),
        )
        self.assertNotIn("line_user_id", result["inquiry"])
        inquiry_query = next(
            query for query in self.database.queries if query.table_name == "inquiries"
        )
        self.assertIn(("company_id", "tenant-a"), inquiry_query.filters)

    def test_inquiry_detail_returns_not_found_for_other_company(self):
        self.assertTrue(hasattr(main, "api_inquiry_detail"), "問い合わせ詳細APIが未実装です")
        with self.assertRaises(HTTPException) as raised:
            main.api_inquiry_detail("other-inquiry")
        self.assertEqual(404, raised.exception.status_code)
        inquiry_query = next(
            query for query in self.database.queries if query.table_name == "inquiries"
        )
        self.assertIn(("company_id", "tenant-a"), inquiry_query.filters)

    def test_inquiry_update_does_not_change_other_company(self):
        with self.assertRaises(HTTPException) as raised:
            main.api_update_inquiry("other-inquiry", main.InquiryUpdate(status="対応済み"))
        self.assertEqual(404, raised.exception.status_code)
        self.assertIn(("company_id", "tenant-a"), self.database.queries[-1].filters)
        other = next(
            row for row in self.database.rows["inquiries"]
            if row["id"] == "other-inquiry"
        )
        self.assertEqual("未対応", other["status"])

    def test_inquiry_insert_sets_company_id_explicitly(self):
        with (
            patch.object(main, "user_states", {"line-user": "waiting_inquiry"}),
            patch.object(main, "get_app_settings", return_value={"inquiry_complete_message": "受付済み"}),
        ):
            main.handle_message("line-user", "問い合わせ本文")

        insert_query = next(
            query
            for query in reversed(self.database.queries)
            if query.table_name == "inquiries" and query.insert_data is not None
        )
        self.assertEqual(main.COMPANY_ID, insert_query.insert_data["company_id"])


if __name__ == "__main__":
    unittest.main()
