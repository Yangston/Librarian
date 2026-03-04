"""Workspace containment edge model."""

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, IdMixin


class WorkspaceEdge(Base, IdMixin, CreatedAtMixin):
    """Non-semantic containment edges for workspace navigation."""

    __tablename__ = "workspace_edges"
    __table_args__ = (
        UniqueConstraint(
            "src_kind",
            "src_id",
            "dst_kind",
            "dst_id",
            "edge_type",
            "namespace",
            name="uq_workspace_edges_tuple",
        ),
    )

    src_kind: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    src_id: Mapped[int] = mapped_column(nullable=False, index=True)
    dst_kind: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    dst_id: Mapped[int] = mapped_column(nullable=False, index=True)
    edge_type: Mapped[str] = mapped_column(String(32), default="CONTAINS", nullable=False)
    namespace: Mapped[str] = mapped_column(String(32), default="workspace", nullable=False, index=True)
