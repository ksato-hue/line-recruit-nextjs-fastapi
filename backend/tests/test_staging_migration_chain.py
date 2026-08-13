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


if __name__ == "__main__":
    unittest.main()
