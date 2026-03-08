"""Evidence linkage model."""

from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, Float, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin


class Evidence(Base, IdMixin):
    """Evidence rows linking fact/relation claims to sources."""

    __tablename__ = "evidence"
    __table_args__ = (
        CheckConstraint(
            "fact_id IS NOT NULL OR relation_id IS NOT NULL OR collection_item_value_id IS NOT NULL OR collection_item_relation_id IS NOT NULL",
            name="ck_evidence_has_claim",
        ),
    )

    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fact_id: Mapped[int | None] = mapped_column(
        ForeignKey("facts.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    relation_id: Mapped[int | None] = mapped_column(
        ForeignKey("relations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    collection_item_value_id: Mapped[int | None] = mapped_column(
        ForeignKey("collection_item_values.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    collection_item_relation_id: Mapped[int | None] = mapped_column(
        ForeignKey("collection_item_relations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    message_id: Mapped[int | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    meta_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
