"""Tests for scoped graph organization queries."""

from __future__ import annotations

import unittest

from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.collection import Collection
from app.models.collection_item import CollectionItem
from app.models.conversation import Conversation
from app.models.conversation_entity_link import ConversationEntityLink
from app.models.entity import Entity
from app.models.pod import Pod
from app.models.relation import Relation
from app.models.workspace_edge import WorkspaceEdge
from app.services.conversations import ensure_conversation_assignment
from app.services.organization import create_pod, get_scoped_graph, rebuild_pod_themes


class ScopedGraphTests(unittest.TestCase):
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

    def test_scoped_graph_modes(self) -> None:
        pod = create_pod(self.db, name="Scoped Graph Pod", description=None)
        ensure_conversation_assignment(
            self.db,
            conversation_id="phase38-graph",
            pod_id=pod.id,
            require_pod_for_new=True,
        )
        entities = [
            Entity(
                conversation_id="phase38-graph",
                name="Apple Inc.",
                display_name="Apple Inc.",
                canonical_name="Apple Inc.",
                type="Company",
                type_label="Company",
            ),
            Entity(
                conversation_id="phase38-graph",
                name="NVIDIA",
                display_name="NVIDIA",
                canonical_name="NVIDIA",
                type="Company",
                type_label="Company",
            ),
            Entity(
                conversation_id="phase38-graph",
                name="TSMC",
                display_name="TSMC",
                canonical_name="TSMC",
                type="Supplier",
                type_label="Supplier",
            ),
        ]
        self.db.add_all(entities)
        self.db.flush()
        self.db.add_all(
            [
                ConversationEntityLink(conversation_id="phase38-graph", entity_id=entities[0].id),
                ConversationEntityLink(conversation_id="phase38-graph", entity_id=entities[1].id),
                ConversationEntityLink(conversation_id="phase38-graph", entity_id=entities[2].id),
            ]
        )

        self.db.add_all(
            [
                Relation(
                    conversation_id="phase38-graph",
                    from_entity_id=entities[0].id,
                    to_entity_id=entities[1].id,
                    relation_type="compared_with",
                    scope="conversation",
                    confidence=0.8,
                    qualifiers_json={},
                    source_message_ids_json=[],
                ),
                Relation(
                    conversation_id="phase38-graph",
                    from_entity_id=entities[1].id,
                    to_entity_id=entities[2].id,
                    relation_type="depends_on",
                    scope="conversation",
                    confidence=0.7,
                    qualifiers_json={},
                    source_message_ids_json=[],
                ),
            ]
        )
        self.db.flush()
        rebuild_pod_themes(self.db, pod_id=pod.id)
        self.db.commit()

        focus_theme = self.db.scalar(
            select(Collection)
            .join(CollectionItem, CollectionItem.collection_id == Collection.id)
            .where(Collection.pod_id == pod.id, Collection.is_auto_generated.is_(True))
            .group_by(Collection.id)
            .having(func.count(CollectionItem.entity_id) >= 2)
            .order_by(Collection.id.asc())
        )
        assert focus_theme is not None

        global_graph = get_scoped_graph(self.db, scope_mode="global")
        self.assertEqual(len(global_graph.nodes), 3)
        self.assertEqual(len(global_graph.edges), 2)

        pod_graph = get_scoped_graph(self.db, scope_mode="pod", pod_id=pod.id)
        self.assertEqual(len(pod_graph.nodes), 3)
        self.assertEqual(len(pod_graph.edges), 2)

        collection_graph = get_scoped_graph(
            self.db,
            scope_mode="collection",
            collection_id=focus_theme.id,
            one_hop=False,
            include_external=False,
        )
        self.assertEqual(len(collection_graph.nodes), 2)
        self.assertEqual(len(collection_graph.edges), 1)

        expanded_graph = get_scoped_graph(
            self.db,
            scope_mode="collection",
            collection_id=focus_theme.id,
            one_hop=True,
            include_external=True,
        )
        self.assertEqual(len(expanded_graph.nodes), 3)
        self.assertEqual(len(expanded_graph.edges), 2)
        self.assertTrue(any(node.external for node in expanded_graph.nodes))

    def _reset_tables(self) -> None:
        self.db.execute(delete(WorkspaceEdge))
        self.db.execute(delete(CollectionItem))
        self.db.execute(delete(Collection))
        self.db.execute(delete(Relation))
        self.db.execute(delete(ConversationEntityLink))
        self.db.execute(delete(Entity))
        self.db.execute(delete(Conversation))
        self.db.execute(delete(Pod))
        self.db.commit()


if __name__ == "__main__":
    unittest.main()
