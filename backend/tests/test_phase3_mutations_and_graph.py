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
    delete_conversation,
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


class _SecondaryMutationsExtractor(ExtractorInterface):
    def extract(self, messages: list[Message]) -> ExtractionResult:
        message_ids = [message.id for message in messages]
        return ExtractionResult(
            entities=[
                ExtractedEntity(
                    name="Tesla Inc.",
                    type_label="Company",
                    aliases=["Tesla", "TSLA"],
                    source_message_ids=message_ids,
                ),
                ExtractedEntity(
                    name="Rivian",
                    type_label="Company",
                    aliases=["RIVN"],
                    source_message_ids=message_ids,
                ),
            ],
            facts=[
                ExtractedFact(
                    entity_name="Tesla Inc.",
                    field_label="market_view",
                    value_text="mixed",
                    confidence=0.68,
                    source_message_ids=message_ids,
                )
            ],
            relations=[
                ExtractedRelation(
                    from_entity="Tesla Inc.",
                    relation_label="benchmarked_against",
                    to_entity="Rivian",
                    qualifiers={"window": "q1"},
                    confidence=0.64,
                    source_message_ids=message_ids,
                )
            ],
        )


class _MessageScopedMutationsExtractor(ExtractorInterface):
    def extract(self, messages: list[Message]) -> ExtractionResult:
        if len(messages) < 2:
            message_ids = [message.id for message in messages]
            return ExtractionResult(
                entities=[
                    ExtractedEntity(
                        name="Carryover Corp.",
                        type_label="Company",
                        aliases=["Carryover"],
                        source_message_ids=message_ids,
                    )
                ],
                facts=[
                    ExtractedFact(
                        entity_name="Carryover Corp.",
                        field_label="carryover_flag",
                        value_text="true",
                        confidence=0.7,
                        source_message_ids=message_ids,
                    )
                ],
                relations=[],
            )

        first_id = messages[0].id
        second_id = messages[1].id
        return ExtractionResult(
            entities=[
                ExtractedEntity(
                    name="First Only Co.",
                    type_label="Company",
                    aliases=["FirstCo"],
                    source_message_ids=[first_id],
                ),
                ExtractedEntity(
                    name="Second Only Co.",
                    type_label="Company",
                    aliases=["SecondCo"],
                    source_message_ids=[second_id],
                ),
            ],
            facts=[
                ExtractedFact(
                    entity_name="First Only Co.",
                    field_label="signal_one",
                    value_text="from-first",
                    confidence=0.7,
                    source_message_ids=[first_id],
                ),
                ExtractedFact(
                    entity_name="Second Only Co.",
                    field_label="signal_two",
                    value_text="from-second",
                    confidence=0.8,
                    source_message_ids=[second_id],
                ),
            ],
            relations=[
                ExtractedRelation(
                    from_entity="First Only Co.",
                    relation_label="paired_with",
                    to_entity="Second Only Co.",
                    qualifiers={},
                    confidence=0.6,
                    source_message_ids=[first_id],
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
        self.assertTrue(delete_message(self.db, message.id))
        self.assertIsNone(self.db.scalar(select(Message).where(Message.id == message.id)))

    def test_delete_conversation_removes_scoped_records(self) -> None:
        first_conversation_id = "phase3-delete-001"
        second_conversation_id = "phase3-delete-002"

        create_messages(
            self.db,
            first_conversation_id,
            [
                MessageCreate(
                    role="user",
                    content="Track Apple and NVIDIA positioning.",
                    timestamp=datetime(2026, 2, 28, 10, 0, tzinfo=timezone.utc),
                )
            ],
        )
        create_messages(
            self.db,
            second_conversation_id,
            [
                MessageCreate(
                    role="user",
                    content="Track Tesla and Rivian positioning.",
                    timestamp=datetime(2026, 2, 28, 10, 5, tzinfo=timezone.utc),
                )
            ],
        )
        run_extraction_for_conversation(self.db, first_conversation_id, extractor=_MutationsExtractor())
        run_extraction_for_conversation(
            self.db, second_conversation_id, extractor=_SecondaryMutationsExtractor()
        )

        self.assertTrue(delete_conversation(self.db, first_conversation_id))
        self.assertFalse(delete_conversation(self.db, "missing-conversation"))

        self.assertEqual(
            0,
            len(
                list(
                    self.db.scalars(
                        select(Message).where(Message.conversation_id == first_conversation_id)
                    ).all()
                )
            ),
        )
        self.assertEqual(
            0,
            len(list(self.db.scalars(select(Fact).where(Fact.conversation_id == first_conversation_id)).all())),
        )
        self.assertEqual(
            0,
            len(
                list(
                    self.db.scalars(
                        select(Relation).where(Relation.conversation_id == first_conversation_id)
                    ).all()
                )
            ),
        )
        self.assertEqual(
            0,
            len(
                list(
                    self.db.scalars(
                        select(ConversationEntityLink).where(
                            ConversationEntityLink.conversation_id == first_conversation_id
                        )
                    ).all()
                )
            ),
        )
        self.assertEqual(
            0,
            len(
                list(
                    self.db.scalars(
                        select(ResolutionEvent).where(
                            ResolutionEvent.conversation_id == first_conversation_id
                        )
                    ).all()
                )
            ),
        )
        self.assertEqual(
            0,
            len(
                list(
                    self.db.scalars(
                        select(EntityMergeAudit).where(
                            EntityMergeAudit.conversation_id == first_conversation_id
                        )
                    ).all()
                )
            ),
        )
        self.assertEqual(
            0,
            len(
                list(
                    self.db.scalars(
                        select(ExtractorRun).where(ExtractorRun.conversation_id == first_conversation_id)
                    ).all()
                )
            ),
        )
        self.assertEqual(
            0,
            len(
                list(
                    self.db.scalars(select(Entity).where(Entity.conversation_id == first_conversation_id)).all()
                )
            ),
        )

        self.assertGreater(
            len(
                list(
                    self.db.scalars(
                        select(Message).where(Message.conversation_id == second_conversation_id)
                    ).all()
                )
            ),
            0,
        )
        self.assertGreater(
            len(
                list(
                    self.db.scalars(
                        select(Fact).where(Fact.conversation_id == second_conversation_id)
                    ).all()
                )
            ),
            0,
        )
        self.assertGreater(
            len(
                list(
                    self.db.scalars(
                        select(Relation).where(Relation.conversation_id == second_conversation_id)
                    ).all()
                )
            ),
            0,
        )
        self.assertEqual(0, len(list(self.db.scalars(select(SchemaField).where(SchemaField.label == "sentiment")).all())))
        self.assertEqual(1, len(list(self.db.scalars(select(SchemaField).where(SchemaField.label == "market_view")).all())))
        self.assertEqual(
            0,
            len(
                list(
                    self.db.scalars(
                        select(SchemaRelation).where(SchemaRelation.label == "compared_with")
                    ).all()
                )
            ),
        )
        self.assertEqual(
            1,
            len(
                list(
                    self.db.scalars(
                        select(SchemaRelation).where(SchemaRelation.label == "benchmarked_against")
                    ).all()
                )
            ),
        )

    def test_delete_last_conversation_clears_global_workspace_state(self) -> None:
        conversation_id = "phase3-delete-last-001"
        create_messages(
            self.db,
            conversation_id,
            [
                MessageCreate(
                    role="user",
                    content="Compare Apple and NVIDIA in a final pass.",
                    timestamp=datetime(2026, 2, 28, 11, 0, tzinfo=timezone.utc),
                )
            ],
        )
        run_extraction_for_conversation(self.db, conversation_id, extractor=_MutationsExtractor())

        self.assertTrue(delete_conversation(self.db, conversation_id))

        self.assertEqual(0, len(list(self.db.scalars(select(Message)).all())))
        self.assertEqual(0, len(list(self.db.scalars(select(Entity)).all())))
        self.assertEqual(0, len(list(self.db.scalars(select(Fact)).all())))
        self.assertEqual(0, len(list(self.db.scalars(select(Relation)).all())))
        self.assertEqual(0, len(list(self.db.scalars(select(ConversationEntityLink)).all())))
        self.assertEqual(0, len(list(self.db.scalars(select(ExtractorRun)).all())))
        self.assertEqual(0, len(list(self.db.scalars(select(ResolutionEvent)).all())))
        self.assertEqual(0, len(list(self.db.scalars(select(EntityMergeAudit)).all())))
        self.assertEqual(0, len(list(self.db.scalars(select(PredicateRegistryEntry)).all())))
        self.assertEqual(0, len(list(self.db.scalars(select(SchemaNode)).all())))
        self.assertEqual(0, len(list(self.db.scalars(select(SchemaField)).all())))
        self.assertEqual(0, len(list(self.db.scalars(select(SchemaRelation)).all())))
        self.assertEqual(0, len(list(self.db.scalars(select(SchemaProposal)).all())))

    def test_delete_message_removes_only_message_scoped_knowledge(self) -> None:
        conversation_id = "phase3-delete-message-001"
        create_messages(
            self.db,
            conversation_id,
            [
                MessageCreate(
                    role="user",
                    content="First insight for one entity.",
                    timestamp=datetime(2026, 2, 28, 11, 5, tzinfo=timezone.utc),
                ),
                MessageCreate(
                    role="user",
                    content="Second insight for another entity.",
                    timestamp=datetime(2026, 2, 28, 11, 6, tzinfo=timezone.utc),
                ),
            ],
        )
        run_extraction_for_conversation(self.db, conversation_id, extractor=_MessageScopedMutationsExtractor())

        first_message = self.db.scalar(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.timestamp.asc(), Message.id.asc())
        )
        assert first_message is not None
        self.assertTrue(delete_message(self.db, first_message.id))

        self.assertEqual(
            1,
            len(list(self.db.scalars(select(Message).where(Message.conversation_id == conversation_id)).all())),
        )
        self.assertEqual(
            1,
            len(list(self.db.scalars(select(Fact).where(Fact.conversation_id == conversation_id)).all())),
        )
        remaining_fact = self.db.scalar(select(Fact).where(Fact.conversation_id == conversation_id))
        assert remaining_fact is not None
        self.assertEqual(remaining_fact.predicate, "signal_two")
        self.assertEqual(remaining_fact.object_value, "from-second")

        self.assertEqual(
            0,
            len(list(self.db.scalars(select(Relation).where(Relation.conversation_id == conversation_id)).all())),
        )
        self.assertEqual(
            1,
            len(
                list(
                    self.db.scalars(
                        select(ConversationEntityLink).where(
                            ConversationEntityLink.conversation_id == conversation_id
                        )
                    ).all()
                )
            ),
        )
        remaining_link = self.db.scalar(
            select(ConversationEntityLink).where(ConversationEntityLink.conversation_id == conversation_id)
        )
        assert remaining_link is not None
        self.assertNotEqual(remaining_link.first_seen_message_id, first_message.id)

        self.assertEqual(
            1,
            len(list(self.db.scalars(select(Entity).where(Entity.conversation_id == conversation_id)).all())),
        )
        remaining_entity = self.db.scalar(select(Entity).where(Entity.conversation_id == conversation_id))
        assert remaining_entity is not None
        self.assertEqual(remaining_entity.canonical_name, "Second Only Co.")

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
