"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../../components/ui/card";
import ConversationGraphCanvas, {
  type ConversationGraphCanvasHandle
} from "../../../components/graph/ConversationGraphCanvas";
import { DeleteActionButton, DeleteConfirmDialog } from "../../../components/ui/delete-controls";
import { Input } from "../../../components/ui/input";
import { Label } from "../../../components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "../../../components/ui/select";
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
} from "../../../lib/api";
import type { GraphNodePosition } from "../../../lib/graph-layout";

function normalizeTypeLabel(typeLabel: string): string {
  const clean = typeLabel.trim();
  return clean.length > 0 ? clean : "untyped";
}

export default function GraphPage() {
  const [conversationList, setConversationList] = useState<ConversationsListResponse | null>(null);
  const [conversationInput, setConversationInput] = useState("");
  const [conversationId, setConversationId] = useState("");
  const [graph, setGraph] = useState<ConversationGraphData | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<number | null>(null);
  const [hoveredNodeId, setHoveredNodeId] = useState<number | null>(null);
  const [nodeFilter, setNodeFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [edgeFilter, setEdgeFilter] = useState("");
  const [highlightRelation, setHighlightRelation] = useState("");
  const [editingRelationId, setEditingRelationId] = useState<number | null>(null);
  const [relationDraft, setRelationDraft] = useState({ relation_type: "", confidence: "" });
  const [nodePositions, setNodePositions] = useState<Record<number, GraphNodePosition>>({});
  const [layoutResetToken, setLayoutResetToken] = useState(0);
  const [pendingDeleteNodeId, setPendingDeleteNodeId] = useState<number | null>(null);
  const [pendingDeleteRelationId, setPendingDeleteRelationId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canvasRef = useRef<ConversationGraphCanvasHandle | null>(null);
  const loadedConversationRef = useRef<string | null>(null);

  async function loadConversations(queryConversationId: string | null) {
    const conversations = await getConversations({ limit: 200, offset: 0 });
    setConversationList(conversations);
    if (queryConversationId) {
      setConversationInput(queryConversationId);
      setConversationId(queryConversationId);
      return;
    }
    if (!conversationId && conversations.items.length > 0) {
      setConversationInput(conversations.items[0].conversation_id);
      setConversationId(conversations.items[0].conversation_id);
    }
  }

  const clearLayoutState = useCallback(() => {
    setNodePositions({});
    setLayoutResetToken((current) => current + 1);
  }, []);

  const pruneStalePositions = useCallback((nextGraph: ConversationGraphData) => {
    setNodePositions((current) => {
      const validIds = new Set(nextGraph.entities.map((entity) => entity.id));
      let changed = false;
      const next: Record<number, GraphNodePosition> = {};
      Object.entries(current).forEach(([key, position]) => {
        const id = Number.parseInt(key, 10);
        if (validIds.has(id)) {
          next[id] = position;
        } else {
          changed = true;
        }
      });
      return changed ? next : current;
    });
  }, []);

  const loadGraph = useCallback(
    async (targetConversationId: string) => {
      const cleanConversationId = targetConversationId.trim();
      if (!cleanConversationId) {
        setGraph(null);
        setSelectedNodeId(null);
        setHoveredNodeId(null);
        loadedConversationRef.current = null;
        clearLayoutState();
        return;
      }

      const payload = await getConversationGraph(cleanConversationId);
      const conversationChanged = loadedConversationRef.current !== payload.conversation_id;
      loadedConversationRef.current = payload.conversation_id;

      if (conversationChanged) {
        clearLayoutState();
      } else {
        pruneStalePositions(payload);
      }

      setGraph(payload);
      setHoveredNodeId(null);
      setSelectedNodeId((current) =>
        current !== null && payload.entities.some((entity) => entity.id === current) ? current : null
      );
    },
    [clearLayoutState, pruneStalePositions]
  );

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
  }, [conversationId, loadGraph]);

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

  const activeNodeId = selectedNodeId ?? hoveredNodeId;

  const selectedNode = useMemo(
    () => graph?.entities.find((entity) => entity.id === activeNodeId) ?? null,
    [activeNodeId, graph?.entities]
  );

  const pinnedNode = useMemo(
    () => graph?.entities.find((entity) => entity.id === selectedNodeId) ?? null,
    [graph?.entities, selectedNodeId]
  );

  const selectedNodeRelations = useMemo(
    () =>
      visibleRelations
        .filter((relation) => relation.from_entity_id === activeNodeId || relation.to_entity_id === activeNodeId)
        .sort((left, right) => left.id - right.id),
    [activeNodeId, visibleRelations]
  );

  const visibleClusterCount = useMemo(
    () => new Set(visibleEntities.map((entity) => normalizeTypeLabel(entity.type_label))).size,
    [visibleEntities]
  );

  const pendingDeleteNode = useMemo(
    () =>
      pendingDeleteNodeId === null
        ? null
        : (graph?.entities.find((entity) => entity.id === pendingDeleteNodeId) ?? null),
    [graph?.entities, pendingDeleteNodeId]
  );

  const pendingDeleteRelation = useMemo(
    () =>
      pendingDeleteRelationId === null
        ? null
        : (graph?.relations.find((relation) => relation.id === pendingDeleteRelationId) ?? null),
    [graph?.relations, pendingDeleteRelationId]
  );

  const isPinnedInspector = selectedNodeId !== null && selectedNode?.id === selectedNodeId;

  const refreshGraph = useCallback(async () => {
    if (!conversationId.trim()) {
      return;
    }
    await loadGraph(conversationId.trim());
  }, [conversationId, loadGraph]);

  async function handleSelectConversation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const clean = conversationInput.trim();
    if (!clean) {
      return;
    }
    setConversationInput(clean);
    if (clean === conversationId) {
      setLoading(true);
      setError(null);
      try {
        await loadGraph(clean);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load graph.");
      } finally {
        setLoading(false);
      }
      return;
    }
    setConversationId(clean);
  }

  const handleNodeHover = useCallback((nodeId: number | null) => {
    setHoveredNodeId(nodeId);
  }, []);

  const handleNodeSelect = useCallback((nodeId: number | null) => {
    setSelectedNodeId((current) => {
      if (nodeId === null) {
        return null;
      }
      return current === nodeId ? null : nodeId;
    });
  }, []);

  const handleNodePositionChange = useCallback((nodeId: number, position: GraphNodePosition) => {
    setNodePositions((current) => {
      const previous = current[nodeId];
      if (
        previous &&
        Math.abs(previous.x - position.x) < 0.4 &&
        Math.abs(previous.y - position.y) < 0.4
      ) {
        return current;
      }
      return {
        ...current,
        [nodeId]: position
      };
    });
  }, []);

  const handleInlineSaveNode = useCallback(
    async (nodeId: number, payload: { canonical_name: string; type_label: string }) => {
      setSaving(true);
      setError(null);
      try {
        await updateEntityRecord(nodeId, payload);
        await refreshGraph();
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to update node.";
        setError(message);
        throw new Error(message);
      } finally {
        setSaving(false);
      }
    },
    [refreshGraph]
  );

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
    if (!pinnedNode) {
      return;
    }
    setPendingDeleteNodeId(pinnedNode.id);
  }

  function cancelDeleteNode() {
    setPendingDeleteNodeId(null);
  }

  async function confirmDeleteNode() {
    if (!pinnedNode) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await deleteEntityRecord(pinnedNode.id);
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

  function handleResetLayout() {
    clearLayoutState();
  }

  return (
    <div className="graphWorkspace routeFade">
      <Card className="border-border/80 bg-card/95">
        <CardHeader>
          <div className="sectionTitleRow">
            <CardTitle className="text-xl">Graph Studio</CardTitle>
            <p className="subtle">
              Whiteboard canvas with freeform clusters. Drag nodes to arrange your workspace.
            </p>
          </div>
        </CardHeader>
        <CardContent>
          <form className="graphTopbar" onSubmit={handleSelectConversation}>
            <label className="field">
              <Label>Conversation</Label>
              <Input
                list="conversation-list"
                value={conversationInput}
                onChange={(event) => setConversationInput(event.target.value)}
                placeholder="conversation id"
              />
              <datalist id="conversation-list">
                {(conversationList?.items ?? []).map((item) => (
                  <option key={item.conversation_id} value={item.conversation_id} />
                ))}
              </datalist>
            </label>
            <label className="field">
              <Label>Node Filter</Label>
              <Input
                value={nodeFilter}
                onChange={(event) => setNodeFilter(event.target.value)}
                placeholder="name contains..."
              />
            </label>
            <label className="field">
              <Label>Type Filter</Label>
              <Input
                value={typeFilter}
                onChange={(event) => setTypeFilter(event.target.value)}
                placeholder="type label..."
              />
            </label>
            <label className="field">
              <Label>Edge Filter</Label>
              <Input
                value={edgeFilter}
                onChange={(event) => setEdgeFilter(event.target.value)}
                placeholder="relation label..."
              />
            </label>
            <label className="field">
              <Label>Highlight Relation</Label>
              <Select
                value={highlightRelation || "__none__"}
                onValueChange={(value) => setHighlightRelation(value === "__none__" ? "" : value)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="(none)" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">(none)</SelectItem>
                  {relationLabels.map((label) => (
                    <SelectItem key={label} value={label}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </label>
            <Button type="submit" disabled={loading}>
              Load Graph
            </Button>
          </form>
        </CardContent>
      </Card>

      {error ? (
        <Card className="border-destructive/35 bg-destructive/5">
          <CardContent className="py-4 text-destructive">{error}</CardContent>
        </Card>
      ) : null}

      {loading ? (
        <Card>
          <CardContent className="py-6">Loading graph...</CardContent>
        </Card>
      ) : graph ? (
        <section className="graphStudioGrid">
          <Card className="graphCanvasPanel border-border/80 bg-card/95 p-4">
            <div className="sectionTitleRow">
              <h3>Graph Canvas</h3>
              <Link href={`/app/conversations/${encodeURIComponent(graph.conversation_id)}`}>Open conversation</Link>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge variant="outline">Nodes: {visibleEntities.length}</Badge>
              <Badge variant="outline">Edges: {visibleRelations.length}</Badge>
              <Badge variant="outline">Clusters: {visibleClusterCount}</Badge>
              <Badge variant="outline">Mode: Freeform</Badge>
            </div>
            <div className="graphCanvasControls">
              <Button type="button" variant="outline" onClick={() => canvasRef.current?.fitView()}>
                Fit to view
              </Button>
              <Button type="button" variant="outline" onClick={handleResetLayout}>
                Reset layout
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => canvasRef.current?.centerSelection()}
                disabled={activeNodeId === null}
              >
                Center selection
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => setSelectedNodeId(null)}
                disabled={selectedNodeId === null}
              >
                Clear pin
              </Button>
            </div>
            <div className="graphLegend">
              <span className="legendItem">
                <span className="legendSwatch graphLegendDefault" /> relation edge
              </span>
              <span className="legendItem">
                <span className="legendSwatch graphLegendHighlight" /> highlighted relation
              </span>
              <span className="legendItem">
                <span className="legendSwatch graphLegendFocus" /> focused neighborhood
              </span>
              <span className="legendItem">
                <span className="legendSwatch graphLegendDim" /> contextual dimming
              </span>
            </div>
            <ConversationGraphCanvas
              ref={canvasRef}
              entities={visibleEntities}
              relations={visibleRelations}
              activeNodeId={activeNodeId}
              selectedNodeId={selectedNodeId}
              selectedNode={pinnedNode}
              highlightRelation={highlightRelation}
              positions={nodePositions}
              resetToken={layoutResetToken}
              onNodeHover={handleNodeHover}
              onNodeSelect={handleNodeSelect}
              onNodePositionChange={handleNodePositionChange}
              onInlineSave={handleInlineSaveNode}
            />
          </Card>

          <Card className="graphInspector border-border/80 bg-card/95 p-4">
            <div className="sectionTitleRow">
              <h3>{isPinnedInspector ? "Pinned Inspector" : "Hover Preview"}</h3>
              {isPinnedInspector ? (
                <Button variant="outline" type="button" onClick={() => setSelectedNodeId(null)}>
                  Clear pin
                </Button>
              ) : null}
            </div>
            {selectedNode ? (
              <>
                <div className="stackLg">
                  <p className="subtle">
                    <strong>{selectedNode.canonical_name}</strong> ({normalizeTypeLabel(selectedNode.type_label)})
                  </p>
                  <p className="subtle">Aliases: {selectedNode.known_aliases_json.join(", ") || "(none)"}</p>
                  {isPinnedInspector ? (
                    <div className="toolbar">
                      <Link href={`/app/entities/${selectedNode.id}`}>Open entity page</Link>
                      <DeleteActionButton type="button" onClick={requestDeleteNode} disabled={saving}>
                        Delete node
                      </DeleteActionButton>
                    </div>
                  ) : (
                    <p className="subtle">Click this node to pin it. Name/type editing is available inline on canvas.</p>
                  )}
                </div>

                <h4>Connected Relationships</h4>
                <div className="tableWrap">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>From</th>
                        <th>Relation</th>
                        <th>To</th>
                        <th>Confidence</th>
                        {isPinnedInspector ? <th>Actions</th> : null}
                      </tr>
                    </thead>
                    <tbody>
                      {selectedNodeRelations.length === 0 ? (
                        <tr>
                          <td colSpan={isPinnedInspector ? 5 : 4} className="emptyCell">
                            No connected relations.
                          </td>
                        </tr>
                      ) : (
                        selectedNodeRelations.map((relation) => {
                          const isEditing = editingRelationId === relation.id;
                          return (
                            <tr key={relation.id}>
                              <td>{relation.from_entity_name}</td>
                              <td>
                                {isEditing ? (
                                  <Input
                                    className="compactInput"
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
                                  <Input
                                    className="compactInput"
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
                              {isPinnedInspector ? (
                                <td>
                                  {isEditing ? (
                                    <div className="inlineActions">
                                      <Button type="button" onClick={handleSaveRelation} disabled={saving}>
                                        Save
                                      </Button>
                                      <Button
                                        variant="outline"
                                        type="button"
                                        onClick={cancelRelationEdit}
                                        disabled={saving}
                                      >
                                        Cancel
                                      </Button>
                                    </div>
                                  ) : (
                                    <div className="inlineActions">
                                      <Button
                                        variant="outline"
                                        type="button"
                                        onClick={() => beginRelationEdit(relation)}
                                        disabled={saving}
                                      >
                                        Edit
                                      </Button>
                                      <DeleteActionButton
                                        type="button"
                                        onClick={() => requestDeleteRelation(relation.id)}
                                        disabled={saving}
                                      />
                                    </div>
                                  )}
                                </td>
                              ) : null}
                            </tr>
                          );
                        })
                      )}
                    </tbody>
                  </table>
                </div>
              </>
            ) : (
              <div className="stackLg">
                <p className="subtle">
                  Hover nodes for preview, click to pin, drag to arrange, and use reset if you want a fresh clustered
                  layout.
                </p>
                <p className="subtle">
                  Edge labels are contextual: they appear for highlighted relations and focused neighborhoods.
                </p>
              </div>
            )}
          </Card>
        </section>
      ) : (
        <Card>
          <CardContent className="py-6">No graph data for this conversation yet.</CardContent>
        </Card>
      )}

      <DeleteConfirmDialog
        open={pendingDeleteNodeId !== null}
        onOpenChange={(open) => {
          if (!open && !saving) {
            cancelDeleteNode();
          }
        }}
        title={pendingDeleteNode ? `Delete node "${pendingDeleteNode.canonical_name}"?` : "Delete node?"}
        description="Deleting a node will also remove connected edges and related facts."
        onConfirm={() => void confirmDeleteNode()}
        isDeleting={saving}
      />

      <DeleteConfirmDialog
        open={pendingDeleteRelationId !== null}
        onOpenChange={(open) => {
          if (!open && !saving) {
            cancelDeleteRelation();
          }
        }}
        title={
          pendingDeleteRelation
            ? `Delete relation "${pendingDeleteRelation.relation_type}"?`
            : "Delete relation?"
        }
        description="This relation edge will be removed from the graph."
        onConfirm={() => {
          if (pendingDeleteRelationId !== null) {
            void confirmDeleteRelation(pendingDeleteRelationId);
          }
        }}
        isDeleting={saving}
      />
    </div>
  );
}
