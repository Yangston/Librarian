"""Unit tests for schema stabilization proposal generation."""

from __future__ import annotations

import unittest

from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.schema_field import SchemaField
from app.models.schema_node import SchemaNode
from app.models.schema_proposal import SchemaProposal
from app.models.schema_relation import SchemaRelation
from app.services.schema_stabilization import run_schema_stabilization


class SchemaStabilizationTests(unittest.TestCase):
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
        self.db.execute(delete(SchemaProposal))
        self.db.execute(delete(SchemaRelation))
        self.db.execute(delete(SchemaField))
        self.db.execute(delete(SchemaNode))
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()

    def test_generates_proposals_and_auto_accepts_high_confidence_pairs(self) -> None:
        self.db.add_all(
            [
                SchemaField(label="services_revenue", stats_json={"observations": 5}),
                SchemaField(label="service_revenue", stats_json={"observations": 2}),
                SchemaRelation(label="impacted_by", stats_json={"observations": 3}),
                SchemaRelation(label="impact_by", stats_json={"observations": 2}),
                SchemaNode(label="operational_risk_event", stats_json={"observations": 2}),
                SchemaNode(label="operation_risk_events", stats_json={"observations": 1}),
            ]
        )
        self.db.commit()

        result = run_schema_stabilization(self.db, conversation_id="schema-stabilization-test-001")
        self.db.commit()

        proposals = list(self.db.scalars(select(SchemaProposal).order_by(SchemaProposal.id.asc())))
        self.assertEqual(result.proposals_created, 3)
        self.assertEqual(len(proposals), 3)
        self.assertGreaterEqual(result.auto_accepted, 1)
        self.assertTrue(any(proposal.status == "auto_accepted" for proposal in proposals))
        self.assertTrue(any(proposal.proposal_type == "merge_fields" for proposal in proposals))
        self.assertTrue(any(proposal.proposal_type == "merge_relations" for proposal in proposals))
        self.assertTrue(any(proposal.proposal_type == "merge_nodes" for proposal in proposals))

        field_rows = list(self.db.scalars(select(SchemaField).order_by(SchemaField.id.asc())))
        canonical_field = next(row for row in field_rows if row.label == "services_revenue")
        alias_field = next(row for row in field_rows if row.label == "service_revenue")
        self.assertEqual(alias_field.canonical_of_id, canonical_field.id)

    def test_second_run_does_not_duplicate_existing_pair_proposals(self) -> None:
        self.db.add_all(
            [
                SchemaRelation(label="impacted_by", stats_json={"observations": 3}),
                SchemaRelation(label="impact_by", stats_json={"observations": 2}),
            ]
        )
        self.db.commit()

        first_result = run_schema_stabilization(self.db, conversation_id="schema-stabilization-test-002")
        self.db.commit()
        second_result = run_schema_stabilization(self.db, conversation_id="schema-stabilization-test-003")
        self.db.commit()

        proposals = list(self.db.scalars(select(SchemaProposal).order_by(SchemaProposal.id.asc())))
        self.assertEqual(first_result.proposals_created, 1)
        self.assertEqual(second_result.proposals_created, 0)
        self.assertEqual(len(proposals), 1)


if __name__ == "__main__":
    unittest.main()
