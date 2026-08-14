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


class StagingMigrationChainTests(unittest.TestCase):
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
        history = subprocess.run(
            ["git", "log", "--all", "--name-only", "--format=", "--", "supabase"],
            cwd=REPOSITORY_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
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
