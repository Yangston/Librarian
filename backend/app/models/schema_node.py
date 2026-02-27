"""Schema node model for learned entity type labels."""

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, IdMixin
from app.models.embedding_type import EMBEDDING_COLUMN_TYPE


class SchemaNode(Base, IdMixin, CreatedAtMixin):
    """Learned type label registry entry."""

    __tablename__ = "schema_nodes"

    label: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    examples_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(EMBEDDING_COLUMN_TYPE, nullable=True)
    stats_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
