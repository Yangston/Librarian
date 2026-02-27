"""Integration tests for expanded explainability payloads."""

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
from app.services.explain import (
    get_fact_explain,
    get_fact_explain_by_id,
    get_relation_explain,
    get_relation_explain_by_id,
)
from app.services.extraction import run_extraction_for_conversation
from app.services.messages import create_messages


class _ExplainStubExtractor(ExtractorInterface):
    def extract(self, messages: list[Message]) -> ExtractionResult:
        message_ids = [message.id for message in messages]
        return ExtractionResult(
            entities=[
                ExtractedEntity(
                    name="Apple Inc.",
                    type_label="Company",
                    aliases=["AAPL"],
                    source_message_ids=message_ids,
                ),
                ExtractedEntity(
                    name="Supply chain disruption",
                    type_label="OperationalRiskEvent",
                    source_message_ids=[message_ids[-1]],
                ),
            ],
            facts=[
                ExtractedFact(
                    entity_name="Apple Inc.",
                    field_label="margin_pressure",
                    value_text="elevated",
                    confidence=0.8,
                    source_message_ids=[message_ids[-1]],
                )
            ],
            relations=[
                ExtractedRelation(
                    from_entity="Apple Inc.",
                    relation_label="impacted_by",
                    to_entity="Supply chain disruption",
                    qualifiers={"snippet": "Supply chain disruption impacted Apple Inc."},
                    confidence=0.85,
                    source_message_ids=[message_ids[-1]],
                )
            ],
        )


class ExplainExpandedTests(unittest.TestCase):
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

    def test_fact_and_relation_explain_include_run_events_and_schema_info(self) -> None:
        conversation_id = "phase2-explain-test-001"
        create_messages(
            self.db,
            conversation_id,
            [
                MessageCreate(
                    role="user",
                    content="Apple Inc. faces supply chain disruption and margin pressure.",
                    timestamp=datetime(2026, 2, 27, 13, 0, tzinfo=timezone.utc),
                )
            ],
        )
        run_result = run_extraction_for_conversation(self.db, conversation_id, extractor=_ExplainStubExtractor())

        fact = self.db.scalar(select(Fact).where(Fact.conversation_id == conversation_id))
        relation = self.db.scalar(select(Relation).where(Relation.conversation_id == conversation_id))
        self.assertIsNotNone(fact)
        self.assertIsNotNone(relation)
        assert fact is not None
        assert relation is not None

        fact_scoped = get_fact_explain(self.db, conversation_id, fact.id)
        fact_global = get_fact_explain_by_id(self.db, fact.id)
        self.assertIsNotNone(fact_scoped)
        self.assertIsNotNone(fact_global)
        assert fact_scoped is not None
        self.assertEqual(fact_scoped.extractor_run_id, run_result.extractor_run_id)
        self.assertGreaterEqual(len(fact_scoped.resolution_events), 1)
        self.assertIn(fact_scoped.schema_canonicalization.status, {"canonical", "canonicalized"})

        relation_scoped = get_relation_explain(self.db, conversation_id, relation.id)
        relation_global = get_relation_explain_by_id(self.db, relation.id)
        self.assertIsNotNone(relation_scoped)
        self.assertIsNotNone(relation_global)
        assert relation_scoped is not None
        self.assertEqual(relation_scoped.extractor_run_id, run_result.extractor_run_id)
        self.assertGreaterEqual(len(relation_scoped.resolution_events), 1)
        self.assertIn(relation_scoped.schema_canonicalization.status, {"canonical", "canonicalized"})

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
