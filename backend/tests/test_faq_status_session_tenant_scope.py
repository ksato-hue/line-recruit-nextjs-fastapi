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
        self.insert_data: dict | list[dict] | None = None
        self.update_data: dict | None = None
        self.delete_requested = False
        self.upsert_data: dict | list[dict] | None = None
        self.conflict_columns: list[str] = []
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

    def delete(self):
        self.delete_requested = True
        return self

    def upsert(self, data: dict | list[dict], on_conflict: str = ""):
        self.upsert_data = copy.deepcopy(data)
        self.conflict_columns = [column.strip() for column in on_conflict.split(",") if column.strip()]
        return self

    def eq(self, column: str, value: object):
        self.equal_filters.append((column, value))
        return self

    def order(self, column: str, desc: bool = False):
        self.order_column = column
        self.order_desc = desc
        return self

    def limit(self, value: int):
        self.row_limit = value
        return self

    def _matches(self, row: dict) -> bool:
        return all(row.get(column) == value for column, value in self.equal_filters)

    def execute(self):
        if self.insert_data is not None:
            operation = "insert"
        elif self.update_data is not None:
            operation = "update"
        elif self.delete_requested:
            operation = "delete"
        elif self.upsert_data is not None:
            operation = "upsert"
        else:
            operation = "select"
        self.database.executed.append({
            "table": self.table_name,
            "operation": operation,
            "eq": copy.deepcopy(self.equal_filters),
        })

        rows = self.database.rows[self.table_name]
        if self.insert_data is not None:
            values = self.insert_data if isinstance(self.insert_data, list) else [self.insert_data]
            inserted = []
            for value in values:
                row = {"id": f"inserted-{self.table_name}-{len(rows) + 1}", **value}
                rows.append(copy.deepcopy(row))
                inserted.append(copy.deepcopy(row))
            return SimpleNamespace(data=inserted)

        if self.upsert_data is not None:
            values = self.upsert_data if isinstance(self.upsert_data, list) else [self.upsert_data]
            saved = []
            for value in values:
                existing = next(
                    (
                        row for row in rows
                        if self.conflict_columns
                        and all(row.get(column) == value.get(column) for column in self.conflict_columns)
                    ),
                    None,
                )
                if existing is None:
                    existing = {"id": f"upserted-{self.table_name}-{len(rows) + 1}"}
                    rows.append(existing)
                existing.update(copy.deepcopy(value))
                saved.append(copy.deepcopy(existing))
            return SimpleNamespace(data=saved)

        matched = [row for row in rows if self._matches(row)]
        if self.order_column:
            matched.sort(
                key=lambda row: (row.get(self.order_column) is None, row.get(self.order_column)),
                reverse=self.order_desc,
            )
        if self.row_limit is not None:
            matched = matched[:self.row_limit]

        if self.update_data is not None:
            for row in matched:
                row.update(copy.deepcopy(self.update_data))
        if self.delete_requested:
            deleted = [copy.deepcopy(row) for row in matched]
            self.database.rows[self.table_name] = [row for row in rows if row not in matched]
            return SimpleNamespace(data=deleted)
        return SimpleNamespace(data=[copy.deepcopy(row) for row in matched])


