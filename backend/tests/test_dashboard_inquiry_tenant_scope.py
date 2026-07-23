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
        self.filters: list[tuple[str, object]] = []
        self.update_data: dict | None = None
        self.insert_data: dict | None = None
        self.order_column: str | None = None
        self.order_desc = False
        self.row_limit: int | None = None

    def select(self, _columns: str):
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
        self.order_column = column
        self.order_desc = desc
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
                    "id": "own-newer", "company_id": "tenant-a", "name": "Own Newer",
                    "status": "新規応募", "interview_status": "面接調整中",
                    "created_at": "2026-07-22T10:00:00+00:00",
                },
                {
                    "id": "own-older", "company_id": "tenant-a", "name": "Own Older",
                    "status": "採用", "interview_status": "面接確定",
                    "created_at": "2026-07-21T10:00:00+00:00",
                },
                {
                    "id": "other-new", "company_id": "tenant-b", "name": "Other",
                    "status": "新規応募", "interview_status": "面接調整中",
                    "created_at": "2026-07-23T10:00:00+00:00",
                },
            ],
            "inquiries": [
                {
                    "id": "own-inquiry-new", "company_id": "tenant-a", "status": "未対応",
                    "message": "own new", "created_at": "2026-07-22T10:00:00+00:00",
                },
                {
                    "id": "own-inquiry-old", "company_id": "tenant-a", "status": "対応済み",
                    "message": "own old", "created_at": "2026-07-21T10:00:00+00:00",
                },
                {
                    "id": "other-inquiry", "company_id": "tenant-b", "status": "未対応",
                    "message": "other", "created_at": "2026-07-23T10:00:00+00:00",
                },
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


class InquiryTenantScopeTests(TenantScopeTestCase):
    def test_inquiry_list_excludes_other_company(self):
        result = main.api_inquiries()
        self.assertEqual(
            ["own-inquiry-new", "own-inquiry-old"],
            [row["id"] for row in result],
        )

    def test_inquiry_detail_returns_own_company_record(self):
        self.assertTrue(hasattr(main, "api_inquiry_detail"), "問い合わせ詳細APIが未実装です")
        result = main.api_inquiry_detail("own-inquiry-new")
        self.assertEqual("own-inquiry-new", result["id"])

    def test_inquiry_detail_returns_not_found_for_other_company(self):
        self.assertTrue(hasattr(main, "api_inquiry_detail"), "問い合わせ詳細APIが未実装です")
        with self.assertRaises(HTTPException) as raised:
            main.api_inquiry_detail("other-inquiry")
        self.assertEqual(404, raised.exception.status_code)

    def test_inquiry_update_does_not_change_other_company(self):
        with self.assertRaises(HTTPException) as raised:
            main.api_update_inquiry("other-inquiry", main.InquiryUpdate(status="対応済み"))
        self.assertEqual(404, raised.exception.status_code)
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

        self.assertEqual("tenant-a", self.database.inserted[-1].get("company_id"))


if __name__ == "__main__":
    unittest.main()
