"""Integration tests for schema registry table persistence."""

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


class SchemaRegistryPersistenceTests(unittest.TestCase):
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

    def test_schema_registry_rows_persist_with_canonical_links(self) -> None:
        node = SchemaNode(
            label="PublicCompany",
            description="Learned type for listed firms",
            examples_json=["Apple", "Microsoft"],
            stats_json={"count": 2},
        )
        self.db.add(node)

        base_field = SchemaField(
            label="services_revenue",
            description="Reported services revenue",
            examples_json=["record services revenue"],
            stats_json={"count": 1},
        )
        self.db.add(base_field)
        self.db.flush()

        alias_field = SchemaField(
            label="service_revenue",
            canonical_of_id=base_field.id,
            examples_json=["services revenue"],
            stats_json={"count": 1},
        )
        self.db.add(alias_field)

        base_relation = SchemaRelation(
            label="impacted_by",
            examples_json=["AAPL impacted by supply chain disruption"],
            stats_json={"count": 1},
        )
        self.db.add(base_relation)
        self.db.flush()

        alias_relation = SchemaRelation(
            label="affected_by",
            canonical_of_id=base_relation.id,
            examples_json=["AAPL affected by supply shock"],
            stats_json={"count": 1},
        )
        self.db.add(alias_relation)

        proposal = SchemaProposal(
            proposal_type="canonicalize_labels",
            payload_json={"target_kind": "schema_fields", "from_label": "service_revenue", "to_label": "services_revenue"},
            confidence=0.97,
            evidence_json={"cooccurrence": 5, "similarity": 0.98},
            status="proposed",
        )
        self.db.add(proposal)
        self.db.commit()

        nodes = list(self.db.scalars(select(SchemaNode).order_by(SchemaNode.id.asc())))
        fields = list(self.db.scalars(select(SchemaField).order_by(SchemaField.id.asc())))
        relations = list(self.db.scalars(select(SchemaRelation).order_by(SchemaRelation.id.asc())))
        proposals = list(self.db.scalars(select(SchemaProposal).order_by(SchemaProposal.id.asc())))

        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0].label, "PublicCompany")
        self.assertEqual(nodes[0].stats_json["count"], 2)

        self.assertEqual(len(fields), 2)
        self.assertIsNone(fields[0].canonical_of_id)
        self.assertEqual(fields[1].canonical_of_id, fields[0].id)

        self.assertEqual(len(relations), 2)
        self.assertIsNone(relations[0].canonical_of_id)
        self.assertEqual(relations[1].canonical_of_id, relations[0].id)

        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0].proposal_type, "canonicalize_labels")
        self.assertEqual(proposals[0].status, "proposed")


if __name__ == "__main__":
    unittest.main()
