from __future__ import annotations

import re
import unittest
from pathlib import Path


MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "supabase"
    / "migrations"
    / "202608070001_inquiry_workflow_columns.sql"
)


class InquiryWorkflowMigrationTests(unittest.TestCase):
    def test_inquiry_metadata_contract(self) -> None:
        """Protect inquiry metadata DDL from unsafe tenant or status backfills."""
        self.assertTrue(
            MIGRATION_PATH.is_file(),
            f"missing inquiry workflow migration: {MIGRATION_PATH}",
        )
        sql = MIGRATION_PATH.read_text(encoding="utf-8")
        normalized = " ".join(sql.lower().split())

        self.assertIn("where company_id is null", normalized)
        self.assertIn("where status is null", normalized)
        self.assertRegex(
            normalized,
            r"where status not in \('未対応', '対応中', '対応済み'\)",
        )
        self.assertGreaterEqual(normalized.count("raise exception"), 3)
        self.assertNotIn("update public.inquiries", normalized)
        self.assertNotIn("set company_id =", normalized)
        self.assertNotIn("set status =", normalized)

        self.assertIn(
            "add column if not exists assignee_name text", normalized
        )
        self.assertIn(
            "add column if not exists last_replied_at timestamptz", normalized
        )
        self.assertIn(
            "add column if not exists updated_at timestamptz default now()",
            normalized,
        )
        self.assertIn("alter column updated_at set not null", normalized)
        self.assertRegex(
            normalized,
            r"constraint inquiries_assignee_name_check check \( assignee_name is null or \(char_length\(assignee_name\) between 1 and 80 and btrim\(assignee_name\) <> ''\) \)",
        )
        self.assertRegex(
            normalized,
            r"constraint inquiries_status_check check \(status in \('未対応', '対応中', '対応済み'\)\)",
        )
        self.assertIn("alter column status set not null", normalized)
        self.assertIn("alter column company_id set not null", normalized)
        self.assertRegex(
            normalized,
            r"constraint inquiries_company_id_id_key unique \(company_id, id\)",
        )
        self.assertIn(
            "create index if not exists idx_inquiries_company_status_created_at on public.inquiries (company_id, status, created_at desc)",
            normalized,
        )
        self.assertIn(
            "drop trigger if exists trg_inquiries_set_updated_at on public.inquiries",
            normalized,
        )
        self.assertIn(
            "create trigger trg_inquiries_set_updated_at before update on public.inquiries for each row execute function public.set_updated_at()",
            normalized,
        )


if __name__ == "__main__":
    unittest.main()
