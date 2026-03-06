"""Latest materialized property values per library item."""

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin


class ItemProperty(Base, IdMixin):
    """One latest property value for a library item and key."""

    __tablename__ = "item_properties"
    __table_args__ = (
        UniqueConstraint("library_item_id", "property_key", name="uq_item_properties_item_key"),
    )

    library_item_id: Mapped[int] = mapped_column(
        ForeignKey("library_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    property_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    property_label: Mapped[str] = mapped_column(String(255), nullable=False)
    property_value: Mapped[str] = mapped_column(String(2048), nullable=False)
    claim_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    claim_id: Mapped[int] = mapped_column(nullable=False, index=True)
    last_observed_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
