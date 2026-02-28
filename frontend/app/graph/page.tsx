"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";

import {
  type ConversationGraphData,
  type ConversationsListResponse,
  type RelationWithEntitiesRead,
  deleteEntityRecord,
  deleteRelation,
  getConversationGraph,
  getConversations,
  updateEntityRecord,
  updateRelation
} from "../../lib/api";

type NodePoint = {
  id: number;
  x: number;
  y: number;
};

type LayoutMode = "ring" | "tree";

function truncate(value: string, limit = 16): string {
  if (value.length <= limit) {
    return value;
  }
  return `${value.slice(0, Math.max(0, limit - 3))}...`;
}

function buildRingLayout(entityIds: number[]): Record<number, NodePoint> {
  const positions: Record<number, NodePoint> = {};
  if (entityIds.length === 0) {
    return positions;
  }
  entityIds.forEach((entityId, index) => {
    const angle = (2 * Math.PI * index) / entityIds.length - Math.PI / 2;
    const radius = 39;
    positions[entityId] = {
      id: entityId,
      x: 50 + radius * Math.cos(angle),
      y: 50 + radius * Math.sin(angle)
    };
  });
  return positions;
}

function buildTreeLayout(
  entityIds: number[],
  relations: RelationWithEntitiesRead[],
  preferredRootId: number | null
): Record<number, NodePoint> {
  const positions: Record<number, NodePoint> = {};
  if (entityIds.length === 0) {
    return positions;
  }

  const neighbors = new Map<number, Set<number>>();
  entityIds.forEach((entityId) => neighbors.set(entityId, new Set<number>()));
  relations.forEach((relation) => {
    if (!neighbors.has(relation.from_entity_id) || !neighbors.has(relation.to_entity_id)) {
      return;
    }
    neighbors.get(relation.from_entity_id)?.add(relation.to_entity_id);
    neighbors.get(relation.to_entity_id)?.add(relation.from_entity_id);
  });

  const orderedRoots: number[] = [];
  if (preferredRootId !== null && entityIds.includes(preferredRootId)) {
    orderedRoots.push(preferredRootId);
  }
  entityIds.forEach((entityId) => {
    if (!orderedRoots.includes(entityId)) {
      orderedRoots.push(entityId);
    }
  });

  const levelById = new Map<number, number>();
  const visited = new Set<number>();
  let levelOffset = 0;

  orderedRoots.forEach((rootId) => {
    if (visited.has(rootId)) {
      return;
    }
    const queue: number[] = [rootId];
    visited.add(rootId);
    levelById.set(rootId, levelOffset);
    let componentMaxLevel = levelOffset;

    while (queue.length > 0) {
      const current = queue.shift();
      if (current === undefined) {
        break;
      }
      const currentLevel = levelById.get(current) ?? levelOffset;
      neighbors.get(current)?.forEach((neighborId) => {
        if (visited.has(neighborId)) {
          return;
        }
        visited.add(neighborId);
        const neighborLevel = currentLevel + 1;
        levelById.set(neighborId, neighborLevel);
        componentMaxLevel = Math.max(componentMaxLevel, neighborLevel);
        queue.push(neighborId);
      });
    }

    levelOffset = componentMaxLevel + 1;
  });

  const levels = new Map<number, number[]>();
  entityIds.forEach((entityId) => {
    const level = levelById.get(entityId) ?? 0;
    const bucket = levels.get(level) ?? [];
    bucket.push(entityId);
    levels.set(level, bucket);
  });

  const orderedLevels = Array.from(levels.keys()).sort((left, right) => left - right);
  orderedLevels.forEach((level, levelIndex) => {
    const ids = levels.get(level) ?? [];
    const y =
      orderedLevels.length === 1
        ? 50
        : 12 + (74 * levelIndex) / Math.max(1, orderedLevels.length - 1);
    ids.forEach((entityId, index) => {
      const x = ids.length === 1 ? 50 : 10 + (80 * index) / Math.max(1, ids.length - 1);
      positions[entityId] = {
        id: entityId,
        x,
        y
      };
    });
  });

  return positions;
}

