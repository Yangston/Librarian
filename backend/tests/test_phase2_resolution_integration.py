"""Integration-style tests for Phase 2 entity resolution persistence."""

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
from app.services.database import (
    list_entities,
    list_entity_merge_audits,
    list_facts,
    list_relations,
    list_resolution_events,
)
from app.services.extraction import run_extraction_for_conversation
from app.services.messages import create_messages


class _StubExtractor(ExtractorInterface):
    def __init__(self, result: ExtractionResult) -> None:
        self._result = result

    def extract(self, messages: list[Message]) -> ExtractionResult:
        return self._result


class Phase2ResolutionIntegrationTests(unittest.TestCase):
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

    def test_extraction_persists_resolution_metadata_and_canonical_links(self) -> None:
        conversation_id = "phase2-resolution-test-001"
        created_messages = create_messages(
            self.db,
            conversation_id,
            [
                MessageCreate(
                    role="user",
                    content="AAPL reported revenue strength.",
                    timestamp=datetime(2026, 2, 24, 14, 0, tzinfo=timezone.utc),
                ),
                MessageCreate(
                    role="assistant",
                    content="Apple Inc. faces supply chain pressure.",
                    timestamp=datetime(2026, 2, 24, 14, 1, tzinfo=timezone.utc),
                ),
            ],
        )

        msg1_id = created_messages[0].id
        msg2_id = created_messages[1].id
        extractor = _StubExtractor(
            ExtractionResult(
                entities=[
                    ExtractedEntity(
                        name="AAPL",
                        type_label="PublicCompany",
                        aliases=["Apple", "Apple Inc."],
                        source_message_ids=[msg1_id],
                    ),
                    ExtractedEntity(
                        name="Apple Inc.",
                        type_label="PublicCompany",
                        aliases=["Apple", "AAPL"],
                        source_message_ids=[msg2_id],
                    ),
                    ExtractedEntity(
                        name="Supply chain disruption",
                        type_label="OperationalRiskEvent",
                        source_message_ids=[msg2_id],
                    ),
                ],
                facts=[
                    ExtractedFact(
                        entity_name="AAPL",
                        field_label="reported_revenues",
                        value_text="revenue strength",
                        confidence=0.95,
                        source_message_ids=[msg1_id],
                    ),
                    ExtractedFact(
                        entity_name="Apple Inc.",
                        field_label="reported_revenue",
                        value_text="guidance commentary",
                        confidence=0.83,
                        source_message_ids=[msg2_id],
                    ),
                ],
                relations=[
                    ExtractedRelation(
                        from_entity="Apple",
                        relation_label="impacted_by",
                        to_entity="Supply chain disruption",
                        qualifiers={},
                        confidence=0.88,
                        source_message_ids=[msg2_id],
                    ),
                    ExtractedRelation(
                        from_entity="Apple Inc.",
                        relation_label="Impacted-By",
                        to_entity="Supply chain disruption",
                        qualifiers={},
                        confidence=0.82,
                        source_message_ids=[msg2_id],
                    ),
                ],
            )
        )

        run_result = run_extraction_for_conversation(self.db, conversation_id, extractor=extractor)
        self.assertEqual(run_result.messages_processed, 2)
        self.assertEqual(run_result.entities_created, 3)
        self.assertEqual(run_result.facts_created, 2)
        self.assertEqual(run_result.relations_created, 2)
        self.assertIsNotNone(run_result.extractor_run_id)

        entities = list_entities(self.db, conversation_id)
        self.assertEqual(len(entities), 3)
        company_entities = [entity for entity in entities if entity.type == "PublicCompany"]
        self.assertEqual(len(company_entities), 2)
        event_entities = [entity for entity in entities if entity.type == "OperationalRiskEvent"]
        self.assertEqual(len(event_entities), 1)

        canonical_company = next(
            entity for entity in company_entities if entity.name == "Apple Inc." and entity.merged_into_id is None
        )
        merged_company = next(entity for entity in company_entities if entity.name == "AAPL")

        self.assertEqual(canonical_company.canonical_name, "Apple Inc.")
        self.assertEqual(merged_company.canonical_name, "Apple Inc.")
        self.assertEqual(merged_company.merged_into_id, canonical_company.id)
        self.assertIn("Apple", canonical_company.known_aliases_json)
        self.assertEqual(canonical_company.resolver_version, "phase2-v1")
        self.assertIsNone(canonical_company.resolution_reason)
        self.assertIsNotNone(merged_company.resolution_reason)

        facts = list_facts(self.db, conversation_id)
        self.assertEqual(len(facts), 2)
        self.assertTrue(all(fact.subject_entity_id == canonical_company.id for fact in facts))
        self.assertTrue(all(fact.subject_entity_name == "Apple Inc." for fact in facts))
        self.assertTrue(all(fact.predicate == "reported_revenue" for fact in facts))

        relations = list_relations(self.db, conversation_id)
        self.assertEqual(len(relations), 2)
        self.assertTrue(all(relation.from_entity_id == canonical_company.id for relation in relations))
        self.assertTrue(all(relation.from_entity_name == "Apple Inc." for relation in relations))
        self.assertTrue(all(relation.relation_type == "impacted_by" for relation in relations))

        audits = list_entity_merge_audits(self.db, conversation_id)
        self.assertEqual(len(audits), 1)
        self.assertEqual(audits[0].survivor_entity_id, canonical_company.id)
        self.assertEqual(audits[0].merged_entity_ids_json, [merged_company.id])
        self.assertTrue(
            audits[0].reason_for_merge
            in {"alias_match", "exact_name_match", "cluster_canonicalization"}
        )
        self.assertEqual(audits[0].resolver_version, "phase2-v1")

        resolution_events = list_resolution_events(self.db, conversation_id)
        self.assertGreaterEqual(len(resolution_events), 5)
        self.assertTrue(any(event.event_type == "match" for event in resolution_events))
        self.assertTrue(any(event.event_type == "merge" for event in resolution_events))
        self.assertTrue(any(event.event_type == "alias_add" for event in resolution_events))
        merge_event = next(event for event in resolution_events if event.event_type == "merge")
        self.assertEqual(len(merge_event.entity_ids_json), 2)
        self.assertIsNotNone(merge_event.similarity_score)

        predicate_entries = list(self.db.query(PredicateRegistryEntry).all())
        self.assertEqual(len(predicate_entries), 2)
        fact_registry = next(entry for entry in predicate_entries if entry.kind == "fact_predicate")
        relation_registry = next(entry for entry in predicate_entries if entry.kind == "relation_type")
        self.assertEqual(fact_registry.predicate, "reported_revenue")
        self.assertEqual(fact_registry.frequency, 2)
        self.assertEqual(relation_registry.predicate, "impacted_by")
        self.assertEqual(relation_registry.frequency, 2)

        schema_nodes = list(self.db.query(SchemaNode).order_by(SchemaNode.label.asc()))
        schema_fields = list(self.db.query(SchemaField).order_by(SchemaField.label.asc()))
        schema_relations = list(self.db.query(SchemaRelation).order_by(SchemaRelation.label.asc()))

        self.assertEqual({node.label for node in schema_nodes}, {"OperationalRiskEvent", "PublicCompany"})
        self.assertEqual([field.label for field in schema_fields], ["reported_revenue"])
        self.assertEqual([relation.label for relation in schema_relations], ["impacted_by"])
        self.assertIn("Apple Inc.: guidance commentary", schema_fields[0].examples_json)
        self.assertGreaterEqual(int(schema_fields[0].stats_json.get("observations", 0)), 1)

    def test_rerun_replaces_merge_audits_for_same_conversation(self) -> None:
        conversation_id = "phase2-resolution-test-002"
        created_messages = create_messages(
            self.db,
            conversation_id,
            [
                MessageCreate(
                    role="user",
                    content="AAPL moved higher.",
                    timestamp=datetime(2026, 2, 24, 15, 0, tzinfo=timezone.utc),
                ),
            ],
        )
        msg_id = created_messages[0].id

        extractor = _StubExtractor(
            ExtractionResult(
                entities=[
                    ExtractedEntity(
                        name="AAPL",
                        type_label="PublicCompany",
                        aliases=["Apple"],
                        source_message_ids=[msg_id],
                    ),
                    ExtractedEntity(
                        name="Apple Inc.",
                        type_label="PublicCompany",
                        aliases=["AAPL"],
                        source_message_ids=[msg_id],
                    ),
                ]
            )
        )

        run_extraction_for_conversation(self.db, conversation_id, extractor=extractor)
        first_audits = list_entity_merge_audits(self.db, conversation_id)
        self.assertEqual(len(first_audits), 1)

        run_extraction_for_conversation(self.db, conversation_id, extractor=extractor)
        second_audits = list_entity_merge_audits(self.db, conversation_id)
        self.assertEqual(len(second_audits), 1)

    def test_extraction_triggers_schema_stabilization_proposals(self) -> None:
        conversation_id = "phase2-resolution-test-003"
        created_messages = create_messages(
            self.db,
            conversation_id,
            [
                MessageCreate(
                    role="user",
                    content="Two related operational risk events were discussed.",
                    timestamp=datetime(2026, 2, 24, 16, 0, tzinfo=timezone.utc),
                ),
            ],
        )
        msg_id = created_messages[0].id
        extractor = _StubExtractor(
            ExtractionResult(
                entities=[
                    ExtractedEntity(
                        name="Supply Chain Shock",
                        type_label="operational_risk_event",
                        source_message_ids=[msg_id],
                    ),
                    ExtractedEntity(
                        name="Logistics Disruption",
                        type_label="operation_risk_events",
                        source_message_ids=[msg_id],
                    ),
                ],
            )
        )

        run_extraction_for_conversation(self.db, conversation_id, extractor=extractor)

        proposals = list(self.db.query(SchemaProposal).filter(SchemaProposal.proposal_type == "merge_nodes"))
        self.assertGreaterEqual(len(proposals), 1)

    def test_cross_conversation_global_entity_linking_reuses_existing_canonical(self) -> None:
        conversation_a = "phase2-global-test-001"
        conversation_b = "phase2-global-test-002"
        message_a = create_messages(
            self.db,
            conversation_a,
            [
                MessageCreate(
                    role="user",
                    content="Apple Inc. posted strong services revenue.",
                    timestamp=datetime(2026, 2, 24, 17, 0, tzinfo=timezone.utc),
                ),
            ],
        )[0]
        run_extraction_for_conversation(
            self.db,
            conversation_a,
            extractor=_StubExtractor(
                ExtractionResult(
                    entities=[
                        ExtractedEntity(
                            name="Apple Inc.",
                            type_label="PublicCompany",
                            aliases=["AAPL", "Apple"],
                            source_message_ids=[message_a.id],
                        )
                    ],
                    facts=[
                        ExtractedFact(
                            entity_name="Apple Inc.",
                            field_label="services_revenue",
                            value_text="strong",
                            confidence=0.9,
                            source_message_ids=[message_a.id],
                        )
                    ],
                )
            ),
        )
        canonical_a = self.db.scalar(
            select(Entity).where(Entity.conversation_id == conversation_a, Entity.merged_into_id.is_(None))
        )
        self.assertIsNotNone(canonical_a)
        assert canonical_a is not None

        message_b = create_messages(
            self.db,
            conversation_b,
            [
                MessageCreate(
                    role="user",
                    content="AAPL faces short-term margin pressure.",
                    timestamp=datetime(2026, 2, 24, 17, 5, tzinfo=timezone.utc),
                ),
            ],
        )[0]
        run_extraction_for_conversation(
            self.db,
            conversation_b,
            extractor=_StubExtractor(
                ExtractionResult(
                    entities=[
                        ExtractedEntity(
                            name="AAPL",
                            type_label="PublicCompany",
                            aliases=["Apple Inc."],
                            source_message_ids=[message_b.id],
                        )
                    ],
                    facts=[
                        ExtractedFact(
                            entity_name="AAPL",
                            field_label="margin_pressure",
                            value_text="short-term",
                            confidence=0.88,
                            source_message_ids=[message_b.id],
                        )
                    ],
                )
            ),
        )

        canonical_b = self.db.scalar(
            select(Entity).where(Entity.conversation_id == conversation_b, Entity.name == "AAPL")
        )
        self.assertIsNotNone(canonical_b)
        assert canonical_b is not None
        self.assertEqual(canonical_b.merged_into_id, canonical_a.id)

        fact_b = self.db.scalar(select(Fact).where(Fact.conversation_id == conversation_b))
        self.assertIsNotNone(fact_b)
        assert fact_b is not None
        self.assertEqual(fact_b.subject_entity_id, canonical_a.id)

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
