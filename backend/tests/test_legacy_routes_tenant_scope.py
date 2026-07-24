import copy
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

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
                    "id": "own-applicant",
                    "company_id": "tenant-a",
                    "created_at": "2026-07-24T10:00:00+00:00",
                },
                {
                    "id": "other-applicant",
                    "company_id": "tenant-b",
                    "created_at": "2026-07-24T11:00:00+00:00",
                },
            ],
            "inquiries": [
                {
                    "id": "own-inquiry",
                    "company_id": "tenant-a",
                    "created_at": "2026-07-24T10:00:00+00:00",
                },
                {
                    "id": "other-inquiry",
                    "company_id": "tenant-b",
                    "created_at": "2026-07-24T11:00:00+00:00",
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


class LegacyJsonTenantScopeTests(unittest.TestCase):
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

    def test_legacy_json_applicant_list_excludes_other_company(self):
        result = main.get_applicants()

        self.assertEqual(["own-applicant"], [row["id"] for row in result])
        self.assertIn(
            ("company_id", "tenant-a"),
            self.database.last_query("applicants")["eq"],
        )
        self.assertEqual(self.database.original_rows, self.database.rows)


class LegacyAdminHtmlRemovalTests(unittest.TestCase):
    def setUp(self):
        self.database = LegacySupabase()
        self.patches = [
            patch.object(main, "supabase", self.database),
            patch.object(main, "COMPANY_ID", "tenant-a"),
            patch.object(main, "ADMIN_API_KEY", "test-admin-key"),
        ]
        for active_patch in self.patches:
            active_patch.start()
        self.client = TestClient(main.app)
        self.admin_headers = {"X-Admin-Key": "test-admin-key"}

    def tearDown(self):
        self.client.close()
        for active_patch in reversed(self.patches):
            active_patch.stop()

    def test_legacy_applicant_dashboard_is_not_published(self):
        response = self.client.get("/applicants-view", headers=self.admin_headers)

        self.assertEqual(404, response.status_code)

    def test_legacy_applicant_detail_is_not_published(self):
        response = self.client.get(
            "/applicant/example-id",
            headers=self.admin_headers,
        )

        self.assertEqual(404, response.status_code)

    def test_legacy_inquiry_dashboard_is_not_published(self):
        response = self.client.get("/inquiries-view", headers=self.admin_headers)

        self.assertEqual(404, response.status_code)

    def test_json_applicant_api_remains_available(self):
        response = self.client.get("/api/applicants", headers=self.admin_headers)

        self.assertEqual(200, response.status_code)
        self.assertEqual("application/json", response.headers["content-type"])
        self.assertEqual(["own-applicant"], [row["id"] for row in response.json()])

    def test_json_inquiry_api_remains_available(self):
        response = self.client.get("/api/inquiries", headers=self.admin_headers)

        self.assertEqual(200, response.status_code)
        self.assertEqual("application/json", response.headers["content-type"])
        self.assertEqual(["own-inquiry"], [row["id"] for row in response.json()])

    def test_json_admin_apis_still_require_admin_key(self):
        for path in ("/api/applicants", "/api/inquiries"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(401, response.status_code)

    def test_health_endpoint_remains_available(self):
        response = self.client.get("/api/health")

        self.assertEqual(200, response.status_code)
        self.assertEqual("ok", response.json()["status"])

    def test_webhook_endpoint_remains_registered(self):
        routes = {
            (route.path, frozenset(route.methods or set()))
            for route in main.app.routes
        }

        self.assertIn(("/webhook", frozenset({"POST"})), routes)


if __name__ == "__main__":
    unittest.main()
