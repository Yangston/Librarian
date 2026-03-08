"""Run a live workspace enrichment smoke test against an isolated in-memory DB.

Usage (from repo root):
    backend/.venv/Scripts/python.exe backend/scripts/smoke_workspace_enrichment.py

Usage (from backend/):
    .venv/Scripts/python.exe scripts/smoke_workspace_enrichment.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import get_settings
from app.models.base import Base
from app.models.collection import Collection
from app.models.collection_column import CollectionColumn
from app.models.collection_item_value_suggestion import CollectionItemValueSuggestion
from app.models.collection_item_relation_suggestion import CollectionItemRelationSuggestion
from app.models.conversation import Conversation
from app.models.entity import Entity
from app.models.fact import Fact
from app.models.message import Message
from app.models.pod import Pod
from app.services.workspace_sync import (
    create_workspace_enrichment_run,
    run_workspace_enrichment_run,
    run_workspace_sync_for_conversation,
)
from app.services.workspace_v3 import accept_collection_suggestions, get_workspace_row_detail, list_workspace_rows


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _seed_workspace(db: Session) -> tuple[Pod, Collection]:
    pod = Pod(slug="workspace-enrichment-smoke", name="Workspace Enrichment Smoke", description=None, is_default=False)
    db.add(pod)
    db.flush()

    conversation = Conversation(conversation_id="workspace-enrichment-smoke", pod_id=pod.id)
    db.add(conversation)
    db.flush()

    message = Message(
        conversation_id=conversation.conversation_id,
        role="user",
        content=(
            "Track Mandarin Oriental Bangkok and Rosewood Bangkok. "
            "Mandarin Oriental Bangkok is in Bangkok and Rosewood Bangkok is in Bangkok."
        ),
    )
    db.add(message)
    db.flush()

    mandarin = Entity(
        conversation_id=conversation.conversation_id,
        pod_id=pod.id,
        name="Mandarin Oriental Bangkok",
        display_name="Mandarin Oriental Bangkok",
        canonical_name="Mandarin Oriental Bangkok",
        type="Hotel",
        type_label="Hotel",
    )
    rosewood = Entity(
        conversation_id=conversation.conversation_id,
        pod_id=pod.id,
        name="Rosewood Bangkok",
        display_name="Rosewood Bangkok",
        canonical_name="Rosewood Bangkok",
        type="Hotel",
        type_label="Hotel",
    )
    db.add_all([mandarin, rosewood])
    db.flush()

    db.add_all(
        [
            Fact(
                conversation_id=conversation.conversation_id,
                pod_id=pod.id,
                subject_entity_id=mandarin.id,
                predicate="location",
                object_value="Bangkok",
                source_message_ids_json=[message.id],
                confidence=0.95,
            ),
            Fact(
                conversation_id=conversation.conversation_id,
                pod_id=pod.id,
                subject_entity_id=rosewood.id,
                predicate="location",
                object_value="Bangkok",
                source_message_ids_json=[message.id],
                confidence=0.95,
            ),
        ]
    )
    db.commit()

    sync_result = run_workspace_sync_for_conversation(
        db,
        conversation_id=conversation.conversation_id,
        allow_enrichment=False,
    )
    db.commit()

    collection = db.scalar(select(Collection).where(Collection.pod_id == pod.id))
    _assert(collection is not None, "Workspace sync did not create a collection.")
    _assert(sync_result.values_upserted >= 2, "Workspace sync did not materialize accepted conversation values.")

    existing_keys = {
        str(column.key)
        for column in db.scalars(select(CollectionColumn).where(CollectionColumn.collection_id == collection.id)).all()
    }
    next_sort_order = len(existing_keys) + 10
    for key, label in [("website", "Website"), ("rating", "Rating")]:
        if key in existing_keys:
            continue
        db.add(
            CollectionColumn(
                collection_id=collection.id,
                key=key,
                label=label,
                data_type="url" if key == "website" else "text",
                kind="property",
                sort_order=next_sort_order,
                required=False,
                is_relation=False,
                origin="legacy",
                planner_locked=False,
                user_locked=False,
                enrichment_policy_json={"enabled": True},
            )
        )
        next_sort_order += 10
    db.commit()
    return pod, collection


def main() -> None:
    settings = get_settings()
    _assert(bool(settings.openai_api_key), "OPENAI_API_KEY is not configured in backend/.env.")

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(engine)

    try:
        with SessionLocal() as db:
            pod, collection = _seed_workspace(db)

            rows_before = list_workspace_rows(db, collection_id=collection.id, limit=50, offset=0, query=None)
            _assert(rows_before is not None, "Failed to read workspace rows after sync.")
            _assert(rows_before.pending_suggestion_count == 0, "Workspace should not have pending suggestions before enrichment.")
            _assert(
                any(cell.display_value == "Bangkok" for row in rows_before.rows for cell in row.cells),
                "Accepted conversation values were not readable before enrichment.",
            )

            run = create_workspace_enrichment_run(
                db,
                pod_id=pod.id,
                collection_id=collection.id,
                requested_by="smoke",
            )
            db.commit()
            completed_run = run_workspace_enrichment_run(db, run_id=run.id)
            db.commit()
            _assert(completed_run is not None, "Enrichment run did not return a result.")
            _assert(completed_run.status == "completed", f"Enrichment run failed: {completed_run.error_message}")

            summary = dict(completed_run.summary_json or {})
            value_suggestions = int(summary.get("value_suggestions_created") or 0)
            relation_suggestions = int(summary.get("relation_suggestions_created") or 0)
            _assert(value_suggestions > 0, "Live enrichment did not create value suggestions.")
            _assert(relation_suggestions > 0, "Live enrichment did not create relation suggestions.")

            pending_rows = list_workspace_rows(db, collection_id=collection.id, limit=50, offset=0, query=None)
            _assert(pending_rows is not None, "Workspace rows were unreadable after enrichment.")
            _assert(pending_rows.pending_suggestion_count > 0, "Pending suggestions were not visible after enrichment.")
            first_row = pending_rows.rows[0]
            row_detail = get_workspace_row_detail(db, row_id=first_row.id)
            _assert(row_detail is not None, "Row detail was unreadable after enrichment.")
            _assert(
                any(cell.pending_suggestion_count > 0 for cell in row_detail.cells),
                "Pending value suggestions were not visible on row detail.",
            )
            _assert(
                row_detail.pending_relation_suggestion_count > 0,
                "Pending relation suggestions were not visible on row detail.",
            )

            accept_result = accept_collection_suggestions(db, collection_id=collection.id)
            _assert(accept_result.applied > 0, "Accepting collection suggestions did not apply any changes.")

            accepted_rows = list_workspace_rows(db, collection_id=collection.id, limit=50, offset=0, query=None)
            _assert(accepted_rows is not None, "Workspace rows were unreadable after accepting suggestions.")
            _assert(accepted_rows.pending_suggestion_count == 0, "Pending suggestions remained after acceptance.")
            _assert(
                any(cell.source_kind == "external" for row in accepted_rows.rows for cell in row.cells),
                "Accepted enrichment values were not materialized into live cells.",
            )

            output = {
                "collection": {"id": collection.id, "name": collection.name, "slug": collection.slug},
                "run": completed_run.model_dump(mode="json"),
                "accept_result": accept_result.model_dump(mode="json"),
                "rows_before": rows_before.model_dump(mode="json"),
                "rows_after_enrich": pending_rows.model_dump(mode="json"),
                "rows_after_accept": accepted_rows.model_dump(mode="json"),
                "value_suggestion_rows": len(list(db.scalars(select(CollectionItemValueSuggestion)).all())),
                "relation_suggestion_rows": len(list(db.scalars(select(CollectionItemRelationSuggestion)).all())),
            }
            print(json.dumps(output, indent=2))
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


if __name__ == "__main__":
    main()
