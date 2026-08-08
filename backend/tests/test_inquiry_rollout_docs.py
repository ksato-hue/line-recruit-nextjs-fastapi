from pathlib import Path
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class InquiryRolloutDocumentationTests(unittest.TestCase):
    def assert_fragments_in_order(self, document: Path, fragments: tuple[str, ...]) -> None:
        content = document.read_text(encoding="utf-8")
        position = 0
        for fragment in fragments:
            position = content.find(fragment, position)
            self.assertNotEqual(
                -1,
                position,
                f"{document.relative_to(REPOSITORY_ROOT)} is missing or reorders {fragment!r}",
            )
            position += len(fragment)

    def test_schema_first_production_rollout_contract(self):
        """New code must never run against the pre-migration inquiry schema."""
        documents = (
            REPOSITORY_ROOT / "docs" / "INQUIRY_RESPONSE_RUNBOOK.md",
            REPOSITORY_ROOT / "docs" / "INQUIRY_RESPONSE_WORKFLOW.md",
            REPOSITORY_ROOT
            / "docs"
            / "superpowers"
            / "plans"
            / "2026-08-06-inquiry-response-workflow.md",
        )
        required_order = (
            "旧appを稼働したまま",
            "migration 1→4",
            "INQUIRY_REPLY_WORKFLOW_ENABLED=false",
            "一覧、詳細、PATCH",
            "固定`COMPANY_ID`",
        )

        for document in documents:
            with self.subTest(document=document.name):
                self.assert_fragments_in_order(document, required_order)


if __name__ == "__main__":
    unittest.main()
