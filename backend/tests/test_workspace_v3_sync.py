"""Tests for workspace v3 sync and stable row materialization."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.collection import Collection
from app.models.collection_column import CollectionColumn
from app.models.collection_item import CollectionItem
from app.models.collection_item_value import CollectionItemValue
from app.models.conversation import Conversation
from app.models.entity import Entity
from app.models.evidence import Evidence
from app.models.fact import Fact
from app.models.message import Message
from app.models.pod import Pod
from app.models.property_catalog import PropertyCatalog
from app.models.relation import Relation
from app.services.organization import get_scoped_graph
from app.services.workspace_sync import run_workspace_sync_for_conversation


class WorkspaceV3SyncTests(unittest.TestCase):
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

    def test_workspace_sync_groups_rows_into_travel_tables(self) -> None:
        pod = Pod(slug="thailand-trip", name="Thailand Trip", description=None, is_default=False)
        self.db.add(pod)
        self.db.flush()
        self.db.add(Conversation(conversation_id="workspace-v3-travel", pod_id=pod.id))
        hotel_message = Message(
            conversation_id="workspace-v3-travel",
            role="user",
            content="Please compare the Mandarin Oriental Bangkok hotel and Jay Fai restaurant.",
        )
        self.db.add(hotel_message)
        self.db.flush()

        hotel = Entity(
            conversation_id="workspace-v3-travel",
            pod_id=pod.id,
            name="Mandarin Oriental Bangkok",
            display_name="Mandarin Oriental Bangkok",
            canonical_name="Mandarin Oriental Bangkok",
            type="Hotel",
            type_label="Hotel",
        )
        restaurant = Entity(
            conversation_id="workspace-v3-travel",
            pod_id=pod.id,
            name="Jay Fai",
            display_name="Jay Fai",
            canonical_name="Jay Fai",
            type="Restaurant",
            type_label="Restaurant",
        )
        self.db.add_all([hotel, restaurant])
        self.db.flush()
        self.db.add_all(
            [
                Fact(
                    conversation_id="workspace-v3-travel",
                    pod_id=pod.id,
                    subject_entity_id=hotel.id,
                    predicate="location",
                    object_value="Bangkok",
                    source_message_ids_json=[hotel_message.id],
                    confidence=0.9,
                ),
                Fact(
                    conversation_id="workspace-v3-travel",
                    pod_id=pod.id,
                    subject_entity_id=hotel.id,
                    predicate="price",
                    object_value="expensive",
                    source_message_ids_json=[hotel_message.id],
                    confidence=0.8,
                ),
                Fact(
                    conversation_id="workspace-v3-travel",
                    pod_id=pod.id,
                    subject_entity_id=restaurant.id,
                    predicate="cuisine",
                    object_value="Thai seafood",
                    source_message_ids_json=[hotel_message.id],
                    confidence=0.85,
                ),
            ]
        )
        self.db.commit()

        result = run_workspace_sync_for_conversation(
            self.db,
            conversation_id="workspace-v3-travel",
            allow_enrichment=False,
        )
        self.db.commit()

        self.assertEqual(result.collections_upserted, 2)
        collection_slugs = {
            collection.slug
            for collection in self.db.scalars(select(Collection).order_by(Collection.slug.asc())).all()
        }
        self.assertIn("accommodations", collection_slugs)
        self.assertIn("food", collection_slugs)

        accommodation = self.db.scalar(select(Collection).where(Collection.slug == "accommodations"))
        assert accommodation is not None
        food = self.db.scalar(select(Collection).where(Collection.slug == "food"))
        assert food is not None

        accommodation_columns = list(
            self.db.scalars(
                select(CollectionColumn).where(CollectionColumn.collection_id == accommodation.id)
            ).all()
        )
        food_columns = list(
            self.db.scalars(select(CollectionColumn).where(CollectionColumn.collection_id == food.id)).all()
        )
        self.assertIn("location", {column.key for column in accommodation_columns})
        self.assertIn("price", {column.key for column in accommodation_columns})
        self.assertIn("cuisine", {column.key for column in food_columns})

        accommodation_rows = list(
            self.db.scalars(select(CollectionItem).where(CollectionItem.collection_id == accommodation.id)).all()
        )
        food_rows = list(
            self.db.scalars(select(CollectionItem).where(CollectionItem.collection_id == food.id)).all()
        )
        self.assertEqual(len(accommodation_rows), 1)
        self.assertEqual(len(food_rows), 1)

        property_catalog_count = self.db.scalar(select(PropertyCatalog.id).limit(1))
        self.assertIsNotNone(property_catalog_count)

    def test_manual_cell_value_survives_resync(self) -> None:
        pod = Pod(slug="manual-space", name="Manual Space", description=None, is_default=False)
        self.db.add(pod)
        self.db.flush()
        self.db.add(Conversation(conversation_id="workspace-v3-manual", pod_id=pod.id))
        message = Message(
            conversation_id="workspace-v3-manual",
            role="user",
            content="The Siam hotel has a high price.",
            timestamp=datetime(2026, 3, 6, 10, 0, tzinfo=timezone.utc),
        )
        self.db.add(message)
        self.db.flush()
        hotel = Entity(
            conversation_id="workspace-v3-manual",
            pod_id=pod.id,
            name="The Siam",
            display_name="The Siam",
            canonical_name="The Siam",
            type="Hotel",
            type_label="Hotel",
        )
        self.db.add(hotel)
        self.db.flush()
        self.db.add(
            Fact(
                conversation_id="workspace-v3-manual",
                pod_id=pod.id,
                subject_entity_id=hotel.id,
                predicate="price",
                object_value="high",
                source_message_ids_json=[message.id],
                confidence=0.8,
            )
        )
        self.db.commit()

        run_workspace_sync_for_conversation(self.db, conversation_id="workspace-v3-manual", allow_enrichment=False)
        self.db.commit()

        row = self.db.scalar(select(CollectionItem).where(CollectionItem.entity_id == hotel.id))
        assert row is not None
        price_column = self.db.scalar(select(CollectionColumn).where(CollectionColumn.collection_id == row.collection_id, CollectionColumn.key == "price"))
        assert price_column is not None
        value = self.db.scalar(
            select(CollectionItemValue).where(
                CollectionItemValue.collection_item_id == row.id,
                CollectionItemValue.collection_column_id == price_column.id,
            )
        )
        assert value is not None
        value.display_value = "custom manual value"
        value.value_json = "custom manual value"
        value.source_kind = "manual"
        value.status = "manual"
        value.edited_by_user = True
        self.db.add(value)
        self.db.commit()

        fact = self.db.scalar(select(Fact).where(Fact.subject_entity_id == hotel.id))
        assert fact is not None
        fact.object_value = "very expensive"
        self.db.add(fact)
        self.db.commit()

        run_workspace_sync_for_conversation(self.db, conversation_id="workspace-v3-manual", allow_enrichment=False)
        self.db.commit()

        refreshed = self.db.scalar(select(CollectionItemValue).where(CollectionItemValue.id == value.id))
        assert refreshed is not None
        self.assertEqual(refreshed.display_value, "custom manual value")
        self.assertTrue(refreshed.edited_by_user)

    def test_scoped_graph_includes_accepted_extracted_relations_without_workspace_relation_rows(self) -> None:
        pod = Pod(slug="graph-space", name="Graph Space", description=None, is_default=False)
        self.db.add(pod)
        self.db.flush()
        self.db.add(Conversation(conversation_id="workspace-v3-graph", pod_id=pod.id))
        message = Message(
            conversation_id="workspace-v3-graph",
            role="user",
            content="Mandarin Oriental Bangkok partners with Rosewood Bangkok.",
        )
        self.db.add(message)
        self.db.flush()
        hotel = Entity(
            conversation_id="workspace-v3-graph",
            pod_id=pod.id,
            name="Mandarin Oriental Bangkok",
            display_name="Mandarin Oriental Bangkok",
            canonical_name="Mandarin Oriental Bangkok",
            type="Hotel",
            type_label="Hotel",
        )
        restaurant = Entity(
            conversation_id="workspace-v3-graph",
            pod_id=pod.id,
            name="Rosewood Bangkok",
            display_name="Rosewood Bangkok",
            canonical_name="Rosewood Bangkok",
            type="Hotel",
            type_label="Hotel",
        )
        self.db.add_all([hotel, restaurant])
        self.db.flush()
        self.db.add(
            Relation(
                conversation_id="workspace-v3-graph",
                pod_id=pod.id,
                from_entity_id=hotel.id,
                relation_type="partners_with",
                to_entity_id=restaurant.id,
                source_message_ids_json=[message.id],
                confidence=0.9,
            )
        )
        self.db.commit()

        run_workspace_sync_for_conversation(self.db, conversation_id="workspace-v3-graph", allow_enrichment=False)
        self.db.commit()

        graph = get_scoped_graph(self.db, scope_mode="pod", pod_id=pod.id, one_hop=False, include_external=False)
        self.assertTrue(any(edge.relation_type == "partners_with" for edge in graph.edges))

    def _reset_tables(self) -> None:
        self.db.execute(delete(Evidence))
        self.db.execute(delete(Relation))
        self.db.execute(delete(CollectionItemValue))
        self.db.execute(delete(CollectionColumn))
        self.db.execute(delete(CollectionItem))
        self.db.execute(delete(Collection))
        self.db.execute(delete(PropertyCatalog))
        self.db.execute(delete(Fact))
        self.db.execute(delete(Entity))
        self.db.execute(delete(Message))
        self.db.execute(delete(Conversation))
        self.db.execute(delete(Pod))
        self.db.commit()


if __name__ == "__main__":
    unittest.main()