export default function GraphPage() {
  const [conversationList, setConversationList] = useState<ConversationsListResponse | null>(null);
  const [conversationId, setConversationId] = useState("");
  const [graph, setGraph] = useState<ConversationGraphData | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<number | null>(null);
  const [nodeFilter, setNodeFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [edgeFilter, setEdgeFilter] = useState("");
  const [highlightRelation, setHighlightRelation] = useState("");
  const [layoutMode, setLayoutMode] = useState<LayoutMode>("ring");
  const [nodeDraft, setNodeDraft] = useState({ canonical_name: "", type_label: "" });
  const [editingRelationId, setEditingRelationId] = useState<number | null>(null);
  const [relationDraft, setRelationDraft] = useState({ relation_type: "", confidence: "" });
  const [pendingDeleteNodeId, setPendingDeleteNodeId] = useState<number | null>(null);
  const [pendingDeleteRelationId, setPendingDeleteRelationId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadConversations(queryConversationId: string | null) {
    const conversations = await getConversations({ limit: 200, offset: 0 });
    setConversationList(conversations);
    if (queryConversationId) {
      setConversationId(queryConversationId);
      return;
    }
    if (!conversationId && conversations.items.length > 0) {
      setConversationId(conversations.items[0].conversation_id);
    }
  }

  async function loadGraph(targetConversationId: string) {
    if (!targetConversationId.trim()) {
      setGraph(null);
      return;
    }
    const payload = await getConversationGraph(targetConversationId.trim());
    setGraph(payload);
    if (payload.entities.length > 0 && selectedNodeId === null) {
      setSelectedNodeId(payload.entities[0].id);
    }
  }

  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const queryConversationId =
          typeof window === "undefined"
            ? null
            : new URLSearchParams(window.location.search).get("conversation_id")?.trim() || null;
        await loadConversations(queryConversationId);
      } catch (err) {
        if (!active) {
          return;
        }
        setError(err instanceof Error ? err.message : "Failed to load conversations.");
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }
    void load();
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    let active = true;
    async function hydrateGraph() {
      if (!conversationId.trim()) {
        return;
      }
      setLoading(true);
      setError(null);
      try {
        await loadGraph(conversationId);
      } catch (err) {
        if (!active) {
          return;
        }
        setError(err instanceof Error ? err.message : "Failed to load graph.");
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }
    void hydrateGraph();
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversationId]);

  const relationLabels = useMemo(
    () => Array.from(new Set((graph?.relations ?? []).map((relation) => relation.relation_type))).sort(),
    [graph?.relations]
  );

  const visibleEntities = useMemo(() => {
    const source = graph?.entities ?? [];
    const cleanNodeFilter = nodeFilter.trim().toLowerCase();
    const cleanTypeFilter = typeFilter.trim().toLowerCase();
    return source.filter((entity) => {
      const nodeMatch =
        !cleanNodeFilter ||
        entity.canonical_name.toLowerCase().includes(cleanNodeFilter) ||
        entity.display_name.toLowerCase().includes(cleanNodeFilter);
      const typeMatch = !cleanTypeFilter || entity.type_label.toLowerCase().includes(cleanTypeFilter);
      return nodeMatch && typeMatch;
    });
  }, [graph?.entities, nodeFilter, typeFilter]);

  const visibleNodeIds = useMemo(() => new Set(visibleEntities.map((entity) => entity.id)), [visibleEntities]);

  const visibleRelations = useMemo(() => {
    const source = graph?.relations ?? [];
    const cleanEdgeFilter = edgeFilter.trim().toLowerCase();
    return source.filter((relation) => {
      if (!visibleNodeIds.has(relation.from_entity_id) || !visibleNodeIds.has(relation.to_entity_id)) {
        return false;
      }
      if (!cleanEdgeFilter) {
        return true;
      }
      return relation.relation_type.toLowerCase().includes(cleanEdgeFilter);
    });
  }, [edgeFilter, graph?.relations, visibleNodeIds]);

  const nodePositions = useMemo(() => {
    const entityIds = visibleEntities.map((entity) => entity.id);
    if (layoutMode === "tree") {
      return buildTreeLayout(entityIds, visibleRelations, selectedNodeId);
    }
    return buildRingLayout(entityIds);
  }, [layoutMode, selectedNodeId, visibleEntities, visibleRelations]);

  const selectedNode = useMemo(
    () => graph?.entities.find((entity) => entity.id === selectedNodeId) ?? null,
    [graph?.entities, selectedNodeId]
  );

  useEffect(() => {
    if (!selectedNode) {
      setNodeDraft({ canonical_name: "", type_label: "" });
      return;
    }
    setNodeDraft({
      canonical_name: selectedNode.canonical_name,
      type_label: selectedNode.type_label || "untyped"
    });
  }, [selectedNode]);

  const selectedNodeRelations = useMemo(
    () =>
      visibleRelations
        .filter((relation) => relation.from_entity_id === selectedNodeId || relation.to_entity_id === selectedNodeId)
        .sort((left, right) => left.id - right.id),
    [selectedNodeId, visibleRelations]
  );

  async function handleSelectConversation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const clean = conversationId.trim();
    if (!clean) {
      return;
    }
    setConversationId(clean);
    await loadGraph(clean);
  }

  async function refreshGraph() {
    if (!conversationId.trim()) {
      return;
    }
    await loadGraph(conversationId.trim());
  }

  async function handleSaveNode() {
    if (!selectedNode) {
      return;
    }
    const nextCanonicalName = nodeDraft.canonical_name.trim();
    const nextTypeLabel = nodeDraft.type_label.trim();
    if (!nextCanonicalName || !nextTypeLabel) {
      setError("Node name and type label are required.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await updateEntityRecord(selectedNode.id, {
        canonical_name: nextCanonicalName,
        type_label: nextTypeLabel
      });
      await refreshGraph();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update node.");
    } finally {
      setSaving(false);
    }
  }

  function beginRelationEdit(relation: RelationWithEntitiesRead) {
    setEditingRelationId(relation.id);
    setPendingDeleteRelationId(null);
    setRelationDraft({
      relation_type: relation.relation_type,
      confidence: relation.confidence.toFixed(2)
    });
  }

  function cancelRelationEdit() {
    setEditingRelationId(null);
    setRelationDraft({ relation_type: "", confidence: "" });
  }

  async function handleSaveRelation() {
    if (editingRelationId === null) {
      return;
    }
    const nextLabel = relationDraft.relation_type.trim();
    const nextConfidence = Number.parseFloat(relationDraft.confidence);
    if (!nextLabel) {
      setError("Relation label is required.");
      return;
    }
    if (!Number.isFinite(nextConfidence) || nextConfidence < 0 || nextConfidence > 1) {
      setError("Confidence must be between 0 and 1.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await updateRelation(editingRelationId, {
        relation_type: nextLabel,
        confidence: nextConfidence
      });
      cancelRelationEdit();
      await refreshGraph();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update relation.");
    } finally {
      setSaving(false);
    }
  }

  function requestDeleteNode() {
    if (!selectedNode) {
      return;
    }
    if (pendingDeleteNodeId === selectedNode.id) {
      return;
    }
    setPendingDeleteNodeId(selectedNode.id);
  }

  function cancelDeleteNode() {
    setPendingDeleteNodeId(null);
  }

  async function confirmDeleteNode() {
    if (!selectedNode) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await deleteEntityRecord(selectedNode.id);
      setSelectedNodeId(null);
      setPendingDeleteNodeId(null);
      await refreshGraph();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete node.");
    } finally {
      setSaving(false);
    }
  }

  function requestDeleteRelation(relationId: number) {
    if (editingRelationId === relationId) {
      cancelRelationEdit();
    }
    setPendingDeleteRelationId(relationId);
  }

  function cancelDeleteRelation() {
    setPendingDeleteRelationId(null);
  }

  async function confirmDeleteRelation(relationId: number) {
    setSaving(true);
    setError(null);
    try {
      await deleteRelation(relationId);
      if (editingRelationId === relationId) {
        cancelRelationEdit();
      }
      setPendingDeleteRelationId((current) => (current === relationId ? null : current));
      await refreshGraph();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete relation.");
    } finally {
      setSaving(false);
    }
  }

  const hasHighlight = highlightRelation.trim().length > 0;

  return (
    <div className="stackLg">
      <section className="panel">
        <h2>Graph Studio</h2>
        <p className="subtle">
          Conversation-wide graph view with filtering, relationship highlighting, and in-place node/edge editing.
        </p>
        <form className="toolbar graphToolbar" onSubmit={handleSelectConversation}>
          <label className="field">
            <span>Conversation</span>
            <input
              className="input"
              list="conversation-list"
              value={conversationId}
              onChange={(event) => setConversationId(event.target.value)}
              placeholder="conversation id"
            />
            <datalist id="conversation-list">
              {(conversationList?.items ?? []).map((item) => (
                <option key={item.conversation_id} value={item.conversation_id} />
              ))}
            </datalist>
          </label>
          <label className="field">
            <span>Layout</span>
            <select
              className="input"
              value={layoutMode}
              onChange={(event) => setLayoutMode(event.target.value as LayoutMode)}
            >
              <option value="ring">Ring</option>
              <option value="tree">Tree</option>
            </select>
          </label>
          <label className="field">
            <span>Node Filter</span>
            <input
              className="input"
              value={nodeFilter}
              onChange={(event) => setNodeFilter(event.target.value)}
              placeholder="name contains..."
            />
          </label>
          <label className="field">
            <span>Type Filter</span>
            <input
              className="input"
              value={typeFilter}
              onChange={(event) => setTypeFilter(event.target.value)}
              placeholder="type label..."
            />
          </label>
          <label className="field">
            <span>Edge Filter</span>
            <input
              className="input"
              value={edgeFilter}
              onChange={(event) => setEdgeFilter(event.target.value)}
              placeholder="relation label..."
            />
          </label>
          <label className="field">
            <span>Highlight Relation</span>
            <select
              className="input"
              value={highlightRelation}
              onChange={(event) => setHighlightRelation(event.target.value)}
            >
              <option value="">(none)</option>
              {relationLabels.map((label) => (
                <option key={label} value={label}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <button className="button" type="submit" disabled={loading}>
            Load Graph
          </button>
        </form>
      </section>

      {error ? <section className="panel errorText">{error}</section> : null}
      {loading ? (
        <section className="panel">Loading graph...</section>
      ) : graph ? (
        <section className="gridTwo">
          <article className="panel">
            <div className="sectionTitleRow">
              <h3>Graph Canvas</h3>
              <Link href={`/conversations/${encodeURIComponent(graph.conversation_id)}`}>Open conversation</Link>
            </div>
            <p className="subtle">
              Nodes: {visibleEntities.length} | Edges: {visibleRelations.length} | Layout: {layoutMode}
            </p>
            <div className="graphLegend">
              <span className="legendItem">
                <span className="legendSwatch graphLegendDefault" /> default edge
              </span>
              <span className="legendItem">
                <span className="legendSwatch graphLegendHighlight" /> highlighted relation
              </span>
              <span className="legendItem">
                <span className="legendSwatch graphLegendFocus" /> selected-node edge
              </span>
            </div>
            <div className="graphCanvasWrap">
              <svg className="entityGraph" viewBox="0 0 100 100" role="img" aria-label="Conversation graph">
                {visibleRelations.map((relation) => {
                  const from = nodePositions[relation.from_entity_id];
                  const to = nodePositions[relation.to_entity_id];
                  if (!from || !to) {
                    return null;
                  }
                  const isHighlighted = hasHighlight && relation.relation_type === highlightRelation;
                  const isDimmed = hasHighlight && !isHighlighted;
                  const touchesSelected =
                    relation.from_entity_id === selectedNodeId || relation.to_entity_id === selectedNodeId;
                  return (
                    <g
                      key={relation.id}
                      className={`graphEdge ${isHighlighted ? "active highlight" : ""} ${
                        touchesSelected ? "focus" : ""
                      } ${isDimmed ? "dim" : ""}`}
                    >
                      <line x1={from.x} y1={from.y} x2={to.x} y2={to.y} />
                      <text x={(from.x + to.x) / 2} y={(from.y + to.y) / 2}>
                        {truncate(relation.relation_type, 18)}
                      </text>
                    </g>
                  );
                })}
                {visibleEntities.map((entity) => {
                  const point = nodePositions[entity.id];
                  if (!point) {
                    return null;
                  }
                  return (
                    <g
                      key={entity.id}
                      className={`graphNode ${selectedNodeId === entity.id ? "active" : ""}`}
                      onClick={() => setSelectedNodeId(entity.id)}
                    >
                      <circle cx={point.x} cy={point.y} r={4.7} />
                      <text x={point.x} y={point.y + 8.2} textAnchor="middle">
                        {truncate(entity.canonical_name)}
                      </text>
                    </g>
                  );
                })}
              </svg>
            </div>
          </article>

          <article className="panel">
            <h3>Node Inspector</h3>
            {selectedNode ? (
              <>
                <div className="gridForm compactGrid">
                  <label className="field">
                    <span>Canonical Name</span>
                    <input
                      className="input"
                      value={nodeDraft.canonical_name}
                      onChange={(event) =>
                        setNodeDraft((current) => ({ ...current, canonical_name: event.target.value }))
                      }
                    />
                  </label>
                  <label className="field">
                    <span>Type Label</span>
                    <input
                      className="input"
                      value={nodeDraft.type_label}
                      onChange={(event) =>
                        setNodeDraft((current) => ({ ...current, type_label: event.target.value }))
                      }
                    />
                  </label>
                  <div className="toolbar">
                    <button className="button" type="button" onClick={handleSaveNode} disabled={saving}>
                      Save node
                    </button>
                    <button className="button ghost" type="button" onClick={requestDeleteNode} disabled={saving}>
                      Delete node
                    </button>
                    <Link href={`/entities/${selectedNode.id}`}>Open entity page</Link>
                  </div>
                  {pendingDeleteNodeId === selectedNode.id ? (
                    <div className="inlineConfirm">
                      <span className="inlineConfirmText">
                        Delete node "{selectedNode.canonical_name}" and connected edges/facts?
                      </span>
                      <button className="button danger" type="button" onClick={() => void confirmDeleteNode()} disabled={saving}>
                        Confirm delete
                      </button>
                      <button className="button ghost" type="button" onClick={cancelDeleteNode} disabled={saving}>
                        Cancel
                      </button>
                    </div>
                  ) : null}
                </div>
                <p className="subtle">
                  Aliases: {selectedNode.known_aliases_json.join(", ") || "(none)"}
                </p>

                <h4>Connected Relationships</h4>
                <div className="tableWrap">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>From</th>
                        <th>Relation</th>
                        <th>To</th>
                        <th>Confidence</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedNodeRelations.length === 0 ? (
                        <tr>
                          <td colSpan={5} className="emptyCell">
                            No connected relations.
                          </td>
                        </tr>
                      ) : (
                        selectedNodeRelations.map((relation) => {
                          const isEditing = editingRelationId === relation.id;
                          const isDeletePending = pendingDeleteRelationId === relation.id;
                          return (
                            <tr key={relation.id}>
                              <td>{relation.from_entity_name}</td>
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
                              <td>{relation.to_entity_name}</td>
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
                                {isEditing ? (
                                  <>
                                    <button className="button" type="button" onClick={handleSaveRelation} disabled={saving}>
                                      Save
                                    </button>{" "}
                                    <button className="button ghost" type="button" onClick={cancelRelationEdit} disabled={saving}>
                                      Cancel
                                    </button>
                                  </>
                                ) : isDeletePending ? (
                                  <div className="inlineConfirm">
                                    <span className="inlineConfirmText">Delete this relation edge?</span>
                                    <button
                                      className="button danger"
                                      type="button"
                                      onClick={() => void confirmDeleteRelation(relation.id)}
                                      disabled={saving}
                                    >
                                      Confirm delete
                                    </button>
                                    <button
                                      className="button ghost"
                                      type="button"
                                      onClick={cancelDeleteRelation}
                                      disabled={saving}
                                    >
                                      Cancel
                                    </button>
                                  </div>
                                ) : (
                                  <>
                                    <button
                                      className="button ghost"
                                      type="button"
                                      onClick={() => beginRelationEdit(relation)}
                                      disabled={saving}
                                    >
                                      Edit
                                    </button>{" "}
                                    <button
                                      className="button ghost"
                                      type="button"
                                      onClick={() => requestDeleteRelation(relation.id)}
                                      disabled={saving}
                                    >
                                      Delete
                                    </button>
                                  </>
                                )}
                              </td>
                            </tr>
                          );
                        })
                      )}
                    </tbody>
                  </table>
                </div>
              </>
            ) : (
              <p className="subtle">Select a node in the graph to inspect and edit it.</p>
            )}
          </article>
        </section>
      ) : (
        <section className="panel">No graph data for this conversation yet.</section>
      )}
    </div>
  );
}
