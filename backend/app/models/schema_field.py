"""Schema field model for learned fact attribute labels."""

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, IdMixin
from app.models.embedding_type import EMBEDDING_COLUMN_TYPE


class SchemaField(Base, IdMixin, CreatedAtMixin):
    """Learned fact field label with optional canonical link."""

    __tablename__ = "schema_fields"

    label: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    canonical_of_id: Mapped[int | None] = mapped_column(
        ForeignKey("schema_fields.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    description: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    examples_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(EMBEDDING_COLUMN_TYPE, nullable=True)
    stats_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
