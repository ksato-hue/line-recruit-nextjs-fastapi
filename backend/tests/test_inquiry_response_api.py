import base64
import copy
from datetime import datetime, timezone
import json
import re
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from tests.support import load_backend_main


main = load_backend_main()

TENANT_A = "tenant-a"
TENANT_B = "tenant-b"
RAW_LINE_ID = "U1234567890abcdef1234567890abcdef"
INQUIRY_1 = "00000000-0000-0000-0000-000000000001"
INQUIRY_2 = "00000000-0000-0000-0000-000000000002"
INQUIRY_3 = "00000000-0000-0000-0000-000000000003"
OTHER_INQUIRY = "00000000-0000-0000-0000-000000000099"


def encode_test_cursor(payload: dict) -> str:
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def encode_raw_test_cursor(payload: str, *, urlsafe: bool = True) -> str:
    encoder = base64.urlsafe_b64encode if urlsafe else base64.b64encode
    return encoder(payload.encode("utf-8")).decode("ascii").rstrip("=")


class InquiryQuery:
    def __init__(self, database, table_name: str):
        self.database = database
        self.table_name = table_name
        self.database.queries.append(self)
        self.selected_columns: str | None = None
        self.equal_filters: list[tuple[str, object]] = []
        self.in_filters: list[tuple[str, tuple[object, ...]]] = []
        self.or_filter: str | None = None
        self.orders: list[tuple[str, bool]] = []
        self.row_limit: int | None = None

    def select(self, columns: str):
        self.selected_columns = columns
        return self

    def eq(self, column: str, value: object):
        self.equal_filters.append((column, value))
        return self

    def in_(self, column: str, values: list[object]):
        self.in_filters.append((column, tuple(values)))
        return self

    def or_(self, expression: str):
        self.or_filter = expression
        return self

    def order(self, column: str, desc: bool = False):
        self.orders.append((column, desc))
        return self

    def limit(self, value: int):
        self.row_limit = value
        return self

    def _matches_cursor(self, row: dict) -> bool:
        if self.or_filter is None:
            return True
        match = re.fullmatch(
            r"created_at\.(gt|lt)\.([^,]+),and\(created_at\.eq\.([^,]+),id\.(gt|lt)\.([^\)]+)\)",
            self.or_filter,
        )
        if match is None:
            raise AssertionError(f"Unexpected cursor expression: {self.or_filter}")
        created_operator, created_at, tied_created_at, id_operator, row_id = match.groups()
        if created_at != tied_created_at or created_operator != id_operator:
            raise AssertionError(f"Inconsistent cursor expression: {self.or_filter}")
        row_key = (str(row.get("created_at") or ""), str(row.get("id") or ""))
        cursor_key = (created_at, row_id)
        return row_key > cursor_key if created_operator == "gt" else row_key < cursor_key

    def execute(self):
        if self.table_name in self.database.fail_tables:
            raise RuntimeError(f"forced {self.table_name} failure")
        rows = [
            row
            for row in self.database.rows[self.table_name]
            if all(row.get(column) == value for column, value in self.equal_filters)
            and all(row.get(column) in values for column, values in self.in_filters)
            and self._matches_cursor(row)
        ]
        for column, desc in reversed(self.orders):
            rows.sort(key=lambda row: str(row.get(column) or ""), reverse=desc)
        if self.row_limit is not None:
            rows = rows[: self.row_limit]
        if self.selected_columns:
            selected = [column.strip() for column in self.selected_columns.split(",")]
            if selected != ["*"]:
                rows = [{key: row.get(key) for key in selected} for row in rows]
        return SimpleNamespace(data=copy.deepcopy(rows))


