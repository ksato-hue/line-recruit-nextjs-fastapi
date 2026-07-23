import importlib
import sys
from unittest.mock import patch


class NoNetworkSupabase:
    """Import-time Supabase placeholder that fails if a test uses it unexpectedly."""

    def table(self, name: str):
        raise AssertionError(f"Unexpected Supabase table access: {name}")

    def rpc(self, name: str, params: dict):
        raise AssertionError(f"Unexpected Supabase RPC access: {name}")


def load_backend_main():
    """Import backend/main.py without constructing a real Supabase client."""
    sys.modules.pop("main", None)
    with patch("supabase.create_client", return_value=NoNetworkSupabase()):
        return importlib.import_module("main")

