import base64
import copy
from datetime import datetime, timedelta, timezone
import json
import re
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from inquiry_response import LinePushDisposition, LinePushResult
from tests.support import load_backend_main


main = load_backend_main()

TENANT_A = "tenant-a"
TENANT_B = "tenant-b"
RAW_LINE_ID = "U1234567890abcdef1234567890abcdef"
INQUIRY_1 = "00000000-0000-0000-0000-000000000001"
INQUIRY_2 = "00000000-0000-0000-0000-000000000002"
INQUIRY_3 = "00000000-0000-0000-0000-000000000003"
OTHER_INQUIRY = "00000000-0000-0000-0000-000000000099"
REPLY_KEY_1 = "20000000-0000-0000-0000-000000000001"
REPLY_KEY_2 = "20000000-0000-0000-0000-000000000002"
REPLY_KEY_3 = "20000000-0000-0000-0000-000000000003"


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
        self.update_data: dict | None = None
        self.insert_data: dict | None = None

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

    def update(self, data: dict):
        self.update_data = copy.deepcopy(data)
        return self

    def insert(self, data: dict):
        self.insert_data = copy.deepcopy(data)
        return self

    @staticmethod
    def _equal_filter_matches(column: str, stored: object, expected: object) -> bool:
        if column != "updated_at":
            return stored == expected
        try:
            stored_at = datetime.fromisoformat(str(stored).replace("Z", "+00:00"))
            expected_at = datetime.fromisoformat(str(expected).replace("Z", "+00:00"))
        except ValueError:
            return stored == expected
        if stored_at.tzinfo is None or expected_at.tzinfo is None:
            return stored == expected
        return stored_at.astimezone(timezone.utc) == expected_at.astimezone(timezone.utc)

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
        if self.insert_data is not None:
            if self.database.fail_next_reply_insert and self.table_name == "inquiry_replies":
                self.database.fail_next_reply_insert = False
                if self.database.reply_insert_race_row is not None:
                    self.database.rows["inquiry_replies"].append(
                        copy.deepcopy(self.database.reply_insert_race_row)
                    )
                raise RuntimeError("forced inquiry reply insert failure")
            row = copy.deepcopy(self.insert_data)
            if self.table_name == "inquiry_replies":
                if not any(
                    inquiry["company_id"] == row.get("company_id")
                    and inquiry["id"] == row.get("inquiry_id")
                    for inquiry in self.database.rows["inquiries"]
                ):
                    raise RuntimeError("inquiry reply composite FK violation")
                if any(
                    existing.get("company_id") == row.get("company_id")
                    and existing.get("inquiry_id") == row.get("inquiry_id")
                    and existing.get("idempotency_key") == row.get("idempotency_key")
                    for existing in self.database.rows["inquiry_replies"]
                ):
                    raise RuntimeError("inquiry reply idempotency uniqueness violation")
                if any(
                    existing.get("line_retry_key") == row.get("line_retry_key")
                    for existing in self.database.rows["inquiry_replies"]
                ):
                    raise RuntimeError("inquiry reply LINE retry key uniqueness violation")
                sequence = self.database.next_reply_sequence
                self.database.next_reply_sequence += 1
                row.setdefault("id", f"30000000-0000-0000-0000-{sequence:012d}")
                row.setdefault("created_at", self.database.reply_created_at)
                row.setdefault("updated_at", self.database.reply_created_at)
                row.setdefault("sent_at", None)
                row.setdefault("safe_error_code", None)
            self.database.rows[self.table_name].append(row)
            return SimpleNamespace(data=[copy.deepcopy(row)])
        rows = [
            row
            for row in self.database.rows[self.table_name]
            if all(
                self._equal_filter_matches(column, row.get(column), value)
                for column, value in self.equal_filters
            )
            and all(row.get(column) in values for column, values in self.in_filters)
            and self._matches_cursor(row)
        ]
        for column, desc in reversed(self.orders):
            rows.sort(key=lambda row: str(row.get(column) or ""), reverse=desc)
        if self.row_limit is not None:
            rows = rows[: self.row_limit]
        if self.update_data is not None:
            if self.database.zero_next_inquiry_update:
                self.database.zero_next_inquiry_update = False
                return SimpleNamespace(data=[])
            if (
                self.table_name == "inquiry_replies"
                and self.update_data.get("delivery_status")
                in self.database.fail_reply_update_statuses
            ):
                raise RuntimeError("forced inquiry reply status failure")
            if self.table_name == "inquiry_replies" and self.database.zero_next_reply_update:
                self.database.zero_next_reply_update = False
                return SimpleNamespace(data=[])
            if self.table_name == "inquiry_replies":
                update_key = (
                    self.update_data.get("delivery_status"),
                    self.update_data.get("safe_error_code"),
                )
                if update_key in self.database.zero_reply_update_results:
                    raced_state = self.database.zero_reply_update_results[update_key]
                    if raced_state is not None:
                        for row in rows:
                            row.update(copy.deepcopy(raced_state))
                            row["updated_at"] = self.database.reply_trigger_updated_at
                    return SimpleNamespace(data=[])
            for row in rows:
                row.update(copy.deepcopy(self.update_data))
                if self.table_name == "inquiries":
                    row["updated_at"] = self.database.trigger_updated_at
                elif self.table_name == "inquiry_replies":
                    row["updated_at"] = self.database.reply_trigger_updated_at
        if self.selected_columns:
            selected = [column.strip() for column in self.selected_columns.split(",")]
            if selected != ["*"]:
                rows = [{key: row.get(key) for key in selected} for row in rows]
        return SimpleNamespace(data=copy.deepcopy(rows))


