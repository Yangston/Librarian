"""Tests for pending workspace enrichment suggestions."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.collection import Collection
from app.models.collection_item import CollectionItem
from app.models.collection_item_relation import CollectionItemRelation
from app.models.collection_item_relation_suggestion import CollectionItemRelationSuggestion
from app.models.collection_item_value import CollectionItemValue
from app.models.collection_item_value_suggestion import CollectionItemValueSuggestion
from app.models.collection_column import CollectionColumn
from app.models.conversation import Conversation
from app.models.entity import Entity
from app.models.message import Message
from app.models.pod import Pod
from app.models.property_catalog import PropertyCatalog
from app.models.source import Source
from app.models.workspace_enrichment_run import WorkspaceEnrichmentRun
from app.services.workspace_sync import (
    create_workspace_enrichment_run,
    generate_enrichment_suggestions,
    generate_relation_enrichment_suggestions,
    generate_value_enrichment_suggestions,
    rebuild_workspace_for_pod,
    run_workspace_enrichment_run,
)
from app.services.workspace_v3 import (
    accept_collection_suggestions,
    get_workspace_row_detail,
    list_workspace_rows,
    reject_collection_suggestions,
)


class _FakeResearchClient:
    def lookup(self, *, entity_name: str, collection_name: str, column_label: str, include_sources: bool = True):
        if column_label.lower() == "location":
            return {
                "value": "Bangkok",
                "confidence": 0.82,
                "sources": (
                    [{"title": "Example", "uri": "https://example.com/hotel", "snippet": "Located in Bangkok."}]
                    if include_sources
                    else []
                ),
            }
        return None


class _RecordingResearchClient:
    def __init__(self) -> None:
        self.lookup_row_calls: list[list[str]] = []
        self.lookup_calls: list[str] = []

    def lookup_row(
        self,
        *,
        entity_name: str,
        collection_name: str,
        column_labels: list[str],
        include_sources: bool = True,
    ):
        self.lookup_row_calls.append(list(column_labels))
        return {}

    def lookup(self, *, entity_name: str, collection_name: str, column_label: str, include_sources: bool = True):
        self.lookup_calls.append(column_label)
        return None


class _BatchResearchClient:
    def __init__(self) -> None:
        self.value_batch_calls: list[list[dict[str, object]]] = []
        self.relation_batch_calls: list[list[dict[str, object]]] = []

    def lookup_value_batch(self, *, scope_label: str, rows: list[dict[str, object]], include_sources: bool = True):
        self.value_batch_calls.append(rows)
        suggestions: list[dict[str, object]] = []
        for row in rows:
            row_id = int(row["row_id"])
            for column in row.get("missing_columns", []):
                if column["column_key"] == "website":
                    suggestions.append(
                        {
                            "row_id": row_id,
                            "column_key": "website",
                            "value": f"https://example.com/{row_id}",
                            "confidence": 0.9,
                            "sources": (
                                [
                                    {
                                        "title": "Example",
                                        "uri": f"https://example.com/{row_id}",
                                        "snippet": "Example site.",
                                    }
                                ]
                                if include_sources
                                else []
                            ),
                        }
                    )
        return suggestions

    def lookup_relation_batch(
        self,
        *,
        scope_label: str,
        rows: list[dict[str, object]],
        candidates: list[dict[str, object]],
        include_sources: bool = True,
    ):
        self.relation_batch_calls.append(candidates)
        if not candidates:
            return []
        first = candidates[0]
        return [
            {
                "candidate_id": first["candidate_id"],
                "relation_label": "related_to",
                "confidence": 0.8,
                "sources": (
                    [{"title": "Example", "uri": "https://example.com/relation", "snippet": "Example relation."}]
                    if include_sources
                    else []
                ),
            }
        ]

    def lookup_row(
        self,
        *,
        entity_name: str,
        collection_name: str,
        column_labels: list[str],
        include_sources: bool = True,
    ):
        raise AssertionError("lookup_row should not be used when batched value enrichment is available")

    def lookup(self, *, entity_name: str, collection_name: str, column_label: str, include_sources: bool = True):
        raise AssertionError("lookup should not be used when batched value enrichment is available")

    def lookup_relations(self, *, collection_name: str, entity_names: list[str], include_sources: bool = True):
        raise AssertionError("lookup_relations should not be used when batched relation enrichment is available")


class _FailingBatchResearchClient(_BatchResearchClient):
    def lookup_value_batch(self, *, scope_label: str, rows: list[dict[str, object]], include_sources: bool = True):
        raise RuntimeError("synthetic batch failure")


class WorkspaceEnrichmentSuggestionTests(unittest.TestCase):
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

    def test_pending_value_suggestion_is_created_without_live_application(self) -> None:
        collection = self._seed_basic_workspace()
        with patch("app.services.workspace_sync.get_default_research_client", return_value=_FakeResearchClient()), patch(
            "app.services.workspace_sync._research_relation_between_entities",
            return_value=None,
        ):
            run = create_workspace_enrichment_run(self.db, pod_id=1, collection_id=collection.id, requested_by="test")
            self.db.commit()
            summary = generate_enrichment_suggestions(
                self.db,
                pod_id=1,
                collection_id=collection.id,
                run_id=run.id,
            )
            self.db.commit()

        self.assertEqual(summary["value_suggestions_created"], 1)
        suggestion = self.db.scalar(select(CollectionItemValueSuggestion))
        assert suggestion is not None
        self.assertEqual(suggestion.suggested_display_value, "Bangkok")
        self.assertEqual(suggestion.status, "pending")
        self.assertIsNone(
            self.db.scalar(
                select(CollectionItemValue).where(CollectionItemValue.collection_item_id == suggestion.collection_item_id)
            )
        )

    def test_pending_suggestions_are_readable_in_table_and_row_detail_views(self) -> None:
        collection = self._seed_basic_workspace()
        row = self.db.scalar(select(CollectionItem))
        assert row is not None

        with patch("app.services.workspace_sync.get_default_research_client", return_value=_FakeResearchClient()), patch(
            "app.services.workspace_sync._research_relation_between_entities",
            return_value=None,
        ):
            run = create_workspace_enrichment_run(self.db, pod_id=1, collection_id=collection.id, requested_by="test")
            self.db.commit()
            generate_enrichment_suggestions(self.db, pod_id=1, collection_id=collection.id, run_id=run.id)
            self.db.commit()

        rows_payload = list_workspace_rows(self.db, collection_id=collection.id, limit=50, offset=0, query=None)
        assert rows_payload is not None
        self.assertEqual(rows_payload.pending_suggestion_count, 1)
        self.assertEqual(rows_payload.rows[0].cells[0].pending_suggestion_count, 1)
        self.assertEqual(
            rows_payload.rows[0].cells[0].pending_suggestions[0].suggested_display_value,
            "Bangkok",
        )

        row_detail = get_workspace_row_detail(self.db, row_id=row.id)
        assert row_detail is not None
        self.assertEqual(row_detail.cells[0].pending_suggestion_count, 1)
        self.assertEqual(row_detail.cells[0].pending_suggestions[0].suggested_display_value, "Bangkok")

    def test_accept_and_reject_collection_suggestions(self) -> None:
        collection = self._seed_basic_workspace()
        row = self.db.scalar(select(CollectionItem))
        assert row is not None

        # generate one value suggestion
        with patch("app.services.workspace_sync.get_default_research_client", return_value=_FakeResearchClient()), patch(
            "app.services.workspace_sync._research_relation_between_entities",
            return_value=None,
        ):
            run = create_workspace_enrichment_run(self.db, pod_id=1, collection_id=collection.id, requested_by="test")
            self.db.commit()
            generate_enrichment_suggestions(self.db, pod_id=1, collection_id=collection.id, run_id=run.id)
            self.db.commit()

        rows_before_accept = list_workspace_rows(self.db, collection_id=collection.id, limit=50, offset=0, query=None)
        assert rows_before_accept is not None
        self.assertEqual(rows_before_accept.pending_suggestion_count, 1)

        apply_result = accept_collection_suggestions(self.db, collection_id=collection.id)
        self.assertGreaterEqual(apply_result.applied, 1)
        live_value = self.db.scalar(select(CollectionItemValue))
        assert live_value is not None
        self.assertEqual(live_value.display_value, "Bangkok")
        accepted_suggestion = self.db.scalar(select(CollectionItemValueSuggestion))
        assert accepted_suggestion is not None
        self.assertEqual(accepted_suggestion.status, "accepted")
        rows_after_accept = list_workspace_rows(self.db, collection_id=collection.id, limit=50, offset=0, query=None)
        assert rows_after_accept is not None
        self.assertEqual(rows_after_accept.pending_suggestion_count, 0)
        row_detail_after_accept = get_workspace_row_detail(self.db, row_id=row.id)
        assert row_detail_after_accept is not None
        self.assertEqual(row_detail_after_accept.cells[0].display_value, "Bangkok")

        # create a new pending relation suggestion and reject it
        relation_suggestion = CollectionItemRelationSuggestion(
            enrichment_run_id=None,
            from_collection_item_id=row.id,
            to_collection_item_id=row.id,
            relation_label="same_location",
            source_kind="inferred",
            confidence=0.7,
            status="pending",
            dedupe_key="same-location-self",
            source_ids_json=[],
            meta_json={},
        )
        self.db.add(relation_suggestion)
        self.db.commit()

        reject_result = reject_collection_suggestions(self.db, collection_id=collection.id)
        self.assertGreaterEqual(reject_result.rejected, 1)
        rejected_relation = self.db.scalar(
            select(CollectionItemRelationSuggestion).where(
                CollectionItemRelationSuggestion.dedupe_key == "same-location-self"
            )
        )
        assert rejected_relation is not None
        self.assertEqual(rejected_relation.status, "rejected")
        self.assertEqual(0, len(list(self.db.scalars(select(CollectionItemRelation)).all())))

    def test_generic_legacy_columns_are_derived_without_external_research(self) -> None:
        collection = self._seed_basic_workspace()
        row = self.db.scalar(select(CollectionItem))
        assert row is not None

        self.db.add_all(
            [
                CollectionColumn(
                    collection_id=collection.id,
                    key="name",
                    label="Name",
                    data_type="text",
                    kind="property",
                    sort_order=100,
                    required=False,
                    is_relation=False,
                    origin="legacy",
                    planner_locked=False,
                    user_locked=False,
                    enrichment_policy_json={"enabled": True},
                ),
                CollectionColumn(
                    collection_id=collection.id,
                    key="type",
                    label="Type",
                    data_type="text",
                    kind="property",
                    sort_order=110,
                    required=False,
                    is_relation=False,
                    origin="legacy",
                    planner_locked=False,
                    user_locked=False,
                    enrichment_policy_json={"enabled": True},
                ),
            ]
        )
        self.db.commit()

        research_client = _RecordingResearchClient()
        with patch("app.services.workspace_sync.get_default_research_client", return_value=research_client), patch(
            "app.services.workspace_sync._research_relation_between_entities",
            return_value=None,
        ):
            run = create_workspace_enrichment_run(self.db, pod_id=1, collection_id=collection.id, requested_by="test")
            self.db.commit()
            summary = generate_enrichment_suggestions(
                self.db,
                pod_id=1,
                collection_id=collection.id,
                run_id=run.id,
            )
            self.db.commit()

        self.assertEqual(summary["value_suggestions_created"], 0)
        self.assertTrue(all("Name" not in call and "Type" not in call for call in research_client.lookup_row_calls))
        self.assertNotIn("Name", research_client.lookup_calls)
        self.assertNotIn("Type", research_client.lookup_calls)

        generic_columns = {
            column.key: column
            for column in self.db.scalars(
                select(CollectionColumn).where(CollectionColumn.collection_id == collection.id)
            ).all()
            if column.key in {"name", "type"}
        }
        self.assertFalse(generic_columns["name"].enrichment_policy_json.get("enabled", True))
        self.assertFalse(generic_columns["type"].enrichment_policy_json.get("enabled", True))

        generic_values = {
            int(value.collection_column_id): value
            for value in self.db.scalars(
                select(CollectionItemValue).where(CollectionItemValue.collection_item_id == row.id)
            ).all()
        }
        self.assertEqual(generic_values[generic_columns["name"].id].display_value, "Mandarin Oriental Bangkok")
        self.assertEqual(generic_values[generic_columns["name"].id].source_kind, "workspace")
        self.assertEqual(generic_values[generic_columns["type"].id].display_value, "Hotel")
        self.assertEqual(generic_values[generic_columns["type"].id].source_kind, "workspace")

    def test_system_chat_run_commits_workspace_sync_before_enrichment_failure(self) -> None:
        collection = self._seed_basic_workspace()
        with patch("app.services.workspace_sync.get_default_research_client", return_value=_FailingBatchResearchClient()):
            run = create_workspace_enrichment_run(
                self.db,
                pod_id=1,
                conversation_id="enrich-test",
                requested_by="system",
                run_kind="system_chat",
            )
            self.db.commit()
            result = run_workspace_enrichment_run(self.db, run_id=run.id)

        assert result is not None
        self.assertEqual(result.status, "failed")
        self.assertIn("workspace_sync", result.summary_json)
        rows_payload = list_workspace_rows(self.db, collection_id=collection.id, limit=50, offset=0, query=None)
        assert rows_payload is not None
        self.assertEqual(rows_payload.rows[0].title, "Mandarin Oriental Bangkok")

    def test_scope_batched_enrichment_uses_batch_calls(self) -> None:
        collection = self._seed_two_row_workspace()
        batch_client = _BatchResearchClient()
        with patch("app.services.workspace_sync.get_default_research_client", return_value=batch_client):
            value_summary = generate_value_enrichment_suggestions(
                self.db,
                pod_id=1,
                collection_id=collection.id,
                run_id=1,
            )
            relation_summary = generate_relation_enrichment_suggestions(
                self.db,
                pod_id=1,
                collection_id=collection.id,
                run_id=1,
            )
            self.db.commit()

        self.assertEqual(value_summary["value_batch_count"], 1)
        self.assertEqual(len(batch_client.value_batch_calls), 1)
        self.assertGreaterEqual(value_summary["value_suggestions_created"], 1)
        self.assertEqual(relation_summary["relation_batch_count"], 1)
        self.assertEqual(len(batch_client.relation_batch_calls), 1)
        self.assertGreaterEqual(relation_summary["relation_suggestions_created"], 1)

    def test_batched_enrichment_allows_source_free_suggestions(self) -> None:
        collection = self._seed_two_row_workspace()
        batch_client = _BatchResearchClient()
        with patch("app.services.workspace_sync.get_default_research_client", return_value=batch_client):
            value_summary = generate_value_enrichment_suggestions(
                self.db,
                pod_id=1,
                collection_id=collection.id,
                run_id=1,
                include_sources=False,
            )
            self.db.commit()

        self.assertEqual(value_summary["value_batch_count"], 1)
        self.assertGreaterEqual(value_summary["value_suggestions_created"], 1)
        suggestion = self.db.scalar(select(CollectionItemValueSuggestion))
        assert suggestion is not None
        self.assertEqual(suggestion.source_ids_json, [])

    def test_pod_relation_candidates_include_cross_collection_pairs(self) -> None:
        hotel_collection = self._seed_two_row_workspace()
        restaurant_collection = Collection(
            pod_id=1,
            parent_id=None,
            kind="TABLE",
            slug="food",
            name="Food",
            description=None,
            schema_json={},
            view_config_json={},
            sort_order=20,
            is_auto_generated=False,
        )
        self.db.add(restaurant_collection)
        self.db.flush()
        restaurant_row = CollectionItem(
            collection_id=restaurant_collection.id,
            entity_id=99,
            primary_entity_id=99,
            title="Jay Fai",
            summary="Location: Bangkok",
            detail_blurb="Jay Fai is in Bangkok.",
            notes_markdown=None,
            sort_key=None,
            sort_order=0,
        )
        self.db.add(restaurant_row)
        self.db.flush()
        location_column = CollectionColumn(
            collection_id=restaurant_collection.id,
            key="location",
            label="Location",
            data_type="text",
            kind="property",
            sort_order=0,
            required=False,
            is_relation=False,
            origin="manual",
            planner_locked=False,
            user_locked=False,
            enrichment_policy_json={"enabled": True},
        )
        self.db.add(location_column)
        self.db.flush()
        self.db.add(
            CollectionItemValue(
                collection_item_id=restaurant_row.id,
                collection_column_id=location_column.id,
                value_json="Bangkok",
                display_value="Bangkok",
                value_type="text",
                source_kind="manual",
                status="manual",
                edited_by_user=True,
            )
        )
        self.db.commit()

        batch_client = _BatchResearchClient()
        with patch("app.services.workspace_sync.get_default_research_client", return_value=batch_client):
            generate_relation_enrichment_suggestions(self.db, pod_id=1, run_id=1)

        self.assertTrue(
            any(
                candidate["from_collection_id"] != candidate["to_collection_id"]
                for batch in batch_client.relation_batch_calls
                for candidate in batch
            )
        )

    def _seed_basic_workspace(self) -> Collection:
        pod = Pod(slug="trip", name="Trip", description=None, is_default=False)
        self.db.add(pod)
        self.db.flush()
        self.db.add(Conversation(conversation_id="enrich-test", pod_id=pod.id))
        self.db.add(
            Message(
                conversation_id="enrich-test",
                role="user",
                content="Please track the Mandarin Oriental Bangkok hotel.",
            )
        )
        self.db.flush()
        entity = Entity(
            conversation_id="enrich-test",
            pod_id=pod.id,
            name="Mandarin Oriental Bangkok",
            display_name="Mandarin Oriental Bangkok",
            canonical_name="Mandarin Oriental Bangkok",
            type="Hotel",
            type_label="Hotel",
        )
        self.db.add(entity)
        self.db.commit()
        rebuild_workspace_for_pod(self.db, pod_id=pod.id, allow_enrichment=False)
        self.db.commit()
        collection = self.db.scalar(select(Collection))
        assert collection is not None
        location_column = self.db.scalar(
            select(CollectionColumn).where(
                CollectionColumn.collection_id == collection.id,
                CollectionColumn.key == "location",
            )
        )
        if location_column is None:
            self.db.add(
                CollectionColumn(
                    collection_id=collection.id,
                    key="location",
                    label="Location",
                    data_type="text",
                    kind="property",
                    sort_order=50,
                    required=False,
                    is_relation=False,
                    origin="legacy",
                    planner_locked=False,
                    user_locked=False,
                    enrichment_policy_json={"enabled": True},
                )
            )
            self.db.commit()
        return collection

    def _seed_two_row_workspace(self) -> Collection:
        pod = Pod(slug="trip", name="Trip", description=None, is_default=False)
        self.db.add(pod)
        self.db.flush()
        self.db.add(Conversation(conversation_id="enrich-two-row", pod_id=pod.id))
        self.db.add(
            Message(
                conversation_id="enrich-two-row",
                role="user",
                content="Track Mandarin Oriental Bangkok and Rosewood Bangkok in Bangkok.",
            )
        )
        self.db.flush()
        self.db.add_all(
            [
                Entity(
                    conversation_id="enrich-two-row",
                    pod_id=pod.id,
                    name="Mandarin Oriental Bangkok",
                    display_name="Mandarin Oriental Bangkok",
                    canonical_name="Mandarin Oriental Bangkok",
                    type="Hotel",
                    type_label="Hotel",
                ),
                Entity(
                    conversation_id="enrich-two-row",
                    pod_id=pod.id,
                    name="Rosewood Bangkok",
                    display_name="Rosewood Bangkok",
                    canonical_name="Rosewood Bangkok",
                    type="Hotel",
                    type_label="Hotel",
                ),
            ]
        )
        self.db.commit()
        rebuild_workspace_for_pod(self.db, pod_id=pod.id, allow_enrichment=False)
        self.db.commit()
        collection = self.db.scalar(select(Collection))
        assert collection is not None
        location_column = self.db.scalar(
            select(CollectionColumn).where(
                CollectionColumn.collection_id == collection.id,
                CollectionColumn.key == "location",
            )
        )
        if location_column is None:
            location_column = CollectionColumn(
                collection_id=collection.id,
                key="location",
                label="Location",
                data_type="text",
                kind="property",
                sort_order=50,
                required=False,
                is_relation=False,
                origin="legacy",
                planner_locked=False,
                user_locked=False,
                enrichment_policy_json={"enabled": True},
            )
            self.db.add(location_column)
            self.db.flush()
        website_column = self.db.scalar(
            select(CollectionColumn).where(
                CollectionColumn.collection_id == collection.id,
                CollectionColumn.key == "website",
            )
        )
        if website_column is None:
            self.db.add(
                CollectionColumn(
                    collection_id=collection.id,
                    key="website",
                    label="Website",
                    data_type="url",
                    kind="property",
                    sort_order=60,
                    required=False,
                    is_relation=False,
                    origin="legacy",
                    planner_locked=False,
                    user_locked=False,
                    enrichment_policy_json={"enabled": True},
                )
            )
        self.db.flush()
        assert location_column is not None
        for row in self.db.scalars(select(CollectionItem).where(CollectionItem.collection_id == collection.id)).all():
            self.db.add(
                CollectionItemValue(
                    collection_item_id=row.id,
                    collection_column_id=location_column.id,
                    value_json="Bangkok",
                    display_value="Bangkok",
                    value_type="text",
                    source_kind="manual",
                    status="manual",
                    edited_by_user=True,
                )
            )
        self.db.commit()
        return collection

    def _reset_tables(self) -> None:
        self.db.execute(delete(CollectionItemRelationSuggestion))
        self.db.execute(delete(CollectionItemValueSuggestion))
        self.db.execute(delete(WorkspaceEnrichmentRun))
        self.db.execute(delete(CollectionItemRelation))
        self.db.execute(delete(CollectionItemValue))
        self.db.execute(delete(Source))
        self.db.execute(delete(CollectionItem))
        self.db.execute(delete(CollectionColumn))
        self.db.execute(delete(Collection))
        self.db.execute(delete(PropertyCatalog))
        self.db.execute(delete(Entity))
        self.db.execute(delete(Message))
        self.db.execute(delete(Conversation))
        self.db.execute(delete(Pod))
        self.db.commit()


if __name__ == "__main__":
    unittest.main()
