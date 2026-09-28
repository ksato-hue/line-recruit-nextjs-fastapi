import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "supabase/tests/fixtures/production-public-schema-contract.json"


class SchemaContractFixtureTests(unittest.TestCase):
    def setUp(self):
        self.contract = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_has_complete_machine_readable_sections(self):
        required = {"metadata", "tables", "columns", "constraints", "indexes",
                    "triggers", "functions", "removed_tenant_defaults",
                    "hardened_functions", "fail_closed_security"}
        self.assertTrue(required.issubset(self.contract))

    def test_inventory_keys_are_unique_and_fields_present(self):
        for section in ("tables", "columns", "constraints", "indexes", "triggers", "functions"):
            self.assertIn(section, self.contract)
            if section not in self.contract:
                return
            keys = [item["key"] for item in self.contract[section]]
            self.assertEqual(len(keys), len(set(keys)), section)
            self.assertTrue(all(keys))
        for item in self.contract["indexes"]:
            for field in ("schema", "table", "name", "normalized_definition"):
                self.assertTrue(item.get(field), f"index missing {field}: {item.get('key')}")
        for item in self.contract["triggers"]:
            for field in ("schema", "table", "name", "normalized_definition"):
                self.assertTrue(item.get(field), f"trigger missing {field}: {item.get('key')}")
        for item in self.contract["functions"]:
            for field in ("schema", "name", "identity_arguments", "signature"):
                self.assertIn(field, item)
            self.assertIsInstance(item["identity_arguments"], list)

    def test_exact_counts_and_intentional_differences(self):
        for section in ("tables", "columns", "constraints", "indexes", "triggers", "functions", "removed_tenant_defaults"):
            self.assertIn(section, self.contract)
        if "columns" not in self.contract:
            return
        self.assertEqual(len(self.contract["tables"]), 12)
        self.assertEqual(len(self.contract["columns"]), 98)
        self.assertEqual(len(self.contract["constraints"]), 19)
        self.assertEqual(len(self.contract["indexes"]), 43)
        self.assertEqual(len(self.contract["triggers"]), 7)
        self.assertEqual(len(self.contract["functions"]), 2)
        self.assertEqual(len(self.contract["removed_tenant_defaults"]), 6)

    def test_difference_references_and_sensitive_data(self):
        self.assertIn("columns", self.contract)
        self.assertIn("removed_tenant_defaults", self.contract)
        if "columns" not in self.contract or "removed_tenant_defaults" not in self.contract:
            return
        column_keys = {item["key"] for item in self.contract["columns"]}
        self.assertTrue(all(item["object_key"] in column_keys
                            for item in self.contract["removed_tenant_defaults"]))
        text = FIXTURE.read_text(encoding="utf-8").lower()
        for marker in ("postgresql://", "access_token", "service_role_key", "phone_number"):
            self.assertNotIn(marker, text)


if __name__ == "__main__":
    unittest.main()
