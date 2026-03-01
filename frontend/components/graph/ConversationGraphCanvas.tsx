"use client";

import cytoscape, { type Core } from "cytoscape";
import {
  type FormEvent,
  forwardRef,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState
} from "react";

import type { EntityRead, RelationWithEntitiesRead } from "@/lib/api";
import {
  buildConversationGraphElements,
  buildCoseLayoutOptions,
  conversationGraphStyles,
  type GraphNodePosition,
  type GraphNodePositionMap
} from "@/lib/graph-layout";

import { Button } from "../ui/button";
import { Input } from "../ui/input";

export type ConversationGraphCanvasHandle = {
  fitView: () => void;
  centerSelection: () => void;
};

type ConversationGraphCanvasProps = {
  entities: EntityRead[];
  relations: RelationWithEntitiesRead[];
  activeNodeId: number | null;
  selectedNodeId: number | null;
  selectedNode: EntityRead | null;
  highlightRelation: string;
  positions: GraphNodePositionMap;
  resetToken: number;
  onNodeHover: (nodeId: number | null) => void;
  onNodeSelect: (nodeId: number | null) => void;
  onNodePositionChange: (nodeId: number, position: GraphNodePosition) => void;
  onInlineSave: (nodeId: number, payload: { canonical_name: string; type_label: string }) => Promise<void>;
};

