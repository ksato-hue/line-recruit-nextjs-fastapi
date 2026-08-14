import copy
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tests.support import load_backend_main


main = load_backend_main()


class EmptyQuery:
    def select(self, _columns: str):
        return self

    def eq(self, _column: str, _value: object):
        return self

    def limit(self, _value: int):
        return self

    def execute(self):
        return SimpleNamespace(data=[])


class CompletionRpc:
    """Test-only result model from the approved fixed interface, not SQL evidence."""

    CONTRACT_SOURCE = (
        "docs/superpowers/plans/"
        "2026-08-11-staging-supabase-baseline-implementation.md "
        "(Fixed Existing Interfaces)"
    )

    def __init__(self, database, name: str, params: dict):
        self.database = database
        self.name = name
        self.params = copy.deepcopy(params)

    def execute(self):
        self.database.rpc_calls.append((self.name, self.params))
        session_id = self.params["p_session_id"]
        if session_id in self.database.completed_sessions:
            result = {"created": False, "already_completed": True}
        else:
            self.database.completed_sessions.add(session_id)
            applicant = {
                "id": f"applicant-{len(self.database.applicants) + 1}",
                "company_id": self.params["p_company_id"],
                "application_session_id": session_id,
                "line_user_id": self.params["p_line_user_id"],
            }
            self.database.applicants.append(applicant)
            result = {
                "created": True,
                "already_completed": False,
                "applicant": applicant,
            }
        self.database.rpc_results.append(copy.deepcopy(result))
        return SimpleNamespace(data=result)


class CompletionSupabase:
    def __init__(self):
        self.applicants: list[dict] = []
        self.completed_sessions: set[str] = set()
        self.rpc_calls: list[tuple[str, dict]] = []
        self.rpc_results: list[dict] = []

    def rpc(self, name: str, params: dict):
        return CompletionRpc(self, name, params)

    def table(self, name: str):
        if name != "application_sessions":
            raise AssertionError(f"Unexpected table access: {name}")
        return EmptyQuery()


class ApplicationSessionRpcContractTests(unittest.TestCase):
    def setUp(self):
        self.database = CompletionSupabase()
        self.user_id = "line-user"
        self.session_id = "session-1"
        self.patches = [
            patch.object(main, "supabase", self.database),
            patch.object(main, "COMPANY_ID", "tenant-a"),
            patch.object(main, "user_states", {}),
            patch.object(main, "applicants", {}),
            patch.object(main, "application_tree_sessions", {}),
            patch.object(main, "get_app_settings", return_value={}),
            patch.object(main, "get_status_name", return_value="new-status"),
        ]
        for active_patch in self.patches:
            active_patch.start()

    def tearDown(self):
        for active_patch in reversed(self.patches):
            active_patch.stop()

    def _seed_confirmation(self):
        main.user_states[self.user_id] = "confirming"
        main.applicants[self.user_id] = {
            "name": "Applicant",
            "phone": "090-0000-0000",
            "job": "Engineer",
            "motivation": "Build products",
        }
        main.application_tree_sessions[self.user_id] = {"id": self.session_id}

    def test_completion_rpc_contract_model_cites_approved_fixed_interface(self):
        self.assertEqual(
            (
                "docs/superpowers/plans/"
                "2026-08-11-staging-supabase-baseline-implementation.md "
                "(Fixed Existing Interfaces)"
            ),
            CompletionRpc.CONTRACT_SOURCE,
        )

    def test_completion_rpc_preserves_first_completion_and_replay_contract(self):
        self._seed_confirmation()
        main.handle_message(self.user_id, "確認", "event-1")

        first_name, first_params = self.database.rpc_calls[0]
        self.assertEqual("complete_application_session", first_name)
        self.assertEqual(
            {
                "p_session_id",
                "p_company_id",
                "p_line_user_id",
                "p_name",
                "p_phone",
                "p_job",
                "p_motivation",
                "p_applicant_status",
                "p_event_id",
            },
            set(first_params),
        )
        self.assertEqual(self.session_id, first_params["p_session_id"])
        self.assertEqual(main.COMPANY_ID, first_params["p_company_id"])
        self.assertEqual(self.user_id, first_params["p_line_user_id"])
        self.assertEqual("event-1", first_params["p_event_id"])
        self.assertEqual(
            {"created", "already_completed", "applicant"},
            set(self.database.rpc_results[0]),
        )
        self.assertTrue(self.database.rpc_results[0]["created"])
        self.assertFalse(self.database.rpc_results[0]["already_completed"])
        self.assertEqual(main.COMPANY_ID, self.database.applicants[0]["company_id"])

        self._seed_confirmation()
        main.handle_message(self.user_id, "確認", "event-2")

        replay_name, replay_params = self.database.rpc_calls[1]
        self.assertEqual("complete_application_session", replay_name)
        self.assertEqual(first_params | {"p_event_id": "event-2"}, replay_params)
        self.assertEqual(1, len(self.database.applicants))
        self.assertEqual(
            {"created", "already_completed"},
            set(self.database.rpc_results[1]),
        )
        self.assertFalse(self.database.rpc_results[1]["created"])
        self.assertTrue(self.database.rpc_results[1]["already_completed"])


if __name__ == "__main__":
    unittest.main()
