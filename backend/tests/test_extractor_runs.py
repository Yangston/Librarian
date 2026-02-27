"""Integration tests for extractor run logging."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.extraction.extractor_interface import ExtractorInterface
from app.extraction.types import ExtractedEntity, ExtractionResult
from app.models.base import Base
from app.models.conversation_entity_link import ConversationEntityLink
from app.models.entity import Entity
from app.models.entity_merge_audit import EntityMergeAudit
from app.models.extractor_run import ExtractorRun
from app.models.fact import Fact
from app.models.message import Message
from app.models.predicate_registry_entry import PredicateRegistryEntry
from app.models.resolution_event import ResolutionEvent
from app.models.relation import Relation
from app.schemas.message import MessageCreate
from app.services.extraction import run_extraction_for_conversation
from app.services.messages import create_messages


class _MetadataStubExtractor(ExtractorInterface):
    model_name = "stub-model-v1"
    prompt_version = "prompt.test.v1"

    def __init__(self) -> None:
        self.last_raw_output = {
            "entities": [
                {
                    "name": "Acme",
                    "type_label": "Company",
                    "aliases": [],
                    "tags": [],
                    "confidence": 0.91,
                    "source_message_ids": [1],
                }
            ],
            "facts": [],
            "relations": [],
        }
        self.last_validated_output = {
            "entities": [
                {
                    "name": "Acme",
                    "type_label": "Company",
                    "aliases": [],
                    "tags": [],
                    "confidence": 0.91,
                    "source_message_ids": [1],
                }
            ],
            "facts": [],
            "relations": [],
        }

    def extract(self, messages: list[Message]) -> ExtractionResult:
        source_ids = [message.id for message in messages]
        self.last_raw_output["entities"][0]["source_message_ids"] = source_ids
        self.last_validated_output["entities"][0]["source_message_ids"] = source_ids
        return ExtractionResult(
            entities=[
                ExtractedEntity(
                    name="Acme",
                    type_label="Company",
                    source_message_ids=source_ids,
                )
            ]
        )


class _MinimalStubExtractor(ExtractorInterface):
    def extract(self, messages: list[Message]) -> ExtractionResult:
        source_ids = [message.id for message in messages]
        return ExtractionResult(
            entities=[
                ExtractedEntity(
                    name="Umbrella Corp",
                    type_label="Company",
                    source_message_ids=source_ids,
                )
            ]
        )


class ExtractorRunLoggingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            future=True,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.SessionLocal = sessionmaker(bind=cls.engine, autoflush=False, autocommit=False, future=True)
        Base.metadata.create_all(cls.engine)

    @classmethod
    def tearDownClass(cls) -> None:
        Base.metadata.drop_all(cls.engine)
        cls.engine.dispose()

    def setUp(self) -> None:
        self.db: Session = self.SessionLocal()
        self.db.execute(delete(ConversationEntityLink))
        self.db.execute(delete(Relation))
        self.db.execute(delete(Fact))
        self.db.execute(delete(PredicateRegistryEntry))
        self.db.execute(delete(ExtractorRun))
        self.db.execute(delete(ResolutionEvent))
        self.db.execute(delete(EntityMergeAudit))
        self.db.execute(delete(Entity))
        self.db.execute(delete(Message))
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()

    def test_logs_model_prompt_and_payloads_from_extractor_metadata(self) -> None:
        conversation_id = "extractor-runs-test-001"
        created_messages = create_messages(
            self.db,
            conversation_id,
            [
                MessageCreate(
                    role="user",
                    content="Track Acme updates.",
                    timestamp=datetime(2026, 2, 27, 9, 0, tzinfo=timezone.utc),
                )
            ],
        )
        extractor = _MetadataStubExtractor()
        result = run_extraction_for_conversation(self.db, conversation_id, extractor=extractor)

        self.assertIsNotNone(result.extractor_run_id)
        stored = self.db.scalar(select(ExtractorRun).where(ExtractorRun.id == result.extractor_run_id))
        self.assertIsNotNone(stored)
        assert stored is not None
        self.assertEqual(stored.conversation_id, conversation_id)
        self.assertEqual(stored.model_name, "stub-model-v1")
        self.assertEqual(stored.prompt_version, "prompt.test.v1")
        self.assertEqual(stored.input_message_ids_json, [created_messages[0].id])
        self.assertEqual(stored.raw_output_json, extractor.last_raw_output)
        self.assertEqual(stored.validated_output_json, extractor.last_validated_output)

    def test_falls_back_to_serialized_result_when_extractor_has_no_payload_metadata(self) -> None:
        conversation_id = "extractor-runs-test-002"
        created_messages = create_messages(
            self.db,
            conversation_id,
            [
                MessageCreate(
                    role="user",
                    content="Track Umbrella Corp updates.",
                    timestamp=datetime(2026, 2, 27, 9, 5, tzinfo=timezone.utc),
                )
            ],
        )
        result = run_extraction_for_conversation(self.db, conversation_id, extractor=_MinimalStubExtractor())

        stored = self.db.scalar(select(ExtractorRun).where(ExtractorRun.id == result.extractor_run_id))
        self.assertIsNotNone(stored)
        assert stored is not None
        self.assertEqual(stored.model_name, "_MinimalStubExtractor")
        self.assertEqual(stored.prompt_version, "unknown")
        self.assertEqual(stored.input_message_ids_json, [created_messages[0].id])
        self.assertEqual(stored.raw_output_json, stored.validated_output_json)
        self.assertEqual(len(stored.validated_output_json.get("entities", [])), 1)
        self.assertEqual(stored.validated_output_json["entities"][0]["name"], "Umbrella Corp")


if __name__ == "__main__":
    unittest.main()
