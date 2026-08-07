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

INQUIRY_REPLIES_MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "supabase"
    / "migrations"
    / "202608070002_inquiry_replies.sql"
)

LINE_MESSAGE_LOG_INQUIRY_REPLY_MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "supabase"
    / "migrations"
    / "202608070003_line_message_log_inquiry_reply.sql"
)


def _has_exact_inquiry_replies_grant_contract(sql: str) -> bool:
    """Return whether inquiry_replies has only its server-role table grant."""
    without_block_comments = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
    without_comments = re.sub(r"--[^\r\n]*", "", without_block_comments)
    grants = [
        " ".join(statement.lower().split())
        for statement in without_comments.split(";")
        if re.match(r"^\s*grant\b", statement, flags=re.IGNORECASE)
    ]
    return grants == [
        "grant select, insert, update on table public.inquiry_replies to service_role"
    ]


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

    def test_inquiry_replies_contract(self) -> None:
        """Protect append-only, tenant-scoped inquiry reply history DDL."""
        self.assertTrue(
            INQUIRY_REPLIES_MIGRATION_PATH.is_file(),
            f"missing inquiry replies migration: {INQUIRY_REPLIES_MIGRATION_PATH}",
        )
        sql = INQUIRY_REPLIES_MIGRATION_PATH.read_text(encoding="utf-8")
        normalized = " ".join(sql.lower().split())

        for column in (
            "id uuid primary key default gen_random_uuid()",
            "company_id text not null",
            "inquiry_id uuid not null",
            "assignee_name text not null",
            "message text not null",
            "delivery_status text not null default 'pending'",
            "idempotency_key uuid not null",
            "line_retry_key uuid not null",
            "safe_error_code text",
            "actor_user_id uuid",
            "created_at timestamptz not null default now()",
            "updated_at timestamptz not null default now()",
            "sent_at timestamptz",
        ):
            with self.subTest(column=column):
                self.assertIn(column, normalized)

        self.assertNotRegex(
            normalized,
            r"company_id text not null default\s+[^, )]+",
        )
        self.assertRegex(
            normalized,
            r"constraint inquiry_replies_company_inquiry_fkey foreign key \(company_id, inquiry_id\) references public\.inquiries \(company_id, id\) on delete restrict",
        )
        self.assertRegex(
            normalized,
            r"constraint inquiry_replies_company_id_id_key unique \(company_id, id\)",
        )
        self.assertRegex(
            normalized,
            r"constraint inquiry_replies_company_inquiry_idempotency_key unique \(company_id, inquiry_id, idempotency_key\)",
        )
        self.assertRegex(
            normalized,
            r"constraint inquiry_replies_line_retry_key_key unique \(line_retry_key\)",
        )
        self.assertRegex(
            normalized,
            r"constraint inquiry_replies_assignee_name_check check \(char_length\(assignee_name\) between 1 and 80 and btrim\(assignee_name\) <> ''\)",
        )
        self.assertRegex(
            normalized,
            r"constraint inquiry_replies_message_check check \(btrim\(message\) <> ''\)",
        )
        self.assertRegex(
            normalized,
            r"constraint inquiry_replies_delivery_status_check check \(delivery_status in \('pending', 'sending', 'sent', 'failed', 'delivery_unknown'\)\)",
        )

        self.assertIn(
            "create index idx_inquiry_replies_company_inquiry_created_at on public.inquiry_replies (company_id, inquiry_id, created_at desc)",
            normalized,
        )
        self.assertIn(
            "create index idx_inquiry_replies_company_delivery_status_created_at on public.inquiry_replies (company_id, delivery_status, created_at)",
            normalized,
        )
        self.assertIn(
            "alter table public.inquiry_replies enable row level security",
            normalized,
        )
        self.assertIn(
            "revoke all on table public.inquiry_replies from public",
            normalized,
        )
        self.assertIn(
            "revoke all on table public.inquiry_replies from anon",
            normalized,
        )
        self.assertIn(
            "revoke all on table public.inquiry_replies from authenticated",
            normalized,
        )
        self.assertTrue(_has_exact_inquiry_replies_grant_contract(sql))
        self.assertNotRegex(normalized, r"create policy\s+[^;]*inquiry_replies")
        self.assertNotRegex(normalized, r"foreign key \(actor_user_id\)")
        self.assertNotIn("references auth.", normalized)
        self.assertIn(
            "create trigger trg_inquiry_replies_set_updated_at before update on public.inquiry_replies for each row execute function public.set_updated_at()",
            normalized,
        )
        self.assertNotRegex(
            sql,
            r"(?im)^\s*(?:insert\s+into|update\s+|delete\s+from)\s+",
        )

    def test_inquiry_replies_grant_contract_rejects_broader_statements(self) -> None:
        """A grant checker must reject broad privileges and mixed browser roles."""
        valid = (
            "grant select, insert, update on table public.inquiry_replies "
            "to service_role;"
        )
        self.assertTrue(_has_exact_inquiry_replies_grant_contract(valid))

        for malicious in (
            "grant all on table public.inquiry_replies to service_role;",
            "grant all privileges on table public.inquiry_replies to service_role;",
            "grant select, insert, update, delete on table public.inquiry_replies "
            "to service_role;",
            "grant select, insert, update on table public.inquiry_replies "
            "to service_role, authenticated;",
            "grant select on table public.inquiry_replies to service_role;",
        ):
            with self.subTest(malicious=malicious):
                self.assertFalse(_has_exact_inquiry_replies_grant_contract(malicious))

        for additional_grant in (
            'grant delete on table "public"."inquiry_replies" to service_role;',
            "grant select on all tables in schema public to authenticated;",
            "/* legacy exception */\ngrant delete on table public.inquiry_replies "
            "to service_role;",
        ):
            with self.subTest(additional_grant=additional_grant):
                self.assertFalse(
                    _has_exact_inquiry_replies_grant_contract(
                        f"{valid}\n{additional_grant}"
                    )
                )

    def test_line_message_log_inquiry_reply_correlation_contract(self) -> None:
        """Protect nullable, tenant-scoped reply-to-log correlation DDL."""
        self.assertTrue(
            LINE_MESSAGE_LOG_INQUIRY_REPLY_MIGRATION_PATH.is_file(),
            "missing line message log inquiry reply migration: "
            f"{LINE_MESSAGE_LOG_INQUIRY_REPLY_MIGRATION_PATH}",
        )
        sql = LINE_MESSAGE_LOG_INQUIRY_REPLY_MIGRATION_PATH.read_text(
            encoding="utf-8"
        )
        normalized = " ".join(sql.lower().split())

        self.assertIn(
            "add column if not exists inquiry_reply_id uuid", normalized
        )
        self.assertNotIn("inquiry_reply_id uuid not null", normalized)
        self.assertRegex(
            normalized,
            r"constraint line_message_logs_inquiry_reply_company_check "
            r"check \(inquiry_reply_id is null or company_id is not null\)",
        )
        self.assertRegex(
            normalized,
            r"constraint line_message_logs_company_inquiry_reply_fkey "
            r"foreign key \(company_id, inquiry_reply_id\) "
            r"references public\.inquiry_replies \(company_id, id\) "
            r"on delete restrict",
        )
        self.assertIn(
            "create index if not exists "
            "idx_line_message_logs_company_inquiry_reply "
            "on public.line_message_logs (company_id, inquiry_reply_id)",
            normalized,
        )
        self.assertIn(
            "create unique index if not exists "
            "uq_line_message_logs_company_inquiry_reply "
            "on public.line_message_logs (company_id, inquiry_reply_id) "
            "where inquiry_reply_id is not null",
            normalized,
        )
        self.assertNotIn("alter column company_id set not null", normalized)
        self.assertNotIn("alter column id", normalized)
        self.assertNotIn("alter column message", normalized)
        self.assertNotIn("line_message_logs_pkey", normalized)
        self.assertNotRegex(
            sql,
            r"(?im)^\s*(?:insert\s+into|update\s+|delete\s+from)\s+",
        )


if __name__ == "__main__":
    unittest.main()
