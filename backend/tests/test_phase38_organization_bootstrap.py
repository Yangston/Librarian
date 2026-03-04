"""Tests for pod creation/deletion and auto-generated themes."""

from __future__ import annotations

import unittest

from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.collection import Collection
from app.models.collection_item import CollectionItem
from app.models.conversation import Conversation
from app.models.conversation_entity_link import ConversationEntityLink
from app.models.entity import Entity
from app.models.fact import Fact
from app.models.message import Message
from app.models.pod import Pod
from app.models.workspace_edge import WorkspaceEdge
from app.schemas.message import MessageCreate
from app.services.conversations import ensure_conversation_assignment
from app.services.messages import create_messages
from app.services.organization import create_pod, delete_pod_with_conversations, rebuild_pod_themes


class OrganizationBootstrapTests(unittest.TestCase):
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

    def test_rebuild_pod_themes_creates_auto_generated_theme_tables(self) -> None:
        pod = create_pod(self.db, name="AI Stock Research", description="test")
        ensure_conversation_assignment(
            self.db,
            conversation_id="phase38-org-bootstrap",
            pod_id=pod.id,
            require_pod_for_new=True,
        )
        entities = [
            Entity(
                conversation_id="phase38-org-bootstrap",
                name="Apple Inc.",
                display_name="Apple Inc.",
                canonical_name="Apple Inc.",
                type="Company",
                type_label="Company",
            ),
            Entity(
                conversation_id="phase38-org-bootstrap",
                name="Macro Event",
                display_name="Macro Event",
                canonical_name="Macro Event",
                type="MacroEvent",
                type_label="MacroEvent",
            ),
            Entity(
                conversation_id="phase38-org-bootstrap",
                name="Unmapped Task",
                display_name="Unmapped Task",
                canonical_name="Unmapped Task",
                type="Unknown",
                type_label="UnmappedType",
            ),
        ]
        self.db.add_all(entities)
        self.db.flush()
        self.db.add_all(
            [
                ConversationEntityLink(
                    conversation_id="phase38-org-bootstrap",
                    entity_id=entity.id,
                )
                for entity in entities
            ]
        )
        self.db.add_all(
            [
                Fact(
                    conversation_id="phase38-org-bootstrap",
                    subject_entity_id=entities[0].id,
                    predicate="ticker",
                    object_value="AAPL",
                    scope="conversation",
                    confidence=0.9,
                    source_message_ids_json=[],
                ),
                Fact(
                    conversation_id="phase38-org-bootstrap",
                    subject_entity_id=entities[1].id,
                    predicate="impact",
                    object_value="high",
                    scope="conversation",
                    confidence=0.8,
                    source_message_ids_json=[],
                ),
            ]
        )
        self.db.flush()

        rebuild_pod_themes(self.db, pod_id=pod.id)
        self.db.commit()

        collections = list(
            self.db.scalars(
                select(Collection).where(
                    Collection.pod_id == pod.id,
                    Collection.is_auto_generated.is_(True),
                )
            ).all()
        )
        self.assertGreaterEqual(len(collections), 2)
        slugs = {collection.slug for collection in collections}
        self.assertFalse(any(slug in {"home", "stocks", "macro"} for slug in slugs))

        memberships = list(self.db.scalars(select(CollectionItem)).all())
        self.assertEqual(len(memberships), 3)

        pod_edges = list(
            self.db.scalars(
                select(WorkspaceEdge).where(
                    WorkspaceEdge.src_kind == "pod",
                    WorkspaceEdge.src_id == pod.id,
                    WorkspaceEdge.dst_kind == "collection",
                )
            ).all()
        )
        self.assertGreaterEqual(len(pod_edges), 2)

    def test_delete_pod_removes_assigned_conversations(self) -> None:
        pod = create_pod(self.db, name="To Delete", description=None)
        create_messages(
            self.db,
            "phase38-org-delete",
            [MessageCreate(role="user", content="hello pod delete")],
            pod_id=pod.id,
            require_pod_for_new=True,
        )

        result = delete_pod_with_conversations(self.db, pod_id=pod.id)
        assert result is not None
        self.assertTrue(result.deleted)
        self.assertEqual(result.pod_id, pod.id)
        self.assertEqual(result.conversations_deleted, 1)

        self.assertIsNone(self.db.scalar(select(Pod).where(Pod.id == pod.id)))
        self.assertIsNone(
            self.db.scalar(
                select(Conversation).where(Conversation.conversation_id == "phase38-org-delete")
            )
        )
        self.assertEqual(
            0,
            len(
                list(
                    self.db.scalars(
                        select(Message).where(Message.conversation_id == "phase38-org-delete")
                    ).all()
                )
            ),
        )

    def _reset_tables(self) -> None:
        self.db.execute(delete(WorkspaceEdge))
        self.db.execute(delete(CollectionItem))
        self.db.execute(delete(Collection))
        self.db.execute(delete(Fact))
        self.db.execute(delete(ConversationEntityLink))
        self.db.execute(delete(Entity))
        self.db.execute(delete(Message))
        self.db.execute(delete(Conversation))
        self.db.execute(delete(Pod))
        self.db.commit()


if __name__ == "__main__":
    unittest.main()
