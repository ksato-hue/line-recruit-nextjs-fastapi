import copy
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tests.support import load_backend_main


main = load_backend_main()


class LegacyQuery:
    def __init__(self, database, table_name: str):
        self.database = database
        self.table_name = table_name
        self.equal_filters: list[tuple[str, object]] = []
        self.order_column: str | None = None
        self.order_desc = False

    def select(self, _columns: str):
        return self

    def eq(self, column: str, value: object):
        self.equal_filters.append((column, value))
        return self

    def order(self, column: str, desc: bool = False):
        self.order_column = column
        self.order_desc = desc
        return self

    def execute(self):
        self.database.executed.append({
            "table": self.table_name,
            "operation": "select",
            "eq": copy.deepcopy(self.equal_filters),
        })
        matched = [
            row for row in self.database.rows[self.table_name]
            if all(row.get(column) == value for column, value in self.equal_filters)
        ]
        if self.order_column:
            matched.sort(
                key=lambda row: str(row.get(self.order_column) or ""),
                reverse=self.order_desc,
            )
        return SimpleNamespace(data=copy.deepcopy(matched))


class LegacySupabase:
    def __init__(self):
        self.rows = {
            "applicants": [
                {
                    "id": "shared-applicant", "company_id": "tenant-b",
                    "line_user_id": "shared-line", "name": "Other Shared Applicant",
                    "phone": "000-OTHER", "job": "Other Job", "motivation": "Other Motivation",
                    "status": "採用", "interview_status": "面接確定",
                    "interview_date": "2026-08-02", "memo": "Other Secret Memo",
                },
                {
                    "id": "shared-applicant", "company_id": "tenant-a",
                    "line_user_id": "shared-line", "name": "Own Shared Applicant",
                    "phone": "000-OWN", "job": "Own Job", "motivation": "Own Motivation",
                    "status": "新規応募", "interview_status": "未設定",
                    "interview_date": None, "memo": "Own Memo",
                },
                {
                    "id": "own-applicant", "company_id": "tenant-a",
                    "line_user_id": "own-line", "name": "Own Applicant",
                    "phone": "111-OWN", "job": "Own Second Job", "motivation": "Own Second Motivation",
                    "status": "採用", "interview_status": "面接調整中",
                    "interview_date": "2026-08-01", "memo": "Own Second Memo",
                },
                {
                    "id": "other-only-applicant", "company_id": "tenant-b",
                    "line_user_id": "other-line", "name": "Other Only Applicant",
                    "phone": "111-OTHER", "job": "Other Only Job", "motivation": "Other Only Motivation",
                    "status": "新規応募", "interview_status": "未設定",
                    "interview_date": None, "memo": "Other Only Secret",
                },
            ],
            "inquiries": [
                {
                    "id": "other-shared-inquiry", "company_id": "tenant-b",
                    "line_user_id": "shared-line", "message": "Other Shared Inquiry",
                    "status": "未対応", "created_at": "2026-07-23T12:00:00+00:00",
                },
                {
                    "id": "own-inquiry", "company_id": "tenant-a",
                    "line_user_id": "shared-line", "message": "Own Inquiry",
                    "status": "対応済み", "created_at": "2026-07-23T11:00:00+00:00",
                },
                {
                    "id": "other-only-inquiry", "company_id": "tenant-b",
                    "line_user_id": "other-line", "message": "Other Only Inquiry",
                    "status": "未対応", "created_at": "2026-07-23T10:00:00+00:00",
                },
            ],
        }
        self.original_rows = copy.deepcopy(self.rows)
        self.executed: list[dict] = []

    def table(self, name: str):
        if name not in self.rows:
            raise AssertionError(f"Unexpected table access: {name}")
        return LegacyQuery(self, name)

    def last_query(self, table_name: str):
        return next(
            query for query in reversed(self.executed)
            if query["table"] == table_name and query["operation"] == "select"
        )