class InquirySupabase:
    def __init__(self):
        self.rows = {
            "inquiries": [
                {
                    "id": INQUIRY_1,
                    "company_id": TENANT_A,
                    "line_user_id": RAW_LINE_ID,
                    "message": "最初の問い合わせです",
                    "created_at": "2026-08-01T00:00:00+00:00",
                    "status": "未対応",
                    "assignee_name": None,
                    "last_replied_at": None,
                    "updated_at": "2026-08-01T00:00:00+00:00",
                },
                {
                    "id": INQUIRY_2,
                    "company_id": TENANT_A,
                    "line_user_id": "Uaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    "message": "同時刻の問い合わせです",
                    "created_at": "2026-08-01T00:00:00+00:00",
                    "status": "未対応",
                    "assignee_name": "鈴木",
                    "last_replied_at": None,
                    "updated_at": "2026-08-01T01:00:00+00:00",
                },
                {
                    "id": INQUIRY_3,
                    "company_id": TENANT_A,
                    "line_user_id": "Ubbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                    "message": "対応中の問い合わせです",
                    "created_at": "2026-08-02T00:00:00+00:00",
                    "status": "対応中",
                    "assignee_name": "田中",
                    "last_replied_at": None,
                    "updated_at": "2026-08-02T01:00:00+00:00",
                },
                {
                    "id": OTHER_INQUIRY,
                    "company_id": TENANT_B,
                    "line_user_id": RAW_LINE_ID,
                    "message": "別企業の問い合わせ",
                    "created_at": "2026-08-03T00:00:00+00:00",
                    "status": "未対応",
                    "assignee_name": None,
                    "last_replied_at": None,
                    "updated_at": "2026-08-03T00:00:00+00:00",
                },
            ],
            "applicants": [
                {
                    "id": "own-applicant",
                    "company_id": TENANT_A,
                    "line_user_id": RAW_LINE_ID,
                    "name": "自社 応募者",
                    "job": "営業",
                    "status": "新規応募",
                    "interview_status": "未設定",
                    "created_at": "2026-07-30T00:00:00+00:00",
                },
                {
                    "id": "other-applicant",
                    "company_id": TENANT_B,
                    "line_user_id": RAW_LINE_ID,
                    "name": "他社 応募者",
                    "job": "開発",
                    "status": "新規応募",
                    "interview_status": "未設定",
                    "created_at": "2026-07-31T00:00:00+00:00",
                },
                {
                    "id": "other-only-batch-applicant",
                    "company_id": TENANT_B,
                    "line_user_id": "Uaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    "name": "他社のみ 応募者",
                    "job": "管理",
                    "status": "新規応募",
                    "interview_status": "未設定",
                    "created_at": "2026-07-31T01:00:00+00:00",
                },
            ],
            "inquiry_replies": [
                {
                    "id": "10000000-0000-0000-0000-000000000002",
                    "company_id": TENANT_A,
                    "inquiry_id": INQUIRY_1,
                    "assignee_name": "佐藤",
                    "message": "後の返信",
                    "delivery_status": "sent",
                    "safe_error_code": None,
                    "created_at": "2026-08-04T02:00:00+00:00",
                    "updated_at": "2026-08-04T02:00:00+00:00",
                    "sent_at": "2026-08-04T02:00:00+00:00",
                },
                {
                    "id": "10000000-0000-0000-0000-000000000001",
                    "company_id": TENANT_A,
                    "inquiry_id": INQUIRY_1,
                    "assignee_name": "佐藤",
                    "message": "先の返信",
                    "delivery_status": "sent",
                    "safe_error_code": None,
                    "created_at": "2026-08-04T01:00:00+00:00",
                    "updated_at": "2026-08-04T01:00:00+00:00",
                    "sent_at": "2026-08-04T01:00:00+00:00",
                },
                {
                    "id": "10000000-0000-0000-0000-000000000099",
                    "company_id": TENANT_B,
                    "inquiry_id": INQUIRY_1,
                    "assignee_name": "他社担当",
                    "message": "他社返信",
                    "delivery_status": "sent",
                    "safe_error_code": None,
                    "created_at": "2026-08-04T00:00:00+00:00",
                    "updated_at": "2026-08-04T00:00:00+00:00",
                    "sent_at": "2026-08-04T00:00:00+00:00",
                },
            ],
            "app_settings": [
                {"company_id": TENANT_A, "key": "recruiter_name", "value": "  佐藤　太郎  "},
                {"company_id": TENANT_B, "key": "recruiter_name", "value": "他社 担当"},
            ],
        }
        self.queries: list[InquiryQuery] = []
        self.fail_tables: set[str] = set()

    def table(self, name: str):
        if name not in self.rows:
            raise AssertionError(f"Unexpected table access: {name}")
        return InquiryQuery(self, name)

    def queries_for(self, table_name: str) -> list[InquiryQuery]:
        return [query for query in self.queries if query.table_name == table_name]