class InquiryRpc:
    def __init__(self, database, function_name: str, parameters: dict):
        self.database = database
        self.function_name = function_name
        self.parameters = copy.deepcopy(parameters)
        self.database.rpc_calls.append(self)

    def execute(self):
        if self.database.fail_finalize:
            raise RuntimeError("forced finalizer failure containing private provider details")
        if self.function_name != "finalize_inquiry_reply":
            raise AssertionError(f"Unexpected RPC: {self.function_name}")
        company_id = self.parameters["p_company_id"]
        inquiry_id = self.parameters["p_inquiry_id"]
        reply_id = self.parameters["p_reply_id"]
        reply = next(
            row
            for row in self.database.rows["inquiry_replies"]
            if row["company_id"] == company_id
            and row["inquiry_id"] == inquiry_id
            and row["id"] == reply_id
        )
        inquiry = next(
            row
            for row in self.database.rows["inquiries"]
            if row["company_id"] == company_id and row["id"] == inquiry_id
        )
        reply.update(
            {
                "delivery_status": "sent",
                "safe_error_code": None,
                "sent_at": self.database.finalized_at,
                "updated_at": self.database.finalized_at,
            }
        )
        inquiry.update(
            {
                "status": "対応済み",
                "assignee_name": reply["assignee_name"],
                "last_replied_at": self.database.finalized_at,
                "updated_at": self.database.finalized_at,
            }
        )
        return SimpleNamespace(
            data={
                "reply_id": reply_id,
                "delivery_status": "sent",
                "inquiry_status": "対応済み",
                "sent_at": self.database.finalized_at,
                "inquiry_updated_at": self.database.finalized_at,
            }
        )


class FakeLineTransport:
    def __init__(self, database):
        self.database = database
        self.results = [LinePushResult(LinePushDisposition.ACCEPTED, 202)]
        self.calls: list[tuple[str, str, object]] = []
        self.durable_snapshots: list[tuple[str, str]] = []

    def __call__(self, line_user_id: str, message: str, line_retry_key: object):
        reply = next(
            (
                row
                for row in self.database.rows["inquiry_replies"]
                if str(row.get("line_retry_key")) == str(line_retry_key)
            ),
            None,
        )
        if reply is None:
            raise AssertionError("LINE called before durable reply insert")
        inquiry = next(
            row
            for row in self.database.rows["inquiries"]
            if row["company_id"] == reply["company_id"]
            and row["id"] == reply["inquiry_id"]
        )
        self.durable_snapshots.append((reply["delivery_status"], inquiry["status"]))
        self.calls.append((line_user_id, message, line_retry_key))
        if not self.results:
            raise AssertionError("Unexpected LINE call")
        return self.results.pop(0)


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
                    "status": "対応済み",
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
                    "inquiry_id": OTHER_INQUIRY,
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
        self.rpc_calls: list[InquiryRpc] = []
        self.fail_tables: set[str] = set()
        self.zero_next_inquiry_update = False
        self.fail_next_reply_insert = False
        self.reply_insert_race_row: dict | None = None
        self.fail_reply_update_statuses: set[str] = set()
        self.zero_next_reply_update = False
        self.zero_reply_update_results: dict[
            tuple[str | None, str | None], dict | None
        ] = {}
        self.fail_finalize = False
        self.next_reply_sequence = 1
        self.reply_created_at = "2026-08-07T01:00:00+00:00"
        self.reply_trigger_updated_at = datetime.now(timezone.utc).isoformat()
        self.trigger_updated_at = "2026-08-07T00:00:00+00:00"
        self.finalized_at = "2026-08-07T02:00:00+00:00"

    def table(self, name: str):
        if name not in self.rows:
            raise AssertionError(f"Unexpected table access: {name}")
        return InquiryQuery(self, name)

    def rpc(self, function_name: str, parameters: dict):
        return InquiryRpc(self, function_name, parameters)

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


