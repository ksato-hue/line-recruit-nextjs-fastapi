from __future__ import annotations

import hashlib
import json
import re
import subprocess
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
LOCK_PATH = REPOSITORY_ROOT / "supabase" / "migration-chain.lock.json"
MIGRATIONS_DIRECTORY = REPOSITORY_ROOT / "supabase" / "migrations"
STRUCTURAL_CONTRACT_PATH = (
    REPOSITORY_ROOT
    / "supabase"
    / "tests"
    / "fixtures"
    / "production-public-schema-contract.json"
)
DATABASE_COMPLETION_TEST_PATH = (
    REPOSITORY_ROOT
    / "supabase"
    / "tests"
    / "database"
    / "0001_application_session_functions.test.sql"
)
VERSION_PATTERN = re.compile(r"^\d{12}$")
BASELINE_VERSION = "202608060001"
SECURITY_VERSION = "202608060002"
INQUIRY_VERSION = "202608070001"
BASELINE_PATH = (
    "supabase/migrations/"
    "202608060001_public_schema_current_state_baseline.sql"
)
SECURITY_PATH = (
    "supabase/migrations/"
    "202608060002_fail_closed_security_privileges.sql"
)
INQUIRY_PATHS = (
    "supabase/migrations/202608070001_inquiry_workflow_columns.sql",
    "supabase/migrations/202608070002_inquiry_replies.sql",
    "supabase/migrations/202608070003_line_message_log_inquiry_reply.sql",
    "supabase/migrations/202608070004_finalize_inquiry_reply.sql",
)
FINAL_ACTIVE_PATHS = (BASELINE_PATH, SECURITY_PATH, *INQUIRY_PATHS)
LEGACY_ARCHIVE_DIRECTORY = (
    REPOSITORY_ROOT / "supabase" / "legacy_migrations" / "2026-07-pre-baseline"
)
LEGACY_MANIFEST_PATH = LEGACY_ARCHIVE_DIRECTORY / "MANIFEST.md"
LEGACY_MIGRATION_FILENAMES = (
    "202607190001_mvp_security_foundation.sql",
    "202607190002_admin_configuration.sql",
    "202607200001_application_sessions.sql",
    "202607210001_applicant_tags.sql",
)
LEGACY_MIGRATION_ORIGINAL_COMMITS = {
    "202607190001_mvp_security_foundation.sql": "49a3362340a1cb5b12f83cd8c67d404409ec6f43",
    "202607190002_admin_configuration.sql": "447cf981da084042751fa65dcae072fa8ef5a3f7",
    "202607200001_application_sessions.sql": "29373824b601e02c93f01dddd598add65575d815",
    "202607210001_applicant_tags.sql": "62344479c9f633f82ca62bf1f36f3a08aa4d0cb4",
}
LEGACY_MIGRATION_PREFIXES = tuple(
    filename[:12] for filename in LEGACY_MIGRATION_FILENAMES
)


