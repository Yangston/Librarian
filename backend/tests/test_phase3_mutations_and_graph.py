"""Service-level tests for graph payloads and editable/deletable records."""

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
from app.schemas.mutations import (
    EntityUpdateRequest,
    FactUpdateRequest,
    MessageUpdateRequest,
    RelationUpdateRequest,
    SchemaFieldUpdateRequest,
    SchemaNodeUpdateRequest,
    SchemaRelationUpdateRequest,
)
from app.services.extraction import run_extraction_for_conversation
from app.services.knowledge import get_conversation_graph
from app.services.messages import create_messages
from app.services.mutations import (
    delete_entity,
    delete_fact,
    delete_message,
    delete_relation,
    delete_schema_field,
    delete_schema_node,
    delete_schema_relation,
    update_entity,
    update_fact,
    update_message,
    update_relation,
    update_schema_field,
    update_schema_node,
    update_schema_relation,
)


class _MutationsExtractor(ExtractorInterface):
    def extract(self, messages: list[Message]) -> ExtractionResult:
        message_ids = [message.id for message in messages]
        return ExtractionResult(
            entities=[
                ExtractedEntity(
                    name="Apple Inc.",
                    type_label="Company",
                    aliases=["Apple", "AAPL"],
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
                    entity_name="Apple Inc.",
                    field_label="sentiment",
                    value_text="positive",
                    confidence=0.75,
                    source_message_ids=message_ids,
                )
            ],
            relations=[
                ExtractedRelation(
                    from_entity="Apple Inc.",
                    relation_label="compared_with",
                    to_entity="NVIDIA",
                    qualifiers={"window": "q4"},
                    confidence=0.71,
                    source_message_ids=message_ids,
                )
            ],
        )


class Phase3MutationsAndGraphTests(unittest.TestCase):
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

    def test_conversation_graph_and_crud_mutations(self) -> None:
        conversation_id = "phase3-mutations-001"
        create_messages(
            self.db,
            conversation_id,
            [
                MessageCreate(
                    role="user",
                    content="Compare Apple and NVIDIA in the latest earnings context.",
                    timestamp=datetime(2026, 2, 28, 9, 0, tzinfo=timezone.utc),
                )
            ],
        )
        run_extraction_for_conversation(self.db, conversation_id, extractor=_MutationsExtractor())

        graph = get_conversation_graph(self.db, conversation_id)
        self.assertEqual(graph.conversation_id, conversation_id)
        self.assertGreaterEqual(len(graph.entities), 2)
        self.assertGreaterEqual(len(graph.relations), 1)

        message = self.db.scalar(select(Message).where(Message.conversation_id == conversation_id))
        assert message is not None
        updated_message = update_message(
            self.db,
            message.id,
            MessageUpdateRequest(content="Updated user prompt for auditing."),
        )
        self.assertIsNotNone(updated_message)
        self.assertEqual(updated_message.content, "Updated user prompt for auditing.")

        apple = self.db.scalar(
            select(Entity).where(Entity.conversation_id == conversation_id, Entity.canonical_name == "Apple Inc.")
        )
        assert apple is not None
        updated_entity = update_entity(
            self.db,
            apple.id,
            EntityUpdateRequest(canonical_name="Apple", type_label="Issuer"),
        )
        self.assertIsNotNone(updated_entity)
        assert updated_entity is not None
        self.assertEqual(updated_entity.canonical_name, "Apple")
        self.assertEqual(updated_entity.type_label, "Issuer")

        fact = self.db.scalar(select(Fact).where(Fact.conversation_id == conversation_id))
        assert fact is not None
        updated_fact = update_fact(
            self.db,
            fact.id,
            FactUpdateRequest(object_value="neutral", confidence=0.63),
        )
        self.assertIsNotNone(updated_fact)
        assert updated_fact is not None
        self.assertEqual(updated_fact.object_value, "neutral")
        self.assertAlmostEqual(updated_fact.confidence, 0.63)

        relation = self.db.scalar(select(Relation).where(Relation.conversation_id == conversation_id))
        assert relation is not None
        updated_relation = update_relation(
            self.db,
            relation.id,
            RelationUpdateRequest(relation_type="benchmarked_against", confidence=0.66),
        )
        self.assertIsNotNone(updated_relation)
        assert updated_relation is not None
        self.assertEqual(updated_relation.relation_type, "benchmarked_against")
        self.assertAlmostEqual(updated_relation.confidence, 0.66)

        self.assertTrue(delete_relation(self.db, relation.id))
        self.assertIsNone(self.db.scalar(select(Relation).where(Relation.id == relation.id)))
        self.assertTrue(delete_fact(self.db, fact.id))
        self.assertIsNone(self.db.scalar(select(Fact).where(Fact.id == fact.id)))
        self.assertTrue(delete_message(self.db, message.id))
        self.assertIsNone(self.db.scalar(select(Message).where(Message.id == message.id)))
        self.assertTrue(delete_entity(self.db, apple.id))
        self.assertIsNone(self.db.scalar(select(Entity).where(Entity.id == apple.id)))

        schema_node = self.db.scalar(select(SchemaNode).where(SchemaNode.label == "Company"))
        assert schema_node is not None
        updated_schema_node = update_schema_node(
            self.db,
            schema_node.id,
            SchemaNodeUpdateRequest(description="Updated description"),
        )
        self.assertIsNotNone(updated_schema_node)
        assert updated_schema_node is not None
        self.assertEqual(updated_schema_node.description, "Updated description")

        schema_field = self.db.scalar(select(SchemaField).where(SchemaField.label == "sentiment"))
        assert schema_field is not None
        updated_schema_field = update_schema_field(
            self.db,
            schema_field.id,
            SchemaFieldUpdateRequest(description="Updated field description"),
        )
        self.assertIsNotNone(updated_schema_field)
        assert updated_schema_field is not None
        self.assertEqual(updated_schema_field.description, "Updated field description")

        schema_relation = self.db.scalar(select(SchemaRelation).where(SchemaRelation.label == "compared_with"))
        assert schema_relation is not None
        updated_schema_relation = update_schema_relation(
            self.db,
            schema_relation.id,
            SchemaRelationUpdateRequest(description="Updated relation description"),
        )
        self.assertIsNotNone(updated_schema_relation)
        assert updated_schema_relation is not None
        self.assertEqual(updated_schema_relation.description, "Updated relation description")

        self.assertTrue(delete_schema_relation(self.db, schema_relation.id))
        self.assertTrue(delete_schema_field(self.db, schema_field.id))
        self.assertTrue(delete_schema_node(self.db, schema_node.id))

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
