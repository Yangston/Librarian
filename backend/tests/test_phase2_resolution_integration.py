"""Integration-style tests for Phase 2 entity resolution persistence."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.extraction.extractor_interface import ExtractorInterface
from app.extraction.types import ExtractedEntity, ExtractedFact, ExtractedRelation, ExtractionResult
from app.models.base import Base
from app.models.entity import Entity
from app.models.entity_merge_audit import EntityMergeAudit
from app.models.fact import Fact
from app.models.message import Message
from app.models.predicate_registry_entry import PredicateRegistryEntry
from app.models.relation import Relation
from app.schemas.message import MessageCreate
from app.services.database import list_entities, list_entity_merge_audits, list_facts, list_relations
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
                        entity_type="Company",
                        aliases=["Apple", "Apple Inc."],
                        source_message_ids=[msg1_id],
                    ),
                    ExtractedEntity(
                        name="Apple Inc.",
                        entity_type="Company",
                        aliases=["Apple", "AAPL"],
                        source_message_ids=[msg2_id],
                    ),
                    ExtractedEntity(
                        name="Supply chain disruption",
                        entity_type="Event",
                        source_message_ids=[msg2_id],
                    ),
                ],
                facts=[
                    ExtractedFact(
                        subject_name="AAPL",
                        subject_type="Company",
                        predicate="reported_revenues",
                        object_value="revenue strength",
                        confidence=0.95,
                        source_message_ids=[msg1_id],
                    ),
                    ExtractedFact(
                        subject_name="Apple Inc.",
                        subject_type="company",
                        predicate="reported_revenue",
                        object_value="guidance commentary",
                        confidence=0.83,
                        source_message_ids=[msg2_id],
                    ),
                ],
                relations=[
                    ExtractedRelation(
                        from_name="Apple",
                        from_type="company",
                        relation_type="impacted_by",
                        to_name="Supply chain disruption",
                        to_type="event",
                        qualifiers={},
                        source_message_ids=[msg2_id],
                    ),
                    ExtractedRelation(
                        from_name="Apple Inc.",
                        from_type="Company",
                        relation_type="Impacted-By",
                        to_name="Supply chain disruption",
                        to_type="Event",
                        qualifiers={},
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

        entities = list_entities(self.db, conversation_id)
        self.assertEqual(len(entities), 3)
        company_entities = [entity for entity in entities if entity.type == "Company"]
        self.assertEqual(len(company_entities), 2)
        event_entities = [entity for entity in entities if entity.type == "Event"]
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

        predicate_entries = list(self.db.query(PredicateRegistryEntry).all())
        self.assertEqual(len(predicate_entries), 2)
        fact_registry = next(entry for entry in predicate_entries if entry.kind == "fact_predicate")
        relation_registry = next(entry for entry in predicate_entries if entry.kind == "relation_type")
        self.assertEqual(fact_registry.predicate, "reported_revenue")
        self.assertEqual(fact_registry.frequency, 2)
        self.assertEqual(relation_registry.predicate, "impacted_by")
        self.assertEqual(relation_registry.frequency, 2)

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
                    ExtractedEntity(name="AAPL", entity_type="Company", aliases=["Apple"], source_message_ids=[msg_id]),
                    ExtractedEntity(
                        name="Apple Inc.",
                        entity_type="Company",
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

    def _reset_tables(self) -> None:
        self.db.execute(delete(Relation))
        self.db.execute(delete(Fact))
        self.db.execute(delete(PredicateRegistryEntry))
        self.db.execute(delete(EntityMergeAudit))
        self.db.execute(delete(Entity))
        self.db.execute(delete(Message))
        self.db.commit()


if __name__ == "__main__":
    unittest.main()