def canonical_git_blob_sha256(revision: str, repository_path: str) -> str:
    blob = subprocess.run(
        ["git", "show", f"{revision}:{repository_path}"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
    ).stdout
    return hashlib.sha256(blob).hexdigest()


def canonical_archive_blob_sha256(archive_path: Path, repository_path: str) -> str:
    object_id = subprocess.run(
        ["git", "hash-object", f"--path={repository_path}", str(archive_path)],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    blob = subprocess.run(
        ["git", "cat-file", "blob", object_id],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
    ).stdout
    return hashlib.sha256(blob).hexdigest()


DOLLAR_QUOTE_PATTERN = re.compile(r'\$(?:[a-z_][\w]*)?\$', re.IGNORECASE)


def split_top_level_sql_statements(sql: str) -> list[str]:
    statements = []
    statement_start = 0
    cursor = 0
    dollar_quote = None
    while cursor < len(sql):
        if dollar_quote is not None:
            closing_index = sql.find(dollar_quote, cursor)
            if closing_index < 0:
                raise ValueError('unterminated dollar-quoted SQL body')
            cursor = closing_index + len(dollar_quote)
            dollar_quote = None
            continue

        dollar_quote_match = DOLLAR_QUOTE_PATTERN.match(sql, cursor)
        if dollar_quote_match is not None:
            dollar_quote = dollar_quote_match.group()
            cursor = dollar_quote_match.end()
            continue

        if sql[cursor] == ';':
            statement = sql[statement_start : cursor + 1].strip()
            if statement:
                statements.append(statement)
            statement_start = cursor + 1
        cursor += 1
    return statements


def normalize_sql_fragment(fragment: str) -> str:
    normalized = re.sub(r"\s+", " ", fragment).strip().lower()
    normalized = re.sub(r"\(\s+", "(", normalized)
    return re.sub(r"\s+\)", ")", normalized)


def split_top_level_comma_items(sql: str) -> list[str]:
    items = []
    item_start = 0
    depth = 0
    in_string = False
    cursor = 0
    while cursor < len(sql):
        character = sql[cursor]
        if character == "'":
            if in_string and cursor + 1 < len(sql) and sql[cursor + 1] == "'":
                cursor += 2
                continue
            in_string = not in_string
        elif not in_string:
            if character == "(":
                depth += 1
            elif character == ")":
                depth -= 1
            elif character == "," and depth == 0:
                items.append(sql[item_start:cursor].strip())
                item_start = cursor + 1
        cursor += 1
    final_item = sql[item_start:].strip()
    if final_item:
        items.append(final_item)
    return items


def extract_unquoted_function_call_arguments(
    sql: str,
    qualified_function_name: str,
) -> list[str]:
    """Return argument text for real calls, ignoring names inside SQL strings."""
    calls = []
    cursor = 0
    in_string = False
    while cursor < len(sql):
        character = sql[cursor]
        if character == "'":
            if in_string and cursor + 1 < len(sql) and sql[cursor + 1] == "'":
                cursor += 2
                continue
            in_string = not in_string
            cursor += 1
            continue
        if in_string or not sql.startswith(qualified_function_name, cursor):
            cursor += 1
            continue

        opening_parenthesis = cursor + len(qualified_function_name)
        while (
            opening_parenthesis < len(sql)
            and sql[opening_parenthesis].isspace()
        ):
            opening_parenthesis += 1
        if (
            opening_parenthesis >= len(sql)
            or sql[opening_parenthesis] != "("
        ):
            cursor += len(qualified_function_name)
            continue

        depth = 1
        call_cursor = opening_parenthesis + 1
        call_in_string = False
        while call_cursor < len(sql) and depth:
            call_character = sql[call_cursor]
            if call_character == "'":
                if (
                    call_in_string
                    and call_cursor + 1 < len(sql)
                    and sql[call_cursor + 1] == "'"
                ):
                    call_cursor += 2
                    continue
                call_in_string = not call_in_string
            elif not call_in_string:
                if call_character == "(":
                    depth += 1
                elif call_character == ")":
                    depth -= 1
            call_cursor += 1
        if depth:
            raise ValueError(f"unterminated call to {qualified_function_name}")
        calls.append(sql[opening_parenthesis + 1 : call_cursor - 1])
        cursor = call_cursor
    return calls


def completion_function_body(migration: str) -> str:
    normalized = re.sub(r"--[^\n]*|/\*.*?\*/", "", migration, flags=re.DOTALL)
    normalized = normalized.lower()
    function = re.search(
        r"\bcreate\s+(?:or\s+replace\s+)?function\s+"
        r"public\s*\.\s*complete_application_session\s*\(.*?\)\s*"
        r"returns\s+jsonb\b.*?\bas\s+"
        r"(?P<quote>\$(?:[a-z_][\w]*)?\$)"
        r"(?P<body>.*?)(?P=quote)\s*;",
        normalized,
        flags=re.DOTALL,
    )
    if function is None:
        raise ValueError("complete_application_session() is absent")
    return normalize_sql_fragment(function.group("body"))


def completion_table_reference_contract_errors(body: str) -> list[str]:
    body_without_string_literals = re.sub(r"'(?:''|[^'])*'", "''", body)
    references = re.findall(
        r"\b(?:from|join|insert\s+into|update|delete\s+from)\s+"
        r"((?:[a-z_][\w$]*\.)?[a-z_][\w$]*)\b",
        body_without_string_literals,
    )
    allowed_references = {
        "public.application_sessions",
        "public.applicants",
    }
    errors = []
    if set(references) != allowed_references:
        errors.append("table references must match the two-table allowlist")
    unqualified_references = [
        reference for reference in references if "." not in reference
    ]
    if unqualified_references:
        errors.append("all table references must be schema-qualified")
    return errors


def completion_update_contract_errors(body: str) -> list[str]:
    update_statements = [
        statement
        for statement in split_top_level_sql_statements(body)
        if re.match(r"^update\s+", statement)
    ]
    if len(update_statements) != 1:
        return ["completion function must contain exactly one update"]
    scoped_update = re.fullmatch(
        r"update\s+public\.application_sessions\s+as\s+session\s+set\s+"
        r".*?where\s+session\.id\s*=\s*p_session_id\s+"
        r"and\s+session\.company_id\s*=\s*p_company_id\s+"
        r"and\s+session\.line_user_id\s*=\s*p_line_user_id\s+"
        r"and\s+session\.status\s*=\s*'active'\s*;",
        update_statements[0],
    )
    return [] if scoped_update is not None else ["missing scoped session update"]


def expected_column_definition(name: str, contract: dict[str, object]) -> str:
    definition = f"{name} {contract['type']}"
    if not contract["nullable"]:
        definition += " NOT NULL"
    if contract["default"] is not None:
        definition += f" DEFAULT {contract['default']}"
    return normalize_sql_fragment(definition)


class StagingMigrationChainTests(unittest.TestCase):
    def test_baseline_matches_approved_structural_inventory(self) -> None:
        """Reject missing or altered base objects and any fixed tenant default."""
        contract = json.loads(STRUCTURAL_CONTRACT_PATH.read_text(encoding="utf-8"))
        lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
        baseline_path = REPOSITORY_ROOT / lock["baseline_path"]
        migration = baseline_path.read_text(encoding="utf-8")
        normalized = re.sub(r"--[^\n]*|/\*.*?\*/", "", migration, flags=re.DOTALL)
        normalized = normalized.lower()

        table_bodies = {
            name: body
            for name, body in re.findall(
                r"\bcreate\s+table\s+public\.([a-z_][\w$]*)\s*"
                r"\((.*?)\)\s*;",
                normalized,
                flags=re.DOTALL,
            )
        }
        self.assertEqual(set(table_bodies), set(contract["tables"]))

        actual_table_items = {}
        all_constraint_definitions = {}
        for table_name, table_contract in contract["tables"].items():
            actual_items = [
                normalize_sql_fragment(item)
                for item in split_top_level_comma_items(table_bodies[table_name])
            ]
            expected_items = [
                expected_column_definition(column_name, column_contract)
                for column_name, column_contract in table_contract["columns"].items()
            ]
            for constraint_name, definition in table_contract["constraints"].items():
                normalized_definition = normalize_sql_fragment(
                    f"CONSTRAINT {constraint_name} {definition}"
                )
                expected_items.append(normalized_definition)
                all_constraint_definitions[constraint_name] = normalized_definition
            self.assertEqual(
                actual_items,
                expected_items,
                f"unexpected structural definition for public.{table_name}",
            )
            actual_table_items[table_name] = actual_items

        self.assertEqual(len(contract["tables"]), 12)
        self.assertEqual(len(all_constraint_definitions), 19)

        legacy_company_columns = contract["legacy_nullable_company_id_columns"]
        self.assertEqual(len(legacy_company_columns), 6)
        for qualified_column in legacy_company_columns:
            table_name, column_name = qualified_column.split(".")
            with self.subTest(legacy_company_id=qualified_column):
                self.assertEqual(column_name, "company_id")
                self.assertIn("company_id text", actual_table_items[table_name])

        for qualified_column in contract["required_company_id_columns"]:
            table_name, column_name = qualified_column.split(".")
            with self.subTest(required_company_id=qualified_column):
                self.assertEqual(column_name, "company_id")
                self.assertIn("company_id text not null", actual_table_items[table_name])

        self.assertFalse(
            any(
                item.startswith("company_id ")
                for item in actual_table_items["contacts"]
            ),
            "public.contacts must not gain a company_id column",
        )
        for table_name, actual_items in actual_table_items.items():
            company_columns = [
                item for item in actual_items if item.startswith("company_id ")
            ]
            for company_column in company_columns:
                with self.subTest(no_tenant_default=table_name):
                    self.assertNotIn(" default ", company_column)

        statements = split_top_level_sql_statements(normalized)
        explicit_indexes = {}
        triggers = {}
        for statement in statements:
            index_match = re.match(
                r"^create\s+(?:unique\s+)?index\s+([a-z_][\w$]*)\b",
                statement,
            )
            if index_match is not None:
                explicit_indexes[index_match.group(1)] = normalize_sql_fragment(
                    statement
                )
            trigger_match = re.match(
                r"^create\s+trigger\s+([a-z_][\w$]*)\b",
                statement,
            )
            if trigger_match is not None:
                triggers[trigger_match.group(1)] = normalize_sql_fragment(statement)
            self.assertNotRegex(
                statement,
                r"^(?:insert|update|delete|merge|copy|truncate)\b",
                "baseline must not contain top-level business DML",
            )

        expected_explicit_indexes = {
            name: normalize_sql_fragment(definition)
            for name, definition in contract["indexes"]["explicit"].items()
        }
        self.assertEqual(explicit_indexes, expected_explicit_indexes)
        self.assertEqual(len(explicit_indexes), 28)

        constraint_backed_indexes = contract["indexes"]["constraint_backed"]
        self.assertEqual(len(constraint_backed_indexes), 15)
        for index_name in constraint_backed_indexes:
            with self.subTest(constraint_backed_index=index_name):
                self.assertIn(index_name, all_constraint_definitions)
                self.assertRegex(
                    all_constraint_definitions[index_name],
                    r"\b(?:primary key|unique)\b",
                )
        self.assertEqual(
            len(constraint_backed_indexes) + len(explicit_indexes),
            43,
        )

        expected_triggers = {
            name: normalize_sql_fragment(definition)
            for name, definition in contract["triggers"].items()
        }
        self.assertEqual(triggers, expected_triggers)
        self.assertEqual(len(triggers), 7)

        self.assertEqual(
            contract["task_7_completion_rpc_body"],
            "separately tested in Task 7",
        )
        self.assertEqual(
            contract["function_signatures"],
            [
                {
                    "name": "set_updated_at",
                    "argument_types": [],
                    "returns": "trigger",
                    "required_in_task_6": True,
                },
                {
                    "name": "complete_application_session",
                    "argument_types": [
                        "uuid",
                        "text",
                        "text",
                        "text",
                        "text",
                        "text",
                        "text",
                        "text",
                        "text",
                    ],
                    "returns": "jsonb",
                    "required_in_task_6": False,
                },
            ],
        )

    def test_baseline_timestamp_function_is_secure_and_has_no_business_dml(self) -> None:
        """Reject a baseline that can expose or alter more than timestamp updates."""
        lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
        baseline_path = REPOSITORY_ROOT / lock["baseline_path"]
        self.assertTrue(
            baseline_path.is_file(),
            f"locked baseline migration does not exist: {baseline_path}",
        )

        migration = baseline_path.read_text(encoding="utf-8")
        normalized = re.sub(r"--[^\n]*|/\*.*?\*/", "", migration, flags=re.DOTALL)
        normalized = normalized.lower()

        self.assertRegex(normalized, r"^\s*begin\s*;")
        self.assertRegex(normalized, r"commit\s*;\s*$")

        statements = split_top_level_sql_statements(normalized)
        contract = json.loads(STRUCTURAL_CONTRACT_PATH.read_text(encoding="utf-8"))
        expected_statement_count = (
            5
            + len(contract["tables"])
            + len(contract["indexes"]["explicit"])
            + len(contract["triggers"])
        )
        self.assertEqual(len(statements), expected_statement_count)
        self.assertRegex(statements[0], r'^begin\s*;$')
        self.assertRegex(
            statements[1],
            r'^create\s+extension\s+if\s+not\s+exists\s+pgcrypto\s+'
            r'with\s+schema\s+extensions\s*;$',
        )
        self.assertRegex(
            statements[2],
            r'^create\s+(?:or\s+replace\s+)?function\s+'
            r'public\s*\.\s*set_updated_at\s*\(\s*\)',
        )
        self.assertRegex(statements[-1], r'^commit\s*;$')

        extensions = re.findall(
            r"\bcreate\s+extension(?:\s+if\s+not\s+exists)?\s+([\w\"]+)",
            normalized,
        )
        self.assertEqual(extensions, ["pgcrypto"])

        create_statements = [
            statement for statement in statements if statement.startswith("create ")
        ]
        for statement in create_statements:
            self.assertRegex(
                statement,
                r"^create\s+(?:extension|(?:or\s+replace\s+)?function|table|"
                r"(?:unique\s+)?index|trigger)\b",
            )
        self.assertEqual(
            sum(
                bool(re.match(r"^create\s+extension\b", statement))
                for statement in create_statements
            ),
            1,
        )
        self.assertEqual(
            sum(
                bool(
                    re.match(
                        r"^create\s+(?:or\s+replace\s+)?function\b",
                        statement,
                    )
                )
                for statement in create_statements
            ),
            2,
        )
        self.assertEqual(
            sum(
                bool(re.match(r"^create\s+table\b", statement))
                for statement in create_statements
            ),
            len(contract["tables"]),
        )
        self.assertEqual(
            sum(
                bool(
                    re.match(
                        r"^create\s+(?:unique\s+)?index\b",
                        statement,
                    )
                )
                for statement in create_statements
            ),
            len(contract["indexes"]["explicit"]),
        )
        self.assertEqual(
            sum(
                bool(re.match(r"^create\s+trigger\b", statement))
                for statement in create_statements
            ),
            len(contract["triggers"]),
        )
        for statement in statements:
            self.assertNotRegex(
                statement,
                r"^(?:alter|drop|truncate|comment|grant|revoke|"
                r"security\s+label|do|call|copy|merge|execute|perform|"
                r"insert|update|delete)\b",
            )
        function_names = re.findall(
            r'\bcreate\s+(?:or\s+replace\s+)?function\s+'
            r'([a-z_][\w$]*)\s*\.\s*([a-z_][\w$]*)',
            normalized,
        )
        self.assertEqual(
            function_names,
            [
                ('public', 'set_updated_at'),
                ('public', 'complete_application_session'),
            ],
        )

        function_contract = re.compile(
            r"\bcreate\s+(?:or\s+replace\s+)?function\s+"
            r"public\s*\.\s*set_updated_at\s*\(\s*\)\s*"
            r"returns\s+trigger\b.*?\bsecurity\s+invoker\b.*?"
            r"\bset\s+search_path\s*=\s*pg_catalog\b",
            re.DOTALL,
        )
        self.assertRegex(normalized, function_contract)
        timestamp_function = re.search(
            r"\bcreate\s+(?:or\s+replace\s+)?function\s+"
            r"public\s*\.\s*set_updated_at\s*\(\s*\)\s*"
            r"returns\s+trigger\b.*?\bas\s+"
            r"(?P<quote>\$(?:[a-z_][\w]*)?\$)"
            r"(?P<body>.*?)"
            r"(?P=quote)\s*;",
            normalized,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(timestamp_function)
        self.assertEqual(
            normalize_sql_fragment(timestamp_function.group("body")),
            "begin new.updated_at := pg_catalog.now(); return new; end;",
            "public.set_updated_at() must retain the exact approved Task 5 body",
        )
        self.assertRegex(
            normalized,
            r'\bset\s+search_path\s*=\s*pg_catalog\s+as\b',
        )
        self.assertNotRegex(normalized, r"\bsecurity\s+definer\b")
        self.assertRegex(
            normalized,
            r"\bnew\s*\.\s*updated_at\s*:=\s*"
            r"pg_catalog\s*\.\s*(?:now|statement_timestamp|"
            r"transaction_timestamp|clock_timestamp)\s*\(\s*\)",
        )
        self.assertNotRegex(
            normalized,
            r"\bgrant\b[^;]*\bto\b[^;]*\b(?:public|anon|authenticated)\b",
        )

    def test_application_completion_function_is_hardened_and_contract_compatible(
        self,
    ) -> None:
        """Reject loss of locking, tenant scope, idempotency, or RPC compatibility."""
        lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
        baseline_path = REPOSITORY_ROOT / lock["baseline_path"]
        migration = baseline_path.read_text(encoding="utf-8")
        normalized = re.sub(r"--[^\n]*|/\*.*?\*/", "", migration, flags=re.DOTALL)
        normalized = normalized.lower()

        completion_function = re.search(
            r"\bcreate\s+(?:or\s+replace\s+)?function\s+"
            r"public\s*\.\s*complete_application_session\s*\("
            r"(?P<arguments>.*?)\)\s*returns\s+jsonb\s+"
            r"language\s+plpgsql\s+security\s+invoker\s+"
            r"set\s+search_path\s*=\s*pg_catalog\s+"
            r"as\s+(?P<quote>\$(?:[a-z_][\w]*)?\$)"
            r"(?P<body>.*?)(?P=quote)\s*;",
            normalized,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(
            completion_function,
            "locked baseline must define complete_application_session() with the hardened header",
        )
        arguments = normalize_sql_fragment(completion_function.group("arguments"))
        self.assertEqual(
            arguments,
            normalize_sql_fragment(
                """
                p_session_id uuid,
                p_company_id text,
                p_line_user_id text,
                p_name text,
                p_phone text,
                p_job text,
                p_motivation text,
                p_applicant_status text,
                p_event_id text default null
                """
            ),
        )

        body = normalize_sql_fragment(completion_function.group("body"))
        self.assertEqual(
            [],
            completion_table_reference_contract_errors(body),
        )
        self.assertNotRegex(body, r"\bsecurity\s+definer\b")
        self.assertNotRegex(body, r"\bexecute\b")

        self.assertRegex(
            body,
            r"select\s+session\.status\s+into\s+v_session_status\s+"
            r"from\s+public\.application_sessions\s+as\s+session\s+"
            r"where\s+session\.id\s*=\s*p_session_id\s+"
            r"and\s+session\.company_id\s*=\s*p_company_id\s+"
            r"and\s+session\.line_user_id\s*=\s*p_line_user_id\s+"
            r"for\s+update",
        )
        self.assertRegex(
            body,
            r"from\s+public\.applicants\s+as\s+applicant\s+"
            r"where\s+applicant\.application_session_id\s*=\s*p_session_id\s+"
            r"and\s+applicant\.company_id\s*=\s*p_company_id\s+"
            r"and\s+applicant\.line_user_id\s*=\s*p_line_user_id",
        )
        self.assertRegex(
            body,
            r"insert\s+into\s+public\.applicants\s+as\s+applicant\s*\("
            r"\s*company_id\s*,\s*application_session_id\s*,\s*line_user_id",
        )
        self.assertRegex(
            body,
            r"values\s*\(\s*p_company_id\s*,\s*p_session_id\s*,\s*p_line_user_id",
        )
        self.assertEqual(
            [],
            completion_update_contract_errors(body),
        )
        self.assertRegex(
            body,
            r"get\s+diagnostics\s+v_updated_count\s*=\s*row_count\s*;\s*"
            r"if\s+v_updated_count\s*<>\s*1\s+then\s+raise\s+exception",
        )
        self.assertRegex(
            body,
            r"if\s+v_session_status\s*=\s*'completed'\s+then\s+"
            r"return\s+pg_catalog\.jsonb_build_object\s*\("
            r"\s*'created'\s*,\s*false\s*,\s*"
            r"'already_completed'\s*,\s*true\s*\)",
        )
        self.assertRegex(
            body,
            r"if\s+v_session_status\s*<>\s*'active'\s+then\s+raise\s+exception",
        )
        self.assertRegex(
            body,
            r"return\s+pg_catalog\.jsonb_build_object\s*\("
            r"\s*'created'\s*,\s*v_created\s*,\s*"
            r"'already_completed'\s*,\s*false\s*,\s*"
            r"'applicant'\s*,\s*v_applicant\s*\)",
        )

    def test_database_completion_contract_is_deferred_transactional_sql(self) -> None:
        """Reject a non-rollback pgTAP suite or accidental privilege/dynamic SQL."""
        sql = DATABASE_COMPLETION_TEST_PATH.read_text(encoding="utf-8")
        normalized = re.sub(r"--[^\n]*|/\*.*?\*/", "", sql, flags=re.DOTALL)
        normalized = normalize_sql_fragment(normalized)

        self.assertRegex(normalized, r"^begin\s*;")
        self.assertRegex(normalized, r"select\s+plan\s*\(\s*15\s*\)")
        self.assertRegex(normalized, r"select\s+\*\s+from\s+finish\s*\(\s*\)")
        self.assertRegex(normalized, r"rollback\s*;\s*$")
        self.assertNotRegex(normalized, r"\bsecurity\s+definer\b")
        self.assertNotRegex(normalized, r"\bexecute\b")
        self.assertNotRegex(normalized, r"\bgrant\b|\brevoke\b")

    def test_pgtap_exact_replay_reuses_all_nine_parameters(self) -> None:
        """Reject replay coverage that changes any request parameter."""
        sql = DATABASE_COMPLETION_TEST_PATH.read_text(encoding="utf-8")
        calls = extract_unquoted_function_call_arguments(
            sql,
            "public.complete_application_session",
        )
        self.assertEqual(2, len(calls), "pgTAP must make two direct RPC calls")
        first_arguments = split_top_level_comma_items(calls[0])
        replay_arguments = split_top_level_comma_items(calls[1])
        self.assertEqual(9, len(first_arguments))
        self.assertEqual(first_arguments, replay_arguments)

    def test_completion_table_guard_rejects_unqualified_business_reference(
        self,
    ) -> None:
        """Reject a business-table reference hidden from qualified-only scans."""
        lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
        migration = (REPOSITORY_ROOT / lock["baseline_path"]).read_text(
            encoding="utf-8"
        )
        mutated_body = completion_function_body(migration) + (
            " perform 1 from applicants;"
        )
        self.assertEqual(
            [
                "table references must match the two-table allowlist",
                "all table references must be schema-qualified",
            ],
            completion_table_reference_contract_errors(mutated_body),
        )

    def test_completion_table_guard_rejects_additional_public_business_table(
        self,
    ) -> None:
        """Reject a schema-qualified table outside the two-table allowlist."""
        lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
        migration = (REPOSITORY_ROOT / lock["baseline_path"]).read_text(
            encoding="utf-8"
        )
        mutated_body = completion_function_body(migration) + (
            " perform 1 from public.contacts;"
        )
        self.assertEqual(
            ["table references must match the two-table allowlist"],
            completion_table_reference_contract_errors(mutated_body),
        )

    def test_completion_update_guard_rejects_additional_unscoped_update(
        self,
    ) -> None:
        """Reject a second application-session update even when one is scoped."""
        lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
        migration = (REPOSITORY_ROOT / lock["baseline_path"]).read_text(
            encoding="utf-8"
        )
        mutated_body = completion_function_body(migration) + (
            " update public.application_sessions set status = 'completed';"
        )
        self.assertEqual(
            ["completion function must contain exactly one update"],
            completion_update_contract_errors(mutated_body),
        )

    def test_approved_migration_chain_lock_contract(self) -> None:
        """Reject a missing, collided, reordered, or altered approved chain."""
        self.assertTrue(
            LOCK_PATH.is_file(),
            f"missing approved migration-chain lock: {LOCK_PATH}",
        )
        lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))

        self.assertEqual(lock["baseline_version"], BASELINE_VERSION)
        self.assertEqual(lock["security_version"], SECURITY_VERSION)
        for field in ("baseline_version", "security_version"):
            with self.subTest(field=field):
                self.assertRegex(lock[field], VERSION_PATTERN)
        self.assertLess(lock["baseline_version"], lock["security_version"])
        self.assertLess(lock["security_version"], INQUIRY_VERSION)
        self.assertEqual(lock["baseline_path"], BASELINE_PATH)
        self.assertEqual(lock["security_path"], SECURITY_PATH)
        self.assertTrue(lock["baseline_path"].endswith("public_schema_current_state_baseline.sql"))
        self.assertTrue(lock["security_path"].endswith("fail_closed_security_privileges.sql"))
        self.assertEqual(lock["supabase_cli_version"], "2.113.0")
        self.assertEqual(lock["backend_database_role"], "service_role")
        self.assertEqual(lock["final_active_paths"], list(FINAL_ACTIVE_PATHS))

        active_filenames = {path.name for path in MIGRATIONS_DIRECTORY.glob("*.sql")}
        active_filenames -= {Path(BASELINE_PATH).name, Path(SECURITY_PATH).name}
        history = subprocess.run(
            ["git", "log", "--all", "--name-only", "--format=", "--", "supabase"],
            cwd=REPOSITORY_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        approved_paths = {BASELINE_PATH, SECURITY_PATH}
        history = [path for path in history if path.replace('\\', '/') not in approved_paths]
        for version in (BASELINE_VERSION, SECURITY_VERSION):
            with self.subTest(version=version):
                self.assertFalse(
                    any(name.startswith(version) for name in active_filenames),
                    f"current migration collision for {version}",
                )
                self.assertFalse(
                    any(version in path for path in history),
                    f"Git history collision for {version}",
                )

        expected_hashes = {
            path: hashlib.sha256(
                (REPOSITORY_ROOT / path).read_bytes()
            ).hexdigest()
            for path in INQUIRY_PATHS
        }
        self.assertEqual(lock["inquiry_migration_sha256"], expected_hashes)

    def test_pre_baseline_legacy_migrations_are_archived_with_verified_hashes(self) -> None:
        """Reject replayable legacy migrations, altered archive bytes, and missing checksums."""
        manifest = (
            LEGACY_MANIFEST_PATH.read_text(encoding="utf-8")
            if LEGACY_MANIFEST_PATH.is_file()
            else ""
        )
        manifest_entries = {}
        for line in manifest.splitlines():
            cells = [cell.strip() for cell in line.split("|")]
            if len(cells) >= 4 and cells[1] in LEGACY_MIGRATION_FILENAMES:
                manifest_entries[cells[1]] = (cells[2], cells[3])

        active_filenames = {path.name for path in MIGRATIONS_DIRECTORY.glob("*.sql")}
        for prefix in LEGACY_MIGRATION_PREFIXES:
            with self.subTest(prefix=prefix):
                self.assertFalse(
                    any(filename.startswith(prefix) for filename in active_filenames),
                    f"legacy migration remains active: {prefix}",
                )

        for filename in LEGACY_MIGRATION_FILENAMES:
            with self.subTest(filename=filename):
                archived_path = LEGACY_ARCHIVE_DIRECTORY / filename
                self.assertTrue(archived_path.is_file())
                self.assertIn(filename, manifest_entries)
                if archived_path.is_file():
                    manifest_hash, manifest_commit = manifest_entries[filename]
                    original_commit = LEGACY_MIGRATION_ORIGINAL_COMMITS[filename]
                    original_path = f"supabase/migrations/{filename}"
                    archive_repository_path = (
                        f"supabase/legacy_migrations/2026-07-pre-baseline/{filename}"
                    )
                    original_hash = canonical_git_blob_sha256(
                        original_commit, original_path
                    )
                    archived_hash = canonical_archive_blob_sha256(
                        archived_path, archive_repository_path
                    )
                    self.assertEqual(
                        manifest_commit,
                        original_commit,
                        "manifest must retain the original first-add commit",
                    )
                    self.assertEqual(
                        manifest_hash,
                        original_hash,
                        "manifest SHA-256 must be calculated from original canonical Git bytes",
                    )
                    self.assertEqual(
                        archived_hash,
                        original_hash,
                        "archive canonical Git bytes must equal original canonical Git bytes",
                    )
        self.assertTrue(
            LEGACY_MANIFEST_PATH.is_file(),
            f"missing legacy migration manifest: {LEGACY_MANIFEST_PATH}",
        )


if __name__ == "__main__":
    unittest.main()