class InquiryApiTestCase(unittest.TestCase):
    def setUp(self):
        self.database = InquirySupabase()
        self.patches = [
            patch.object(main, "supabase", self.database),
            patch.object(main, "COMPANY_ID", TENANT_A),
            patch.object(main, "ADMIN_API_KEY", "test-admin-key"),
        ]
        for active_patch in self.patches:
            active_patch.start()
        self.client = TestClient(main.app, raise_server_exceptions=False)
        self.headers = {"X-Admin-Key": "test-admin-key"}

    def tearDown(self):
        self.client.close()
        for active_patch in reversed(self.patches):
            active_patch.stop()

    def assert_company_scoped(self, table_name: str):
        queries = self.database.queries_for(table_name)
        self.assertTrue(queries, f"expected a {table_name} query")
        for query in queries:
            self.assertIn(("company_id", TENANT_A), query.equal_filters)


class InquiryListApiTests(InquiryApiTestCase):
    def test_list_filters_status_in_the_company_scoped_query(self):
        response = self.client.get(
            "/api/inquiries",
            params={"status": "対応中"},
            headers=self.headers,
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual([INQUIRY_3], [item["id"] for item in response.json()["items"]])
        inquiry_query = self.database.queries_for("inquiries")[-1]
        self.assertIn(("company_id", TENANT_A), inquiry_query.equal_filters)
        self.assertIn(("status", "対応中"), inquiry_query.equal_filters)

    def test_list_orders_oldest_and_newest_by_created_at_then_id(self):
        oldest = self.client.get(
            "/api/inquiries",
            params={"sort": "oldest"},
            headers=self.headers,
        )
        newest = self.client.get(
            "/api/inquiries",
            params={"sort": "newest"},
            headers=self.headers,
        )

        self.assertEqual([INQUIRY_1, INQUIRY_2, INQUIRY_3], [row["id"] for row in oldest.json()["items"]])
        self.assertEqual([INQUIRY_3, INQUIRY_2, INQUIRY_1], [row["id"] for row in newest.json()["items"]])
        inquiry_queries = self.database.queries_for("inquiries")
        self.assertEqual([("created_at", False), ("id", False)], inquiry_queries[-2].orders)
        self.assertEqual([("created_at", True), ("id", True)], inquiry_queries[-1].orders)

    def test_list_rejects_invalid_cursor_components_before_querying(self):
        canonical = encode_test_cursor({
            "created_at": "2026-08-01T00:00:00+00:00",
            "id": INQUIRY_1,
        })
        duplicate_id_json = (
            '{"id":"00000000-0000-0000-0000-000000000099",'
            '"created_at":"2026-08-01T00:00:00+00:00",'
            f'"id":"{INQUIRY_1}"}}'
        )
        duplicate_created_at_json = (
            '"created_at":"2026-08-02T00:00:00+00:00",'
            '"created_at":"2026-08-01T00:00:00+00:00",'
            f'"id":"{INQUIRY_1}"'
        )
        standard_plus = encode_raw_test_cursor(
            '{"id":"¾","created_at":"2026-08-01T00:00:00+00:00",'
            f'"id":"{INQUIRY_1}"}}',
            urlsafe=False,
        )
        standard_slash = encode_raw_test_cursor(
            '{"id":"¿","created_at":"2026-08-01T00:00:00+00:00",'
            f'"id":"{INQUIRY_1}"}}',
            urlsafe=False,
        )
        self.assertIn("+", standard_plus)
        self.assertIn("/", standard_slash)
        invalid_cursors = [
            "not-base64!",
            canonical + "=",
            encode_raw_test_cursor(
                '{ "created_at": "2026-08-01T00:00:00+00:00", '
                f'"id": "{INQUIRY_1}" }}'
            ),
            encode_raw_test_cursor(duplicate_id_json),
            encode_raw_test_cursor("{" + duplicate_created_at_json + "}"),
            standard_plus,
            standard_slash,
            encode_test_cursor({
                "created_at": "2026-08-01T00:00:00+00:00",
                "id": INQUIRY_1,
                "extra": "forbidden",
            }),
            encode_test_cursor({"created_at": "2026-08-01T00:00:00", "id": INQUIRY_1}),
            encode_test_cursor({"created_at": "2026-08-01T00:00:00+00:00", "id": "not-a-uuid"}),
        ]

        for cursor in invalid_cursors:
            with self.subTest(cursor=cursor):
                self.database.queries.clear()
                response = self.client.get(
                    "/api/inquiries",
                    params={"cursor": cursor},
                    headers=self.headers,
                )
                self.assertEqual(422, response.status_code)
                self.assertEqual([], self.database.queries)

    def test_list_rejects_invalid_status_and_sort_before_querying(self):
        for params in ({"status": "unknown"}, {"sort": "sideways"}):
            with self.subTest(params=params):
                self.database.queries.clear()
                response = self.client.get(
                    "/api/inquiries",
                    params=params,
                    headers=self.headers,
                )
                self.assertEqual(422, response.status_code)
                self.assertEqual([], self.database.queries)

    def test_list_rejects_limit_outside_one_to_one_hundred(self):
        for limit in (0, 101):
            with self.subTest(limit=limit):
                response = self.client.get(
                    "/api/inquiries",
                    params={"limit": limit},
                    headers=self.headers,
                )
                self.assertEqual(422, response.status_code)

    def test_list_returns_url_safe_next_cursor_and_uses_it_as_a_keyset(self):
        first = self.client.get(
            "/api/inquiries",
            params={"sort": "oldest", "limit": 2},
            headers=self.headers,
        )

        self.assertEqual(200, first.status_code)
        first_body = first.json()
        self.assertEqual([INQUIRY_1, INQUIRY_2], [row["id"] for row in first_body["items"]])
        self.assertRegex(first_body["next_cursor"], r"^[A-Za-z0-9_-]+$")

        second = self.client.get(
            "/api/inquiries",
            params={"sort": "oldest", "limit": 2, "cursor": first_body["next_cursor"]},
            headers=self.headers,
        )
        self.assertEqual([INQUIRY_3], [row["id"] for row in second.json()["items"]])
        self.assertIsNone(second.json()["next_cursor"])
        self.assertIsNotNone(self.database.queries_for("inquiries")[-1].or_filter)

    def test_list_newest_cursor_keeps_equal_timestamp_uuid_boundary(self):
        first = self.client.get(
            "/api/inquiries",
            params={"sort": "newest", "limit": 2},
            headers=self.headers,
        )
        second = self.client.get(
            "/api/inquiries",
            params={
                "sort": "newest",
                "limit": 2,
                "cursor": first.json()["next_cursor"],
            },
            headers=self.headers,
        )

        self.assertEqual([INQUIRY_3, INQUIRY_2], [row["id"] for row in first.json()["items"]])
        self.assertEqual([INQUIRY_1], [row["id"] for row in second.json()["items"]])
        self.assertIsNone(second.json()["next_cursor"])

    def test_list_batches_related_applicant_existence_in_one_company_scoped_read(self):
        response = self.client.get("/api/inquiries", headers=self.headers)

        self.assertEqual(200, response.status_code)
        applicant_queries = self.database.queries_for("applicants")
        self.assertEqual(1, len(applicant_queries))
        self.assertEqual(
            ["inquiries", "applicants"],
            [query.table_name for query in self.database.queries],
        )
        query = applicant_queries[0]
        self.assertEqual("line_user_id", query.selected_columns)
        self.assertEqual([("company_id", TENANT_A)], query.equal_filters)
        self.assertEqual(
            {
                RAW_LINE_ID,
                "Uaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "Ubbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            },
            set(query.in_filters[0][1]),
        )
        items = {item["id"]: item for item in response.json()["items"]}
        self.assertTrue(items[INQUIRY_1]["related_applicant_exists"])
        self.assertFalse(items[INQUIRY_2]["related_applicant_exists"])
        self.assertFalse(items[INQUIRY_3]["related_applicant_exists"])
        self.assertNotIn(RAW_LINE_ID, response.text)

    def test_list_returns_only_safe_summary_fields_and_a_message_preview(self):
        response = self.client.get("/api/inquiries", headers=self.headers)

        self.assertEqual(200, response.status_code)
        item = next(row for row in response.json()["items"] if row["id"] == INQUIRY_1)
        self.assertEqual(
            {
                "id",
                "message_preview",
                "created_at",
                "status",
                "assignee_name",
                "last_replied_at",
                "updated_at",
                "related_applicant_exists",
                "unanswered_age_seconds",
            },
            set(item),
        )
        self.assertEqual("最初の問い合わせです", item["message_preview"])
        self.assertTrue(item["related_applicant_exists"])
        self.assertGreaterEqual(item["unanswered_age_seconds"], 0)
        self.assertNotIn(RAW_LINE_ID, response.text)
        self.assertNotEqual("*", self.database.queries_for("inquiries")[-1].selected_columns)
        self.assert_company_scoped("inquiries")
        self.assert_company_scoped("applicants")

    def test_list_distinguishes_an_empty_result_from_a_database_failure(self):
        self.database.rows["inquiries"] = [
            row for row in self.database.rows["inquiries"] if row["company_id"] == TENANT_B
        ]
        empty_response = self.client.get("/api/inquiries", headers=self.headers)
        self.assertEqual({"items": [], "next_cursor": None}, empty_response.json())
        self.assertEqual([], self.database.queries_for("applicants"))

        self.database.fail_tables.add("inquiries")
        failed_response = self.client.get("/api/inquiries", headers=self.headers)
        self.assertEqual(503, failed_response.status_code)
        self.assertNotEqual({"items": [], "next_cursor": None}, failed_response.json())


class InquiryDetailApiTests(InquiryApiTestCase):
    def test_detail_returns_safe_inquiry_related_applicants_and_chronological_replies(self):
        response = self.client.get(f"/api/inquiries/{INQUIRY_1}", headers=self.headers)

        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual(
            {
                "inquiry",
                "default_assignee_name",
                "masked_destination",
                "related_applicants",
                "replies",
                "reply_enabled",
            },
            set(body),
        )
        self.assertEqual(
            {"id", "message", "created_at", "status", "assignee_name", "last_replied_at", "updated_at"},
            set(body["inquiry"]),
        )
        self.assertEqual("U1234…cdef", body["masked_destination"])
        self.assertEqual(["own-applicant"], [row["id"] for row in body["related_applicants"]])
        self.assertEqual(
            ["先の返信", "後の返信"],
            [row["message"] for row in body["replies"]],
        )
        self.assertEqual("佐藤", body["default_assignee_name"])
        self.assertFalse(body["reply_enabled"])
        self.assertNotIn(RAW_LINE_ID, response.text)
        self.assertNotIn("他社返信", response.text)

        for table_name in ("inquiries", "applicants", "inquiry_replies", "app_settings"):
            self.assert_company_scoped(table_name)
            self.assertNotEqual("*", self.database.queries_for(table_name)[-1].selected_columns)
        reply_query = self.database.queries_for("inquiry_replies")[-1]
        self.assertIn(("inquiry_id", INQUIRY_1), reply_query.equal_filters)
        self.assertEqual([("created_at", False), ("id", False)], reply_query.orders)
        applicant_query = self.database.queries_for("applicants")[-1]
        self.assertIn(("line_user_id", RAW_LINE_ID), applicant_query.equal_filters)

    def test_detail_feature_flag_is_derived_from_the_server_only_setting(self):
        with patch.object(main, "INQUIRY_REPLY_WORKFLOW_ENABLED", True):
            response = self.client.get(f"/api/inquiries/{INQUIRY_1}", headers=self.headers)

        self.assertTrue(response.json()["reply_enabled"])
        self.assertNotIn("INQUIRY_REPLY_WORKFLOW_ENABLED", response.text)

    def test_detail_returns_the_same_not_found_for_missing_and_other_tenant_ids(self):
        responses = [
            self.client.get(f"/api/inquiries/{OTHER_INQUIRY}", headers=self.headers),
            self.client.get(
                "/api/inquiries/00000000-0000-0000-0000-000000000404",
                headers=self.headers,
            ),
        ]

        self.assertEqual([404, 404], [response.status_code for response in responses])
        self.assertEqual(responses[0].json(), responses[1].json())
        self.assert_company_scoped("inquiries")
        self.assertEqual([], self.database.queries_for("applicants"))
        self.assertEqual([], self.database.queries_for("inquiry_replies"))

    def test_detail_database_failure_is_not_reported_as_not_found(self):
        self.database.fail_tables.add("inquiries")

        response = self.client.get(f"/api/inquiries/{INQUIRY_1}", headers=self.headers)

        self.assertEqual(503, response.status_code)
        self.assertNotEqual(404, response.status_code)


if __name__ == "__main__":
    unittest.main()
