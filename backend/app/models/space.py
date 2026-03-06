"""User-facing workspace space model projected from pods."""

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, IdMixin, UpdatedAtMixin


class Space(Base, IdMixin, CreatedAtMixin, UpdatedAtMixin):
    """User-facing container that maps 1:1 to a pod."""

    __tablename__ = "spaces"

    pod_id: Mapped[int] = mapped_column(
        ForeignKey("pods.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
