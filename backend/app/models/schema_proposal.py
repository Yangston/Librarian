"""Schema proposal model for stabilization/canonicalization suggestions."""

from sqlalchemy import JSON, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, IdMixin


class SchemaProposal(Base, IdMixin, CreatedAtMixin):
    """Proposed schema canonicalization or merge action."""

    __tablename__ = "schema_proposals"

    proposal_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="proposed", nullable=False)