class TenantSupabase:
    def __init__(self):
        template_category = main.FAQ_TEMPLATES[0]
        template_question = template_category["questions"][0]
        self.template_category_label = template_category["category_label"]
        self.template_question = template_question["question"]
        self.template_faq_key = template_question["faq_key"]
        self.rows = {
            "faq_categories": [
                {"id": "own-category", "company_id": "tenant-a", "name": "Own", "sort_order": 1, "is_active": True},
                {"id": "other-category", "company_id": "tenant-b", "name": "Other", "sort_order": 2, "is_active": True},
            ],
            "faqs": [
                {
                    "id": "other-shared-faq", "company_id": "tenant-b", "category_id": "other-category",
                    "question": "Shared question", "answer": "Other answer", "sort_order": 0, "is_visible": True,
                },
                {
                    "id": "own-shared-faq", "company_id": "tenant-a", "category_id": "own-category",
                    "question": "Shared question", "answer": "Own answer", "sort_order": 1, "is_visible": True,
                },
                {
                    "id": "other-only-faq", "company_id": "tenant-b", "category_id": "other-category",
                    "question": "Other only", "answer": "Secret answer", "sort_order": 2, "is_visible": True,
                },
            ],
            "faq_settings": [
                {
                    "id": "own-setting", "company_id": "tenant-a", "faq_key": self.template_faq_key,
                    "answer": "Own Webhook answer", "is_visible": True,
                },
                {
                    "id": "other-setting", "company_id": "tenant-b", "faq_key": self.template_faq_key,
                    "answer": "Other Webhook answer", "is_visible": True,
                },
            ],
            "applicant_status_settings": [
                {"id": "own-new", "company_id": "tenant-a", "status_key": "new", "name": "新規応募", "sort_order": 1, "is_active": True},
                {"id": "own-adjusting", "company_id": "tenant-a", "status_key": "interview_adjusting", "name": "面接調整中", "sort_order": 2, "is_active": True},
                {"id": "own-confirmed", "company_id": "tenant-a", "status_key": "interview_confirmed", "name": "面接確定", "sort_order": 3, "is_active": True},
                {"id": "own-custom", "company_id": "tenant-a", "status_key": "custom", "name": "旧名称", "sort_order": 4, "is_active": True},
                {"id": "own-unused", "company_id": "tenant-a", "status_key": "unused", "name": "他社のみ使用", "sort_order": 5, "is_active": True},
                {"id": "other-custom", "company_id": "tenant-b", "status_key": "custom", "name": "旧名称", "sort_order": 1, "is_active": True},
            ],
            "applicants": [
                {"id": "own-applicant", "company_id": "tenant-a", "status": "旧名称"},
                {"id": "other-applicant", "company_id": "tenant-b", "status": "旧名称"},
                {"id": "other-unused-user", "company_id": "tenant-b", "status": "他社のみ使用"},
            ],
            "application_sessions": [
                {
                    "id": "shared-session", "company_id": "tenant-a", "line_user_id": "shared-line",
                    "status": "active", "started_at": "2026-07-23T10:00:00+00:00", "answers": [{"question_id": "name", "answer": "Own"}],
                },
                {
                    "id": "shared-session", "company_id": "tenant-b", "line_user_id": "shared-line",
                    "status": "active", "started_at": "2026-07-23T11:00:00+00:00", "answers": [{"question_id": "name", "answer": "Other"}],
                },
                {
                    "id": "other-session", "company_id": "tenant-b", "line_user_id": "other-only-line",
                    "status": "active", "started_at": "2026-07-23T12:00:00+00:00", "answers": [],
                },
            ],
        }
        self.executed: list[dict] = []

    def table(self, name: str):
        if name not in self.rows:
            raise AssertionError(f"Unexpected table access: {name}")
        return TenantQuery(self, name)

    def row(self, table_name: str, row_id: str, company_id: str):
        return next(
            row for row in self.rows[table_name]
            if row.get("id") == row_id and row.get("company_id") == company_id
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
            patch.object(main, "faq_sessions", {}),
            patch.object(main, "application_tree_sessions", {}),
            patch.object(main, "applicants", {}),
            patch.object(main, "_utc_now", return_value="2026-07-23T15:00:00+00:00"),
        ]
        for active_patch in self.patches:
            active_patch.start()

    def tearDown(self):
        for active_patch in reversed(self.patches):
            active_patch.stop()

    def assert_last_query_is_scoped(self, table_name: str, operation: str):
        query = self.database.last_query(table_name, operation)
        self.assertIn(("company_id", "tenant-a"), query["eq"])

    def assert_http_404(self, callback):
        with self.assertRaises(HTTPException) as raised:
            callback()
        self.assertEqual(404, raised.exception.status_code)