class InquiryUpdateApiTests(InquiryApiTestCase):
    def assert_safe_update_response(self, response):
        self.assertEqual(
            {
                "id",
                "message",
                "created_at",
                "status",
                "assignee_name",
                "last_replied_at",
                "updated_at",
            },
            set(response.json()),
        )
        self.assertNotIn("company_id", response.json())
        self.assertNotIn("line_user_id", response.json())

    def inquiry_row(self, inquiry_id: str) -> dict:
        return next(row for row in self.database.rows["inquiries"] if row["id"] == inquiry_id)

    def patch_inquiry(self, inquiry_id: str, **payload):
        return self.client.patch(
            f"/api/inquiries/{inquiry_id}",
            json=payload,
            headers=self.headers,
        )

    def test_operator_status_transition_matrix(self):
        cases = [
            (INQUIRY_1, "未対応", "未対応", 200, None),
            (INQUIRY_1, "未対応", "対応中", 200, None),
            (INQUIRY_1, "未対応", "対応済み", 409, "INVALID_STATUS_TRANSITION"),
            (INQUIRY_3, "対応中", "未対応", 409, "INVALID_STATUS_TRANSITION"),
            (INQUIRY_3, "対応中", "対応中", 200, None),
            (INQUIRY_3, "対応中", "対応済み", 409, "INVALID_STATUS_TRANSITION"),
            (INQUIRY_2, "対応済み", "未対応", 409, "INVALID_STATUS_TRANSITION"),
            (INQUIRY_2, "対応済み", "対応中", 200, None),
            (INQUIRY_2, "対応済み", "対応済み", 200, None),
        ]

        for inquiry_id, current, target, status_code, reason_code in cases:
            with self.subTest(current=current, target=target):
                row = self.inquiry_row(inquiry_id)
                row["status"] = current
                row["updated_at"] = "2026-08-01T00:00:00+00:00"
                before = copy.deepcopy(row)
                self.database.queries.clear()

                response = self.patch_inquiry(
                    inquiry_id,
                    status=target,
                    expected_updated_at=before["updated_at"],
                )

                self.assertEqual(status_code, response.status_code)
                if reason_code is None:
                    self.assertEqual(target, self.inquiry_row(inquiry_id)["status"])
                else:
                    self.assertEqual({"detail": reason_code}, response.json())
                    self.assertEqual(before, self.inquiry_row(inquiry_id))
                    self.assertFalse(any(query.update_data is not None for query in self.database.queries))

    def test_assignee_only_update_preserves_the_normalized_manual_value(self):
        row = self.inquiry_row(INQUIRY_1)

        response = self.patch_inquiry(
            INQUIRY_1,
            assignee_name="  山田 花子　",
            expected_updated_at=row["updated_at"],
        )

        self.assertEqual(200, response.status_code)
        self.assert_safe_update_response(response)
        self.assertEqual("山田 花子", response.json()["assignee_name"])
        update_query = next(
            query for query in self.database.queries_for("inquiries")
            if query.update_data is not None
        )
        self.assertEqual({"assignee_name": "山田 花子"}, update_query.update_data)

    def test_status_only_update_preserves_the_existing_assignee(self):
        row = self.inquiry_row(INQUIRY_2)

        response = self.patch_inquiry(
            INQUIRY_2,
            status="対応中",
            expected_updated_at=row["updated_at"],
        )

        self.assertEqual(200, response.status_code)
        self.assert_safe_update_response(response)
        self.assertEqual("鈴木", response.json()["assignee_name"])
        self.assertEqual("鈴木", self.inquiry_row(INQUIRY_2)["assignee_name"])

    def test_update_request_shape_is_strict_and_validation_never_mutates(self):
        invalid_payloads = [
            {"assignee_name": "　 ", "expected_updated_at": "2026-08-01T00:00:00+00:00"},
            {"status": "unknown", "expected_updated_at": "2026-08-01T00:00:00+00:00"},
            {"status": "対応中"},
            {
                "status": "対応中",
                "expected_updated_at": "2026-08-01T00:00:00+00:00",
                "company_id": TENANT_B,
            },
        ]
        before = copy.deepcopy(self.database.rows["inquiries"])

        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                self.database.queries.clear()
                response = self.patch_inquiry(INQUIRY_1, **payload)
                self.assertEqual(422, response.status_code)
                self.assertEqual([], self.database.queries)
                self.assertEqual(before, self.database.rows["inquiries"])

    def test_stale_timestamp_returns_conflict_without_mutation(self):
        before = copy.deepcopy(self.inquiry_row(INQUIRY_1))

        response = self.patch_inquiry(
            INQUIRY_1,
            status="対応中",
            assignee_name="佐藤",
            expected_updated_at="2026-07-31T23:59:59+00:00",
        )

        self.assertEqual(409, response.status_code)
        self.assertEqual({"detail": "INQUIRY_CONFLICT"}, response.json())
        self.assertEqual(before, self.inquiry_row(INQUIRY_1))

    def test_matching_timestamp_updates_with_id_company_and_timestamp_predicates(self):
        row = self.inquiry_row(INQUIRY_1)
        expected_updated_at = row["updated_at"]

        response = self.patch_inquiry(
            INQUIRY_1,
            status="対応中",
            expected_updated_at=expected_updated_at,
        )

        self.assertEqual(200, response.status_code)
        self.assert_safe_update_response(response)
        update_query = next(
            query for query in self.database.queries_for("inquiries")
            if query.update_data is not None
        )
        self.assertIn(("id", INQUIRY_1), update_query.equal_filters)
        self.assertIn(("company_id", TENANT_A), update_query.equal_filters)
        self.assertIn(("updated_at", expected_updated_at), update_query.equal_filters)
        self.assertNotIn("updated_at", update_query.update_data)
        self.assertEqual(self.database.trigger_updated_at, response.json()["updated_at"])

    def test_compare_and_set_accepts_an_offset_equivalent_timestamp(self):
        response = self.patch_inquiry(
            INQUIRY_1,
            status="対応中",
            expected_updated_at="2026-08-01T09:00:00+09:00",
        )

        self.assertEqual(200, response.status_code)
        self.assert_safe_update_response(response)
        self.assertEqual("対応中", self.inquiry_row(INQUIRY_1)["status"])

    def test_matching_same_status_is_a_safe_no_op_without_advancing_updated_at(self):
        before = copy.deepcopy(self.inquiry_row(INQUIRY_1))

        response = self.patch_inquiry(
            INQUIRY_1,
            status="未対応",
            expected_updated_at="2026-08-01T00:00:00Z",
        )

        self.assertEqual(200, response.status_code)
        self.assert_safe_update_response(response)
        self.assertEqual("最初の問い合わせです", response.json()["message"])
        self.assertEqual(before["updated_at"], response.json()["updated_at"])
        self.assertEqual(before, self.inquiry_row(INQUIRY_1))
        self.assertFalse(any(query.update_data is not None for query in self.database.queries))
        self.assertEqual(1, len(self.database.queries_for("inquiries")))

    def test_stale_same_status_is_a_conflict_without_an_update(self):
        before = copy.deepcopy(self.inquiry_row(INQUIRY_1))

        response = self.patch_inquiry(
            INQUIRY_1,
            status="未対応",
            expected_updated_at="2026-07-31T23:59:59+00:00",
        )

        self.assertEqual(409, response.status_code)
        self.assertEqual({"detail": "INQUIRY_CONFLICT"}, response.json())
        self.assertEqual(before, self.inquiry_row(INQUIRY_1))
        self.assertFalse(any(query.update_data is not None for query in self.database.queries))

    def test_same_status_with_assignee_updates_only_the_assignee(self):
        row = self.inquiry_row(INQUIRY_1)

        response = self.patch_inquiry(
            INQUIRY_1,
            status="未対応",
            assignee_name="佐藤",
            expected_updated_at=row["updated_at"],
        )

        self.assertEqual(200, response.status_code)
        self.assert_safe_update_response(response)
        update_query = next(
            query for query in self.database.queries_for("inquiries")
            if query.update_data is not None
        )
        self.assertEqual({"assignee_name": "佐藤"}, update_query.update_data)

    def test_other_tenant_returns_not_found_without_mutation(self):
        before = copy.deepcopy(self.database.rows["inquiries"])

        response = self.patch_inquiry(
            OTHER_INQUIRY,
            status="対応中",
            expected_updated_at="2026-08-03T00:00:00+00:00",
        )

        self.assertEqual(404, response.status_code)
        self.assertEqual(before, self.database.rows["inquiries"])
        self.assertFalse(any(query.update_data is not None for query in self.database.queries))
        self.assert_company_scoped("inquiries")

    def test_compare_and_set_race_returns_conflict_without_mutation(self):
        before = copy.deepcopy(self.inquiry_row(INQUIRY_1))
        self.database.zero_next_inquiry_update = True

        response = self.patch_inquiry(
            INQUIRY_1,
            status="対応中",
            expected_updated_at=before["updated_at"],
        )

        self.assertEqual(409, response.status_code)
        self.assertEqual({"detail": "INQUIRY_CONFLICT"}, response.json())
        self.assertEqual(before, self.inquiry_row(INQUIRY_1))
        inquiries_queries = self.database.queries_for("inquiries")
        self.assertEqual(3, len(inquiries_queries))
        self.assertIsNotNone(inquiries_queries[1].update_data)
        self.assertIsNone(inquiries_queries[2].update_data)
        self.assert_company_scoped("inquiries")

    def test_database_failure_is_not_reported_as_missing_or_conflict(self):
        before = copy.deepcopy(self.database.rows["inquiries"])
        self.database.fail_tables.add("inquiries")

        response = self.patch_inquiry(
            INQUIRY_1,
            status="対応中",
            expected_updated_at="2026-08-01T00:00:00+00:00",
        )

        self.assertEqual(503, response.status_code)
        self.assertNotIn(response.status_code, {404, 409})
        self.assertEqual(before, self.database.rows["inquiries"])