class LegacyRouteTenantScopeTests(unittest.TestCase):
    def setUp(self):
        self.database = LegacySupabase()
        self.patches = [
            patch.object(main, "supabase", self.database),
            patch.object(main, "COMPANY_ID", "tenant-a"),
        ]
        for active_patch in self.patches:
            active_patch.start()

    def tearDown(self):
        for active_patch in reversed(self.patches):
            active_patch.stop()

    def assert_query_is_company_scoped(self, table_name: str):
        self.assertIn(
            ("company_id", "tenant-a"),
            self.database.last_query(table_name)["eq"],
        )

    def assert_rows_unchanged(self):
        self.assertEqual(self.database.original_rows, self.database.rows)

    def test_legacy_json_applicant_list_excludes_other_company(self):
        result = main.get_applicants()

        self.assertEqual(
            ["shared-applicant", "own-applicant"],
            [row["id"] for row in result],
        )
        self.assertTrue(all(row["company_id"] == "tenant-a" for row in result))
        self.assert_query_is_company_scoped("applicants")
        self.assert_rows_unchanged()

    def test_legacy_applicant_dashboard_html_excludes_other_company_data_and_counts(self):
        html = main.applicants_view()

        self.assertIn("Own Shared Applicant", html)
        self.assertIn("Own Applicant", html)
        self.assertNotIn("Other Shared Applicant", html)
        self.assertNotIn("Other Only Applicant", html)
        self.assertNotIn("Other Shared Inquiry", html)
        self.assertNotIn("Other Only Inquiry", html)
        self.assertIn('<div class="card-value">2</div>', html)
        self.assert_query_is_company_scoped("applicants")
        self.assert_query_is_company_scoped("inquiries")
        self.assert_rows_unchanged()

    def test_legacy_applicant_detail_with_duplicate_id_returns_own_company_row(self):
        html = main.applicant_detail("shared-applicant")

        self.assertIn("Own Shared Applicant", html)
        self.assertIn("Own Memo", html)
        self.assertNotIn("Other Shared Applicant", html)
        self.assertNotIn("Other Secret Memo", html)
        query = self.database.last_query("applicants")
        self.assertIn(("id", "shared-applicant"), query["eq"])
        self.assertIn(("company_id", "tenant-a"), query["eq"])
        self.assert_rows_unchanged()

    def test_legacy_other_company_applicant_detail_returns_not_found_without_leak(self):
        html = main.applicant_detail("other-only-applicant")

        self.assertEqual("<h1>応募者が見つかりません</h1>", html)
        self.assertNotIn("Other Only Applicant", html)
        query = self.database.last_query("applicants")
        self.assertIn(("id", "other-only-applicant"), query["eq"])
        self.assertIn(("company_id", "tenant-a"), query["eq"])
        self.assert_rows_unchanged()

    def test_legacy_inquiry_html_excludes_other_company_data(self):
        html = main.inquiries_view()

        self.assertIn("Own Inquiry", html)
        self.assertNotIn("Other Shared Inquiry", html)
        self.assertNotIn("Other Only Inquiry", html)
        self.assert_query_is_company_scoped("inquiries")
        self.assert_rows_unchanged()

    def test_legacy_route_surface_is_get_only_and_has_no_inquiry_detail(self):
        routes = {
            route.path: route
            for route in main.app.routes
            if getattr(route, "path", "") in {
                "/applicants",
                "/applicants-view",
                "/applicant/{applicant_id}",
                "/inquiries-view",
            }
        }

        self.assertEqual(
            {
                "/applicants",
                "/applicants-view",
                "/applicant/{applicant_id}",
                "/inquiries-view",
            },
            set(routes),
        )
        for route in routes.values():
            self.assertEqual({"GET"}, route.methods)
            dependencies = {
                getattr(dependency.call, "__name__", "")
                for dependency in route.dependant.dependencies
            }
            self.assertIn("require_admin", dependencies)

        all_paths = {getattr(route, "path", "") for route in main.app.routes}
        self.assertNotIn("/inquiry/{inquiry_id}", all_paths)
        self.assertNotIn("/inquiries/{inquiry_id}", all_paths)


if __name__ == "__main__":
    unittest.main()
