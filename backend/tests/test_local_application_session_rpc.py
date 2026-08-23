from __future__ import annotations

import json
import os
import subprocess
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import requests


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PROJECT_REF_PATHS = (
    REPOSITORY_ROOT / ".supabase" / "project-ref",
    REPOSITORY_ROOT / "supabase" / ".temp" / "project-ref",
)
RUN_LOCAL_DB_TESTS = os.getenv("RUN_LOCAL_DB_TESTS") == "1"


@unittest.skipUnless(
    RUN_LOCAL_DB_TESTS,
    "set RUN_LOCAL_DB_TESTS=1 after the Task 10 local Supabase stack exists",
)
class LocalApplicationSessionRpcTests(unittest.TestCase):
    api_url: str
    server_key: str
    company_id: str
    line_user_id: str
    session_id: str

    @classmethod
    def setUpClass(cls) -> None:
        for project_ref_path in PROJECT_REF_PATHS:
            if (
                project_ref_path.is_file()
                and project_ref_path.read_text(encoding="utf-8").strip()
            ):
                raise RuntimeError(
                    f"local RPC tests refuse linked project ref: {project_ref_path}"
                )

        status_process = subprocess.run(
            ["supabase", "status", "-o", "json"],
            cwd=REPOSITORY_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        status = json.loads(status_process.stdout)
        cls.api_url = status.get("API_URL") or status.get("api_url") or ""
        cls.server_key = (
            status.get("SERVICE_ROLE_KEY")
            or status.get("SECRET_KEY")
            or status.get("service_role_key")
            or status.get("secret_key")
            or ""
        )
        parsed_api_url = urlparse(cls.api_url)
        if parsed_api_url.scheme != "http" or parsed_api_url.hostname not in {
            "127.0.0.1",
            "localhost",
            "::1",
        }:
            raise RuntimeError("local RPC tests require a loopback HTTP API URL")
        if not cls.server_key:
            raise RuntimeError("local Supabase status did not provide a server key")

        test_suffix = uuid4().hex
        cls.company_id = f"task7-company-{test_suffix}"
        cls.line_user_id = f"task7-user-{test_suffix}"
        cls.session_id = str(uuid4())

    @classmethod
    def _headers(cls) -> dict[str, str]:
        return {
            "apikey": cls.server_key,
            "Authorization": f"Bearer {cls.server_key}",
            "Content-Type": "application/json",
        }

    @classmethod
    def _request(cls, method: str, path: str, **kwargs) -> requests.Response:
        headers = kwargs.pop("headers", cls._headers())
        response = requests.request(
            method,
            f"{cls.api_url}/rest/v1/{path}",
            headers=headers,
            timeout=10,
            **kwargs,
        )
        response.raise_for_status()
        return response

    def test_concurrent_completion_is_idempotent_and_creates_one_applicant(self) -> None:
        self._request(
            "POST",
            "application_sessions",
            headers=self._headers() | {"Prefer": "return=minimal"},
            json={
                "id": self.session_id,
                "company_id": self.company_id,
                "line_user_id": self.line_user_id,
                "status": "active",
            },
        )
        rpc_payload = {
            "p_session_id": self.session_id,
            "p_company_id": self.company_id,
            "p_line_user_id": self.line_user_id,
            "p_name": "Task 7 synthetic applicant",
            "p_phone": None,
            "p_job": "Synthetic role",
            "p_motivation": "Concurrency verification",
            "p_applicant_status": "synthetic-new",
            "p_event_id": f"task7-event-{uuid4().hex}",
        }

        def complete() -> dict[str, object]:
            return self._request(
                "POST",
                "rpc/complete_application_session",
                json=rpc_payload,
            ).json()

        try:
            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(lambda _index: complete(), range(2)))

            self.assertEqual(
                [(False, True), (True, False)],
                sorted(
                    (
                        result["created"],
                        result["already_completed"],
                    )
                    for result in results
                ),
            )
            created_result = next(result for result in results if result["created"])
            self.assertEqual(
                {"created", "already_completed", "applicant"},
                set(created_result),
            )
            replay_result = next(
                result for result in results if result["already_completed"]
            )
            self.assertEqual(
                {"created", "already_completed"},
                set(replay_result),
            )

            applicants = self._request(
                "GET",
                "applicants",
                params={
                    "select": "id",
                    "application_session_id": f"eq.{self.session_id}",
                    "company_id": f"eq.{self.company_id}",
                    "line_user_id": f"eq.{self.line_user_id}",
                },
            ).json()
            self.assertEqual(1, len(applicants))
        finally:
            self._request(
                "DELETE",
                "applicants",
                params={
                    "application_session_id": f"eq.{self.session_id}",
                    "company_id": f"eq.{self.company_id}",
                    "line_user_id": f"eq.{self.line_user_id}",
                },
            )
            self._request(
                "DELETE",
                "application_sessions",
                params={
                    "id": f"eq.{self.session_id}",
                    "company_id": f"eq.{self.company_id}",
                    "line_user_id": f"eq.{self.line_user_id}",
                },
            )


if __name__ == "__main__":
    unittest.main()
