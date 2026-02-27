"""Knowledge query response schemas."""

from datetime import datetime

from pydantic import BaseModel

from app.schemas.entity import EntityRead
from app.schemas.fact import FactWithSubjectRead
from app.schemas.relation import RelationWithEntitiesRead


class FactTimelineItem(BaseModel):
    """Fact item with timeline timestamp."""

    fact: FactWithSubjectRead
    timestamp: datetime | None


class EntityGraphData(BaseModel):
    """Entity neighborhood graph payload."""

    entity: EntityRead
    outgoing_relations: list[RelationWithEntitiesRead]
    incoming_relations: list[RelationWithEntitiesRead]
    related_entities: list[EntityRead]
    supporting_facts: list[FactWithSubjectRead]


class RelationCluster(BaseModel):
    """Grouped relation summary."""

    relation_label: str
    relation_count: int
    sample_edges: list[str]


class ConversationSchemaChanges(BaseModel):
    """Schema labels touched by a conversation."""

    node_labels: list[str]
    field_labels: list[str]
    relation_labels: list[str]


class ConversationSummaryData(BaseModel):
    """Conversation-level knowledge summary payload."""

    conversation_id: str
    key_entities: list[EntityRead]
    key_facts: list[FactWithSubjectRead]
    schema_changes_triggered: ConversationSchemaChanges
    relation_clusters: list[RelationCluster]