class FAQCategoryTenantScopeTests(TenantScopeTestCase):
    def test_category_list_excludes_other_company(self):
        rows = main.api_faq_categories()

        self.assertEqual(["own-category"], [row["id"] for row in rows])
        self.assert_last_query_is_scoped("faq_categories", "select")

    def test_other_company_category_faqs_returns_404(self):
        self.assert_http_404(lambda: main.api_category_faqs("other-category"))

    def test_category_insert_writes_company_id(self):
        created = main.api_create_faq_category(main.FAQCategoryPayload(name="New category"))

        self.assertEqual("tenant-a", created["company_id"])

    def test_other_company_category_update_returns_404_without_mutation(self):
        before = copy.deepcopy(self.database.row("faq_categories", "other-category", "tenant-b"))

        self.assert_http_404(
            lambda: main.api_update_faq_category(
                "other-category", main.FAQCategoryUpdatePayload(name="Changed")
            )
        )

        self.assertEqual(before, self.database.row("faq_categories", "other-category", "tenant-b"))
        self.assert_last_query_is_scoped("faq_categories", "update")

    def test_other_company_category_delete_returns_404_without_mutation(self):
        before = copy.deepcopy(self.database.row("faq_categories", "other-category", "tenant-b"))

        self.assert_http_404(lambda: main.api_delete_faq_category("other-category"))

        self.assertEqual(before, self.database.row("faq_categories", "other-category", "tenant-b"))
        self.assert_last_query_is_scoped("faq_categories", "delete")

    def test_own_category_delete_removes_only_target_with_id_and_company_scope(self):
        kept_category = {
            "id": "own-category-kept", "company_id": "tenant-a", "name": "Kept",
            "sort_order": 3, "is_active": True,
        }
        self.database.rows["faq_categories"].append(copy.deepcopy(kept_category))
        untouched_faqs = copy.deepcopy(self.database.rows["faqs"])
        other_category = copy.deepcopy(
            self.database.row("faq_categories", "other-category", "tenant-b")
        )

        deleted = main.api_delete_faq_category("own-category")

        self.assertEqual("own-category", deleted["id"])
        self.assertFalse(
            any(row["id"] == "own-category" for row in self.database.rows["faq_categories"])
        )
        self.assertEqual(
            kept_category,
            self.database.row("faq_categories", "own-category-kept", "tenant-a"),
        )
        self.assertEqual(
            other_category,
            self.database.row("faq_categories", "other-category", "tenant-b"),
        )
        self.assertEqual(untouched_faqs, self.database.rows["faqs"])
        query = self.database.last_query("faq_categories", "delete")
        self.assertIn(("id", "own-category"), query["eq"])
        self.assertIn(("company_id", "tenant-a"), query["eq"])


class FAQTenantScopeTests(TenantScopeTestCase):
    def test_faq_list_excludes_other_company(self):
        categories = main.api_faqs()

        self.assertEqual(["own-category"], [category["id"] for category in categories])
        self.assertEqual(["own-shared-faq"], [faq["id"] for faq in categories[0]["faqs"]])

    def test_same_question_search_returns_only_own_company_faq(self):
        faq = main.find_faq_by_question("Shared question")

        self.assertIsNotNone(faq)
        self.assertEqual("own-shared-faq", faq["id"])
        self.assert_last_query_is_scoped("faqs", "select")

    def test_webhook_faq_answer_uses_scoped_faq_settings(self):
        user_id = "faq-user"
        main.handle_db_faq_message(user_id, "よくある質問")
        main.handle_db_faq_message(user_id, self.database.template_category_label)
        response = main.handle_db_faq_message(user_id, self.database.template_question)

        self.assertEqual("Own Webhook answer", response["body"])
        self.assertNotIn("Other Webhook answer", response["body"])
        self.assert_last_query_is_scoped("faq_settings", "select")

    def test_faq_insert_writes_company_id(self):
        created = main.api_create_faq(
            main.FAQPayload(
                category_id="own-category", question="New question", answer="New answer", is_visible=True
            )
        )

        self.assertEqual("tenant-a", created["company_id"])

    def test_faq_create_rejects_other_company_category_without_insert(self):
        before = copy.deepcopy(self.database.rows["faqs"])

        self.assert_http_404(
            lambda: main.api_create_faq(
                main.FAQPayload(
                    category_id="other-category", question="Cross tenant", answer="No", is_visible=True
                )
            )
        )

        self.assertEqual(before, self.database.rows["faqs"])

    def test_faq_update_rejects_other_company_category_without_mutation(self):
        before = copy.deepcopy(self.database.row("faqs", "own-shared-faq", "tenant-a"))

        self.assert_http_404(
            lambda: main.api_update_faq(
                "own-shared-faq", main.FAQUpdatePayload(category_id="other-category")
            )
        )

        self.assertEqual(before, self.database.row("faqs", "own-shared-faq", "tenant-a"))

    def test_other_company_faq_update_returns_404_without_mutation(self):
        before = copy.deepcopy(self.database.row("faqs", "other-only-faq", "tenant-b"))

        self.assert_http_404(
            lambda: main.api_update_faq(
                "other-only-faq", main.FAQUpdatePayload(answer="Changed")
            )
        )

        self.assertEqual(before, self.database.row("faqs", "other-only-faq", "tenant-b"))

    def test_faq_update_query_is_company_scoped(self):
        main.api_update_faq("own-shared-faq", main.FAQUpdatePayload(answer="Updated own answer"))

        self.assert_last_query_is_scoped("faqs", "update")

    def test_other_company_faq_delete_returns_404_without_mutation(self):
        before = copy.deepcopy(self.database.row("faqs", "other-only-faq", "tenant-b"))

        self.assert_http_404(lambda: main.api_delete_faq("other-only-faq"))

        self.assertEqual(before, self.database.row("faqs", "other-only-faq", "tenant-b"))
        self.assert_last_query_is_scoped("faqs", "delete")

    def test_own_faq_delete_removes_only_target_with_id_and_company_scope(self):
        kept_faq = {
            "id": "own-kept-faq", "company_id": "tenant-a", "category_id": "own-category",
            "question": "Kept question", "answer": "Kept answer", "sort_order": 3,
            "is_visible": True,
        }
        self.database.rows["faqs"].append(copy.deepcopy(kept_faq))
        untouched_other_faqs = copy.deepcopy([
            row for row in self.database.rows["faqs"] if row["company_id"] == "tenant-b"
        ])
        untouched_categories = copy.deepcopy(self.database.rows["faq_categories"])

        deleted = main.api_delete_faq("own-shared-faq")

        self.assertEqual("own-shared-faq", deleted["id"])
        self.assertFalse(any(row["id"] == "own-shared-faq" for row in self.database.rows["faqs"]))
        self.assertEqual(kept_faq, self.database.row("faqs", "own-kept-faq", "tenant-a"))
        self.assertEqual(
            untouched_other_faqs,
            [row for row in self.database.rows["faqs"] if row["company_id"] == "tenant-b"],
        )
        self.assertEqual(untouched_categories, self.database.rows["faq_categories"])
        query = self.database.last_query("faqs", "delete")
        self.assertIn(("id", "own-shared-faq"), query["eq"])
        self.assertIn(("company_id", "tenant-a"), query["eq"])


