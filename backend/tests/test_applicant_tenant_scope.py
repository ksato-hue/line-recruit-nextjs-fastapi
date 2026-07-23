import copy
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from tests.support import load_backend_main


main = load_backend_main()


class ApplicantQuery:
    def __init__(self, rows: list[dict]):
        self.rows = rows
        self.filters: list[tuple[str, object]] = []
        self.update_data: dict | None = None

    def select(self, _columns: str):
        return self

    def update(self, data: dict):
        self.update_data = data
        return self

    def eq(self, column: str, value: object):
        self.filters.append((column, value))
        return self

    def order(self, _column: str, desc: bool = False):
        return self

    def execute(self):
        matched = [
            row for row in self.rows
            if all(row.get(column) == value for column, value in self.filters)
        ]
        if self.update_data is not None:
            for row in matched:
                row.update(self.update_data)
        return SimpleNamespace(data=[copy.deepcopy(row) for row in matched])


class ApplicantSupabase:
    def __init__(self):
        self.rows = [
            {"id": "own", "company_id": "tenant-a", "name": "Own Applicant", "memo": ""},
            {"id": "other", "company_id": "tenant-b", "name": "Other Applicant", "memo": ""},
        ]

    def table(self, name: str):
        if name != "applicants":
            raise AssertionError(f"Unexpected table access: {name}")
        return ApplicantQuery(self.rows)


class ApplicantTenantScopeTests(unittest.TestCase):
    def setUp(self):
        self.database = ApplicantSupabase()
        self.patches = [
            patch.object(main, "supabase", self.database),
            patch.object(main, "COMPANY_ID", "tenant-a"),
        ]
        for active_patch in self.patches:
            active_patch.start()

    def tearDown(self):
        for active_patch in reversed(self.patches):
            active_patch.stop()

    def test_applicant_list_excludes_other_company(self):
        result = main.api_applicants()
        self.assertEqual(["own"], [row["id"] for row in result])

    def test_applicant_detail_returns_not_found_for_other_company(self):
        with self.assertRaises(HTTPException) as raised:
            main.api_applicant_detail("other")
        self.assertEqual(404, raised.exception.status_code)

    def test_applicant_update_returns_not_found_for_other_company(self):
        with self.assertRaises(HTTPException) as raised:
            main.api_update_applicant("other", main.ApplicantUpdate(memo="changed"))
        self.assertEqual(404, raised.exception.status_code)
        other = next(row for row in self.database.rows if row["id"] == "other")
        self.assertEqual("", other["memo"])

    def test_applicant_lookup_helper_returns_not_found_for_other_company(self):
        with self.assertRaises(HTTPException) as raised:
            main._get_applicant_or_404("other")
        self.assertEqual(404, raised.exception.status_code)


if __name__ == "__main__":
    unittest.main()
