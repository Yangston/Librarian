"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useAppSettings, useIsDevMode } from "@/components/AppSettingsProvider";
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
  acceptWorkspaceGraphSuggestionsV3,
  type CollectionTreeNode,
  type ConversationGraphData,
  type ConversationsListResponse,
  type PodRead,
  type RelationWithEntitiesRead,
  deleteEntityRecord,
  deleteRelation,
  enrichWorkspaceCollectionV3,
  enrichWorkspaceSpaceV3,
  getConversationGraph,
  getConversations,
  getLatestWorkspaceEnrichmentRunForSpaceV3,
  getPodTree,
  getPods,
  getScopedGraph,
  rejectWorkspaceGraphSuggestionsV3,
  updateEntityRecord,
  updateRelation
} from "../../../lib/api";
import type { GraphNodePosition } from "../../../lib/graph-layout";
import { useWorkspaceEnrichmentMonitor } from "../../../lib/use-workspace-enrichment-monitor";

function normalizeTypeLabel(typeLabel: string): string {
  const clean = typeLabel.trim();
  return clean.length > 0 ? clean : "untyped";
}

function mapScopedGraphToConversationGraph(payload: Awaited<ReturnType<typeof getScopedGraph>>): ConversationGraphData {
  const nodeById = new Map(payload.nodes.map((node) => [node.entity_id, node]));
  const now = new Date().toISOString();
  return {
    conversation_id: `workspace:${payload.scope_mode}`,
    entities: payload.nodes.map((node) => ({
      id: node.entity_id,
      conversation_id: `workspace:${payload.scope_mode}`,
      name: node.canonical_name,
      display_name: node.display_name,
      canonical_name: node.canonical_name,
      type: node.type_label || "Unspecified",
      type_label: node.type_label || "Unspecified",
      aliases_json: [],
      known_aliases_json: [],
      tags_json: [
        ...(node.external ? ["external"] : []),
        ...(node.pending_suggestion_count > 0 ? ["pending-suggestions"] : [])
      ],
      first_seen_timestamp: now,
      resolution_confidence: 1,
      resolution_reason: null,
      resolver_version: null,
      merged_into_id: null,
      created_at: now,
      updated_at: now
    })),
    relations: payload.edges.map((edge) => ({
      id: edge.relation_id,
      conversation_id: `workspace:${payload.scope_mode}`,
      from_entity_id: edge.from_entity_id,
      from_entity_name: nodeById.get(edge.from_entity_id)?.canonical_name ?? String(edge.from_entity_id),
      relation_type: edge.relation_type,
      to_entity_id: edge.to_entity_id,
      to_entity_name: nodeById.get(edge.to_entity_id)?.canonical_name ?? String(edge.to_entity_id),
      scope: "global",
      confidence: edge.confidence,
      qualifiers_json: {
        suggested: edge.suggested,
        status: edge.status,
        source_kind: edge.source_kind
      },
      source_message_ids_json: [],
      extractor_run_id: null,
      created_at: now
    }))
  };
}