class ApplicantStatusTenantScopeTests(TenantScopeTestCase):
    @staticmethod
    def _payload(include_unused: bool = True):
        statuses = [
            main.ApplicantStatusSetting(status_key="new", name="新規応募", sort_order=1, is_active=True),
            main.ApplicantStatusSetting(status_key="interview_adjusting", name="面接調整中", sort_order=2, is_active=True),
            main.ApplicantStatusSetting(status_key="interview_confirmed", name="面接確定", sort_order=3, is_active=True),
            main.ApplicantStatusSetting(status_key="custom", name="新名称", sort_order=4, is_active=True),
        ]
        if include_unused:
            statuses.append(
                main.ApplicantStatusSetting(status_key="unused", name="他社のみ使用", sort_order=5, is_active=True)
            )
        return main.ApplicantStatusSettingsPayload(statuses=statuses)

    def test_status_rename_updates_only_own_company_applicants(self):
        main.api_update_status_settings(self._payload())

        self.assertEqual("新名称", self.database.row("applicants", "own-applicant", "tenant-a")["status"])
        self.assertEqual("旧名称", self.database.row("applicants", "other-applicant", "tenant-b")["status"])
        self.assert_last_query_is_scoped("applicants", "update")

    def test_other_company_status_usage_does_not_block_local_removal(self):
        main.api_update_status_settings(self._payload(include_unused=False))

        self.assertEqual(
            "他社のみ使用",
            self.database.row("applicants", "other-unused-user", "tenant-b")["status"],
        )
        applicant_selects = [
            query for query in self.database.executed
            if query["table"] == "applicants" and query["operation"] == "select"
        ]
        self.assertTrue(applicant_selects)
        self.assertTrue(all(("company_id", "tenant-a") in query["eq"] for query in applicant_selects))


class ApplicationSessionTenantScopeTests(TenantScopeTestCase):
    def test_cancel_updates_only_same_company_session_for_shared_line_user(self):
        main._cancel_application_session("shared-line", "event-1")

        self.assertEqual(
            "cancelled",
            self.database.row("application_sessions", "shared-session", "tenant-a")["status"],
        )
        self.assertEqual(
            "active",
            self.database.row("application_sessions", "shared-session", "tenant-b")["status"],
        )
        self.assert_last_query_is_scoped("application_sessions", "update")

    def test_other_company_only_session_is_safe_no_op(self):
        before = copy.deepcopy(self.database.row("application_sessions", "other-session", "tenant-b"))

        main._cancel_application_session("other-only-line", "event-2")

        self.assertEqual(before, self.database.row("application_sessions", "other-session", "tenant-b"))
        updates = [
            query for query in self.database.executed
            if query["table"] == "application_sessions" and query["operation"] == "update"
        ]
        self.assertEqual([], updates)


if __name__ == "__main__":
    unittest.main()
