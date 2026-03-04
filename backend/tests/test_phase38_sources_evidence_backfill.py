"""Tests for source/evidence persistence during extraction."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.extraction.extractor_interface import ExtractorInterface
from app.extraction.types import ExtractedEntity, ExtractedFact, ExtractedRelation, ExtractionResult
from app.models.base import Base
from app.models.collection import Collection
from app.models.collection_item import CollectionItem
from app.models.conversation import Conversation
from app.models.conversation_entity_link import ConversationEntityLink
from app.models.entity import Entity
from app.models.entity_merge_audit import EntityMergeAudit
from app.models.evidence import Evidence
from app.models.extractor_run import ExtractorRun
from app.models.fact import Fact
from app.models.message import Message
from app.models.predicate_registry_entry import PredicateRegistryEntry
from app.models.pod import Pod
from app.models.resolution_event import ResolutionEvent
from app.models.relation import Relation
from app.models.schema_field import SchemaField
from app.models.schema_node import SchemaNode
from app.models.schema_proposal import SchemaProposal
from app.models.schema_relation import SchemaRelation
from app.models.source import Source
from app.models.workspace_edge import WorkspaceEdge
from app.schemas.message import MessageCreate
from app.services.extraction import run_extraction_for_conversation
from app.services.messages import create_messages


class _EvidenceStubExtractor(ExtractorInterface):
    def extract(self, messages: list[Message]) -> ExtractionResult:
        ids = [message.id for message in messages]
        return ExtractionResult(
            entities=[
                ExtractedEntity(
                    name="Apple Inc.",
                    type_label="Company",
                    aliases=["Apple"],
                    source_message_ids=ids,
                ),
                ExtractedEntity(
                    name="NVIDIA",
                    type_label="Company",
                    aliases=["NVDA"],
                    source_message_ids=ids,
                ),
            ],
            facts=[
                ExtractedFact(
                    entity_name="Apple Inc.",
                    field_label="sentiment",
                    value_text="positive",
                    confidence=0.82,
                    source_message_ids=[ids[0]],
                )
            ],
            relations=[
                ExtractedRelation(
                    from_entity="Apple Inc.",
                    relation_label="compared_with",
                    to_entity="NVIDIA",
                    qualifiers={},
                    confidence=0.73,
                    source_message_ids=[ids[-1]],
                )
            ],
        )


class SourceEvidenceBackfillTests(unittest.TestCase):
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

    def test_extraction_creates_sources_and_evidence(self) -> None:
        conversation_id = "phase38-evidence-001"
        create_messages(
            self.db,
            conversation_id,
            [
                MessageCreate(
                    role="user",
                    content="Apple sentiment is positive this quarter.",
                    timestamp=datetime(2026, 3, 3, 9, 0, tzinfo=timezone.utc),
                ),
                MessageCreate(
                    role="assistant",
                    content="Apple compared with NVIDIA on momentum.",
                    timestamp=datetime(2026, 3, 3, 9, 1, tzinfo=timezone.utc),
                ),
            ],
        )

        run_extraction_for_conversation(self.db, conversation_id, extractor=_EvidenceStubExtractor())

        source_rows = list(
            self.db.scalars(
                select(Source).where(Source.conversation_id == conversation_id).order_by(Source.message_id.asc())
            ).all()
        )
        self.assertEqual(len(source_rows), 2)
        self.assertTrue(all(row.source_kind == "message" for row in source_rows))

        evidence_rows = list(self.db.scalars(select(Evidence).order_by(Evidence.id.asc())).all())
        self.assertEqual(len(evidence_rows), 2)
        self.assertTrue(any(row.fact_id is not None for row in evidence_rows))
        self.assertTrue(any(row.relation_id is not None for row in evidence_rows))
        self.assertTrue(all(row.source_id is not None for row in evidence_rows))
        self.assertTrue(all(row.confidence is not None for row in evidence_rows))
        self.assertTrue(all(row.snippet for row in evidence_rows))

    def _reset_tables(self) -> None:
        self.db.execute(delete(Evidence))
        self.db.execute(delete(Source))
        self.db.execute(delete(WorkspaceEdge))
        self.db.execute(delete(CollectionItem))
        self.db.execute(delete(Collection))
        self.db.execute(delete(Conversation))
        self.db.execute(delete(Pod))
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