export default function GraphPage() {
  const isDevMode = useIsDevMode();
  const { settings } = useAppSettings();
  const [viewMode, setViewMode] = useState<"conversation" | "workspace">("conversation");
  const [conversationList, setConversationList] = useState<ConversationsListResponse | null>(null);
  const [conversationInput, setConversationInput] = useState("");
  const [conversationId, setConversationId] = useState("");
  const [workspaceScopeMode, setWorkspaceScopeMode] = useState<"global" | "pod" | "collection">("global");
  const [scopePodId, setScopePodId] = useState<string>("__none__");
  const [scopeCollectionId, setScopeCollectionId] = useState<string>("__none__");
  const [oneHopScope, setOneHopScope] = useState(false);
  const [includeExternalScope, setIncludeExternalScope] = useState(false);
  const [pendingGraphSuggestionCount, setPendingGraphSuggestionCount] = useState(0);
  const [pods, setPods] = useState<PodRead[]>([]);
  const [scopeCollections, setScopeCollections] = useState<CollectionTreeNode[]>([]);
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
  const [nodeDraft, setNodeDraft] = useState({ canonical_name: "", type_label: "" });
  const [nodeDraftError, setNodeDraftError] = useState<string | null>(null);
  const [isGraphFullscreen, setIsGraphFullscreen] = useState(false);

  const canvasRef = useRef<ConversationGraphCanvasHandle | null>(null);
  const graphPanelRef = useRef<HTMLDivElement | null>(null);
  const loadedConversationRef = useRef<string | null>(null);

  useEffect(() => {
    if (!isDevMode && viewMode !== "conversation") {
      setViewMode("conversation");
    }
  }, [isDevMode, viewMode]);

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

  async function loadPods() {
    const podRows = await getPods();
    setPods(podRows);
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

  const loadConversationGraph = useCallback(
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
      setPendingGraphSuggestionCount(0);
      setHoveredNodeId(null);
      setSelectedNodeId((current) =>
        current !== null && payload.entities.some((entity) => entity.id === current) ? current : null
      );
    },
    [clearLayoutState, pruneStalePositions]
  );

  const loadWorkspaceGraph = useCallback(
    async ({
      scopeMode,
      podId,
      collectionId,
      oneHop,
      includeExternal
    }: {
      scopeMode: "global" | "pod" | "collection";
      podId?: number;
      collectionId?: number;
      oneHop: boolean;
      includeExternal: boolean;
    }) => {
      const payload = await getScopedGraph({
        scope_mode: scopeMode,
        pod_id: podId,
        collection_id: collectionId,
        one_hop: oneHop,
        include_external: includeExternal
      });
      const mapped = mapScopedGraphToConversationGraph(payload);
      const graphKey = `${payload.scope_mode}:${payload.pod_id ?? "none"}:${payload.collection_id ?? "none"}:${
        payload.one_hop ? "1" : "0"
      }:${payload.include_external ? "1" : "0"}`;
      const conversationChanged = loadedConversationRef.current !== graphKey;
      loadedConversationRef.current = graphKey;
      if (conversationChanged) {
        clearLayoutState();
      } else {
        pruneStalePositions(mapped);
      }
      setGraph(mapped);
      setPendingGraphSuggestionCount(payload.pending_suggestion_count ?? 0);
      setHoveredNodeId(null);
      setSelectedNodeId((current) =>
        current !== null && mapped.entities.some((entity) => entity.id === current) ? current : null
      );
    },
    [clearLayoutState, pruneStalePositions]
  );

  function buildGraphScopeKey(): string {
    if (workspaceScopeMode === "collection" && scopeCollectionId !== "__none__") {
      return `collection-${scopeCollectionId}`;
    }
    if (workspaceScopeMode === "pod" && scopePodId !== "__none__") {
      return `pod-${scopePodId}`;
    }
    return "global";
  }

  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const query = typeof window === "undefined" ? new URLSearchParams() : new URLSearchParams(window.location.search);
        const queryConversationId = query.get("conversation_id")?.trim() || null;
        const queryScopeMode = query.get("scope_mode")?.trim() || null;
        const queryPodId = query.get("pod_id")?.trim() || null;
        const queryCollectionId = query.get("collection_id")?.trim() || null;
        const queryOneHop = query.get("one_hop");
        const queryIncludeExternal = query.get("include_external");
        await loadConversations(queryConversationId);
        await loadPods();
        if (
          isDevMode &&
          (queryScopeMode === "global" || queryScopeMode === "pod" || queryScopeMode === "collection")
        ) {
          setViewMode("workspace");
          setWorkspaceScopeMode(queryScopeMode);
          setScopePodId(queryPodId || "__none__");
          setScopeCollectionId(queryCollectionId || "__none__");
          setOneHopScope(queryOneHop === "true" || queryOneHop === "1");
          setIncludeExternalScope(queryIncludeExternal === "true" || queryIncludeExternal === "1");
        } else {
          setViewMode("conversation");
        }
      } catch (err) {
        if (!active) {
          return;
        }
        setError(err instanceof Error ? err.message : "Failed to load graph controls.");
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
  }, [isDevMode]);

  useEffect(() => {
    if (scopePodId === "__none__") {
      setScopeCollections([]);
      if (workspaceScopeMode === "collection") {
        setScopeCollectionId("__none__");
      }
      return;
    }
    let active = true;
    async function loadScopeCollections() {
      try {
        const payload = await getPodTree(Number.parseInt(scopePodId, 10));
        if (!active) {
          return;
        }
        setScopeCollections(payload.tree);
      } catch {
        if (!active) {
          return;
        }
        setScopeCollections([]);
      }
    }
    void loadScopeCollections();
    return () => {
      active = false;
    };
  }, [scopePodId, workspaceScopeMode]);

  useEffect(() => {
    let active = true;
    async function hydrateGraph() {
      if (viewMode !== "conversation") {
        return;
      }
      if (!conversationId.trim()) {
        return;
      }
      setLoading(true);
      setError(null);
      try {
        await loadConversationGraph(conversationId);
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
  }, [conversationId, loadConversationGraph, viewMode]);

  const relationLabels = useMemo(
    () => Array.from(new Set((graph?.relations ?? []).map((relation) => relation.relation_type))).sort(),
    [graph?.relations]
  );
  const scopeCollectionOptions = useMemo(() => {
    const flat: Array<{ id: number; name: string }> = [];
    const walk = (nodes: CollectionTreeNode[]) => {
      nodes.forEach((node) => {
        flat.push({ id: node.collection.id, name: node.collection.name });
        walk(node.children);
      });
    };
    walk(scopeCollections);
    return flat;
  }, [scopeCollections]);

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

  useEffect(() => {
    if (!pinnedNode) {
      setNodeDraft({ canonical_name: "", type_label: "" });
      setNodeDraftError(null);
      return;
    }
    setNodeDraft({
      canonical_name: pinnedNode.canonical_name,
      type_label: pinnedNode.type_label || "untyped"
    });
    setNodeDraftError(null);
  }, [pinnedNode]);

  const refreshGraph = useCallback(async () => {
    if (viewMode === "conversation") {
      if (!conversationId.trim()) {
        return;
      }
      await loadConversationGraph(conversationId.trim());
      return;
    }
    const podId = scopePodId === "__none__" ? undefined : Number.parseInt(scopePodId, 10);
    const collectionId =
      scopeCollectionId === "__none__" ? undefined : Number.parseInt(scopeCollectionId, 10);
    await loadWorkspaceGraph({
      scopeMode: workspaceScopeMode,
      podId,
      collectionId,
      oneHop: oneHopScope,
      includeExternal: includeExternalScope
    });
  }, [
    conversationId,
    includeExternalScope,
    loadConversationGraph,
    loadWorkspaceGraph,
    oneHopScope,
    scopeCollectionId,
    scopePodId,
    viewMode,
    workspaceScopeMode
  ]);

  const graphEnrichment = useWorkspaceEnrichmentMonitor({
    onCompleted: async () => {
      await refreshGraph();
    },
    onFailed: (message) => {
      setError(message);
    }
  });

  async function handleEnrichWorkspaceGraph() {
    setError(null);
    try {
      const activePodId =
        workspaceScopeMode === "collection" && scopePodId !== "__none__"
          ? Number.parseInt(scopePodId, 10)
          : scopePodId !== "__none__"
          ? Number.parseInt(scopePodId, 10)
          : null;
      if (activePodId !== null) {
        const latestRun = await getLatestWorkspaceEnrichmentRunForSpaceV3(activePodId);
        if (latestRun && (latestRun.status === "queued" || latestRun.status === "running")) {
          graphEnrichment.beginMonitoring(latestRun);
          return;
        }
      }
      if (workspaceScopeMode === "collection" && scopeCollectionId !== "__none__") {
        await graphEnrichment.startRun(() =>
          enrichWorkspaceCollectionV3(Number.parseInt(scopeCollectionId, 10), {
            include_sources: settings.enrichmentSources
          })
        );
      } else if (scopePodId !== "__none__") {
        await graphEnrichment.startRun(() =>
          enrichWorkspaceSpaceV3(Number.parseInt(scopePodId, 10), {
            include_sources: settings.enrichmentSources
          })
        );
      } else {
        throw new Error("Select a pod or collection scope before enriching the graph.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to enrich graph.");
    }
  }

  async function handleAcceptGraphSuggestions() {
    try {
      await acceptWorkspaceGraphSuggestionsV3(buildGraphScopeKey());
      await refreshGraph();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to accept graph suggestions.");
    }
  }

  async function handleRejectGraphSuggestions() {
    try {
      await rejectWorkspaceGraphSuggestionsV3(buildGraphScopeKey());
      await refreshGraph();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to reject graph suggestions.");
    }
  }

  const hasActiveGraphRun = graphEnrichment.run?.status === "queued" || graphEnrichment.run?.status === "running";

  useEffect(() => {
    let active = true;
    async function hydrateWorkspaceGraph() {
      if (viewMode !== "workspace") {
        return;
      }
      if (workspaceScopeMode === "pod" && scopePodId === "__none__") {
        return;
      }
      if (workspaceScopeMode === "collection" && scopeCollectionId === "__none__") {
        return;
      }
      setLoading(true);
      setError(null);
      try {
        await refreshGraph();
      } catch (err) {
        if (!active) {
          return;
        }
        setError(err instanceof Error ? err.message : "Failed to load scoped graph.");
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }
    void hydrateWorkspaceGraph();
    return () => {
      active = false;
    };
  }, [refreshGraph, scopeCollectionId, scopePodId, viewMode, workspaceScopeMode]);

  useEffect(() => {
    if (viewMode !== "workspace" || scopePodId === "__none__") {
      graphEnrichment.clearRun();
      return;
    }
    let active = true;
    async function loadLatestRun() {
      try {
        const latestRun = await getLatestWorkspaceEnrichmentRunForSpaceV3(Number.parseInt(scopePodId, 10));
        if (!active) {
          return;
        }
        if (latestRun && (latestRun.status === "queued" || latestRun.status === "running")) {
          graphEnrichment.beginMonitoring(latestRun);
        } else {
          graphEnrichment.clearRun();
        }
      } catch {
        if (active) {
          graphEnrichment.clearRun();
        }
      }
    }
    void loadLatestRun();
    return () => {
      active = false;
    };
  }, [scopePodId, viewMode]);

  async function handleLoadGraph(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (viewMode === "conversation") {
      const clean = conversationInput.trim();
      if (!clean) {
        return;
      }
      setConversationInput(clean);
      if (clean === conversationId) {
        setLoading(true);
        setError(null);
        try {
          await loadConversationGraph(clean);
        } catch (err) {
          setError(err instanceof Error ? err.message : "Failed to load graph.");
        } finally {
          setLoading(false);
        }
        return;
      }
      setConversationId(clean);
      return;
    }

    if (workspaceScopeMode === "pod" && scopePodId === "__none__") {
      setError("Select a pod for pod scope.");
      return;
    }
    if (workspaceScopeMode === "collection" && scopeCollectionId === "__none__") {
      setError("Select a collection for collection scope.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await refreshGraph();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load scoped graph.");
    } finally {
      setLoading(false);
    }
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

  useEffect(() => {
    if (selectedNodeId === null) {
      return;
    }
    const handleDocumentPointerDown = (event: PointerEvent) => {
      const target = event.target as Element | null;
      if (!target) {
        return;
      }
      if (target.closest(".graphInspector")) {
        return;
      }
      if (target.closest(".graphCySurface")) {
        return;
      }
      setSelectedNodeId(null);
    };

    document.addEventListener("pointerdown", handleDocumentPointerDown, true);
    return () => {
      document.removeEventListener("pointerdown", handleDocumentPointerDown, true);
    };
  }, [selectedNodeId]);

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

  const handleSavePinnedNode = useCallback(async () => {
    if (!pinnedNode) {
      return;
    }
    const nextCanonicalName = nodeDraft.canonical_name.trim();
    const nextTypeLabel = nodeDraft.type_label.trim();
    if (!nextCanonicalName || !nextTypeLabel) {
      setNodeDraftError("Node name and type label are required.");
      return;
    }
    setSaving(true);
    setError(null);
    setNodeDraftError(null);
    try {
      await updateEntityRecord(pinnedNode.id, {
        canonical_name: nextCanonicalName,
        type_label: nextTypeLabel
      });
      await refreshGraph();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to update node.";
      setError(message);
      setNodeDraftError(message);
    } finally {
      setSaving(false);
    }
  }, [nodeDraft.canonical_name, nodeDraft.type_label, pinnedNode, refreshGraph]);

  const handleResetPinnedNodeDraft = useCallback(() => {
    if (!pinnedNode) {
      return;
    }
    setNodeDraft({
      canonical_name: pinnedNode.canonical_name,
      type_label: pinnedNode.type_label || "untyped"
    });
    setNodeDraftError(null);
  }, [pinnedNode]);

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

  async function toggleGraphFullscreen() {
    const panel = graphPanelRef.current;
    if (!panel) {
      return;
    }
    try {
      if (document.fullscreenElement === panel) {
        await document.exitFullscreen();
        return;
      }
      await panel.requestFullscreen();
    } catch {
      setError("Fullscreen is not available in this browser context.");
    }
  }

  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsGraphFullscreen(document.fullscreenElement === graphPanelRef.current);
    };
    document.addEventListener("fullscreenchange", handleFullscreenChange);
    return () => {
      document.removeEventListener("fullscreenchange", handleFullscreenChange);
    };
  }, []);

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
          <form className="graphTopbar" onSubmit={handleLoadGraph}>
            {isDevMode ? (
              <label className="field">
                <Label>View Mode</Label>
                <Select
                  value={viewMode}
                  onValueChange={(value) => setViewMode(value as "conversation" | "workspace")}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="conversation">Conversation</SelectItem>
                    <SelectItem value="workspace">Workspace Scope</SelectItem>
                  </SelectContent>
                </Select>
              </label>
            ) : null}
            <label className="field">
              <Label>{viewMode === "conversation" ? "Conversation" : "Scope"}</Label>
              {!isDevMode || viewMode === "conversation" ? (
                <>
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
                </>
              ) : (
                <Select
                  value={workspaceScopeMode}
                  onValueChange={(value) =>
                    setWorkspaceScopeMode(value as "global" | "pod" | "collection")
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="global">Global</SelectItem>
                    <SelectItem value="pod">Pod</SelectItem>
                    <SelectItem value="collection">Collection</SelectItem>
                  </SelectContent>
                </Select>
              )}
            </label>
            {isDevMode && viewMode === "workspace" ? (
              <label className="field">
                <Label>Pod</Label>
                <Select value={scopePodId} onValueChange={setScopePodId}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__none__">(none)</SelectItem>
                    {pods.map((pod) => (
                      <SelectItem key={pod.id} value={String(pod.id)}>
                        {pod.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </label>
            ) : null}
            {isDevMode && viewMode === "workspace" ? (
              <label className="field">
                <Label>Collection</Label>
                <Select value={scopeCollectionId} onValueChange={setScopeCollectionId}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__none__">(none)</SelectItem>
                    {scopeCollectionOptions.map((collection) => (
                      <SelectItem key={collection.id} value={String(collection.id)}>
                        {collection.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </label>
            ) : null}
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
            {isDevMode && viewMode === "workspace" ? (
              <>
                <label className="field">
                  <Label>Collection 1-hop</Label>
                  <Select
                    value={oneHopScope ? "true" : "false"}
                    onValueChange={(value) => setOneHopScope(value === "true")}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="false">Disabled</SelectItem>
                      <SelectItem value="true">Enabled</SelectItem>
                    </SelectContent>
                  </Select>
                </label>
                <label className="field">
                  <Label>Include External</Label>
                  <Select
                    value={includeExternalScope ? "true" : "false"}
                    onValueChange={(value) => setIncludeExternalScope(value === "true")}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="false">No</SelectItem>
                      <SelectItem value="true">Yes</SelectItem>
                    </SelectContent>
                  </Select>
                </label>
              </>
            ) : null}
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
          <Card ref={graphPanelRef} className="graphCanvasPanel border-border/80 bg-card/95 p-4">
            <div className="sectionTitleRow">
              <h3>Graph Canvas</h3>
              {viewMode === "conversation" ? (
                <Link href={`/app/conversations/${encodeURIComponent(graph.conversation_id)}`}>Open conversation</Link>
              ) : (
                <span className="subtle">Workspace-scoped graph</span>
              )}
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge variant="outline">Nodes: {visibleEntities.length}</Badge>
              <Badge variant="outline">Edges: {visibleRelations.length}</Badge>
              <Badge variant="outline">Clusters: {visibleClusterCount}</Badge>
              <Badge variant="outline">Mode: Freeform</Badge>
              {viewMode === "workspace" && pendingGraphSuggestionCount > 0 ? (
                <Badge variant="outline">{pendingGraphSuggestionCount} pending suggestions</Badge>
              ) : null}
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
              <Button type="button" variant="outline" onClick={() => void toggleGraphFullscreen()}>
                {isGraphFullscreen ? "Exit fullscreen" : "Fullscreen"}
              </Button>
              {viewMode === "workspace" ? (
                <>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => void handleEnrichWorkspaceGraph()}
                    disabled={graphEnrichment.isStartingRun || hasActiveGraphRun}
                  >
                    {graphEnrichment.isStartingRun ? "Starting..." : "Refresh enrichment"}
                  </Button>
                  {hasActiveGraphRun ? (
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => void graphEnrichment.refreshStatus()}
                      disabled={graphEnrichment.isStartingRun}
                    >
                      Refresh status
                    </Button>
                  ) : null}
                </>
              ) : null}
              {viewMode === "workspace" && pendingGraphSuggestionCount > 0 ? (
                <>
                  <Button type="button" variant="outline" onClick={() => void handleAcceptGraphSuggestions()}>
                    Accept pending
                  </Button>
                  <Button type="button" variant="outline" onClick={() => void handleRejectGraphSuggestions()}>
                    Reject pending
                  </Button>
                </>
              ) : null}
            </div>
            {viewMode === "workspace" && graphEnrichment.statusMessage ? (
              <p className="text-xs text-muted-foreground">{graphEnrichment.statusMessage}</p>
            ) : null}
            <div className="graphLegend">
              <span className="legendItem">
                <span className="legendSwatch graphLegendDefault" /> relation edge
              </span>
              <span className="legendItem">
                <span className="legendSwatch graphLegendHighlight" /> pending suggested edge
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
              highlightRelation={highlightRelation}
              positions={nodePositions}
              resetToken={layoutResetToken}
              onNodeHover={handleNodeHover}
              onNodeSelect={handleNodeSelect}
              onNodePositionChange={handleNodePositionChange}
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
                  {isDevMode ? (
                    <p className="subtle">Aliases: {selectedNode.known_aliases_json.join(", ") || "(none)"}</p>
                  ) : null}
                  {isPinnedInspector ? (
                    <>
                      <form
                        className="gridForm"
                        onSubmit={(event) => {
                          event.preventDefault();
                          void handleSavePinnedNode();
                        }}
                      >
                        <label className="field">
                          <span>Name</span>
                          <Input
                            value={nodeDraft.canonical_name}
                            onChange={(event) =>
                              setNodeDraft((current) => ({ ...current, canonical_name: event.target.value }))
                            }
                            disabled={saving}
                          />
                        </label>
                        <label className="field">
                          <span>Type</span>
                          <Input
                            value={nodeDraft.type_label}
                            onChange={(event) =>
                              setNodeDraft((current) => ({ ...current, type_label: event.target.value }))
                            }
                            disabled={saving}
                          />
                        </label>
                        <div className="inlineActions">
                          <Button type="submit" disabled={saving}>
                            Save node
                          </Button>
                          <Button
                            type="button"
                            variant="outline"
                            onClick={handleResetPinnedNodeDraft}
                            disabled={saving}
                          >
                            Reset
                          </Button>
                        </div>
                      </form>
                      {nodeDraftError ? <p className="errorText">{nodeDraftError}</p> : null}
                      <div className="toolbar">
                        <Link href={`/app/entities/${selectedNode.id}`}>Open entity page</Link>
                        <DeleteActionButton type="button" onClick={requestDeleteNode} disabled={saving}>
                          Delete node
                        </DeleteActionButton>
                      </div>
                    </>
                  ) : (
                    <p className="subtle">Click this node to pin it. Name/type editing is available in this panel.</p>
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
                        {isDevMode ? <th>Confidence</th> : null}
                        {isPinnedInspector ? <th>Actions</th> : null}
                      </tr>
                    </thead>
                    <tbody>
                      {selectedNodeRelations.length === 0 ? (
                        <tr>
                          <td
                            colSpan={isPinnedInspector ? (isDevMode ? 5 : 4) : isDevMode ? 4 : 3}
                            className="emptyCell"
                          >
                            No connected relations.
                          </td>
                        </tr>
                      ) : (
                        selectedNodeRelations.map((relation) => {
                          const isEditing = editingRelationId === relation.id;
                          const isWorkspaceSuggestion = Boolean(relation.qualifiers_json?.suggested) || relation.id < 0;
                          const isSyntheticWorkspaceEdge = relation.id >= 1000000;
                          const canMutateRelation = !isWorkspaceSuggestion && !isSyntheticWorkspaceEdge;
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
                                  <div className="flex items-center gap-2">
                                    <span>{relation.relation_type}</span>
                                    {isWorkspaceSuggestion ? (
                                      <span className="tag border-amber-300 bg-amber-100 text-amber-900">pending</span>
                                    ) : null}
                                  </div>
                                )}
                              </td>
                              <td>{relation.to_entity_name}</td>
                              {isDevMode ? (
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
                              ) : null}
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
                                        disabled={saving || !canMutateRelation}
                                      >
                                        Edit
                                      </Button>
                                      <DeleteActionButton
                                        type="button"
                                        onClick={() => requestDeleteRelation(relation.id)}
                                        disabled={saving || !canMutateRelation}
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
          <CardContent className="py-6">
            {viewMode === "workspace" && hasActiveGraphRun
              ? "Workspace graph updating. Accepted graph edges will appear when sync finishes."
              : "No graph data for this conversation yet."}
          </CardContent>
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
