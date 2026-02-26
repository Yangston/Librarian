"""Tests for live chat testing service."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.extraction.extractor_interface import ExtractorInterface
from app.extraction.types import ExtractedEntity, ExtractedFact, ExtractionResult
from app.models.base import Base
from app.models.entity import Entity
from app.models.entity_merge_audit import EntityMergeAudit
from app.models.fact import Fact
from app.models.message import Message
from app.models.relation import Relation
from app.schemas.message import MessageCreate
from app.services.live_chat import run_live_chat_turn
from app.services.messages import create_messages


class _StubExtractor(ExtractorInterface):
    def extract(self, messages: list[Message]) -> ExtractionResult:
        user_ids = [m.id for m in messages if m.role == "user"]
        if not user_ids:
            return ExtractionResult()
        return ExtractionResult(
            entities=[
                ExtractedEntity(
                    name="AAPL",
                    entity_type="Company",
                    aliases=["Apple", "Apple Inc."],
                    source_message_ids=user_ids,
                ),
                ExtractedEntity(
                    name="Apple Inc.",
                    entity_type="Company",
                    aliases=["AAPL"],
                    source_message_ids=user_ids,
                ),
            ],
            facts=[
                ExtractedFact(
                    subject_name="Apple",
                    subject_type="Company",
                    predicate="discussed_in_chat",
                    object_value="live_test_turn",
                    confidence=0.8,
                    source_message_ids=user_ids,
                )
            ],
        )


class _StubChatClient:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls: list[list[dict[str, str]]] = []

    def complete(self, messages: list[dict[str, str]]) -> str:
        self.calls.append(messages)
        return self.reply


class LiveChatServiceTests(unittest.TestCase):
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
        self.db.execute(delete(Relation))
        self.db.execute(delete(Fact))
        self.db.execute(delete(EntityMergeAudit))
        self.db.execute(delete(Entity))
        self.db.execute(delete(Message))
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()

    def test_live_chat_turn_persists_messages_and_runs_extraction(self) -> None:
        conversation_id = "live-chat-test-001"
        create_messages(
            self.db,
            conversation_id,
            [
                MessageCreate(
                    role="user",
                    content="Earlier context about Apple.",
                    timestamp=datetime(2026, 2, 25, 10, 0, tzinfo=timezone.utc),
                )
            ],
        )

        chat_client = _StubChatClient("Apple Inc. could face margin pressure from supply chain constraints.")
        result = run_live_chat_turn(
            self.db,
            conversation_id,
            user_content="What is the risk to AAPL margins?",
            auto_extract=True,
            chat_client=chat_client,
            extractor=_StubExtractor(),
        )

        self.assertEqual(result.conversation_id, conversation_id)
        self.assertEqual(result.user_message.role, "user")
        self.assertEqual(result.assistant_message.role, "assistant")
        self.assertIsNotNone(result.extraction)
        self.assertGreaterEqual(result.extraction.entities_created, 2)
        self.assertEqual(len(chat_client.calls), 1)
        self.assertEqual(chat_client.calls[0][0]["role"], "system")
        self.assertTrue(any(msg["role"] == "user" for msg in chat_client.calls[0]))
        self.assertEqual(chat_client.calls[0][-1]["role"], "user")

        stored_messages = list(self.db.scalars(select(Message).where(Message.conversation_id == conversation_id)))
        self.assertEqual(len(stored_messages), 3)

        entities = list(self.db.scalars(select(Entity).where(Entity.conversation_id == conversation_id)))
        self.assertEqual(len(entities), 2)
        self.assertEqual(sum(1 for e in entities if e.merged_into_id is not None), 1)

    def test_live_chat_turn_can_skip_extraction(self) -> None:
        conversation_id = "live-chat-test-002"
        chat_client = _StubChatClient("Short answer.")

        result = run_live_chat_turn(
            self.db,
            conversation_id,
            user_content="Hello",
            auto_extract=False,
            chat_client=chat_client,
        )

        self.assertIsNone(result.extraction)
        self.assertEqual(len(chat_client.calls), 1)
        self.assertEqual(chat_client.calls[0][0]["role"], "system")


if __name__ == "__main__":
    unittest.main()
