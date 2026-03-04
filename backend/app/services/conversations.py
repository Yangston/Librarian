"""Conversation registry services for pod assignment and lookup."""

from __future__ import annotations

from threading import Lock

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.conversation import Conversation
from app.models.pod import Pod

_LEGACY_POD_DEFAULT_TABLES = (
    "messages",
    "extractor_runs",
    "predicate_registry_entries",
    "schema_nodes",
    "schema_fields",
    "schema_relations",
    "schema_proposals",
)
_legacy_defaults_lock = Lock()
_legacy_defaults_normalized = False


class ConversationAssignmentError(ValueError):
    """Base error for conversation assignment constraints."""


class ConversationPodRequiredError(ConversationAssignmentError):
    """Raised when a new conversation is created without pod_id."""


class ConversationPodConflictError(ConversationAssignmentError):
    """Raised when caller passes a mismatched pod_id for existing conversation."""


class ConversationPodNotFoundError(ConversationAssignmentError):
    """Raised when caller references a pod that does not exist."""


def ensure_conversation_assignment(
    db: Session,
    *,
    conversation_id: str,
    pod_id: int | None,
    require_pod_for_new: bool = True,
) -> Conversation:
    """Ensure a conversation row exists and is bound to exactly one pod."""

    _ensure_legacy_pod_defaults_target_imported(db)

    clean_conversation_id = conversation_id.strip()
    existing = db.scalar(
        select(Conversation).where(Conversation.conversation_id == clean_conversation_id)
    )
    if existing is not None:
        if pod_id is not None and existing.pod_id != pod_id:
            raise ConversationPodConflictError(
                f"Conversation {clean_conversation_id!r} already belongs to pod {existing.pod_id}."
            )
        return existing

    if pod_id is None and require_pod_for_new:
        raise ConversationPodRequiredError("pod_id is required when creating a new conversation.")
    if pod_id is None:
        pod_id = _get_or_create_imported_pod_id(db)

    pod_exists = db.scalar(select(Pod.id).where(Pod.id == pod_id))
    if pod_exists is None:
        raise ConversationPodNotFoundError(f"Pod {pod_id} does not exist.")

    created = Conversation(conversation_id=clean_conversation_id, pod_id=pod_id)
    db.add(created)
    db.flush()
    return created


def get_conversation(db: Session, conversation_id: str) -> Conversation | None:
    """Return a conversation row by conversation id."""

    clean_conversation_id = conversation_id.strip()
    if not clean_conversation_id:
        return None
    return db.scalar(
        select(Conversation).where(Conversation.conversation_id == clean_conversation_id)
    )


def get_conversation_pod_id(db: Session, conversation_id: str) -> int | None:
    """Return pod id for the conversation if mapped."""

    row = get_conversation(db, conversation_id)
    return int(row.pod_id) if row is not None else None


def list_conversation_ids_for_pod(db: Session, pod_id: int) -> list[str]:
    """List conversation ids assigned to one pod."""

    return list(
        db.scalars(
            select(Conversation.conversation_id)
            .where(Conversation.pod_id == pod_id)
            .order_by(Conversation.conversation_id.asc())
        ).all()
    )


def _get_or_create_imported_pod_id(db: Session) -> int:
    imported = db.scalar(select(Pod).where(Pod.slug == "imported"))
    if imported is not None:
        return int(imported.id)
    imported = Pod(
        slug="imported",
        name="Imported",
        description="Backfilled and internal conversations.",
        is_default=True,
    )
    db.add(imported)
    db.flush()
    return int(imported.id)


def _ensure_legacy_pod_defaults_target_imported(db: Session) -> None:
    """Normalize legacy pod_id defaults to imported pod and retire compatibility pods."""

    global _legacy_defaults_normalized
    bind = db.get_bind()
    if bind.dialect.name != "postgresql":
        return
    if _legacy_defaults_normalized:
        return

    with _legacy_defaults_lock:
        if _legacy_defaults_normalized:
            return

        imported_pod_id = _get_or_create_imported_pod_id(db)
        compat_ids = [
            int(value)
            for value in db.scalars(
                select(Pod.id).where(Pod.slug.like("compat-pod-%"))
            ).all()
        ]
        compat_sql = ",".join(str(value) for value in compat_ids)

        for table_name in _LEGACY_POD_DEFAULT_TABLES:
            has_column = db.execute(
                text(
                    """
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = current_schema()
                      AND table_name = :table_name
                      AND column_name = 'pod_id'
                    """
                ),
                {"table_name": table_name},
            ).scalar_one_or_none()
            if has_column is None:
                continue

            db.execute(
                text(f'UPDATE "{table_name}" SET pod_id = :pod_id WHERE pod_id IS NULL'),
                {"pod_id": imported_pod_id},
            )
            if compat_sql:
                db.execute(
                    text(
                        f'UPDATE "{table_name}" SET pod_id = :pod_id WHERE pod_id IN ({compat_sql})'
                    ),
                    {"pod_id": imported_pod_id},
                )
            db.execute(
                text(
                    f'ALTER TABLE "{table_name}" ALTER COLUMN pod_id SET DEFAULT {int(imported_pod_id)}'
                )
            )

        if compat_sql:
            has_conversations = (
                db.execute(
                    text(
                        """
                        SELECT 1
                        FROM information_schema.tables
                        WHERE table_schema = current_schema()
                          AND table_name = 'conversations'
                        """
                    )
                ).scalar_one_or_none()
                is not None
            )
            has_collections = (
                db.execute(
                    text(
                        """
                        SELECT 1
                        FROM information_schema.tables
                        WHERE table_schema = current_schema()
                          AND table_name = 'collections'
                        """
                    )
                ).scalar_one_or_none()
                is not None
            )
            if has_conversations and has_collections:
                db.execute(
                    text(
                        f"""
                        DELETE FROM pods
                        WHERE id IN ({compat_sql})
                          AND NOT EXISTS (SELECT 1 FROM conversations WHERE conversations.pod_id = pods.id)
                          AND NOT EXISTS (SELECT 1 FROM collections WHERE collections.pod_id = pods.id)
                        """
                    )
                )

        _legacy_defaults_normalized = True
        db.flush()
