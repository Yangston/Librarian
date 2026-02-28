"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import {
  deleteEntityRecord,
  deleteFact,
  deleteRelation,
  type EntityGraphData,
  type EntityRead,
  type FactTimelineItem,
  getEntitiesCatalog,
  getEntity,
  getEntityGraph,
  getEntityTimeline,
  getSchemaOverview,
  updateEntityRecord,
  updateFact,
  updateRelation
} from "../../../lib/api";
import { formatTimestamp } from "../../../lib/format";

type CombinedTimelineEvent = {
  id: string;
  timestamp: string;
  kind: "fact" | "outgoing_relation" | "incoming_relation";
  title: string;
  explainPath: string;
};

type GraphNodeVisual = {
  entity: EntityRead;
  x: number;
  y: number;
};

type GraphEdgeVisual = {
  key: string;
  neighborId: number;
  direction: "incoming" | "outgoing";
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  labelX: number;
  labelY: number;
  label: string;
};

function summarizeLabels(labels: string[]): string {
  if (labels.length === 0) {
    return "";
  }
  if (labels.length <= 2) {
    return labels.join(", ");
  }
  return `${labels.slice(0, 2).join(", ")} +${labels.length - 2}`;
}

function truncateLabel(value: string, max = 14): string {
  if (value.length <= max) {
    return value;
  }
  return `${value.slice(0, Math.max(0, max - 3))}...`;
}

