"""Service-level tests for Phase 3 workspace endpoints."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.extraction.extractor_interface import ExtractorInterface
from app.extraction.types import ExtractedEntity, ExtractedFact, ExtractedRelation, ExtractionResult
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
from app.models.schema_field import SchemaField
from app.models.schema_node import SchemaNode
from app.models.schema_proposal import SchemaProposal
from app.models.schema_relation import SchemaRelation
from app.schemas.message import MessageCreate
from app.services.extraction import run_extraction_for_conversation
from app.services.messages import create_messages
from app.services.workspace import (
    get_schema_overview,
    list_conversations,
    list_entities_catalog,
    list_recent_entities,
)


class _WorkspaceStubExtractor(ExtractorInterface):
    def extract(self, messages: list[Message]) -> ExtractionResult:
        message_ids = [message.id for message in messages]
        base_label = "market_context"
        if any("macro" in message.content.lower() for message in messages):
            base_label = "macro_context"
        return ExtractionResult(
            entities=[
                ExtractedEntity(
                    name="Apple Inc.",
                    type_label="Company",
                    aliases=["AAPL", "Apple"],
                    source_message_ids=message_ids,
                ),
                ExtractedEntity(
                    name="Global Supply Chain",
                    type_label="OperationalRisk",
                    aliases=["Supply Chain"],
                    source_message_ids=message_ids,
                ),
            ],
            facts=[
                ExtractedFact(
                    entity_name="Apple Inc.",
                    field_label=base_label,
                    value_text="elevated",
                    confidence=0.82,
                    source_message_ids=[message_ids[0]],
                ),
                ExtractedFact(
                    entity_name="Apple Inc.",
                    field_label="sentiment",
                    value_text="positive",
                    confidence=0.77,
                    source_message_ids=[message_ids[-1]],
                ),
            ],
            relations=[
                ExtractedRelation(
                    from_entity="Apple Inc.",
                    relation_label="impacted_by",
                    to_entity="Global Supply Chain",
                    qualifiers={},
                    confidence=0.8,
                    source_message_ids=[message_ids[-1]],
                )
            ],
        )


class Phase3WorkspaceServiceTests(unittest.TestCase):
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
        self._reset_tables()

    def tearDown(self) -> None:
        self.db.close()

    def test_workspace_queries_return_conversations_entities_and_schema(self) -> None:
        self._seed_conversation(
            "phase3-conv-a",
            "Apple earnings impacted by supply constraints.",
            datetime(2026, 2, 28, 10, 0, tzinfo=timezone.utc),
        )
        self._seed_conversation(
            "phase3-conv-b",
            "Macro backdrop changed while Apple tracked inventory closely.",
            datetime(2026, 2, 28, 11, 0, tzinfo=timezone.utc),
        )

        conversations = list_conversations(self.db, limit=10, offset=0)
        self.assertEqual(conversations.total, 2)
        self.assertEqual(len(conversations.items), 2)
        self.assertEqual(conversations.items[0].conversation_id, "phase3-conv-b")
        self.assertGreaterEqual(conversations.items[0].entity_count, 1)
        self.assertGreaterEqual(conversations.items[0].fact_count, 1)
        self.assertGreaterEqual(conversations.items[0].relation_count, 1)

        recent_entities = list_recent_entities(self.db, limit=10)
        self.assertGreaterEqual(len(recent_entities.items), 1)
        names = {item.canonical_name for item in recent_entities.items}
        self.assertIn("Apple Inc.", names)
        self.assertTrue(any(item.conversation_count >= 1 for item in recent_entities.items))

        entities_catalog = list_entities_catalog(
            self.db,
            limit=25,
            offset=0,
            sort="last_seen",
            order="desc",
            selected_fields=["sentiment", "macro_context"],
        )
        self.assertGreaterEqual(entities_catalog.total, 1)
        self.assertIn("sentiment", entities_catalog.selected_fields)
        apple_row = next(row for row in entities_catalog.items if row.canonical_name == "Apple Inc.")
        self.assertEqual(apple_row.dynamic_fields.get("sentiment"), "positive")

        schema_overview = get_schema_overview(self.db, per_section_limit=100, proposal_limit=20)
        self.assertGreaterEqual(len(schema_overview.nodes), 1)
        self.assertGreaterEqual(len(schema_overview.fields), 1)
        self.assertGreaterEqual(len(schema_overview.relations), 1)
        self.assertIn("sentiment", {field.label for field in schema_overview.fields})

    def test_workspace_queries_prune_stale_state_when_no_conversations_exist(self) -> None:
        self.db.add(
            Entity(
                conversation_id="orphan-conversation",
                name="Orphan Entity",
                display_name="Orphan Entity",
                canonical_name="Orphan Entity",
                type="Unknown",
                type_label="Unknown",
            )
        )
        self.db.add(PredicateRegistryEntry(kind="fact_predicate", predicate="orphan_metric"))
        self.db.add(SchemaNode(label="OrphanNode"))
        self.db.add(SchemaField(label="orphan_field"))
        self.db.add(SchemaRelation(label="orphan_relation"))
        self.db.add(
            SchemaProposal(
                proposal_type="field_merge",
                payload_json={"from": "a", "to": "b"},
                confidence=0.42,
                evidence_json={},
                status="proposed",
            )
        )
        self.db.commit()

        conversations = list_conversations(self.db, limit=10, offset=0)
        self.assertEqual(conversations.total, 0)
        self.assertEqual(len(conversations.items), 0)

        self.assertIsNone(self.db.scalar(select(Entity.id).limit(1)))
        self.assertIsNone(self.db.scalar(select(PredicateRegistryEntry.id).limit(1)))
        self.assertIsNone(self.db.scalar(select(SchemaNode.id).limit(1)))
        self.assertIsNone(self.db.scalar(select(SchemaField.id).limit(1)))
        self.assertIsNone(self.db.scalar(select(SchemaRelation.id).limit(1)))
        self.assertIsNone(self.db.scalar(select(SchemaProposal.id).limit(1)))

    def _seed_conversation(self, conversation_id: str, content: str, timestamp: datetime) -> None:
        create_messages(
            self.db,
            conversation_id,
            [
                MessageCreate(
                    role="user",
                    content=content,
                    timestamp=timestamp,
                )
            ],
        )
        run_extraction_for_conversation(self.db, conversation_id, extractor=_WorkspaceStubExtractor())

    def _reset_tables(self) -> None:
        self.db.execute(delete(SchemaProposal))
        self.db.execute(delete(SchemaRelation))
        self.db.execute(delete(SchemaField))
        self.db.execute(delete(SchemaNode))
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


if __name__ == "__main__":
    unittest.main()
