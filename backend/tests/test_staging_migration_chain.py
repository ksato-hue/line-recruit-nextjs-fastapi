from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
import unittest
from collections.abc import Mapping, Sequence
from pathlib import Path
from unittest import mock


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
DATABASE_SECURITY_TEST_PATH = (
    REPOSITORY_ROOT
    / "supabase"
    / "tests"
    / "database"
    / "0002_fail_closed_security.test.sql"
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
CANONICAL_INQUIRY_SHA256 = {
    "supabase/migrations/202608070001_inquiry_workflow_columns.sql": (
        "30c760d9bc1a5fc7a061ba23475c08e6601ed30fd8d48bdec236fd9a88b4962b"
    ),
    "supabase/migrations/202608070002_inquiry_replies.sql": (
        "13d936b3598176f4675ac52eaae07950973741fb29c92d4e57782b670c495935"
    ),
    "supabase/migrations/202608070003_line_message_log_inquiry_reply.sql": (
        "25cbdc3bcb71d8a0c85095dd444edec824a67b3c0af8c39bd67c047c9e17d428"
    ),
    "supabase/migrations/202608070004_finalize_inquiry_reply.sql": (
        "8efd6dc9ab4ae4519b607f6ea75a3a8b555b546decd46f33d2dec7ebb0d304a9"
    ),
}
BASE_TABLES = (
    "app_settings",
    "applicant_status_settings",
    "applicants",
    "application_sessions",
    "contacts",
    "faq_categories",
    "faq_settings",
    "faqs",
    "inquiries",
    "interview_slots",
    "line_message_logs",
    "question_tree_settings",
)
APPLICATION_FUNCTIONS = (
    "public.set_updated_at()",
    (
        "public.complete_application_session("
        "uuid, text, text, text, jsonb, text, jsonb, timestamptz, text)"
    ),
)
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


def canonical_git_blob_bytes(revision: str, repository_path: str) -> bytes:
    return subprocess.run(
        ["git", "show", f"{revision}:{repository_path}"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
    ).stdout


def canonical_git_blob_sha256(revision: str, repository_path: str) -> str:
    return hashlib.sha256(
        canonical_git_blob_bytes(revision, repository_path)
    ).hexdigest()


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


def inquiry_checkout_equivalence_errors() -> list[str]:
    errors = []
    comparisons = (
        (
            ["git", "diff", "--quiet", "--", *INQUIRY_PATHS],
            "inquiry migration working tree differs from index",
        ),
        (
            [
                "git",
                "diff",
                "--cached",
                "--quiet",
                "HEAD",
                "--",
                *INQUIRY_PATHS,
            ],
            "inquiry migration index differs from HEAD",
        ),
    )
    for command, error in comparisons:
        result = subprocess.run(
            command,
            cwd=REPOSITORY_ROOT,
            check=False,
            capture_output=True,
        )
        if result.returncode == 1:
            errors.append(error)
        elif result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode,
                command,
                output=result.stdout,
                stderr=result.stderr,
            )
    return errors


def inquiry_chain_contract_errors(
    active_paths: Sequence[str], inquiry_sql_by_path: Mapping[str, bytes]
) -> list[str]:
    errors = []
    if tuple(active_paths) != FINAL_ACTIVE_PATHS:
        errors.append("active migration order")

    supplied_paths = set(inquiry_sql_by_path)
    expected_paths = set(INQUIRY_PATHS)
    if supplied_paths != expected_paths:
        errors.append("inquiry migration filenames")

    for path, expected_hash in CANONICAL_INQUIRY_SHA256.items():
        sql = inquiry_sql_by_path.get(path)
        if sql is None:
            errors.append(f"missing inquiry migration: {path}")
        elif hashlib.sha256(sql).hexdigest() != expected_hash:
            errors.append(f"SHA-256 mismatch: {path}")
    errors.extend(inquiry_checkout_equivalence_errors())
    return errors


def migration_capabilities(sql: str) -> set[str]:
    executable_sql = mask_sql_comments_and_literals(sql)
    statements = [
        normalize_sql_fragment(statement)
        for statement in split_top_level_sql_statements(executable_sql)
    ]
    capabilities = set()

    required_table_columns = {
        "inquiries": (
            r"(?:\(|, )id uuid\b",
            r"(?:\(|, )line_user_id text\b",
            r"(?:\(|, )message text\b",
            r"(?:\(|, )status text\b",
            r"(?:\(|, )created_at timestamptz\b",
            r"(?:\(|, )company_id text\b",
        ),
        "line_message_logs": (
            r"(?:\(|, )id uuid\b",
            r"(?:\(|, )created_at timestamptz\b",
            r"(?:\(|, )line_user_id text\b",
            r"(?:\(|, )message text\b",
            r"(?:\(|, )direction text\b",
            r"(?:\(|, )message_type text\b",
            r"(?:\(|, )company_id text\b",
        ),
        "inquiry_replies": (
            r"(?:\(|, )id uuid\b",
            r"(?:\(|, )company_id text\b",
            r"(?:\(|, )inquiry_id uuid\b",
            r"(?:\(|, )assignee_name text\b",
            r"(?:\(|, )message text\b",
            r"(?:\(|, )delivery_status text\b",
            r"(?:\(|, )sent_at timestamptz\b",
        ),
    }
    table_statements = {}
    for capability, column_patterns in required_table_columns.items():
        table_name = capability
        statement = next(
            (
                candidate
                for candidate in statements
                if re.fullmatch(
                    rf"create table public\.{table_name} \(.*\);",
                    candidate,
                )
                and all(
                    re.search(pattern, candidate)
                    for pattern in column_patterns
                )
            ),
            None,
        )
        if statement is not None:
            table_statements[capability] = statement
            capabilities.add(capability)

    if any(
        re.fullmatch(
            r"create or replace function public\.set_updated_at\(\) "
            r"returns trigger language plpgsql security invoker "
            r"set search_path = pg_catalog as ;",
            statement,
        )
        for statement in statements
    ):
        capabilities.add("set_updated_at")

    if any(
        re.fullmatch(
            r"create function public\.finalize_inquiry_reply\("
            r"p_company_id text, p_inquiry_id uuid, p_reply_id uuid\) "
            r"returns jsonb language plpgsql security invoker "
            r"set search_path = pg_catalog as ;",
            statement,
        )
        for statement in statements
    ):
        capabilities.add("finalize_inquiry_reply")

    if any(
        re.fullmatch(
            r"create extension if not exists pgcrypto(?: with schema extensions)?;",
            statement,
        )
        for statement in statements
    ) and any(
        "default gen_random_uuid()" in statement
        for statement in table_statements.values()
    ):
        capabilities.add("uuid_generation")

    if any(
        statement.startswith("alter table public.inquiries ")
        and re.search(
            r"\badd constraint inquiries_company_id_id_key "
            r"unique \(company_id, id\)",
            statement,
        )
        for statement in statements
    ):
        capabilities.add("inquiries_company_id_id_key")

    inquiry_replies_statement = table_statements.get("inquiry_replies")
    if inquiry_replies_statement is not None and re.search(
        r"\bconstraint inquiry_replies_company_id_id_key "
        r"unique \(company_id, id\)",
        inquiry_replies_statement,
    ):
        capabilities.add("inquiry_replies_company_id_id_key")

    has_correlation_column = any(
        re.fullmatch(
            r"alter table public\.line_message_logs "
            r"add column if not exists inquiry_reply_id uuid;",
            statement,
        )
        for statement in statements
    )
    has_correlation_foreign_key = any(
        statement.startswith("alter table public.line_message_logs ")
        and re.search(
            r"\badd constraint line_message_logs_company_inquiry_reply_fkey "
            r"foreign key \(company_id, inquiry_reply_id\) references "
            r"public\.inquiry_replies \(company_id, id\) on delete restrict",
            statement,
        )
        for statement in statements
    )
    has_correlation_unique_index = any(
        re.fullmatch(
            r"create unique index if not exists "
            r"uq_line_message_logs_company_inquiry_reply on "
            r"public\.line_message_logs \(company_id, inquiry_reply_id\) "
            r"where inquiry_reply_id is not null;",
            statement,
        )
        for statement in statements
    )
    if (
        has_correlation_column
        and has_correlation_foreign_key
        and has_correlation_unique_index
    ):
        capabilities.add("inquiry_reply_correlation")
    return capabilities


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


def pgtap_assertion_signature(
    statement: str,
) -> tuple[str, str, str | None] | None:
    match = re.fullmatch(r"select (is|ok)\((.*)\);", statement)
    if match is None:
        return None
    function_name = match.group(1)
    arguments = split_top_level_comma_items(match.group(2))
    expected_argument_count = 3 if function_name == "is" else 2
    if len(arguments) != expected_argument_count:
        return ("invalid", statement, None)
    expected = arguments[1] if function_name == "is" else None
    return (function_name, arguments[0], expected)


def expected_database_security_assertion_signatures(
) -> list[tuple[str, str, str | None]]:
    contracts = (
        (
            "is",
            """
            (
              SELECT pg_catalog.count(*)
              FROM task8_application_functions AS expected
              WHERE pg_catalog.to_regprocedure(expected.function_signature)
                IS NOT NULL
            )
            """,
            "2::bigint",
        ),
        (
            "is",
            """
            (
              SELECT pg_catalog.count(*)
              FROM pg_catalog.pg_class AS relation
              INNER JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = relation.relnamespace
              INNER JOIN task8_base_tables AS expected
                ON expected.table_name = relation.relname
              WHERE namespace.nspname = 'public'
                AND relation.relrowsecurity
            )
            """,
            "12::bigint",
        ),
        (
            "is",
            """
            (
              SELECT pg_catalog.count(*)
              FROM pg_catalog.pg_class AS relation
              INNER JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = relation.relnamespace
              INNER JOIN task8_base_tables AS expected
                ON expected.table_name = relation.relname
              WHERE namespace.nspname = 'public'
                AND relation.relforcerowsecurity
            )
            """,
            "0::bigint",
        ),
        (
            "is",
            """
            (
              SELECT pg_catalog.count(*)
              FROM pg_catalog.pg_policy AS policy
              INNER JOIN pg_catalog.pg_class AS relation
                ON relation.oid = policy.polrelid
              INNER JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = relation.relnamespace
              INNER JOIN task8_base_tables AS expected
                ON expected.table_name = relation.relname
              WHERE namespace.nspname = 'public'
            )
            """,
            "0::bigint",
        ),
        (
            "is",
            """
            (
              SELECT pg_catalog.count(*)
              FROM task8_base_tables AS expected
              CROSS JOIN (
                VALUES ('anon'), ('authenticated')
              ) AS client_role(role_name)
              CROSS JOIN (
                VALUES ('SELECT'), ('INSERT'), ('UPDATE'), ('DELETE')
              ) AS table_privilege(privilege_name)
              WHERE pg_catalog.has_table_privilege(
                client_role.role_name,
                pg_catalog.format('public.%I', expected.table_name),
                table_privilege.privilege_name
              )
            )
            """,
            "0::bigint",
        ),
        (
            "is",
            """
            (
              SELECT pg_catalog.count(*)
              FROM task8_base_tables AS expected
              CROSS JOIN (
                VALUES ('SELECT'), ('INSERT'), ('UPDATE'), ('DELETE')
              ) AS table_privilege(privilege_name)
              WHERE NOT pg_catalog.has_table_privilege(
                'service_role',
                pg_catalog.format('public.%I', expected.table_name),
                table_privilege.privilege_name
              )
            )
            """,
            "0::bigint",
        ),
        (
            "ok",
            """
            (
              SELECT
                role.rolsuper
                OR role.rolbypassrls
                OR NOT EXISTS (
                  SELECT 1
                  FROM task8_base_tables AS expected
                  INNER JOIN pg_catalog.pg_class AS relation
                    ON relation.relname = expected.table_name
                  INNER JOIN pg_catalog.pg_namespace AS namespace
                    ON namespace.oid = relation.relnamespace
                  WHERE namespace.nspname = 'public'
                    AND relation.relowner <> role.oid
                )
              FROM pg_catalog.pg_roles AS role
              WHERE role.rolname = 'service_role'
            )
            """,
            None,
        ),
        (
            "is",
            """
            (
              SELECT pg_catalog.count(*)
              FROM task8_application_functions AS expected
              INNER JOIN pg_catalog.pg_proc AS routine
                ON routine.oid =
                  pg_catalog.to_regprocedure(expected.function_signature)
              CROSS JOIN LATERAL pg_catalog.aclexplode(
                COALESCE(
                  routine.proacl,
                  pg_catalog.acldefault('f', routine.proowner)
                )
              ) AS function_acl
              WHERE function_acl.grantee = 0
                AND function_acl.privilege_type = 'EXECUTE'
            )
            """,
            "0::bigint",
        ),
        (
            "is",
            """
            (
              SELECT pg_catalog.count(*)
              FROM task8_application_functions AS expected
              CROSS JOIN (
                VALUES ('anon'), ('authenticated')
              ) AS client_role(role_name)
              WHERE pg_catalog.has_function_privilege(
                client_role.role_name,
                pg_catalog.to_regprocedure(expected.function_signature),
                'EXECUTE'
              )
            )
            """,
            "0::bigint",
        ),
        (
            "is",
            """
            (
              SELECT pg_catalog.count(*)
              FROM task8_application_functions AS expected
              WHERE NOT pg_catalog.has_function_privilege(
                'service_role',
                pg_catalog.to_regprocedure(expected.function_signature),
                'EXECUTE'
              )
            )
            """,
            "0::bigint",
        ),
        (
            "is",
            """
            (
              SELECT pg_catalog.count(*)
              FROM (
                VALUES ('anon'), ('authenticated')
              ) AS client_role(role_name)
              WHERE pg_catalog.has_schema_privilege(
                client_role.role_name,
                'public',
                'CREATE'
              )
            )
            """,
            "0::bigint",
        ),
        (
            "ok",
            "pg_catalog.has_schema_privilege('service_role', 'public', 'USAGE')",
            None,
        ),
        (
            "is",
            """
            (
              SELECT pg_catalog.count(*)
              FROM (
                VALUES ('anon'), ('authenticated')
              ) AS client_role(role_name)
              CROSS JOIN (
                VALUES ('SELECT'), ('INSERT'), ('UPDATE'), ('DELETE')
              ) AS table_privilege(privilege_name)
              WHERE pg_catalog.has_table_privilege(
                client_role.role_name,
                'public.task8_default_privilege_table',
                table_privilege.privilege_name
              )
            )
            """,
            "0::bigint",
        ),
        (
            "is",
            """
            (
              SELECT pg_catalog.count(*)
              FROM (
                VALUES ('anon'), ('authenticated')
              ) AS client_role(role_name)
              WHERE pg_catalog.has_function_privilege(
                client_role.role_name,
                'public.task8_default_privilege_function()',
                'EXECUTE'
              )
            )
            """,
            "0::bigint",
        ),
        (
            "is",
            """
            (
              SELECT pg_catalog.count(*)
              FROM (
                VALUES ('anon'), ('authenticated')
              ) AS client_role(role_name)
              CROSS JOIN (
                VALUES ('USAGE'), ('SELECT'), ('UPDATE')
              ) AS sequence_privilege(privilege_name)
              WHERE pg_catalog.has_sequence_privilege(
                client_role.role_name,
                'public.task8_default_privilege_sequence',
                sequence_privilege.privilege_name
              )
            )
            """,
            "0::bigint",
        ),
    )
    return [
        (function_name, normalize_sql_fragment(actual), expected)
        for function_name, actual, expected in contracts
    ]


def database_security_contract_errors(sql: str) -> list[str]:
    executable = re.sub(r"--[^\n]*|/\*.*?\*/", "", sql, flags=re.DOTALL)
    statements = [
        normalize_sql_fragment(statement)
        for statement in split_top_level_sql_statements(executable)
    ]
    errors = []
    if not statements or statements[0] != "begin;":
        errors.append("pgTAP contract must begin a transaction")
    if not statements or statements[-1] != "rollback;":
        errors.append("pgTAP contract must end with rollback")
    if statements.count("select plan(15);") != 1:
        errors.append("pgTAP contract must plan exactly 15 assertions")
    if statements.count("select * from finish();") != 1:
        errors.append("pgTAP contract must finish exactly once")

    expected_table_inventory = normalize_sql_fragment(
        "INSERT INTO task8_base_tables (table_name) VALUES "
        + ", ".join(f"('{table_name}')" for table_name in BASE_TABLES)
        + ";"
    )
    expected_function_inventory = normalize_sql_fragment(
        "INSERT INTO task8_application_functions (function_signature) VALUES "
        + ", ".join(f"('{function}')" for function in APPLICATION_FUNCTIONS)
        + ";"
    )
    required_statements = (
        normalize_sql_fragment(
            "CREATE TEMPORARY TABLE task8_base_tables "
            "(table_name text PRIMARY KEY) ON COMMIT DROP;"
        ),
        expected_table_inventory,
        normalize_sql_fragment(
            "CREATE TEMPORARY TABLE task8_application_functions "
            "(function_signature text PRIMARY KEY) ON COMMIT DROP;"
        ),
        expected_function_inventory,
        normalize_sql_fragment(
            "CREATE TABLE public.task8_default_privilege_table "
            "(id integer PRIMARY KEY);"
        ),
        normalize_sql_fragment(
            "CREATE FUNCTION public.task8_default_privilege_function() "
            "RETURNS integer LANGUAGE sql SECURITY INVOKER "
            "SET search_path = pg_catalog AS 'SELECT 1';"
        ),
        "create sequence public.task8_default_privilege_sequence;",
    )
    for required_statement in required_statements:
        if statements.count(required_statement) != 1:
            errors.append(
                "missing or altered structural statement: " + required_statement
            )

    assertion_signatures = [
        signature
        for statement in statements
        if (signature := pgtap_assertion_signature(statement)) is not None
    ]
    if assertion_signatures != expected_database_security_assertion_signatures():
        errors.append(
            "pgTAP assertion structures must match the exact 15-case security matrix"
        )
    return errors


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


def mask_sql_comments_and_literals(sql: str) -> str:
    """Mask non-code SQL while preserving offsets and statement delimiters."""
    masked = list(sql)

    def mask_range(start: int, end: int) -> None:
        for index in range(start, end):
            if masked[index] not in {"\r", "\n"}:
                masked[index] = " "

    cursor = 0
    while cursor < len(sql):
        if sql.startswith("--", cursor):
            end = sql.find("\n", cursor + 2)
            end = len(sql) if end < 0 else end
            mask_range(cursor, end)
            cursor = end
            continue
        if sql.startswith("/*", cursor):
            depth = 1
            end = cursor + 2
            while end < len(sql) and depth:
                if sql.startswith("/*", end):
                    depth += 1
                    end += 2
                elif sql.startswith("*/", end):
                    depth -= 1
                    end += 2
                else:
                    end += 1
            if depth:
                raise ValueError("unterminated SQL block comment")
            mask_range(cursor, end)
            cursor = end
            continue
        if sql[cursor] == "'":
            end = cursor + 1
            while end < len(sql):
                if sql[end] != "'":
                    end += 1
                    continue
                if end + 1 < len(sql) and sql[end + 1] == "'":
                    end += 2
                    continue
                end += 1
                break
            else:
                raise ValueError("unterminated SQL string literal")
            mask_range(cursor, end)
            cursor = end
            continue
        if sql[cursor] == '"':
            end = cursor + 1
            while end < len(sql):
                if sql[end] != '"':
                    end += 1
                    continue
                if end + 1 < len(sql) and sql[end + 1] == '"':
                    end += 2
                    continue
                end += 1
                break
            else:
                raise ValueError("unterminated SQL quoted identifier")
            cursor = end
            continue
        dollar_quote = DOLLAR_QUOTE_PATTERN.match(sql, cursor)
        if dollar_quote is not None:
            delimiter = dollar_quote.group()
            closing_index = sql.find(delimiter, dollar_quote.end())
            if closing_index < 0:
                raise ValueError("unterminated dollar-quoted SQL literal")
            end = closing_index + len(delimiter)
            mask_range(cursor, end)
            cursor = end
            continue
        cursor += 1
    return "".join(masked)


def normalized_sql_identifier(token: re.Match[str]) -> str | None:
    quoted_identifier = token.group("quoted_identifier")
    if quoted_identifier is not None:
        return quoted_identifier[1:-1].replace('""', '"')
    word = token.group("word")
    return word.lower() if word is not None else None


def executable_update_statements(body: str) -> list[tuple[str, str]]:
    """Return normalized targets/statements for DML UPDATE, excluding row locks."""
    masked_body = mask_sql_comments_and_literals(body)
    token_pattern = re.compile(
        r'(?P<quoted_identifier>"(?:[^"]|"")*")'
        r'|(?P<word>[a-z_][\w$]*)'
        r'|(?P<semicolon>;)'
        r'|(?P<dot>\.)'
        r'|(?P<symbol>\S)',
        flags=re.IGNORECASE,
    )
    tokens = list(token_pattern.finditer(masked_body))
    updates = []
    for index, token in enumerate(tokens):
        word = token.group("word")
        if word is None or word.lower() != "update":
            continue

        preceding_words = []
        preceding_index = index - 1
        while preceding_index >= 0 and len(preceding_words) < 3:
            preceding_token = tokens[preceding_index]
            if preceding_token.group("semicolon") is not None:
                break
            preceding_word = preceding_token.group("word")
            if preceding_word is not None:
                preceding_words.append(preceding_word.lower())
            preceding_index -= 1
        if preceding_words[:1] == ["for"]:
            continue
        if preceding_words[:3] == ["key", "no", "for"]:
            continue

        target_index = index + 1
        if (
            target_index < len(tokens)
            and (tokens[target_index].group("word") or "").lower() == "only"
        ):
            target_index += 1
        if target_index >= len(tokens):
            raise ValueError("update statement has no target")
        first_identifier = normalized_sql_identifier(tokens[target_index])
        if first_identifier is None:
            raise ValueError("update statement has an invalid target")
        target = first_identifier
        if (
            target_index + 2 < len(tokens)
            and tokens[target_index + 1].group("dot") is not None
        ):
            second_identifier = normalized_sql_identifier(tokens[target_index + 2])
            if second_identifier is None:
                raise ValueError("update statement has an invalid qualified target")
            target = f"{first_identifier}.{second_identifier}"

        statement_end = next(
            (
                candidate.end()
                for candidate in tokens[index + 1 :]
                if candidate.group("semicolon") is not None
            ),
            None,
        )
        if statement_end is None:
            raise ValueError("unterminated update statement")
        updates.append(
            (
                target,
                normalize_sql_fragment(body[token.start() : statement_end]),
            )
        )
    return updates


def completion_update_contract_errors(body: str) -> list[str]:
    try:
        updates = executable_update_statements(body)
    except ValueError as error:
        return [str(error)]
    if len(updates) != 1:
        return ["completion function must contain exactly one update"]
    update_target, update_statement = updates[0]
    if update_target != "public.application_sessions":
        return ["missing scoped session update"]
    scoped_update = re.fullmatch(
        r"update\s+public\.application_sessions\s+as\s+session\s+set\s+"
        r".*?where\s+session\.id\s*=\s*p_session_id\s+"
        r"and\s+session\.company_id\s*=\s*p_company_id\s+"
        r"and\s+session\.line_user_id\s*=\s*p_line_user_id\s+"
        r"and\s+session\.status\s*=\s*'active'\s*;",
        update_statement,
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

    def test_fail_closed_security_migration_is_exact(self) -> None:
        """Reject missing RLS or any privilege broadening beyond the allowlist."""
        lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
        self.assertEqual("service_role", lock["backend_database_role"])
        security_path = REPOSITORY_ROOT / lock["security_path"]
        self.assertTrue(
            security_path.is_file(),
            f"locked security migration is absent: {security_path}",
        )
        migration = security_path.read_text(encoding="utf-8")
        executable = re.sub(
            r"--[^\n]*|/\*.*?\*/",
            "",
            migration,
            flags=re.DOTALL,
        )
        statements = [
            normalize_sql_fragment(statement)
            for statement in split_top_level_sql_statements(executable)
        ]

        qualified_tables = ", ".join(
            f"public.{table_name}" for table_name in BASE_TABLES
        )
        functions = ", ".join(APPLICATION_FUNCTIONS)
        client_roles = "public, anon, authenticated"
        expected_statements = [
            "begin;",
            *(
                f"alter table public.{table_name} enable row level security;"
                for table_name in BASE_TABLES
            ),
            f"revoke create on schema public from {client_roles};",
            "grant usage on schema public to service_role;",
            (
                f"revoke all privileges on table {qualified_tables} "
                f"from {client_roles};"
            ),
            (
                "grant select, insert, update, delete on table "
                f"{qualified_tables} to service_role;"
            ),
            (
                f"revoke all privileges on function {functions} "
                f"from {client_roles};"
            ),
            f"grant execute on function {functions} to service_role;",
            (
                "alter default privileges in schema public revoke all privileges "
                f"on tables from {client_roles};"
            ),
            (
                "alter default privileges in schema public revoke all privileges "
                f"on functions from {client_roles};"
            ),
            (
                "alter default privileges in schema public revoke all privileges "
                f"on sequences from {client_roles};"
            ),
            "commit;",
        ]
        expected_statements = [
            normalize_sql_fragment(statement) for statement in expected_statements
        ]
        self.assertEqual(expected_statements, statements)

        normalized = " ".join(statements)
        self.assertNotRegex(normalized, r"\bforce\s+row\s+level\s+security\b")
        self.assertNotRegex(normalized, r"\b(?:create|alter|drop)\s+policy\b")
        self.assertNotRegex(normalized, r"\balter\s+role\b")
        self.assertNotRegex(normalized, r"\bowner\s+to\b")
        self.assertNotRegex(normalized, r"\bgrant\s+all(?:\s+privileges)?\b")
        self.assertNotRegex(
            normalized,
            r"\bgrant\b[^;]*\bto\b[^;]*\b(?:public|anon|authenticated)\b",
        )
        self.assertNotRegex(
            normalized,
            r"\bon\s+all\s+(?:tables|functions|sequences)\s+in\s+schema\b",
        )
        self.assertNotRegex(
            normalized,
            (
                r"\b(?:auth|storage|realtime|extensions|graphql|graphql_public|"
                r"net|vault|supabase_functions)\."
            ),
        )

    def test_database_security_contract_is_deferred_transactional_sql(self) -> None:
        """Reject pgTAP coverage that omits a fail-closed runtime invariant."""
        sql = DATABASE_SECURITY_TEST_PATH.read_text(encoding="utf-8")
        errors = database_security_contract_errors(sql)
        self.assertEqual([], errors, "\n".join(errors))

    def test_database_security_contract_requires_service_role_rls_capability(
        self,
    ) -> None:
        """Reject ACL-only coverage that never proves service_role can pass RLS."""
        sql = DATABASE_SECURITY_TEST_PATH.read_text(encoding="utf-8")
        statements = [
            normalize_sql_fragment(statement)
            for statement in split_top_level_sql_statements(sql)
        ]
        self.assertTrue(
            any(
                statement.startswith("select ok(")
                and all(
                    token in statement
                    for token in (
                        "pg_catalog.pg_roles",
                        "rolsuper",
                        "rolbypassrls",
                        "relowner",
                        "task8_base_tables",
                        "service_role",
                    )
                )
                for statement in statements
            ),
            "pgTAP must prove service_role can bypass RLS or owns every base table",
        )

    def test_database_security_contract_requires_both_functions_to_exist(
        self,
    ) -> None:
        """Reject privilege assertions that can discard unresolved signatures."""
        sql = DATABASE_SECURITY_TEST_PATH.read_text(encoding="utf-8")
        statements = [
            normalize_sql_fragment(statement)
            for statement in split_top_level_sql_statements(sql)
        ]
        self.assertTrue(
            any(
                statement.startswith("select is(")
                and all(
                    token in statement
                    for token in (
                        "task8_application_functions",
                        "pg_catalog.to_regprocedure",
                        "is not null",
                        "2::bigint",
                    )
                )
                for statement in statements
            ),
            "pgTAP must fail unless both exact application signatures resolve",
        )

    def test_database_security_contract_rejects_inert_assertion_tokens(
        self,
    ) -> None:
        """Reject real query text hidden in 15 unconditional assertion labels."""
        sql = DATABASE_SECURITY_TEST_PATH.read_text(encoding="utf-8")
        inert_statements = []
        replaced_assertions = 0
        for statement in split_top_level_sql_statements(sql):
            normalized = normalize_sql_fragment(statement)
            if pgtap_assertion_signature(normalized) is None:
                inert_statements.append(statement)
                continue
            replaced_assertions += 1
            inert_statements.append(
                "SELECT ok(true, $inert$" + statement + "$inert$);"
            )
        self.assertEqual(15, replaced_assertions)
        inert_sql = "\n".join(inert_statements)
        with mock.patch.object(Path, "read_text", return_value=inert_sql):
            with self.assertRaises(AssertionError):
                self.test_database_security_contract_is_deferred_transactional_sql()

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

    def test_completion_update_guard_rejects_nested_unscoped_update(
        self,
    ) -> None:
        """Reject an extra update nested behind a PL/pgSQL control-flow prefix."""
        lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
        migration = (REPOSITORY_ROOT / lock["baseline_path"]).read_text(
            encoding="utf-8"
        )
        body = completion_function_body(migration)
        body_before_final_end, final_end = body.rsplit("end;", 1)
        mutated_body = (
            body_before_final_end
            + " if p_event_id is null then"
            + " update public.application_sessions set status = 'completed';"
            + " end if; end;"
            + final_end
        )
        self.assertEqual(
            ["completion function must contain exactly one update"],
            completion_update_contract_errors(mutated_body),
        )

    def test_completion_update_guard_rejects_nested_quoted_unscoped_update(
        self,
    ) -> None:
        """Reject a nested update whose relation uses quoted identifiers."""
        lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
        migration = (REPOSITORY_ROOT / lock["baseline_path"]).read_text(
            encoding="utf-8"
        )
        body = completion_function_body(migration)
        body_before_final_end, final_end = body.rsplit("end;", 1)
        mutated_body = (
            body_before_final_end
            + " if p_event_id is null then"
            + ' update "public"."application_sessions"'
            + " set status = 'completed';"
            + " end if; end;"
            + final_end
        )
        self.assertEqual(
            ["completion function must contain exactly one update"],
            completion_update_contract_errors(mutated_body),
        )

    def test_completion_update_guard_ignores_valid_row_lock_variants(
        self,
    ) -> None:
        """Do not classify PostgreSQL FOR UPDATE clauses as DML updates."""
        lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
        migration = (REPOSITORY_ROOT / lock["baseline_path"]).read_text(
            encoding="utf-8"
        )
        body = completion_function_body(migration)
        lock_clauses = (
            "for update of session;",
            "for update nowait;",
            "for update skip locked;",
        )
        for lock_clause in lock_clauses:
            with self.subTest(lock_clause=lock_clause):
                mutated_body = body.replace("for update;", lock_clause, 1)
                self.assertNotEqual(body, mutated_body)
                self.assertEqual([], completion_update_contract_errors(mutated_body))

    def test_completion_update_guard_ignores_comments_and_string_literals(
        self,
    ) -> None:
        """Do not mistake inert UPDATE text for executable statements."""
        lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
        migration = (REPOSITORY_ROOT / lock["baseline_path"]).read_text(
            encoding="utf-8"
        )
        body = completion_function_body(migration)
        body_before_final_end, final_end = body.rsplit("end;", 1)
        mutated_body = (
            body_before_final_end
            + " raise notice 'UPDATE public.application_sessions;';"
            + " perform $message$UPDATE public.application_sessions;$message$;"
            + " -- UPDATE public.application_sessions;\n"
            + " /* UPDATE public.application_sessions; */ end;"
            + final_end
        )
        self.assertEqual([], completion_update_contract_errors(mutated_body))

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
            path: canonical_git_blob_sha256("HEAD", path)
            for path in INQUIRY_PATHS
        }
        self.assertEqual(lock["inquiry_migration_sha256"], expected_hashes)

    def test_canonical_inquiry_migration_identity_and_active_order(self) -> None:
        """Reject extra active SQL, renamed versions, or altered inquiry bytes."""
        lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
        active_paths = tuple(
            f"supabase/migrations/{path.name}"
            for path in sorted(MIGRATIONS_DIRECTORY.glob("*.sql"))
        )
        inquiry_sql_by_path = {
            path: canonical_git_blob_bytes("HEAD", path)
            for path in INQUIRY_PATHS
        }

        self.assertEqual(
            [],
            inquiry_chain_contract_errors(active_paths, inquiry_sql_by_path),
        )
        self.assertEqual(list(FINAL_ACTIVE_PATHS), lock["final_active_paths"])
        self.assertEqual(
            CANONICAL_INQUIRY_SHA256,
            lock["inquiry_migration_sha256"],
        )

    def test_inquiry_lock_uses_canonical_git_blob_hashes(self) -> None:
        """Reject checkout-dependent inquiry hashes in the chain lock."""
        lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
        expected_hashes = {
            path: canonical_git_blob_sha256("HEAD", path)
            for path in INQUIRY_PATHS
        }

        self.assertEqual(
            expected_hashes,
            lock["inquiry_migration_sha256"],
        )

    def test_inquiry_identity_ignores_checkout_line_endings(self) -> None:
        """Verify Git blob bytes even when a checkout would contain CRLF."""
        canonical_blobs = {
            path: subprocess.run(
                ["git", "show", f"HEAD:{path}"],
                cwd=REPOSITORY_ROOT,
                check=True,
                capture_output=True,
            ).stdout
            for path in INQUIRY_PATHS
        }
        crlf_checkout_blobs = {
            path: blob.replace(b"\n", b"\r\n")
            for path, blob in canonical_blobs.items()
        }
        self.assertNotEqual(
            {
                path: hashlib.sha256(blob).hexdigest()
                for path, blob in canonical_blobs.items()
            },
            {
                path: hashlib.sha256(blob).hexdigest()
                for path, blob in crlf_checkout_blobs.items()
            },
        )

        with mock.patch.object(
            Path,
            "read_bytes",
            side_effect=AssertionError("checkout bytes must not be read"),
        ):
            self.assertEqual(
                [],
                inquiry_chain_contract_errors(
                    FINAL_ACTIVE_PATHS,
                    canonical_blobs,
                ),
            )

    def test_inquiry_guard_rejects_worktree_mutation_with_crlf_checkout(
        self,
    ) -> None:
        """Accept clean CRLF but reject a real protected-SQL checkout edit."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            clone_root = Path(temporary_directory) / "repository"
            subprocess.run(
                [
                    "git",
                    "-c",
                    "core.autocrlf=true",
                    "clone",
                    "--quiet",
                    "--no-hardlinks",
                    str(REPOSITORY_ROOT),
                    str(clone_root),
                ],
                check=True,
            )
            subprocess.run(
                ["git", "config", "--local", "core.autocrlf", "true"],
                cwd=clone_root,
                check=True,
            )
            clone_autocrlf = subprocess.run(
                ["git", "config", "--local", "--get", "core.autocrlf"],
                cwd=clone_root,
                check=False,
                capture_output=True,
                text=True,
            ).stdout.strip()
            self.assertEqual("true", clone_autocrlf)
            checkout_eol = subprocess.run(
                ["git", "ls-files", "--eol", "--", *INQUIRY_PATHS],
                cwd=clone_root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout
            self.assertEqual(len(INQUIRY_PATHS), checkout_eol.count("w/crlf"))
            canonical_blobs = {
                path: subprocess.run(
                    ["git", "show", f"HEAD:{path}"],
                    cwd=clone_root,
                    check=True,
                    capture_output=True,
                ).stdout
                for path in INQUIRY_PATHS
            }

            with mock.patch(f"{__name__}.REPOSITORY_ROOT", clone_root):
                self.assertEqual(
                    [],
                    inquiry_chain_contract_errors(
                        FINAL_ACTIVE_PATHS,
                        canonical_blobs,
                    ),
                )
                protected_sql = clone_root / INQUIRY_PATHS[0]
                with protected_sql.open(
                    "a", encoding="utf-8", newline=""
                ) as migration:
                    migration.write("\r\n-- isolated worktree mutation\r\n")

                self.assertIn(
                    "inquiry migration working tree differs from index",
                    inquiry_chain_contract_errors(
                        FINAL_ACTIVE_PATHS,
                        canonical_blobs,
                    ),
                )
                subprocess.run(
                    ["git", "add", "--", INQUIRY_PATHS[0]],
                    cwd=clone_root,
                    check=True,
                )
                self.assertIn(
                    "inquiry migration index differs from HEAD",
                    inquiry_chain_contract_errors(
                        FINAL_ACTIVE_PATHS,
                        canonical_blobs,
                    ),
                )

    def test_inquiry_git_blobs_match_task_9_base(self) -> None:
        """Reject any inquiry SQL blob change after the approved Task 9 base."""
        task_9_base = "3baa4eb616e56c1e262c63fa9becfb5b5016c2e6"
        for path in INQUIRY_PATHS:
            with self.subTest(path=path):
                self.assertEqual(
                    canonical_git_blob_sha256(task_9_base, path),
                    canonical_git_blob_sha256("HEAD", path),
                )

    def test_inquiry_chain_guard_rejects_in_memory_mutations(self) -> None:
        """Prove rename, reorder, and content mutations cannot pass the guard."""
        canonical_paths = list(FINAL_ACTIVE_PATHS)
        canonical_sql = {
            path: canonical_git_blob_bytes("HEAD", path)
            for path in INQUIRY_PATHS
        }
        renamed_path = INQUIRY_PATHS[0].replace(
            "202608070001_", "202608070005_"
        )
        renamed_paths = canonical_paths.copy()
        renamed_paths[2] = renamed_path
        renamed_sql = canonical_sql.copy()
        renamed_sql[renamed_path] = renamed_sql.pop(INQUIRY_PATHS[0])
        reordered_paths = canonical_paths.copy()
        reordered_paths[2], reordered_paths[3] = (
            reordered_paths[3],
            reordered_paths[2],
        )
        modified_sql = canonical_sql.copy()
        modified_sql[INQUIRY_PATHS[0]] += b"\n-- in-memory mutation"

        mutations = (
            ("renamed", renamed_paths, renamed_sql, "active migration order"),
            (
                "reordered",
                reordered_paths,
                canonical_sql,
                "active migration order",
            ),
            (
                "modified",
                canonical_paths,
                modified_sql,
                f"SHA-256 mismatch: {INQUIRY_PATHS[0]}",
            ),
        )
        for mutation, active_paths, sql_by_path, expected_error in mutations:
            with self.subTest(mutation=mutation):
                self.assertIn(
                    expected_error,
                    inquiry_chain_contract_errors(active_paths, sql_by_path),
                )

    def test_migration_capabilities_require_complete_target_bound_ddl(
        self,
    ) -> None:
        """Reject truncated, partial, wrong-signature, or wrong-table DDL."""
        invalid_provisions = (
            (
                "truncated inquiries table",
                "create table public.inquiries (",
                "inquiries",
            ),
            (
                "partial inquiries table",
                "create table public.inquiries (id uuid);",
                "inquiries",
            ),
            (
                "truncated line message logs table",
                "create table public.line_message_logs (",
                "line_message_logs",
            ),
            (
                "truncated inquiry replies table",
                "create table public.inquiry_replies (",
                "inquiry_replies",
            ),
            (
                "truncated timestamp function",
                "create or replace function public.set_updated_at (",
                "set_updated_at",
            ),
            (
                "wrong timestamp function signature",
                "create or replace function public.set_updated_at(p_id uuid) "
                "returns trigger language sql as $$ select null; $$;",
                "set_updated_at",
            ),
            (
                "bodyless timestamp function",
                "create or replace function public.set_updated_at() "
                "returns trigger;",
                "set_updated_at",
            ),
            (
                "truncated finalizer",
                "create function public.finalize_inquiry_reply (",
                "finalize_inquiry_reply",
            ),
            (
                "wrong finalizer signature",
                "create function public.finalize_inquiry_reply(p_reply_id uuid) "
                "returns jsonb language sql as $$ select '{}'::jsonb; $$;",
                "finalize_inquiry_reply",
            ),
            (
                "bodyless finalizer",
                "create function public.finalize_inquiry_reply("
                "p_company_id text, p_inquiry_id uuid, p_reply_id uuid) "
                "returns jsonb;",
                "finalize_inquiry_reply",
            ),
            (
                "inquiries unique on wrong table",
                "alter table public.not_inquiries add constraint "
                "inquiries_company_id_id_key unique (company_id, id);",
                "inquiries_company_id_id_key",
            ),
        )

        for mutation, sql, capability in invalid_provisions:
            with self.subTest(mutation=mutation):
                self.assertNotIn(capability, migration_capabilities(sql))

    def test_migration_capabilities_ignore_semicolons_in_inert_sql(
        self,
    ) -> None:
        """Do not split strings, comments, or dollar bodies at inert semicolons."""
        inert_table = (
            "create table public.inquiries (id uuid, line_user_id text, "
            "message text, status text, created_at timestamptz, "
            "company_id text);"
        )
        cases = (
            (
                "single-quoted string",
                f"select 'inert; {inert_table}';",
            ),
            (
                "line comment",
                f"-- inert; {inert_table}\nselect 1;",
            ),
            (
                "block comment",
                f"/* inert; {inert_table} */\nselect 1;",
            ),
            (
                "dollar-quoted body",
                f"do $body$ begin perform 1; {inert_table} end; $body$;",
            ),
        )

        for mutation, sql in cases:
            with self.subTest(mutation=mutation):
                try:
                    capabilities = migration_capabilities(sql)
                except ValueError as error:
                    self.fail(f"valid inert SQL raised ValueError: {error}")
                self.assertNotIn("inquiries", capabilities)

    def test_migration_capabilities_reject_unterminated_inert_sql(self) -> None:
        """Do not accept an unterminated string, block comment, or dollar body."""
        incomplete = (
            "select 'unterminated;",
            "/* unterminated;",
            "do $body$ begin perform 1;",
        )
        for sql in incomplete:
            with self.subTest(sql=sql):
                with self.assertRaises(ValueError):
                    migration_capabilities(sql)

    def test_correlation_capability_requires_each_exact_target(self) -> None:
        """Reject correlation DDL when its column, FK, or index targets another table."""
        column = (
            "alter table public.line_message_logs "
            "add column if not exists inquiry_reply_id uuid;"
        )
        foreign_key = (
            "alter table public.line_message_logs add constraint "
            "line_message_logs_company_inquiry_reply_fkey foreign key "
            "(company_id, inquiry_reply_id) references "
            "public.inquiry_replies (company_id, id) on delete restrict;"
        )
        unique_index = (
            "create unique index if not exists "
            "uq_line_message_logs_company_inquiry_reply on "
            "public.line_message_logs (company_id, inquiry_reply_id) "
            "where inquiry_reply_id is not null;"
        )
        canonical = "\n".join((column, foreign_key, unique_index))
        self.assertIn(
            "inquiry_reply_correlation",
            migration_capabilities(canonical),
        )

        mutations = (
            (
                "column target",
                canonical.replace(
                    "alter table public.line_message_logs add column",
                    "alter table public.wrong add column",
                    1,
                ),
            ),
            (
                "foreign-key target",
                canonical.replace(
                    "alter table public.line_message_logs add constraint",
                    "alter table public.wrong add constraint",
                    1,
                ),
            ),
            (
                "index target",
                canonical.replace(
                    "on public.line_message_logs (company_id, inquiry_reply_id)",
                    "on public.wrong (company_id, inquiry_reply_id)",
                    1,
                ),
            ),
        )
        for mutation, sql in mutations:
            with self.subTest(mutation=mutation):
                self.assertNotIn(
                    "inquiry_reply_correlation",
                    migration_capabilities(sql),
                )

    def test_inquiry_replies_composite_unique_is_an_explicit_provision(
        self,
    ) -> None:
        """Reject a missing or wrong-table key required by migration 3's FK."""
        canonical = (REPOSITORY_ROOT / INQUIRY_PATHS[1]).read_text(
            encoding="utf-8"
        )
        unique_clause = (
            "  constraint inquiry_replies_company_id_id_key "
            "unique (company_id, id),\n"
        )
        self.assertIn(unique_clause, canonical)
        missing = canonical.replace(unique_clause, "", 1)
        misplaced = missing + (
            "\nalter table public.not_inquiry_replies add constraint "
            "inquiry_replies_company_id_id_key unique (company_id, id);\n"
        )

        self.assertIn(
            "inquiry_replies_company_id_id_key",
            migration_capabilities(canonical),
        )
        for mutation, sql in (("missing", missing), ("misplaced", misplaced)):
            with self.subTest(mutation=mutation):
                self.assertNotIn(
                    "inquiry_replies_company_id_id_key",
                    migration_capabilities(sql),
                )

    def test_inquiry_migration_dependencies_are_satisfied_in_order(self) -> None:
        """Reject any inquiry migration that precedes an object it requires."""
        sql_by_path = {
            path: (REPOSITORY_ROOT / path).read_text(encoding="utf-8")
            for path in FINAL_ACTIVE_PATHS
        }
        required_before = {
            INQUIRY_PATHS[0]: {
                "inquiries",
                "set_updated_at",
            },
            INQUIRY_PATHS[1]: {
                "inquiries_company_id_id_key",
                "set_updated_at",
                "uuid_generation",
            },
            INQUIRY_PATHS[2]: {
                "line_message_logs",
                "inquiry_replies",
                "inquiry_replies_company_id_id_key",
            },
            INQUIRY_PATHS[3]: {
                "inquiries",
                "line_message_logs",
                "inquiry_replies",
                "inquiry_reply_correlation",
            },
        }
        expected_provided = {
            BASELINE_PATH: {
                "inquiries",
                "line_message_logs",
                "set_updated_at",
                "uuid_generation",
            },
            INQUIRY_PATHS[0]: {"inquiries_company_id_id_key"},
            INQUIRY_PATHS[1]: {
                "inquiry_replies",
                "inquiry_replies_company_id_id_key",
            },
            INQUIRY_PATHS[2]: {"inquiry_reply_correlation"},
            INQUIRY_PATHS[3]: {"finalize_inquiry_reply"},
        }
        available: set[str] = set()

        for path in FINAL_ACTIVE_PATHS:
            with self.subTest(path=path, phase="requirements"):
                self.assertTrue(
                    required_before.get(path, set()) <= available,
                    f"missing prerequisite before {path}",
                )
            provided = migration_capabilities(sql_by_path[path])
            with self.subTest(path=path, phase="provisions"):
                self.assertTrue(
                    expected_provided.get(path, set()) <= provided,
                    f"missing provision in {path}",
                )
            available.update(provided)

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
