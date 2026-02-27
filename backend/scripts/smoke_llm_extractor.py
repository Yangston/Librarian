"""Run a real LLM extraction call against a small in-memory conversation.

Usage (from repo root):
    python backend/scripts/smoke_llm_extractor.py

Usage (from backend/):
    python scripts/smoke_llm_extractor.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.models.message import Message
from app.services.extraction import get_default_extractor


def _demo_messages() -> list[Message]:
    base = datetime(2026, 2, 24, 14, 0, 0, tzinfo=timezone.utc)
    rows = [
        (
            1,
            "user",
            "Fed rate decision pressured semiconductor names, and NVDA fell 2.4% after the announcement.",
        ),
        (
            2,
            "assistant",
            "Meanwhile, Apple said Services revenue reached a record and management guided gross margin to the high end.",
        ),
        (
            3,
            "user",
            "Analyst Priya Shah linked cloud capex demand to MSFT and AMZN, but warned enterprise budgets remain uneven.",
        ),
    ]
    return [
        Message(
            id=message_id,
            conversation_id="smoke-llm",
            role=role,
            content=content,
            timestamp=base.replace(minute=base.minute + idx),
        )
        for idx, (message_id, role, content) in enumerate(rows)
    ]


def main() -> None:
    extractor = get_default_extractor()
    result = extractor.extract(_demo_messages())
    print(
        json.dumps(
            {
                "entities": [
                    {
                        "name": entity.name,
                        "type_label": entity.type_label,
                        "aliases": entity.aliases,
                        "confidence": entity.confidence,
                        "tags": entity.tags,
                        "source_message_ids": entity.source_message_ids,
                    }
                    for entity in result.entities
                ],
                "facts": [
                    {
                        "entity_name": fact.entity_name,
                        "field_label": fact.field_label,
                        "value_text": fact.value_text,
                        "confidence": fact.confidence,
                        "source_message_ids": fact.source_message_ids,
                        "snippet": fact.snippet,
                    }
                    for fact in result.facts
                ],
                "relations": [
                    {
                        "from_entity": relation.from_entity,
                        "relation_label": relation.relation_label,
                        "to_entity": relation.to_entity,
                        "qualifiers": relation.qualifiers,
                        "confidence": relation.confidence,
                        "source_message_ids": relation.source_message_ids,
                        "snippet": relation.snippet,
                    }
                    for relation in result.relations
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