export default function EntityDetailPage() {
  const router = useRouter();
  const params = useParams<{ entity_id: string }>();
  const entityId = useMemo(() => Number.parseInt(params.entity_id, 10), [params.entity_id]);
  const [entity, setEntity] = useState<EntityRead | null>(null);
  const [graph, setGraph] = useState<EntityGraphData | null>(null);
  const [timeline, setTimeline] = useState<FactTimelineItem[]>([]);
  const [fieldCanonicalByLabel, setFieldCanonicalByLabel] = useState<Record<string, string>>({});
  const [conversationCount, setConversationCount] = useState<number | null>(null);
  const [fieldFilter, setFieldFilter] = useState("");
  const [showRawFieldVariants, setShowRawFieldVariants] = useState(false);
  const [neighborLimit, setNeighborLimit] = useState(8);
  const [hoveredNeighborId, setHoveredNeighborId] = useState<number | null>(null);
  const [refreshNonce, setRefreshNonce] = useState(0);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [editingEntity, setEditingEntity] = useState(false);
  const [entityDraft, setEntityDraft] = useState({ canonical_name: "", type_label: "" });
  const [pendingDeleteEntity, setPendingDeleteEntity] = useState(false);
  const [editingFactId, setEditingFactId] = useState<number | null>(null);
  const [factDraft, setFactDraft] = useState({ predicate: "", object_value: "", confidence: "" });
  const [pendingDeleteFactId, setPendingDeleteFactId] = useState<number | null>(null);
  const [editingRelationId, setEditingRelationId] = useState<number | null>(null);
  const [relationDraft, setRelationDraft] = useState({
    relation_type: "",
    confidence: "",
    qualifiers_json: "{}"
  });
  const [pendingDeleteRelationId, setPendingDeleteRelationId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const loadedEntityIdRef = useRef<number | null>(null);

  useEffect(() => {
    if (!Number.isFinite(entityId) || entityId < 1) {
      setError("Invalid entity id.");
      setLoading(false);
      setRefreshing(false);
      return;
    }
    let active = true;
    async function load() {
      const isReloadForCurrentEntity = loadedEntityIdRef.current === entityId;
      if (isReloadForCurrentEntity) {
        setRefreshing(true);
      } else {
        setLoading(true);
        setEntity(null);
        setGraph(null);
        setTimeline([]);
        setConversationCount(null);
      }
      setError(null);
      try {
        const [entityData, graphData, timelineData, schemaData] = await Promise.all([
          getEntity(entityId),
          getEntityGraph(entityId),
          getEntityTimeline(entityId),
          getSchemaOverview({ limit: 1000, proposal_limit: 100 })
        ]);
        const entityCatalog = await getEntitiesCatalog({
          q: entityData.canonical_name,
          limit: 100,
          offset: 0
        });
        if (!active) {
          return;
        }
        setEntity(entityData);
        setGraph(graphData);
        setTimeline(timelineData);
        const map: Record<string, string> = {};
        schemaData.fields.forEach((field) => {
          map[field.label] = field.canonical_label ?? field.label;
        });
        setFieldCanonicalByLabel(map);
        const row = entityCatalog.items.find((item) => item.id === entityData.id);
        setConversationCount(row?.conversation_count ?? null);
        loadedEntityIdRef.current = entityId;
      } catch (err) {
        if (!active) {
          return;
        }
        setError(err instanceof Error ? err.message : "Failed to load entity detail.");
      } finally {
        if (active) {
          setLoading(false);
          setRefreshing(false);
        }
      }
    }
    void load();
    return () => {
      active = false;
    };
  }, [entityId, refreshNonce]);

  useEffect(() => {
    if (!entity) {
      setEntityDraft({ canonical_name: "", type_label: "" });
      setEditingEntity(false);
      setPendingDeleteEntity(false);
      return;
    }
    setEntityDraft({
      canonical_name: entity.canonical_name,
      type_label: entity.type_label || "untyped"
    });
    setEditingEntity(false);
    setPendingDeleteEntity(false);
  }, [entity]);

  function beginEditEntity() {
    if (!entity) {
      return;
    }
    setEditingEntity(true);
    setPendingDeleteEntity(false);
    setEntityDraft({
      canonical_name: entity.canonical_name,
      type_label: entity.type_label || "untyped"
    });
  }

  function cancelEditEntity() {
    if (!entity) {
      return;
    }
    setEditingEntity(false);
    setEntityDraft({
      canonical_name: entity.canonical_name,
      type_label: entity.type_label || "untyped"
    });
  }

  async function saveEditedEntity() {
    if (!entity) {
      return;
    }
    const nextName = entityDraft.canonical_name.trim();
    const nextType = entityDraft.type_label.trim();
    if (!nextName || !nextType) {
      setError("Canonical name and type label are required.");
      return;
    }
    setBusyKey("entity");
    setError(null);
    try {
      await updateEntityRecord(entity.id, {
        canonical_name: nextName,
        type_label: nextType
      });
      setEditingEntity(false);
      setRefreshNonce((current) => current + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update entity.");
    } finally {
      setBusyKey(null);
    }
  }

  function requestDeleteEntity() {
    setEditingEntity(false);
    setPendingDeleteEntity(true);
  }

  function cancelDeleteEntity() {
    setPendingDeleteEntity(false);
  }

  async function confirmDeleteEntity() {
    if (!entity) {
      return;
    }
    setBusyKey("entity");
    setError(null);
    try {
      await deleteEntityRecord(entity.id);
      router.push("/entities");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete entity.");
    } finally {
      setBusyKey(null);
    }
  }

  function beginEditFact(factId: number, predicate: string, objectValue: string, confidence: number) {
    setEditingFactId(factId);
    setPendingDeleteFactId(null);
    setFactDraft({
      predicate,
      object_value: objectValue,
      confidence: confidence.toFixed(2)
    });
  }

  function cancelEditFact() {
    setEditingFactId(null);
    setFactDraft({ predicate: "", object_value: "", confidence: "" });
  }

  async function saveEditedFact(
    factId: number,
    fallbackPredicate: string,
    fallbackValue: string,
    fallbackConfidence: number
  ) {
    const nextPredicate = factDraft.predicate.trim();
    const nextValue = factDraft.object_value.trim();
    const nextConfidence = Number.parseFloat(factDraft.confidence);
    if (!Number.isFinite(nextConfidence) || nextConfidence < 0 || nextConfidence > 1) {
      setError("Confidence must be between 0 and 1.");
      return;
    }
    setBusyKey(`fact-${factId}`);
    setError(null);
    try {
      await updateFact(factId, {
        predicate: nextPredicate || fallbackPredicate,
        object_value: nextValue || fallbackValue,
        confidence: nextConfidence ?? fallbackConfidence
      });
      cancelEditFact();
      setRefreshNonce((current) => current + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update fact.");
    } finally {
      setBusyKey(null);
    }
  }

  function requestDeleteFact(factId: number) {
    if (editingFactId === factId) {
      cancelEditFact();
    }
    setPendingDeleteFactId(factId);
  }

  function cancelDeleteFact() {
    setPendingDeleteFactId(null);
  }

  async function confirmDeleteFact(factId: number) {
    setBusyKey(`fact-${factId}`);
    setError(null);
    try {
      await deleteFact(factId);
      setPendingDeleteFactId((current) => (current === factId ? null : current));
      setRefreshNonce((current) => current + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete fact.");
    } finally {
      setBusyKey(null);
    }
  }

  function beginEditRelation(
    relationId: number,
    relationType: string,
    confidence: number,
    qualifiers: Record<string, unknown>
  ) {
    setEditingRelationId(relationId);
    setPendingDeleteRelationId(null);
    setRelationDraft({
      relation_type: relationType,
      confidence: confidence.toFixed(2),
      qualifiers_json: JSON.stringify(qualifiers ?? {})
    });
  }

  function cancelEditRelation() {
    setEditingRelationId(null);
    setRelationDraft({ relation_type: "", confidence: "", qualifiers_json: "{}" });
  }

  async function saveEditedRelation(
    relationId: number,
    fallbackType: string,
    fallbackConfidence: number,
    fallbackQualifiers: Record<string, unknown>
  ) {
    const nextType = relationDraft.relation_type.trim();
    const nextConfidence = Number.parseFloat(relationDraft.confidence);
    if (!Number.isFinite(nextConfidence) || nextConfidence < 0 || nextConfidence > 1) {
      setError("Confidence must be between 0 and 1.");
      return;
    }
    let parsedQualifiers: Record<string, unknown> = fallbackQualifiers;
    try {
      const parsed = JSON.parse(relationDraft.qualifiers_json || "{}");
      parsedQualifiers = parsed && typeof parsed === "object" ? (parsed as Record<string, unknown>) : {};
    } catch {
      setError("Qualifiers must be valid JSON.");
      return;
    }
    setBusyKey(`relation-${relationId}`);
    setError(null);
    try {
      await updateRelation(relationId, {
        relation_type: nextType || fallbackType,
        confidence: nextConfidence ?? fallbackConfidence,
        qualifiers_json: parsedQualifiers
      });
      cancelEditRelation();
      setRefreshNonce((current) => current + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update relation.");
    } finally {
      setBusyKey(null);
    }
  }

  function requestDeleteRelation(relationId: number) {
    if (editingRelationId === relationId) {
      cancelEditRelation();
    }
    setPendingDeleteRelationId(relationId);
  }

  function cancelDeleteRelation() {
    setPendingDeleteRelationId(null);
  }

  async function confirmDeleteRelation(relationId: number) {
    setBusyKey(`relation-${relationId}`);
    setError(null);
    try {
      await deleteRelation(relationId);
      setPendingDeleteRelationId((current) => (current === relationId ? null : current));
      setRefreshNonce((current) => current + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete relation.");
    } finally {
      setBusyKey(null);
    }
  }

  const factRows = useMemo(() => {
    const source = graph?.supporting_facts ?? [];
    return source
      .map((fact) => {
        const canonicalLabel = fieldCanonicalByLabel[fact.predicate] ?? fact.predicate;
        return {
          ...fact,
          canonicalLabel,
          rawLabel: fact.predicate
        };
      })
      .filter((fact) => (showRawFieldVariants ? true : fact.rawLabel === fact.canonicalLabel))
      .filter((fact) => {
        const query = fieldFilter.trim().toLowerCase();
        if (!query) {
          return true;
        }
        return (
          fact.canonicalLabel.toLowerCase().includes(query) ||
          fact.rawLabel.toLowerCase().includes(query)
        );
      })
      .sort((left, right) => new Date(right.created_at).valueOf() - new Date(left.created_at).valueOf());
  }, [fieldCanonicalByLabel, fieldFilter, graph?.supporting_facts, showRawFieldVariants]);

  const combinedTimeline = useMemo(() => {
    if (!graph) {
      return [] as CombinedTimelineEvent[];
    }
    const relationEvents = [...graph.outgoing_relations, ...graph.incoming_relations].map((relation) => {
      const isOutgoing = relation.from_entity_id === entityId;
      return {
        id: `relation-${relation.id}`,
        timestamp: relation.created_at,
        kind: isOutgoing ? ("outgoing_relation" as const) : ("incoming_relation" as const),
        title: isOutgoing
          ? `${relation.relation_type} -> ${relation.to_entity_name}`
          : `${relation.from_entity_name} -> ${relation.relation_type}`,
        explainPath: `/explain/relations/${relation.id}`
      };
    });
    const factEvents = timeline.map((item) => ({
      id: `fact-${item.fact.id}`,
      timestamp: item.timestamp ?? item.fact.created_at,
      kind: "fact" as const,
      title: `${item.fact.predicate}: ${item.fact.object_value}`,
      explainPath: `/explain/facts/${item.fact.id}`
    }));
    return [...factEvents, ...relationEvents].sort(
      (left, right) => new Date(left.timestamp).valueOf() - new Date(right.timestamp).valueOf()
    );
  }, [entityId, graph, timeline]);

  const neighborPreview = useMemo(() => {
    if (!graph || hoveredNeighborId === null) {
      return null;
    }
    const neighbor = graph.related_entities.find((item) => item.id === hoveredNeighborId);
    if (!neighbor) {
      return null;
    }
    const incoming = graph.incoming_relations.filter((item) => item.from_entity_id === hoveredNeighborId);
    const outgoing = graph.outgoing_relations.filter((item) => item.to_entity_id === hoveredNeighborId);
    return {
      neighbor,
      incomingCount: incoming.length,
      outgoingCount: outgoing.length,
      labels: Array.from(new Set([...incoming, ...outgoing].map((relation) => relation.relation_type))).slice(0, 6)
    };
  }, [graph, hoveredNeighborId]);

  const visibleNeighbors = useMemo(
    () => (graph?.related_entities ?? []).slice(0, neighborLimit),
    [graph?.related_entities, neighborLimit]
  );

  const graphNodes = useMemo(() => {
    if (!entity || !graph) {
      return [] as GraphNodeVisual[];
    }
    if (visibleNeighbors.length === 0) {
      return [] as GraphNodeVisual[];
    }
    return visibleNeighbors.map((neighbor, index) => {
      const angle = (2 * Math.PI * index) / visibleNeighbors.length - Math.PI / 2;
      return {
        entity: neighbor,
        x: 50 + 35 * Math.cos(angle),
        y: 50 + 35 * Math.sin(angle)
      };
    });
  }, [entity, graph, visibleNeighbors]);

  const graphEdges = useMemo(() => {
    if (!graph || graphNodes.length === 0) {
      return [] as GraphEdgeVisual[];
    }

    return graphNodes.flatMap((node) => {
      const outgoing = graph.outgoing_relations.filter(
        (relation) => relation.to_entity_id === node.entity.id
      );
      const incoming = graph.incoming_relations.filter(
        (relation) => relation.from_entity_id === node.entity.id
      );

      const dx = node.x - 50;
      const dy = node.y - 50;
      const distance = Math.hypot(dx, dy) || 1;
      const offsetX = (-dy / distance) * 1.2;
      const offsetY = (dx / distance) * 1.2;

      const edges: GraphEdgeVisual[] = [];
      if (outgoing.length > 0) {
        const labels = Array.from(new Set(outgoing.map((relation) => relation.relation_type)));
        edges.push({
          key: `outgoing-${node.entity.id}`,
          neighborId: node.entity.id,
          direction: "outgoing",
          x1: 50 + offsetX,
          y1: 50 + offsetY,
          x2: node.x + offsetX,
          y2: node.y + offsetY,
          labelX: 50 + dx * 0.58 + offsetX * 1.3,
          labelY: 50 + dy * 0.58 + offsetY * 1.3,
          label: `out: ${summarizeLabels(labels)}`
        });
      }
      if (incoming.length > 0) {
        const labels = Array.from(new Set(incoming.map((relation) => relation.relation_type)));
        edges.push({
          key: `incoming-${node.entity.id}`,
          neighborId: node.entity.id,
          direction: "incoming",
          x1: node.x - offsetX,
          y1: node.y - offsetY,
          x2: 50 - offsetX,
          y2: 50 - offsetY,
          labelX: 50 + dx * 0.42 - offsetX * 1.7,
          labelY: 50 + dy * 0.42 - offsetY * 1.7,
          label: `in: ${summarizeLabels(labels)}`
        });
      }
      return edges;
    });
  }, [graph, graphNodes]);

  return (
    <div className="stackLg">
      {error ? <section className="panel errorText">{error}</section> : null}
      {refreshing ? <section className="panel"><p className="subtle">Refreshing entity details...</p></section> : null}
      {loading ? (
        <section className="panel">Loading entity...</section>
      ) : entity && graph ? (
        <>
          <section className="panel">
            <div className="sectionTitleRow">
              <h2>{entity.canonical_name}</h2>
              {editingEntity ? (
                <div className="toolbar">
                  <input
                    className="input compactInput"
                    value={entityDraft.canonical_name}
                    onChange={(event) =>
                      setEntityDraft((current) => ({ ...current, canonical_name: event.target.value }))
                    }
                    placeholder="Canonical name"
                  />
                  <input
                    className="input compactInput"
                    value={entityDraft.type_label}
                    onChange={(event) =>
                      setEntityDraft((current) => ({ ...current, type_label: event.target.value }))
                    }
                    placeholder="Type label"
                  />
                  <button className="button" type="button" onClick={() => void saveEditedEntity()} disabled={busyKey === "entity"}>
                    Save
                  </button>
                  <button className="button ghost" type="button" onClick={cancelEditEntity} disabled={busyKey === "entity"}>
                    Cancel
                  </button>
                </div>
              ) : (
                <div className="toolbar">
                  <button className="button ghost" type="button" onClick={beginEditEntity} disabled={busyKey === "entity"}>
                    Edit entity
                  </button>
                  <button className="button ghost" type="button" onClick={requestDeleteEntity} disabled={busyKey === "entity"}>
                    Delete entity
                  </button>
                </div>
              )}
            </div>
            {pendingDeleteEntity ? (
              <div className="inlineConfirm">
                <span className="inlineConfirmText">
                  Delete entity "{entity.canonical_name}" and all related facts/relations?
                </span>
                <button className="button danger" type="button" onClick={() => void confirmDeleteEntity()} disabled={busyKey === "entity"}>
                  Confirm delete
                </button>
                <button className="button ghost" type="button" onClick={cancelDeleteEntity} disabled={busyKey === "entity"}>
                  Cancel
                </button>
              </div>
            ) : null}
            <p className="subtle">
              Type: {entity.type_label || "untyped"} | First seen: {formatTimestamp(entity.first_seen_timestamp)} |
              Last seen: {formatTimestamp(entity.updated_at)} | Conversations:{" "}
              {conversationCount ?? "-"}
            </p>
            <p className="subtle">
              Aliases: {entity.known_aliases_json.length > 0 ? entity.known_aliases_json.join(", ") : "(none)"}
            </p>
          </section>

          <section className="panel">
            <div className="sectionTitleRow">
              <h3>Properties (Facts)</h3>
              <div className="toolbar">
                <input
                  className="input compactInput"
                  placeholder="Filter field..."
                  value={fieldFilter}
                  onChange={(event) => setFieldFilter(event.target.value)}
                />
                <label className="checkTag">
                  <input
                    type="checkbox"
                    checked={showRawFieldVariants}
                    onChange={(event) => setShowRawFieldVariants(event.target.checked)}
                  />
                  <span>Show raw label variants</span>
                </label>
              </div>
            </div>
            <div className="tableWrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Field</th>
                    <th>Value</th>
                    <th>Confidence</th>
                    <th>Scope</th>
                    <th>Timestamp</th>
                    <th>Explain</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {factRows.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="emptyCell">
                        No facts match the current filters.
                      </td>
                    </tr>
                  ) : (
                    factRows.map((fact) => {
                      const rowKey = `fact-${fact.id}`;
                      const isEditing = editingFactId === fact.id;
                      const isDeletePending = pendingDeleteFactId === fact.id;
                      return (
                        <tr key={fact.id}>
                          <td>
                            {isEditing ? (
                              <input
                                className="input compactInput"
                                value={factDraft.predicate}
                                onChange={(event) =>
                                  setFactDraft((current) => ({ ...current, predicate: event.target.value }))
                                }
                              />
                            ) : (
                              <>
                                {fact.canonicalLabel}
                                {fact.canonicalLabel !== fact.rawLabel ? (
                                  <span className="muted"> (raw: {fact.rawLabel})</span>
                                ) : null}
                              </>
                            )}
                          </td>
                          <td>
                            {isEditing ? (
                              <input
                                className="input"
                                value={factDraft.object_value}
                                onChange={(event) =>
                                  setFactDraft((current) => ({ ...current, object_value: event.target.value }))
                                }
                              />
                            ) : (
                              fact.object_value
                            )}
                          </td>
                          <td>
                            {isEditing ? (
                              <input
                                className="input compactInput"
                                value={factDraft.confidence}
                                onChange={(event) =>
                                  setFactDraft((current) => ({ ...current, confidence: event.target.value }))
                                }
                              />
                            ) : (
                              fact.confidence.toFixed(2)
                            )}
                          </td>
                          <td>{fact.scope}</td>
                          <td>{formatTimestamp(fact.created_at)}</td>
                          <td>
                            <Link href={`/explain/facts/${fact.id}`}>Explain</Link>
                          </td>
                          <td>
                            {isEditing ? (
                              <div className="inlineActions">
                                <button
                                  className="button"
                                  type="button"
                                  onClick={() =>
                                    void saveEditedFact(
                                      fact.id,
                                      fact.rawLabel,
                                      fact.object_value,
                                      fact.confidence
                                    )
                                  }
                                  disabled={busyKey === rowKey}
                                >
                                  Save
                                </button>
                                <button
                                  className="button ghost"
                                  type="button"
                                  onClick={cancelEditFact}
                                  disabled={busyKey === rowKey}
                                >
                                  Cancel
                                </button>
                              </div>
                            ) : isDeletePending ? (
                              <div className="inlineConfirm">
                                <span className="inlineConfirmText">Delete this fact?</span>
                                <button
                                  className="button danger"
                                  type="button"
                                  onClick={() => void confirmDeleteFact(fact.id)}
                                  disabled={busyKey === rowKey}
                                >
                                  Confirm delete
                                </button>
                                <button
                                  className="button ghost"
                                  type="button"
                                  onClick={cancelDeleteFact}
                                  disabled={busyKey === rowKey}
                                >
                                  Cancel
                                </button>
                              </div>
                            ) : (
                              <div className="inlineActions">
                                <button
                                  className="button ghost"
                                  type="button"
                                  onClick={() =>
                                    beginEditFact(fact.id, fact.rawLabel, fact.object_value, fact.confidence)
                                  }
                                  disabled={busyKey === rowKey}
                                >
                                  Edit
                                </button>
                                <button
                                  className="button ghost"
                                  type="button"
                                  onClick={() => requestDeleteFact(fact.id)}
                                  disabled={busyKey === rowKey}
                                >
                                  Delete
                                </button>
                              </div>
                            )}
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </section>

          <section className="gridTwo">
            <article className="panel">
              <h3>Outgoing Relations</h3>
              <div className="tableWrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Relation</th>
                      <th>To</th>
                      <th>Qualifiers</th>
                      <th>Confidence</th>
                      <th>Explain</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {graph.outgoing_relations.length === 0 ? (
                      <tr>
                        <td colSpan={6} className="emptyCell">
                          No outgoing relations.
                        </td>
                      </tr>
                    ) : (
                      graph.outgoing_relations.map((relation) => {
                        const rowKey = `relation-${relation.id}`;
                        const isEditing = editingRelationId === relation.id;
                        const isDeletePending = pendingDeleteRelationId === relation.id;
                        return (
                          <tr key={relation.id}>
                            <td>
                              {isEditing ? (
                                <input
                                  className="input compactInput"
                                  value={relationDraft.relation_type}
                                  onChange={(event) =>
                                    setRelationDraft((current) => ({
                                      ...current,
                                      relation_type: event.target.value
                                    }))
                                  }
                                />
                              ) : (
                                relation.relation_type
                              )}
                            </td>
                            <td>
                              <Link href={`/entities/${relation.to_entity_id}`}>{relation.to_entity_name}</Link>
                            </td>
                            <td>
                              {isEditing ? (
                                <input
                                  className="input"
                                  value={relationDraft.qualifiers_json}
                                  onChange={(event) =>
                                    setRelationDraft((current) => ({
                                      ...current,
                                      qualifiers_json: event.target.value
                                    }))
                                  }
                                />
                              ) : Object.keys(relation.qualifiers_json).length > 0 ? (
                                JSON.stringify(relation.qualifiers_json)
                              ) : (
                                "-"
                              )}
                            </td>
                            <td>
                              {isEditing ? (
                                <input
                                  className="input compactInput"
                                  value={relationDraft.confidence}
                                  onChange={(event) =>
                                    setRelationDraft((current) => ({
                                      ...current,
                                      confidence: event.target.value
                                    }))
                                  }
                                />
                              ) : (
                                relation.confidence.toFixed(2)
                              )}
                            </td>
                            <td>
                              <Link href={`/explain/relations/${relation.id}`}>Explain</Link>
                            </td>
                            <td>
                              {isEditing ? (
                                <div className="inlineActions">
                                  <button
                                    className="button"
                                    type="button"
                                    onClick={() =>
                                      void saveEditedRelation(
                                        relation.id,
                                        relation.relation_type,
                                        relation.confidence,
                                        relation.qualifiers_json
                                      )
                                    }
                                    disabled={busyKey === rowKey}
                                  >
                                    Save
                                  </button>
                                  <button
                                    className="button ghost"
                                    type="button"
                                    onClick={cancelEditRelation}
                                    disabled={busyKey === rowKey}
                                  >
                                    Cancel
                                  </button>
                                </div>
                              ) : isDeletePending ? (
                                <div className="inlineConfirm">
                                  <span className="inlineConfirmText">Delete this relation?</span>
                                  <button
                                    className="button danger"
                                    type="button"
                                    onClick={() => void confirmDeleteRelation(relation.id)}
                                    disabled={busyKey === rowKey}
                                  >
                                    Confirm delete
                                  </button>
                                  <button
                                    className="button ghost"
                                    type="button"
                                    onClick={cancelDeleteRelation}
                                    disabled={busyKey === rowKey}
                                  >
                                    Cancel
                                  </button>
                                </div>
                              ) : (
                                <div className="inlineActions">
                                  <button
                                    className="button ghost"
                                    type="button"
                                    onClick={() =>
                                      beginEditRelation(
                                        relation.id,
                                        relation.relation_type,
                                        relation.confidence,
                                        relation.qualifiers_json
                                      )
                                    }
                                    disabled={busyKey === rowKey}
                                  >
                                    Edit
                                  </button>
                                  <button
                                    className="button ghost"
                                    type="button"
                                    onClick={() => requestDeleteRelation(relation.id)}
                                    disabled={busyKey === rowKey}
                                  >
                                    Delete
                                  </button>
                                </div>
                              )}
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            </article>

            <article className="panel">
              <h3>Incoming Relations</h3>
              <div className="tableWrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Relation</th>
                      <th>From</th>
                      <th>Qualifiers</th>
                      <th>Confidence</th>
                      <th>Explain</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {graph.incoming_relations.length === 0 ? (
                      <tr>
                        <td colSpan={6} className="emptyCell">
                          No incoming relations.
                        </td>
                      </tr>
                    ) : (
                      graph.incoming_relations.map((relation) => {
                        const rowKey = `relation-${relation.id}`;
                        const isEditing = editingRelationId === relation.id;
                        const isDeletePending = pendingDeleteRelationId === relation.id;
                        return (
                          <tr key={relation.id}>
                            <td>
                              {isEditing ? (
                                <input
                                  className="input compactInput"
                                  value={relationDraft.relation_type}
                                  onChange={(event) =>
                                    setRelationDraft((current) => ({
                                      ...current,
                                      relation_type: event.target.value
                                    }))
                                  }
                                />
                              ) : (
                                relation.relation_type
                              )}
                            </td>
                            <td>
                              <Link href={`/entities/${relation.from_entity_id}`}>{relation.from_entity_name}</Link>
                            </td>
                            <td>
                              {isEditing ? (
                                <input
                                  className="input"
                                  value={relationDraft.qualifiers_json}
                                  onChange={(event) =>
                                    setRelationDraft((current) => ({
                                      ...current,
                                      qualifiers_json: event.target.value
                                    }))
                                  }
                                />
                              ) : Object.keys(relation.qualifiers_json).length > 0 ? (
                                JSON.stringify(relation.qualifiers_json)
                              ) : (
                                "-"
                              )}
                            </td>
                            <td>
                              {isEditing ? (
                                <input
                                  className="input compactInput"
                                  value={relationDraft.confidence}
                                  onChange={(event) =>
                                    setRelationDraft((current) => ({
                                      ...current,
                                      confidence: event.target.value
                                    }))
                                  }
                                />
                              ) : (
                                relation.confidence.toFixed(2)
                              )}
                            </td>
                            <td>
                              <Link href={`/explain/relations/${relation.id}`}>Explain</Link>
                            </td>
                            <td>
                              {isEditing ? (
                                <div className="inlineActions">
                                  <button
                                    className="button"
                                    type="button"
                                    onClick={() =>
                                      void saveEditedRelation(
                                        relation.id,
                                        relation.relation_type,
                                        relation.confidence,
                                        relation.qualifiers_json
                                      )
                                    }
                                    disabled={busyKey === rowKey}
                                  >
                                    Save
                                  </button>
                                  <button
                                    className="button ghost"
                                    type="button"
                                    onClick={cancelEditRelation}
                                    disabled={busyKey === rowKey}
                                  >
                                    Cancel
                                  </button>
                                </div>
                              ) : isDeletePending ? (
                                <div className="inlineConfirm">
                                  <span className="inlineConfirmText">Delete this relation?</span>
                                  <button
                                    className="button danger"
                                    type="button"
                                    onClick={() => void confirmDeleteRelation(relation.id)}
                                    disabled={busyKey === rowKey}
                                  >
                                    Confirm delete
                                  </button>
                                  <button
                                    className="button ghost"
                                    type="button"
                                    onClick={cancelDeleteRelation}
                                    disabled={busyKey === rowKey}
                                  >
                                    Cancel
                                  </button>
                                </div>
                              ) : (
                                <div className="inlineActions">
                                  <button
                                    className="button ghost"
                                    type="button"
                                    onClick={() =>
                                      beginEditRelation(
                                        relation.id,
                                        relation.relation_type,
                                        relation.confidence,
                                        relation.qualifiers_json
                                      )
                                    }
                                    disabled={busyKey === rowKey}
                                  >
                                    Edit
                                  </button>
                                  <button
                                    className="button ghost"
                                    type="button"
                                    onClick={() => requestDeleteRelation(relation.id)}
                                    disabled={busyKey === rowKey}
                                  >
                                    Delete
                                  </button>
                                </div>
                              )}
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            </article>
          </section>

          <section className="gridTwo">
            <article className="panel">
              <h3>Timeline</h3>
              <ul className="simpleList">
                {combinedTimeline.length === 0 ? (
                  <li className="muted">No timeline activity.</li>
                ) : (
                  combinedTimeline.map((event) => (
                    <li key={event.id}>
                      {formatTimestamp(event.timestamp)} | {event.kind.replace("_", " ")} | {event.title} |{" "}
                      <Link href={event.explainPath}>Explain</Link>
                    </li>
                  ))
                )}
              </ul>
            </article>
            <article className="panel">
              <h3>Graph Neighborhood</h3>
              <div className="graphCanvasWrap">
                <svg
                  className="entityGraph"
                  viewBox="0 0 100 100"
                  role="img"
                  aria-label={`Neighborhood graph for ${entity.canonical_name}`}
                >
                  {graphEdges.map((edge) => (
                    <g
                      key={edge.key}
                      className={`graphEdge ${edge.direction} ${
                        hoveredNeighborId === edge.neighborId ? "active" : ""
                      }`}
                      onMouseEnter={() => setHoveredNeighborId(edge.neighborId)}
                    >
                      <line x1={edge.x1} y1={edge.y1} x2={edge.x2} y2={edge.y2} />
                      <text x={edge.labelX} y={edge.labelY}>
                        {edge.label}
                      </text>
                    </g>
                  ))}
                  <g className="graphNode center">
                    <circle cx={50} cy={50} r={7.2} />
                    <text x={50} y={50} textAnchor="middle" dominantBaseline="middle">
                      {truncateLabel(entity.canonical_name)}
                    </text>
                  </g>
                  {graphNodes.map((node) => (
                    <g
                      key={node.entity.id}
                      className={`graphNode ${hoveredNeighborId === node.entity.id ? "active" : ""}`}
                      onMouseEnter={() => setHoveredNeighborId(node.entity.id)}
                    >
                      <a href={`/entities/${node.entity.id}`}>
                        <circle cx={node.x} cy={node.y} r={5.1} />
                      </a>
                      <text x={node.x} y={node.y + 8.8} textAnchor="middle">
                        {truncateLabel(node.entity.canonical_name)}
                      </text>
                    </g>
                  ))}
                </svg>
              </div>
              <p className="subtle">
                Center node is the current entity. Click any outer node to navigate.
                {graph.related_entities.length > visibleNeighbors.length
                  ? " Use Load more neighbors to expand this graph."
                  : ""}
              </p>
              <div className="gridTwo">
                <ul className="simpleList neighborList">
                  {visibleNeighbors.length === 0 ? (
                    <li className="muted">No neighboring entities.</li>
                  ) : (
                    visibleNeighbors.map((related) => (
                      <li
                        key={related.id}
                        onMouseEnter={() => setHoveredNeighborId(related.id)}
                        onFocus={() => setHoveredNeighborId(related.id)}
                      >
                        <Link href={`/entities/${related.id}`}>{related.canonical_name}</Link>
                      </li>
                    ))
                  )}
                </ul>
                <div className="panel insetPanel">
                  <h4>Hover Preview</h4>
                  {neighborPreview ? (
                    <>
                      <p>
                        <strong>{neighborPreview.neighbor.canonical_name}</strong>
                      </p>
                      <p className="subtle">Type: {neighborPreview.neighbor.type_label || "untyped"}</p>
                      <p className="subtle">
                        Incoming edges: {neighborPreview.incomingCount} | Outgoing edges:{" "}
                        {neighborPreview.outgoingCount}
                      </p>
                      <p className="subtle">
                        Labels: {neighborPreview.labels.length > 0 ? neighborPreview.labels.join(", ") : "-"}
                      </p>
                    </>
                  ) : (
                    <p className="subtle">Hover a neighbor to preview relationship context.</p>
                  )}
                </div>
              </div>
              {graph.related_entities.length > visibleNeighbors.length ? (
                <button
                  className="button ghost"
                  type="button"
                  onClick={() => setNeighborLimit((current) => current + 8)}
                >
                  Load more neighbors
                </button>
              ) : null}
            </article>
          </section>
        </>
      ) : (
        <section className="panel">Entity not found.</section>
      )}
    </div>
  );
}
