"""Background enrichment run tracking for workspace suggestions."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, UpdatedAtMixin


class WorkspaceEnrichmentRun(Base, IdMixin, UpdatedAtMixin):
    """Tracks one queued/running/completed enrichment suggestion generation run."""

    __tablename__ = "workspace_enrichment_runs"

    pod_id: Mapped[int] = mapped_column(
        ForeignKey("pods.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversation_id: Mapped[str | None] = mapped_column(
        ForeignKey("conversations.conversation_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    collection_id: Mapped[int | None] = mapped_column(
        ForeignKey("collections.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    collection_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("collection_items.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    requested_by: Mapped[str] = mapped_column(String(32), default="system", nullable=False)
    run_kind: Mapped[str] = mapped_column(String(32), default="manual_space", nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(32), default="queued", nullable=False, index=True)
    error_message: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    summary_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
