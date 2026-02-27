"""Integration tests for semantic search and knowledge query services."""

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
from app.services.knowledge import get_conversation_summary, get_entity_graph, get_entity_timeline
from app.services.messages import create_messages
from app.services.search import semantic_search


class _SearchStubExtractor(ExtractorInterface):
    def extract(self, messages: list[Message]) -> ExtractionResult:
        message_ids = [message.id for message in messages]
        return ExtractionResult(
            entities=[
                ExtractedEntity(
                    name="Apple Inc.",
                    type_label="Company",
                    aliases=["AAPL", "Apple"],
                    source_message_ids=message_ids,
                ),
                ExtractedEntity(
                    name="NVIDIA",
                    type_label="Company",
                    aliases=["NVDA"],
                    source_message_ids=message_ids,
                ),
            ],
            facts=[
                ExtractedFact(
                    entity_name="Apple",
                    field_label="services_revenue",
                    value_text="record quarter",
                    confidence=0.88,
                    source_message_ids=[message_ids[0]],
                )
            ],
            relations=[
                ExtractedRelation(
                    from_entity="Apple Inc.",
                    relation_label="compared_with",
                    to_entity="NVIDIA",
                    qualifiers={},
                    confidence=0.7,
                    source_message_ids=[message_ids[-1]],
                )
            ],
        )


class SearchAndKnowledgeTests(unittest.TestCase):
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

    def test_semantic_search_and_knowledge_views(self) -> None:
        conversation_id = "phase2-search-test-001"
        create_messages(
            self.db,
            conversation_id,
            [
                MessageCreate(
                    role="user",
                    content="Apple said services revenue reached a record this quarter.",
                    timestamp=datetime(2026, 2, 27, 12, 0, tzinfo=timezone.utc),
                ),
                MessageCreate(
                    role="assistant",
                    content="Analysts compared AAPL and NVDA into next quarter.",
                    timestamp=datetime(2026, 2, 27, 12, 1, tzinfo=timezone.utc),
                ),
            ],
        )

        run_extraction_for_conversation(self.db, conversation_id, extractor=_SearchStubExtractor())

        entities = list(self.db.scalars(select(Entity).where(Entity.conversation_id == conversation_id)))
        facts = list(self.db.scalars(select(Fact).where(Fact.conversation_id == conversation_id)))
        self.assertTrue(all(entity.embedding for entity in entities))
        self.assertTrue(all(fact.embedding for fact in facts))

        search_result = semantic_search(self.db, query="Apple services revenue", conversation_id=conversation_id)
        self.assertGreaterEqual(len(search_result.entities), 1)
        self.assertGreaterEqual(len(search_result.facts), 1)
        self.assertEqual(search_result.entities[0].entity.canonical_name, "Apple Inc.")

        apple_entity = next(entity for entity in entities if entity.canonical_name == "Apple Inc.")
        graph = get_entity_graph(self.db, apple_entity.id)
        assert graph is not None
        self.assertGreaterEqual(len(graph.supporting_facts), 1)
        self.assertGreaterEqual(len(graph.outgoing_relations), 1)

        timeline = get_entity_timeline(self.db, apple_entity.id)
        assert timeline is not None
        self.assertGreaterEqual(len(timeline), 1)
        self.assertIsNotNone(timeline[0].timestamp)

        summary = get_conversation_summary(self.db, conversation_id)
        self.assertEqual(summary.conversation_id, conversation_id)
        self.assertGreaterEqual(len(summary.key_entities), 1)
        self.assertGreaterEqual(len(summary.key_facts), 1)
        self.assertGreaterEqual(len(summary.schema_changes_triggered.field_labels), 1)
        self.assertGreaterEqual(len(summary.relation_clusters), 1)

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