class InquiryReplyApiTests(InquiryApiTestCase):
    def setUp(self):
        super().setUp()
        self.line_transport = FakeLineTransport(self.database)
        self.reply_patches = [
            patch.object(main, "INQUIRY_REPLY_WORKFLOW_ENABLED", True),
            patch.object(main, "LINE_ACCESS_TOKEN", "test-line-access-token"),
            patch.object(main, "_push_inquiry_reply", self.line_transport),
        ]
        for active_patch in self.reply_patches:
            active_patch.start()

    def tearDown(self):
        for active_patch in reversed(self.reply_patches):
            active_patch.stop()
        super().tearDown()

    def inquiry_row(self, inquiry_id: str = INQUIRY_1, company_id: str = TENANT_A) -> dict:
        return next(
            row
            for row in self.database.rows["inquiries"]
            if row["id"] == inquiry_id and row["company_id"] == company_id
        )

    def post_reply(
        self,
        inquiry_id: str = INQUIRY_1,
        *,
        assignee_name: str = "佐藤",
        message: str = "お問い合わせありがとうございます。",
        idempotency_key: str = REPLY_KEY_1,
        expected_updated_at: str | None = None,
        extra: dict | None = None,
    ):
        if expected_updated_at is None:
            expected_updated_at = self.inquiry_row(inquiry_id)["updated_at"]
        payload = {
            "assignee_name": assignee_name,
            "message": message,
            "idempotency_key": idempotency_key,
            "expected_updated_at": expected_updated_at,
        }
        payload.update(extra or {})
        return self.client.post(
            f"/api/inquiries/{inquiry_id}/replies",
            json=payload,
            headers=self.headers,
        )

    def add_reply(
        self,
        *,
        company_id: str = TENANT_A,
        inquiry_id: str = INQUIRY_1,
        idempotency_key: str = REPLY_KEY_1,
        assignee_name: str = "佐藤",
        message: str = "お問い合わせありがとうございます。",
        delivery_status: str,
        line_retry_key: str = "40000000-0000-0000-0000-000000000001",
        safe_error_code: str | None = None,
        created_at: str | None = None,
        sent_at: str | None = None,
    ) -> dict:
        row = {
            "id": f"50000000-0000-0000-0000-{len(self.database.rows['inquiry_replies']) + 1:012d}",
            "company_id": company_id,
            "inquiry_id": inquiry_id,
            "assignee_name": assignee_name,
            "message": message,
            "delivery_status": delivery_status,
            "idempotency_key": idempotency_key,
            "line_retry_key": line_retry_key,
            "safe_error_code": safe_error_code,
            "actor_user_id": None,
            "created_at": created_at or datetime.now(timezone.utc).isoformat(),
            "updated_at": created_at or datetime.now(timezone.utc).isoformat(),
            "sent_at": sent_at,
        }
        self.database.rows["inquiry_replies"].append(row)
        return row

    def prepare_insert_race(self, *, delivery_status: str, safe_error_code: str | None = None) -> dict:
        row = self.add_reply(
            delivery_status=delivery_status,
            safe_error_code=safe_error_code,
            line_retry_key="40000000-0000-0000-0000-000000000777",
            sent_at="2026-08-07T03:00:00+00:00" if delivery_status == "sent" else None,
        )
        self.database.rows["inquiry_replies"].remove(row)
        self.database.fail_next_reply_insert = True
        self.database.reply_insert_race_row = row
        return row

    def replies_for(self, company_id: str, inquiry_id: str = INQUIRY_1) -> list[dict]:
        return [
            row
            for row in self.database.rows["inquiry_replies"]
            if row["company_id"] == company_id and row["inquiry_id"] == inquiry_id
        ]

    def test_browser_destination_and_company_fields_are_rejected_before_side_effects(self):
        for extra in ({"company_id": TENANT_B}, {"line_user_id": RAW_LINE_ID}):
            with self.subTest(field=next(iter(extra))):
                self.database.queries.clear()
                self.line_transport.calls.clear()

                response = self.post_reply(extra=extra)

                self.assertEqual(422, response.status_code)
                self.assertEqual([], self.database.queries)
                self.assertEqual([], self.database.rpc_calls)
                self.assertEqual([], self.line_transport.calls)

    def test_feature_gate_off_returns_service_unavailable_without_side_effects(self):
        with patch.object(main, "INQUIRY_REPLY_WORKFLOW_ENABLED", False):
            response = self.post_reply()

        self.assertEqual(503, response.status_code)
        self.assertEqual([], self.database.queries)
        self.assertEqual([], self.line_transport.calls)

    def test_missing_line_configuration_is_known_unavailable_before_persistence(self):
        with patch.object(main, "LINE_ACCESS_TOKEN", None):
            response = self.post_reply()

        self.assertEqual(503, response.status_code)
        self.assertEqual([], self.database.queries)
        self.assertEqual([], self.line_transport.calls)

    def test_blank_line_configuration_is_known_unavailable_before_persistence(self):
        with patch.object(main, "LINE_ACCESS_TOKEN", "   "):
            response = self.post_reply()

        self.assertEqual(503, response.status_code)
        self.assertEqual([], self.database.queries)
        self.assertEqual([], self.line_transport.calls)

    def test_reply_resolves_destination_from_scoped_inquiry_without_applicant_read(self):
        response = self.post_reply(message="サーバー側で宛先を解決します。")

        self.assertEqual(200, response.status_code)
        self.assertEqual(
            [(RAW_LINE_ID, "サーバー側で宛先を解決します。")],
            [(line_id, message) for line_id, message, _key in self.line_transport.calls],
        )
        self.assertEqual([], self.database.queries_for("applicants"))

    def test_other_tenant_inquiry_is_not_found_before_insert_or_send(self):
        response = self.client.post(
            f"/api/inquiries/{OTHER_INQUIRY}/replies",
            json={
                "assignee_name": "佐藤",
                "message": "他社へ送ってはいけません。",
                "idempotency_key": REPLY_KEY_1,
                "expected_updated_at": "2026-08-03T00:00:00+00:00",
            },
            headers=self.headers,
        )

        self.assertEqual(404, response.status_code)
        self.assertEqual([], self.database.queries_for("inquiry_replies"))
        self.assertEqual([], self.line_transport.calls)
        self.assert_company_scoped("inquiries")

    def test_new_reply_is_durable_and_in_progress_before_line(self):
        expected_updated_at = self.inquiry_row()["updated_at"]

        response = self.post_reply(expected_updated_at=expected_updated_at)

        self.assertEqual(200, response.status_code)
        insert_query = next(
            query
            for query in self.database.queries_for("inquiry_replies")
            if query.insert_data is not None
        )
        inserted = insert_query.insert_data
        self.assertEqual(TENANT_A, inserted["company_id"])
        self.assertEqual(INQUIRY_1, inserted["inquiry_id"])
        self.assertEqual(REPLY_KEY_1, inserted["idempotency_key"])
        self.assertEqual("pending", inserted["delivery_status"])
        self.assertIsNone(inserted["actor_user_id"])
        self.assertRegex(
            str(inserted["line_retry_key"]),
            r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
        )
        self.assertNotEqual(REPLY_KEY_1, str(inserted["line_retry_key"]))
        self.assertEqual([("sending", "対応中")], self.line_transport.durable_snapshots)
        inquiry_update = next(
            query
            for query in self.database.queries_for("inquiries")
            if query.update_data is not None
        )
        self.assertEqual(
            {"status": "対応中", "assignee_name": "佐藤"},
            inquiry_update.update_data,
        )
        self.assertIn(("id", INQUIRY_1), inquiry_update.equal_filters)
        self.assertIn(("company_id", TENANT_A), inquiry_update.equal_filters)
        self.assertIn(("updated_at", expected_updated_at), inquiry_update.equal_filters)

    def test_sent_same_key_and_payload_replays_stored_result_without_line(self):
        sent_at = "2026-08-07T03:00:00+00:00"
        stored = self.add_reply(delivery_status="sent", sent_at=sent_at)
        self.inquiry_row()["status"] = "対応済み"

        response = self.post_reply()

        self.assertEqual(200, response.status_code)
        self.assertEqual(
            {
                "outcome": "sent",
                "reply_id": stored["id"],
                "delivery_status": "sent",
                "inquiry_status": "対応済み",
                "sent_at": sent_at,
                "idempotent_replay": True,
            },
            response.json(),
        )
        self.assertEqual([], self.line_transport.calls)
        self.assertEqual([], self.database.rpc_calls)

    def test_unique_insert_race_replays_the_winning_sent_result(self):
        sent_at = "2026-08-07T03:00:00+00:00"
        winning = self.prepare_insert_race(delivery_status="sent")
        winning["id"] = "50000000-0000-0000-0000-000000000777"
        winning["created_at"] = "2026-08-07T02:59:00+00:00"
        winning["updated_at"] = sent_at
        winning["sent_at"] = sent_at
        self.database.reply_insert_race_row = winning

        response = self.post_reply()

        self.assertEqual(200, response.status_code)
        self.assertEqual("50000000-0000-0000-0000-000000000777", response.json()["reply_id"])
        self.assertTrue(response.json()["idempotent_replay"])
        self.assertEqual([], self.line_transport.calls)

    def test_unique_insert_race_returns_active_pending_or_sending_state(self):
        for status in ("pending", "sending"):
            with self.subTest(status=status):
                self.prepare_insert_race(delivery_status=status)

                response = self.post_reply()

                self.assertEqual(409, response.status_code)
                self.assertEqual({"detail": "REPLY_IN_PROGRESS"}, response.json())
                self.assertEqual([], self.line_transport.calls)
                self.database.rows["inquiry_replies"] = [
                    row
                    for row in self.database.rows["inquiry_replies"]
                    if row.get("idempotency_key") != REPLY_KEY_1
                ]
                self.database.queries.clear()

    def test_unique_insert_race_replays_failed_line_or_conflict_outcome(self):
        cases = [
            ("LINE_REJECTED", 502),
            ("INQUIRY_CONFLICT", 409),
        ]
        for safe_error_code, status_code in cases:
            with self.subTest(safe_error_code=safe_error_code):
                self.prepare_insert_race(
                    delivery_status="failed",
                    safe_error_code=safe_error_code,
                )

                response = self.post_reply()

                self.assertEqual(status_code, response.status_code)
                self.assertEqual({"detail": safe_error_code}, response.json())
                self.assertEqual([], self.line_transport.calls)
                self.database.rows["inquiry_replies"] = [
                    row
                    for row in self.database.rows["inquiry_replies"]
                    if row.get("idempotency_key") != REPLY_KEY_1
                ]
                self.database.queries.clear()

    def test_unique_insert_race_recovers_winning_unknown_with_stored_retry_key(self):
        winning = self.prepare_insert_race(delivery_status="delivery_unknown")
        self.inquiry_row()["status"] = "対応中"

        response = self.post_reply()

        self.assertEqual(200, response.status_code)
        self.assertTrue(response.json()["idempotent_replay"])
        self.assertEqual(winning["line_retry_key"], str(self.line_transport.calls[0][2]))

    def test_same_key_with_changed_message_or_assignee_is_an_idempotency_conflict(self):
        self.add_reply(delivery_status="failed", safe_error_code="LINE_REJECTED")
        for changes in (
            {"message": "変更された返信"},
            {"assignee_name": "鈴木"},
        ):
            with self.subTest(changes=changes):
                response = self.post_reply(**changes)

                self.assertEqual(409, response.status_code)
                self.assertEqual({"detail": "IDEMPOTENCY_CONFLICT"}, response.json())
                self.assertEqual([], self.line_transport.calls)

    def test_pending_or_sending_duplicate_is_in_progress_without_second_line_call(self):
        for status in ("pending", "sending"):
            with self.subTest(status=status):
                stored = self.add_reply(
                    idempotency_key=REPLY_KEY_2 if status == "sending" else REPLY_KEY_1,
                    delivery_status=status,
                )
                response = self.post_reply(idempotency_key=stored["idempotency_key"])

                self.assertEqual(409, response.status_code)
                self.assertEqual({"detail": "REPLY_IN_PROGRESS"}, response.json())
                self.assertEqual([], self.line_transport.calls)

    def test_failed_same_key_returns_stored_rejection_and_new_action_can_send(self):
        self.add_reply(delivery_status="failed", safe_error_code="LINE_REJECTED")

        replay = self.post_reply()
        new_action = self.post_reply(
            message="内容を修正して再確認しました。",
            idempotency_key=REPLY_KEY_2,
        )

        self.assertEqual(502, replay.status_code)
        self.assertEqual({"detail": "LINE_REJECTED"}, replay.json())
        self.assertEqual(200, new_action.status_code)
        self.assertEqual(1, len(self.line_transport.calls))
        self.assertEqual("内容を修正して再確認しました。", self.line_transport.calls[0][1])

    def test_failed_conditional_inquiry_update_marks_unsent_intent_as_conflict(self):
        self.database.zero_next_inquiry_update = True

        response = self.post_reply()

        self.assertEqual(409, response.status_code)
        self.assertEqual({"detail": "INQUIRY_CONFLICT"}, response.json())
        self.assertEqual([], self.line_transport.calls)
        reply = self.replies_for(TENANT_A)[-1]
        self.assertEqual("failed", reply["delivery_status"])
        self.assertEqual("INQUIRY_CONFLICT", reply["safe_error_code"])

    def test_same_key_replays_the_stored_pre_send_conflict(self):
        self.database.zero_next_inquiry_update = True

        first = self.post_reply()
        replay = self.post_reply()

        self.assertEqual(409, first.status_code)
        self.assertEqual(409, replay.status_code)
        self.assertEqual({"detail": "INQUIRY_CONFLICT"}, replay.json())
        self.assertEqual([], self.line_transport.calls)

    def test_pre_send_conflict_marker_zero_rows_returns_unavailable_without_line(self):
        self.database.zero_next_inquiry_update = True
        self.database.zero_reply_update_results[("failed", "INQUIRY_CONFLICT")] = None

        response = self.post_reply()

        self.assertEqual(503, response.status_code)
        self.assertEqual({"detail": "INQUIRY_REPLY_UNAVAILABLE"}, response.json())
        self.assertEqual([], self.line_transport.calls)
        reply = self.replies_for(TENANT_A)[-1]
        self.assertEqual("pending", reply["delivery_status"])
        self.assertIsNone(reply["safe_error_code"])

    def test_pre_send_conflict_accepts_verified_matching_race_winner(self):
        self.database.zero_next_inquiry_update = True
        self.database.zero_reply_update_results[("failed", "INQUIRY_CONFLICT")] = {
            "delivery_status": "failed",
            "safe_error_code": "INQUIRY_CONFLICT",
        }

        response = self.post_reply()

        self.assertEqual(409, response.status_code)
        self.assertEqual({"detail": "INQUIRY_CONFLICT"}, response.json())
        self.assertEqual([], self.line_transport.calls)
        reply = self.replies_for(TENANT_A)[-1]
        verification_reads = [
            query
            for query in self.database.queries_for("inquiry_replies")
            if query.selected_columns is not None
            and ("id", reply["id"]) in query.equal_filters
            and ("inquiry_id", INQUIRY_1) in query.equal_filters
            and ("company_id", TENANT_A) in query.equal_filters
        ]
        self.assertEqual(1, len(verification_reads))

    def test_completed_inquiry_requires_explicit_reopen_before_new_reply(self):
        completed = self.inquiry_row(INQUIRY_2)

        blocked = self.post_reply(INQUIRY_2)
        reopened = self.client.patch(
            f"/api/inquiries/{INQUIRY_2}",
            json={
                "status": "対応中",
                "expected_updated_at": completed["updated_at"],
            },
            headers=self.headers,
        )
        sent = self.post_reply(
            INQUIRY_2,
            idempotency_key=REPLY_KEY_2,
            expected_updated_at=reopened.json()["updated_at"],
        )

        self.assertEqual(409, blocked.status_code)
        self.assertEqual({"detail": "INQUIRY_REOPEN_REQUIRED"}, blocked.json())
        self.assertEqual(200, reopened.status_code)
        self.assertEqual(200, sent.status_code)
        self.assertEqual(1, len(self.line_transport.calls))

    def test_line_acceptance_finalizes_once_with_scoped_ids_and_safe_response(self):
        response = self.post_reply()

        self.assertEqual(200, response.status_code)
        reply = self.replies_for(TENANT_A)[-1]
        self.assertEqual(
            {
                "outcome": "sent",
                "reply_id": reply["id"],
                "delivery_status": "sent",
                "inquiry_status": "対応済み",
                "sent_at": self.database.finalized_at,
                "idempotent_replay": False,
            },
            response.json(),
        )
        self.assertEqual(1, len(self.database.rpc_calls))
        rpc = self.database.rpc_calls[0]
        self.assertEqual("finalize_inquiry_reply", rpc.function_name)
        self.assertEqual(
            {
                "p_company_id": TENANT_A,
                "p_inquiry_id": INQUIRY_1,
                "p_reply_id": reply["id"],
            },
            rpc.parameters,
        )

    def test_accepted_retry_key_conflict_also_finalizes(self):
        self.line_transport.results = [
            LinePushResult(LinePushDisposition.ALREADY_ACCEPTED, 409)
        ]

        response = self.post_reply()

        self.assertEqual(200, response.status_code)
        self.assertEqual("sent", response.json()["delivery_status"])
        self.assertEqual(1, len(self.database.rpc_calls))

    def test_finalizer_failure_returns_unknown_even_if_followup_write_fails(self):
        self.database.fail_finalize = True
        self.database.fail_reply_update_statuses.add("delivery_unknown")

        response = self.post_reply()

        self.assertEqual(202, response.status_code)
        self.assertEqual("delivery_unknown", response.json()["outcome"])
        self.assertEqual("DELIVERY_RESULT_UNKNOWN", response.json()["reason_code"])
        reply = self.replies_for(TENANT_A)[-1]
        self.assertEqual("sending", reply["delivery_status"])
        self.assertEqual("対応中", self.inquiry_row()["status"])
        self.assertEqual(1, len(self.line_transport.calls))
        self.assertEqual(1, len(self.database.rpc_calls))

    def test_stranded_sending_reply_recovers_after_the_active_attempt_lease(self):
        self.database.fail_finalize = True
        self.database.fail_reply_update_statuses.add("delivery_unknown")

        first = self.post_reply()
        reply = self.replies_for(TENANT_A)[-1]
        immediate = self.post_reply()
        reply["updated_at"] = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
        stale_updated_at = reply["updated_at"]
        self.database.fail_finalize = False
        self.database.fail_reply_update_statuses.clear()
        self.line_transport.results = [
            LinePushResult(LinePushDisposition.ALREADY_ACCEPTED, 409)
        ]

        recovered = self.post_reply()

        self.assertEqual(202, first.status_code)
        self.assertEqual(409, immediate.status_code)
        self.assertEqual({"detail": "REPLY_IN_PROGRESS"}, immediate.json())
        self.assertEqual(200, recovered.status_code)
        self.assertTrue(recovered.json()["idempotent_replay"])
        self.assertEqual(2, len(self.line_transport.calls))
        self.assertEqual(
            str(self.line_transport.calls[0][2]),
            str(self.line_transport.calls[1][2]),
        )
        self.assertEqual(2, len(self.database.rpc_calls))
        stale_claim = next(
            query
            for query in self.database.queries_for("inquiry_replies")
            if query.update_data == {
                "delivery_status": "sending",
                "safe_error_code": None,
            }
            and ("updated_at", stale_updated_at) in query.equal_filters
        )
        self.assertIn(("company_id", TENANT_A), stale_claim.equal_filters)
        self.assertIn(("id", reply["id"]), stale_claim.equal_filters)

    def test_only_one_stale_sending_claimant_can_reach_line(self):
        reply = self.add_reply(delivery_status="sending")
        reply["updated_at"] = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
        self.inquiry_row()["status"] = "対応中"
        self.database.zero_next_reply_update = True

        response = self.post_reply()

        self.assertEqual(409, response.status_code)
        self.assertEqual({"detail": "REPLY_IN_PROGRESS"}, response.json())
        claims = [
            query
            for query in self.database.queries_for("inquiry_replies")
            if query.update_data is not None
        ]
        self.assertTrue(claims, "stale sending retry did not attempt a CAS claim")
        claim = claims[0]
        self.assertIn(("updated_at", reply["updated_at"]), claim.equal_filters)
        self.assertEqual([], self.line_transport.calls)

    def test_future_sending_timestamp_remains_active_without_claim_or_line(self):
        reply = self.add_reply(delivery_status="sending")
        reply["updated_at"] = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
        self.inquiry_row()["status"] = "対応中"

        response = self.post_reply()

        self.assertEqual(409, response.status_code)
        self.assertEqual({"detail": "REPLY_IN_PROGRESS"}, response.json())
        self.assertEqual([], self.line_transport.calls)
        self.assertFalse(
            any(
                query.update_data is not None
                for query in self.database.queries_for("inquiry_replies")
            )
        )

    def test_timeout_and_five_xx_are_unknown_without_automatic_retry(self):
        self.line_transport.results = [
            LinePushResult(LinePushDisposition.UNKNOWN, None),
            LinePushResult(LinePushDisposition.UNKNOWN, 503),
        ]

        timeout = self.post_reply(INQUIRY_1, idempotency_key=REPLY_KEY_1)
        server_error = self.post_reply(INQUIRY_3, idempotency_key=REPLY_KEY_2)

        self.assertEqual([202, 202], [timeout.status_code, server_error.status_code])
        self.assertEqual(2, len(self.line_transport.calls))
        self.assertEqual([], self.database.rpc_calls)
        self.assertEqual("delivery_unknown", self.replies_for(TENANT_A, INQUIRY_1)[-1]["delivery_status"])
        self.assertEqual("delivery_unknown", self.replies_for(TENANT_A, INQUIRY_3)[-1]["delivery_status"])

    def test_explicit_line_rejection_is_persisted_and_never_finalized(self):
        self.line_transport.results = [LinePushResult(LinePushDisposition.REJECTED, 400)]

        response = self.post_reply()

        self.assertEqual(502, response.status_code)
        self.assertEqual({"detail": "LINE_REJECTED"}, response.json())
        reply = self.replies_for(TENANT_A)[-1]
        self.assertEqual("failed", reply["delivery_status"])
        self.assertEqual("LINE_REJECTED", reply["safe_error_code"])
        self.assertEqual([], self.database.rpc_calls)

    def test_line_rejection_zero_row_write_returns_unknown_and_does_not_resend(self):
        self.database.zero_reply_update_results[("failed", "LINE_REJECTED")] = None
        self.line_transport.results = [LinePushResult(LinePushDisposition.REJECTED, 400)]

        first = self.post_reply()
        same_key = self.post_reply()

        self.assertEqual(202, first.status_code)
        self.assertEqual("delivery_unknown", first.json()["outcome"])
        self.assertEqual("DELIVERY_RESULT_UNKNOWN", first.json()["reason_code"])
        self.assertEqual(409, same_key.status_code)
        self.assertEqual({"detail": "REPLY_IN_PROGRESS"}, same_key.json())
        self.assertEqual(1, len(self.line_transport.calls))
        reply = self.replies_for(TENANT_A)[-1]
        self.assertEqual("sending", reply["delivery_status"])
        self.assertIsNone(reply["safe_error_code"])

    def test_line_rejection_accepts_verified_matching_race_winner(self):
        self.database.zero_reply_update_results[("failed", "LINE_REJECTED")] = {
            "delivery_status": "failed",
            "safe_error_code": "LINE_REJECTED",
        }
        self.line_transport.results = [LinePushResult(LinePushDisposition.REJECTED, 400)]

        first = self.post_reply()
        same_key = self.post_reply()

        self.assertEqual(502, first.status_code)
        self.assertEqual({"detail": "LINE_REJECTED"}, first.json())
        self.assertEqual(502, same_key.status_code)
        self.assertEqual({"detail": "LINE_REJECTED"}, same_key.json())
        self.assertEqual(1, len(self.line_transport.calls))
        reply = self.replies_for(TENANT_A)[-1]
        verification_reads = [
            query
            for query in self.database.queries_for("inquiry_replies")
            if query.selected_columns is not None
            and ("id", reply["id"]) in query.equal_filters
            and ("inquiry_id", INQUIRY_1) in query.equal_filters
            and ("company_id", TENANT_A) in query.equal_filters
        ]
        self.assertEqual(1, len(verification_reads))

    def test_unknown_retry_within_twenty_four_hours_reuses_stored_line_key(self):
        line_retry_key = "40000000-0000-0000-0000-000000000024"
        stored = self.add_reply(
            delivery_status="delivery_unknown",
            line_retry_key=line_retry_key,
            created_at=(datetime.now(timezone.utc) - timedelta(hours=23)).isoformat(),
        )
        self.inquiry_row()["status"] = "対応中"
        self.line_transport.results = [
            LinePushResult(LinePushDisposition.ALREADY_ACCEPTED, 409)
        ]

        response = self.post_reply()

        self.assertEqual(200, response.status_code)
        self.assertTrue(response.json()["idempotent_replay"])
        self.assertEqual(line_retry_key, str(self.line_transport.calls[0][2]))
        self.assertEqual(stored["id"], response.json()["reply_id"])
        self.assertEqual(1, len(self.database.rpc_calls))

    def test_unknown_retry_after_twenty_four_hours_expires_without_line(self):
        self.add_reply(
            delivery_status="delivery_unknown",
            created_at=(datetime.now(timezone.utc) - timedelta(hours=25)).isoformat(),
        )
        self.inquiry_row()["status"] = "対応中"

        response = self.post_reply()

        self.assertEqual(409, response.status_code)
        self.assertEqual({"detail": "RETRY_WINDOW_EXPIRED"}, response.json())
        self.assertEqual([], self.line_transport.calls)

    def test_other_company_reply_key_is_not_reused_and_all_reply_operations_are_scoped(self):
        other = self.add_reply(
            company_id=TENANT_B,
            inquiry_id=OTHER_INQUIRY,
            delivery_status="sent",
            line_retry_key="40000000-0000-0000-0000-000000000099",
            sent_at="2026-08-07T01:00:00+00:00",
        )

        response = self.post_reply()

        self.assertEqual(200, response.status_code)
        own = [row for row in self.replies_for(TENANT_A) if row.get("idempotency_key") == REPLY_KEY_1]
        self.assertEqual(1, len(own))
        self.assertNotEqual(other["line_retry_key"], str(self.line_transport.calls[0][2]))
        for query in self.database.queries_for("inquiry_replies"):
            if query.insert_data is not None:
                self.assertEqual(TENANT_A, query.insert_data["company_id"])
            else:
                self.assertIn(("company_id", TENANT_A), query.equal_filters)
        for rpc in self.database.rpc_calls:
            self.assertEqual(TENANT_A, rpc.parameters["p_company_id"])
            self.assertIn("p_inquiry_id", rpc.parameters)
            self.assertIn("p_reply_id", rpc.parameters)

    def test_database_failure_before_external_send_returns_service_unavailable(self):
        self.database.fail_next_reply_insert = True

        response = self.post_reply()

        self.assertEqual(503, response.status_code)
        self.assertEqual([], self.line_transport.calls)

    def test_orchestration_failure_log_contains_only_allowlisted_safe_fields(self):
        self.database.fail_finalize = True
        reply_text = "ログへ出してはいけない返信本文"
        assignee = "秘密 担当者"
        source_message = self.inquiry_row()["message"]
        with (
            patch.object(main, "LINE_ACCESS_TOKEN", "secret-line-token"),
            patch.object(main.logger, "info") as info,
        ):
            response = self.post_reply(
                assignee_name=assignee,
                message=reply_text,
            )

        self.assertEqual(202, response.status_code)
        info.assert_called_once()
        record = json.loads(info.call_args.args[0])
        self.assertEqual(
            {
                "event": "inquiry.reply.orchestrate",
                "result": "delivery_unknown",
                "stage": "finalize",
                "reason_code": "DELIVERY_RESULT_UNKNOWN",
                "subject_id": "7ac1b8d7010b",
                "error": "RuntimeError",
            },
            record,
        )
        serialized = info.call_args.args[0]
        for forbidden in (
            source_message,
            reply_text,
            assignee,
            RAW_LINE_ID,
            "secret-line-token",
            "test-admin-key",
            "private provider details",
            "provider response must not be logged",
        ):
            self.assertNotIn(forbidden, serialized)


if __name__ == "__main__":
    unittest.main()
