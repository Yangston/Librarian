"""Extractor run audit log model."""

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, IdMixin


class ExtractorRun(Base, IdMixin, CreatedAtMixin):
    """Stores metadata and payloads for each extraction execution."""

    __tablename__ = "extractor_runs"

    conversation_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    input_message_ids_json: Mapped[list[int]] = mapped_column(JSON, default=list, nullable=False)
    raw_output_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    validated_output_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
