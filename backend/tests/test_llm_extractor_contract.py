"""Unit tests for dynamic LLM extractor output contract behavior."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from app.extraction.llm_extractor import LLMExtractor
from app.models.message import Message


class _StubClient:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def extract_structured(self, messages, *, conversation_hints=None):  # noqa: ANN001
        _ = messages, conversation_hints
        return self.payload


class LLMExtractorContractTests(unittest.TestCase):
    def test_entity_with_type_label_is_not_duplicated_by_fact_reference(self) -> None:
        extractor = LLMExtractor(
            _StubClient(
                {
                    "entities": [
                        {
                            "name": "Apple",
                            "type_label": "company",
                            "aliases": ["AAPL"],
                            "tags": [],
                            "confidence": 0.82,
                            "source_message_ids": [1],
                        }
                    ],
                    "facts": [
                        {
                            "entity_name": "Apple",
                            "field_label": "services_revenue",
                            "value_text": "record",
                            "confidence": 0.74,
                            "source_message_ids": [1],
                            "snippet": None,
                        }
                    ],
                    "relations": [],
                }
            )
        )
        result = extractor.extract(
            [
                Message(
                    id=1,
                    conversation_id="llm-contract-test",
                    role="assistant",
                    content="Apple services revenue reached a record.",
                    timestamp=datetime(2026, 2, 27, 10, 0, tzinfo=timezone.utc),
                )
            ]
        )

        self.assertEqual(len(result.entities), 1)
        self.assertEqual(result.entities[0].name, "Apple")
        self.assertEqual(result.entities[0].type_label, "company")
        self.assertEqual(result.entities[0].confidence, 0.82)
        self.assertEqual(result.entities[0].source_message_ids, [1])


if __name__ == "__main__":
    unittest.main()
