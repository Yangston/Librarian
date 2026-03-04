"""Tests for theme row listing and membership mutations."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.collection import Collection
from app.models.collection_item import CollectionItem
from app.models.conversation import Conversation
from app.models.conversation_entity_link import ConversationEntityLink
from app.models.entity import Entity
from app.models.fact import Fact
from app.models.pod import Pod
from app.models.workspace_edge import WorkspaceEdge
from app.services.conversations import ensure_conversation_assignment
from app.services.organization import (
    create_pod,
    list_collection_items,
    rebuild_pod_themes,
    upsert_collection_item,
)


class CollectionItemsTests(unittest.TestCase):
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

    def test_collection_items_listing_and_duplicate_prevention(self) -> None:
        pod = create_pod(self.db, name="Item Tests", description=None)
        ensure_conversation_assignment(
            self.db,
            conversation_id="phase38-items",
            pod_id=pod.id,
            require_pod_for_new=True,
        )
        entities = [
            Entity(
                conversation_id="phase38-items",
                name="Apple Inc.",
                display_name="Apple Inc.",
                canonical_name="Apple Inc.",
                type="Company",
                type_label="Company",
            ),
            Entity(
                conversation_id="phase38-items",
                name="NVIDIA",
                display_name="NVIDIA",
                canonical_name="NVIDIA",
                type="Company",
                type_label="Company",
            ),
        ]
        self.db.add_all(entities)
        self.db.flush()

        self.db.add_all(
            [
                ConversationEntityLink(conversation_id="phase38-items", entity_id=entities[0].id),
                ConversationEntityLink(conversation_id="phase38-items", entity_id=entities[1].id),
                Fact(
                    conversation_id="phase38-items",
                    subject_entity_id=entities[0].id,
                    predicate="sentiment",
                    object_value="positive",
                    scope="conversation",
                    confidence=0.81,
                    source_message_ids_json=[],
                ),
                Fact(
                    conversation_id="phase38-items",
                    subject_entity_id=entities[1].id,
                    predicate="sentiment",
                    object_value="mixed",
                    scope="conversation",
                    confidence=0.73,
                    source_message_ids_json=[],
                    created_at=datetime(2026, 3, 3, 13, 0, tzinfo=timezone.utc),
                ),
            ]
        )
        self.db.flush()

        rebuild_pod_themes(self.db, pod_id=pod.id)
        theme_collection = self.db.scalar(
            select(Collection)
            .join(CollectionItem, CollectionItem.collection_id == Collection.id)
            .where(Collection.pod_id == pod.id, Collection.is_auto_generated.is_(True))
            .group_by(Collection.id)
            .having(func.count(CollectionItem.entity_id) >= 2)
            .order_by(Collection.id.asc())
        )
        assert theme_collection is not None
        theme_collection_id = theme_collection.id

        first_add = upsert_collection_item(self.db, collection_id=theme_collection_id, entity_id=entities[0].id)
        second_add = upsert_collection_item(self.db, collection_id=theme_collection_id, entity_id=entities[0].id)
        third_add = upsert_collection_item(self.db, collection_id=theme_collection_id, entity_id=entities[1].id)
        self.db.commit()

        assert first_add is not None
        assert second_add is not None
        assert third_add is not None
        self.assertFalse(first_add.added)
        self.assertFalse(second_add.added)
        self.assertFalse(third_add.added)

        payload = list_collection_items(
            self.db,
            collection_id=theme_collection_id,
            limit=25,
            offset=0,
            sort="canonical_name",
            order="asc",
            query="",
            selected_fields=["sentiment"],
        )
        assert payload is not None
        self.assertEqual(payload.total, 2)
        self.assertIn("sentiment", payload.available_fields)
        self.assertEqual(payload.items[0].canonical_name, "Apple Inc.")
        self.assertEqual(payload.items[0].dynamic_fields.get("sentiment"), "positive")

    def _reset_tables(self) -> None:
        self.db.execute(delete(WorkspaceEdge))
        self.db.execute(delete(CollectionItem))
        self.db.execute(delete(Collection))
        self.db.execute(delete(Fact))
        self.db.execute(delete(ConversationEntityLink))
        self.db.execute(delete(Entity))
        self.db.execute(delete(Conversation))
        self.db.execute(delete(Pod))
        self.db.commit()


if __name__ == "__main__":
    unittest.main()
