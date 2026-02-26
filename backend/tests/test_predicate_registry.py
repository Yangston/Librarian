"""Unit tests for schema governance predicate registry."""

from __future__ import annotations

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.predicate_registry_entry import PredicateRegistryEntry
from app.schema.predicate_registry import PredicateRegistry, normalize_predicate_label
from app.services.schema import list_predicate_registry_entries


class PredicateRegistryTests(unittest.TestCase):
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
        self.db.query(PredicateRegistryEntry).delete()
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()

    def test_normalize_predicate_label_snake_cases_and_singularizes(self) -> None:
        self.assertEqual(normalize_predicate_label("Reported Revenues"), "reported_revenue")
        self.assertEqual(normalize_predicate_label("impacted-by"), "impacted_by")
        self.assertEqual(normalize_predicate_label(""), "")

    def test_registry_collapses_near_duplicate_predicates(self) -> None:
        registry = PredicateRegistry()

        first = registry.register(self.db, value="reported_revenues", kind="fact_predicate")
        second = registry.register(self.db, value="reported_revenue", kind="fact_predicate")
        third = registry.register(self.db, value="reported_revenuee", kind="fact_predicate")

        self.assertEqual(first.canonical_predicate, "reported_revenue")
        self.assertEqual(second.canonical_predicate, "reported_revenue")
        self.assertEqual(third.canonical_predicate, "reported_revenue")

        entries = list(self.db.query(PredicateRegistryEntry).all())
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].predicate, "reported_revenue")
        self.assertEqual(entries[0].frequency, 3)
        self.assertIn("reported_revenuee", entries[0].aliases_json)

    def test_registry_is_scoped_by_kind(self) -> None:
        registry = PredicateRegistry()

        fact_entry = registry.register(self.db, value="impacted_by", kind="fact_predicate")
        relation_entry = registry.register(self.db, value="impacted_by", kind="relation_type")

        self.assertEqual(fact_entry.canonical_predicate, "impacted_by")
        self.assertEqual(relation_entry.canonical_predicate, "impacted_by")
        self.assertNotEqual(fact_entry.registry_entry_id, relation_entry.registry_entry_id)
        self.assertEqual(self.db.query(PredicateRegistryEntry).count(), 2)

    def test_schema_service_lists_entries_sorted_and_filterable(self) -> None:
        registry = PredicateRegistry()
        registry.register(self.db, value="reported_revenue", kind="fact_predicate")
        registry.register(self.db, value="reported_revenue", kind="fact_predicate")
        registry.register(self.db, value="impacted_by", kind="relation_type")
        registry.register(self.db, value="supplies", kind="relation_type")

        all_entries = list_predicate_registry_entries(self.db)
        self.assertEqual(len(all_entries), 3)
        self.assertEqual(all_entries[0].kind, "fact_predicate")
        self.assertEqual(all_entries[0].predicate, "reported_revenue")
        self.assertEqual(all_entries[0].frequency, 2)

        relation_entries = list_predicate_registry_entries(self.db, kind="relation_type")
        self.assertEqual(len(relation_entries), 2)
        self.assertTrue(all(entry.kind == "relation_type" for entry in relation_entries))


if __name__ == "__main__":
    unittest.main()