const ConversationGraphCanvas = forwardRef<ConversationGraphCanvasHandle, ConversationGraphCanvasProps>(
  function ConversationGraphCanvas(
    {
      entities,
      relations,
      activeNodeId,
      selectedNodeId,
      selectedNode,
      highlightRelation,
      positions,
      resetToken,
      onNodeHover,
      onNodeSelect,
      onNodePositionChange,
      onInlineSave
    },
    ref
  ) {
    const containerRef = useRef<HTMLDivElement | null>(null);
    const cyRef = useRef<Core | null>(null);
    const isMountedRef = useRef(true);
    const layoutRef = useRef<cytoscape.Layouts | null>(null);
    const resetTokenRef = useRef(resetToken);
    const callbacksRef = useRef({
      onNodeHover,
      onNodeSelect,
      onNodePositionChange
    });

    const [inlineDraft, setInlineDraft] = useState({ canonical_name: "", type_label: "" });
    const [inlineSaving, setInlineSaving] = useState(false);
    const [inlineError, setInlineError] = useState<string | null>(null);
    const [editorPosition, setEditorPosition] = useState<{ x: number; y: number } | null>(null);

    callbacksRef.current = {
      onNodeHover,
      onNodeSelect,
      onNodePositionChange
    };

    const elements = useMemo(
      () =>
        buildConversationGraphElements({
          entities,
          relations,
          activeNodeId,
          selectedNodeId,
          highlightRelation,
          positions
        }),
      [activeNodeId, entities, highlightRelation, positions, relations, selectedNodeId]
    );

    useImperativeHandle(
      ref,
      () => ({
        fitView() {
          const cy = cyRef.current;
          if (!cy) {
            return;
          }
          const nodes = cy.nodes(".entity");
          if (nodes.length === 0) {
            return;
          }
          cy.fit(nodes, 90);
        },
        centerSelection() {
          const cy = cyRef.current;
          if (!cy) {
            return;
          }
          const targetId = selectedNodeId ?? activeNodeId;
          if (targetId === null) {
            return;
          }
          const node = cy.$id(String(targetId));
          if (node.empty()) {
            return;
          }
          cy.center(node);
        }
      }),
      [activeNodeId, selectedNodeId]
    );

    useEffect(() => {
      if (!containerRef.current) {
        return;
      }
      isMountedRef.current = true;

      const cy = cytoscape({
        container: containerRef.current,
        elements: [],
        style: conversationGraphStyles as any,
        minZoom: 0.18,
        maxZoom: 2.6,
        wheelSensitivity: 0.22,
        autoungrabify: false,
        boxSelectionEnabled: false,
        userPanningEnabled: true,
        userZoomingEnabled: true
      });
      cyRef.current = cy;

      const handleNodeMouseOver = (event: cytoscape.EventObjectNode) => {
        if (!isMountedRef.current) {
          return;
        }
        const id = Number.parseInt(event.target.id(), 10);
        if (!Number.isNaN(id)) {
          callbacksRef.current.onNodeHover(id);
        }
      };
      const handleNodeMouseOut = () => {
        if (!isMountedRef.current) {
          return;
        }
        callbacksRef.current.onNodeHover(null);
      };
      const handleNodeTap = (event: cytoscape.EventObjectNode) => {
        if (!isMountedRef.current) {
          return;
        }
        const id = Number.parseInt(event.target.id(), 10);
        if (!Number.isNaN(id)) {
          callbacksRef.current.onNodeSelect(id);
        }
      };
      const handleCanvasTap = (event: cytoscape.EventObject) => {
        if (event.target === cy) {
          callbacksRef.current.onNodeHover(null);
        }
      };
      const handleNodeDrag = (event: cytoscape.EventObjectNode) => {
        const id = Number.parseInt(event.target.id(), 10);
        if (Number.isNaN(id)) {
          return;
        }
        const position = event.target.position();
        callbacksRef.current.onNodePositionChange(id, {
          x: position.x,
          y: position.y
        });
      };

      cy.on("mouseover", "node.entity", handleNodeMouseOver);
      cy.on("mouseout", "node.entity", handleNodeMouseOut);
      cy.on("tap", "node.entity", handleNodeTap);
      cy.on("tap", handleCanvasTap);
      cy.on("dragfree", "node.entity", handleNodeDrag);

      return () => {
        isMountedRef.current = false;
        layoutRef.current?.stop();
        layoutRef.current = null;
        cy.removeListener("mouseover", "node.entity", handleNodeMouseOver);
        cy.removeListener("mouseout", "node.entity", handleNodeMouseOut);
        cy.removeListener("tap", "node.entity", handleNodeTap);
        cy.removeListener("tap", handleCanvasTap);
        cy.removeListener("dragfree", "node.entity", handleNodeDrag);
        cy.destroy();
        cyRef.current = null;
      };
    }, []);

    useEffect(() => {
      const cy = cyRef.current;
      if (!cy) {
        return;
      }
      layoutRef.current?.stop();
      layoutRef.current = null;

      cy.batch(() => {
        cy.elements().remove();
        cy.add(elements);
      });

      if (selectedNodeId !== null) {
        const selected = cy.$id(String(selectedNodeId));
        if (selected.nonempty()) {
          selected.select();
        }
      }

      const hasVisiblePositions = entities.some((entity) => positions[entity.id] !== undefined);
      const layoutRequested = resetTokenRef.current !== resetToken;
      if (!hasVisiblePositions || layoutRequested) {
        cy.stop();
        const layout = cy.layout(buildCoseLayoutOptions(true));
        layoutRef.current = layout;
        layout.on("layoutstop", () => {
          if (!isMountedRef.current) {
            return;
          }
          const runtimeCy = cyRef.current;
          if (!runtimeCy || runtimeCy.destroyed()) {
            return;
          }
          runtimeCy.nodes(".entity").forEach((node) => {
            const id = Number.parseInt(node.id(), 10);
            if (Number.isNaN(id)) {
              return;
            }
            const position = node.position();
            callbacksRef.current.onNodePositionChange(id, { x: position.x, y: position.y });
          });
          layoutRef.current = null;
          const nodeCollection = runtimeCy.nodes(".entity");
          if (nodeCollection.length > 0) {
            runtimeCy.fit(nodeCollection, 90);
          }
        });
        layout.run();
      }
      resetTokenRef.current = resetToken;
    }, [elements, entities, positions, resetToken, selectedNodeId]);

    useEffect(() => {
      if (!selectedNode) {
        setInlineDraft({ canonical_name: "", type_label: "" });
        setInlineError(null);
        return;
      }
      setInlineDraft({
        canonical_name: selectedNode.canonical_name,
        type_label: selectedNode.type_label || "untyped"
      });
      setInlineError(null);
    }, [selectedNode]);

    useEffect(() => {
      const cy = cyRef.current;
      if (!cy || !selectedNodeId) {
        setEditorPosition(null);
        return;
      }
      const node = cy.$id(String(selectedNodeId));
      if (node.empty()) {
        setEditorPosition(null);
        return;
      }

      let rafId: number | null = null;
      const scheduleUpdate = () => {
        if (rafId !== null) {
          return;
        }
        rafId = window.requestAnimationFrame(() => {
          rafId = null;
          if (!isMountedRef.current) {
            return;
          }
          const runtimeCy = cyRef.current;
          if (!runtimeCy || runtimeCy.destroyed() || node.removed()) {
            return;
          }
          const rendered = node.renderedPosition();
          setEditorPosition({ x: rendered.x, y: rendered.y });
        });
      };

      scheduleUpdate();
      cy.on("pan", scheduleUpdate);
      cy.on("zoom", scheduleUpdate);
      cy.on("resize", scheduleUpdate);
      cy.on("layoutstop", scheduleUpdate);
      node.on("position", scheduleUpdate);

      return () => {
        cy.removeListener("pan", scheduleUpdate);
        cy.removeListener("zoom", scheduleUpdate);
        cy.removeListener("resize", scheduleUpdate);
        cy.removeListener("layoutstop", scheduleUpdate);
        node.removeListener("position");
        if (rafId !== null) {
          window.cancelAnimationFrame(rafId);
        }
      };
    }, [selectedNodeId, elements]);

    async function handleInlineSubmit(event: FormEvent<HTMLFormElement>) {
      event.preventDefault();
      if (!selectedNode) {
        return;
      }
      const nextCanonicalName = inlineDraft.canonical_name.trim();
      const nextTypeLabel = inlineDraft.type_label.trim();
      if (!nextCanonicalName || !nextTypeLabel) {
        setInlineError("Node name and type label are required.");
        return;
      }
      setInlineSaving(true);
      setInlineError(null);
      try {
        await onInlineSave(selectedNode.id, {
          canonical_name: nextCanonicalName,
          type_label: nextTypeLabel
        });
      } catch (error) {
        setInlineError(error instanceof Error ? error.message : "Failed to save node.");
      } finally {
        setInlineSaving(false);
      }
    }

    function handleInlineReset() {
      if (!selectedNode) {
        return;
      }
      setInlineDraft({
        canonical_name: selectedNode.canonical_name,
        type_label: selectedNode.type_label || "untyped"
      });
      setInlineError(null);
    }

    return (
      <div className="graphStudioCanvasWrap">
        <div
          ref={containerRef}
          className="graphCySurface"
          role="img"
          aria-label="Conversation graph whiteboard canvas"
        />
        {selectedNode && editorPosition ? (
          <form
            className="graphInlineEditor"
            style={{ left: editorPosition.x, top: editorPosition.y }}
            onSubmit={handleInlineSubmit}
          >
            <label className="field">
              <span>Name</span>
              <Input
                value={inlineDraft.canonical_name}
                onChange={(event) =>
                  setInlineDraft((current) => ({ ...current, canonical_name: event.target.value }))
                }
                disabled={inlineSaving}
              />
            </label>
            <label className="field">
              <span>Type</span>
              <Input
                value={inlineDraft.type_label}
                onChange={(event) =>
                  setInlineDraft((current) => ({ ...current, type_label: event.target.value }))
                }
                disabled={inlineSaving}
              />
            </label>
            {inlineError ? <p className="graphInlineError">{inlineError}</p> : null}
            <div className="graphInlineEditorActions">
              <Button type="submit" size="sm" disabled={inlineSaving}>
                {inlineSaving ? "Saving..." : "Save"}
              </Button>
              <Button type="button" size="sm" variant="outline" onClick={handleInlineReset} disabled={inlineSaving}>
                Reset
              </Button>
            </div>
          </form>
        ) : null}
      </div>
    );
  }
);

export default ConversationGraphCanvas;
