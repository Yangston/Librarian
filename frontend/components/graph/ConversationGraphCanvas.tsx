"use client";

import cytoscape, { type Core } from "cytoscape";
import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef
} from "react";

import type { EntityRead, RelationWithEntitiesRead } from "@/lib/api";
import {
  buildClusteredRadialPositions,
  buildConversationGraphElements,
  buildGraphInteractionState,
  conversationGraphStyles,
  type GraphInteractionState,
  type GraphNodePosition,
  type GraphNodePositionMap
} from "@/lib/graph-layout";

export type ConversationGraphCanvasHandle = {
  fitView: () => void;
  centerSelection: () => void;
};

type ConversationGraphCanvasProps = {
  entities: EntityRead[];
  relations: RelationWithEntitiesRead[];
  activeNodeId: number | null;
  selectedNodeId: number | null;
  highlightRelation: string;
  positions: GraphNodePositionMap;
  resetToken: number;
  onNodeHover: (nodeId: number | null) => void;
  onNodeSelect: (nodeId: number | null) => void;
  onNodePositionChange: (nodeId: number, position: GraphNodePosition) => void;
};

type ClusterMoveSession = {
  clusterId: string;
  startPointer: { x: number; y: number };
  childStartPositions: Array<{ nodeId: number; x: number; y: number }>;
};

const CLUSTER_EDGE_RING_THRESHOLD_PX = 14;

function isClusterEdgeGrab(
  node: cytoscape.NodeSingular,
  renderedPosition: cytoscape.Position,
  thresholdPx: number
): boolean {
  const bounds = node.renderedBoundingBox({
    includeLabels: false,
    includeNodes: true,
    includeEdges: false,
    includeOverlays: false
  });
  const distanceToNearestEdge = Math.min(
    Math.abs(renderedPosition.x - bounds.x1),
    Math.abs(bounds.x2 - renderedPosition.x),
    Math.abs(renderedPosition.y - bounds.y1),
    Math.abs(bounds.y2 - renderedPosition.y)
  );
  const halfSize = Math.max(2, Math.min(bounds.w, bounds.h) / 2);
  return distanceToNearestEdge <= Math.min(thresholdPx, halfSize);
}

function applyInteractionClasses(cy: Core, interactionState: GraphInteractionState): void {
  cy.batch(() => {
    cy.nodes(".entity").forEach((node) => {
      const nodeId = node.id();
      node.removeClass("selected focused dimmed");
      if (interactionState.selectedNodeId === nodeId) {
        node.addClass("selected");
      }
      if (interactionState.focusedNodeIds) {
        if (interactionState.focusedNodeIds.has(nodeId)) {
          node.addClass("focused");
        } else {
          node.addClass("dimmed");
        }
      }
    });

    cy.edges(".relation").forEach((edge) => {
      const edgeId = edge.id();
      edge.removeClass("focus highlight showLabel dimmed");
      if (interactionState.focusEdgeIds.has(edgeId)) {
        edge.addClass("focus");
      }
      if (interactionState.highlightEdgeIds.has(edgeId)) {
        edge.addClass("highlight");
      }
      if (interactionState.labelEdgeIds.has(edgeId)) {
        edge.addClass("showLabel");
      }
      if (interactionState.dimmedEdgeIds.has(edgeId)) {
        edge.addClass("dimmed");
      }
    });
  });
}

const ConversationGraphCanvas = forwardRef<ConversationGraphCanvasHandle, ConversationGraphCanvasProps>(
  function ConversationGraphCanvas(
    {
      entities,
      relations,
      activeNodeId,
      selectedNodeId,
      highlightRelation,
      positions,
      resetToken,
      onNodeHover,
      onNodeSelect,
      onNodePositionChange
    },
    ref
  ) {
    const containerRef = useRef<HTMLDivElement | null>(null);
    const cyRef = useRef<Core | null>(null);
    const isMountedRef = useRef(true);
    const resetTokenRef = useRef(resetToken);
    const clusterMoveSessionRef = useRef<ClusterMoveSession | null>(null);
    const callbacksRef = useRef({
      onNodeHover,
      onNodeSelect,
      onNodePositionChange
    });

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
          positions
        }),
      [entities, positions, relations]
    );

    const interactionState = useMemo(
      () =>
        buildGraphInteractionState({
          entities,
          relations,
          activeNodeId,
          selectedNodeId,
          highlightRelation
        }),
      [activeNodeId, entities, highlightRelation, relations, selectedNodeId]
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
        minZoom: 0.12,
        maxZoom: 3.4,
        wheelSensitivity: 1.15,
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
        if (!isMountedRef.current) {
          return;
        }
        const target = event.target;
        if (target !== cy && typeof (target as cytoscape.SingularElementReturnValue).hasClass === "function") {
          const maybeElement = target as cytoscape.SingularElementReturnValue;
          if (maybeElement.hasClass("entity")) {
            return;
          }
        }
        callbacksRef.current.onNodeSelect(null);
        if (target === cy) {
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
      const handleClusterMouseMove = (event: cytoscape.EventObjectNode) => {
        if (clusterMoveSessionRef.current?.clusterId === event.target.id()) {
          return;
        }
        const rendered = event.renderedPosition;
        if (!rendered) {
          return;
        }
        const nearEdge = isClusterEdgeGrab(event.target, rendered, CLUSTER_EDGE_RING_THRESHOLD_PX);
        event.target.toggleClass("dragArmed", nearEdge);
      };
      const handleClusterMouseOut = (event: cytoscape.EventObjectNode) => {
        if (clusterMoveSessionRef.current?.clusterId !== event.target.id()) {
          event.target.removeClass("dragArmed");
        }
      };
      const finishClusterMoveSession = (commit: boolean) => {
        const session = clusterMoveSessionRef.current;
        if (!session) {
          return;
        }
        const cluster = cy.$id(session.clusterId);
        if (cluster.nonempty()) {
          cluster.removeClass("dragging");
          cluster.removeClass("dragArmed");
          if (commit) {
            cluster.children(".entity").forEach((child) => {
              const nodeId = Number.parseInt(child.id(), 10);
              if (Number.isNaN(nodeId)) {
                return;
              }
              const position = child.position();
              callbacksRef.current.onNodePositionChange(nodeId, {
                x: position.x,
                y: position.y
              });
            });
          }
        }
        clusterMoveSessionRef.current = null;
        cy.userPanningEnabled(true);
      };
      const handleClusterTapStart = (event: cytoscape.EventObjectNode) => {
        if (clusterMoveSessionRef.current) {
          return;
        }
        const rendered = event.renderedPosition;
        if (!rendered) {
          return;
        }
        const cluster = event.target;
        const nearEdge = isClusterEdgeGrab(cluster, rendered, CLUSTER_EDGE_RING_THRESHOLD_PX);
        if (nearEdge) {
          callbacksRef.current.onNodeSelect(null);
          callbacksRef.current.onNodeHover(null);
          const childStartPositions: Array<{ nodeId: number; x: number; y: number }> = [];
          cluster.children(".entity").forEach((child) => {
            const nodeId = Number.parseInt(child.id(), 10);
            if (Number.isNaN(nodeId)) {
              return;
            }
            const start = child.position();
            childStartPositions.push({ nodeId, x: start.x, y: start.y });
          });
          clusterMoveSessionRef.current = {
            clusterId: cluster.id(),
            startPointer: { x: rendered.x, y: rendered.y },
            childStartPositions
          };
          cy.userPanningEnabled(false);
          cluster.removeClass("dragArmed");
          cluster.addClass("dragging");
          return;
        }
      };
      const handleTapDrag = (event: cytoscape.EventObject) => {
        const moveSession = clusterMoveSessionRef.current;
        if (!moveSession) {
          return;
        }
        const rendered = event.renderedPosition;
        if (!rendered) {
          return;
        }
        const cluster = cy.$id(moveSession.clusterId);
        if (cluster.empty()) {
          finishClusterMoveSession(false);
          return;
        }
        const zoom = cy.zoom() || 1;
        const dx = (rendered.x - moveSession.startPointer.x) / zoom;
        const dy = (rendered.y - moveSession.startPointer.y) / zoom;
        cy.batch(() => {
          moveSession.childStartPositions.forEach((entry) => {
            const child = cy.$id(String(entry.nodeId));
            if (child.nonempty()) {
              child.position({
                x: entry.x + dx,
                y: entry.y + dy
              });
            }
          });
        });
      };
      const handleTapEnd = () => {
        finishClusterMoveSession(true);
      };
      const handlePointerUp = () => {
        finishClusterMoveSession(true);
      };

      cy.on("mouseover", "node.entity", handleNodeMouseOver);
      cy.on("mouseout", "node.entity", handleNodeMouseOut);
      cy.on("tap", "node.entity", handleNodeTap);
      cy.on("tap", handleCanvasTap);
      cy.on("dragfree", "node.entity", handleNodeDrag);
      cy.on("mousemove", "node.cluster", handleClusterMouseMove);
      cy.on("mouseout", "node.cluster", handleClusterMouseOut);
      cy.on("tapstart", "node.cluster", handleClusterTapStart);
      cy.on("tapdrag", handleTapDrag);
      cy.on("tapend", handleTapEnd);
      cy.on("mouseup", handlePointerUp);
      cy.on("touchend", handlePointerUp);

      return () => {
        isMountedRef.current = false;
        finishClusterMoveSession(false);
        cy.removeListener("mouseover", "node.entity", handleNodeMouseOver);
        cy.removeListener("mouseout", "node.entity", handleNodeMouseOut);
        cy.removeListener("tap", "node.entity", handleNodeTap);
        cy.removeListener("tap", handleCanvasTap);
        cy.removeListener("dragfree", "node.entity", handleNodeDrag);
        cy.removeListener("mousemove", "node.cluster", handleClusterMouseMove);
        cy.removeListener("mouseout", "node.cluster", handleClusterMouseOut);
        cy.removeListener("tapstart", "node.cluster", handleClusterTapStart);
        cy.removeListener("tapdrag", handleTapDrag);
        cy.removeListener("tapend", handleTapEnd);
        cy.removeListener("mouseup", handlePointerUp);
        cy.removeListener("touchend", handlePointerUp);
        cy.destroy();
        cyRef.current = null;
      };
    }, []);

    useEffect(() => {
      const cy = cyRef.current;
      if (!cy) {
        return;
      }

      cy.batch(() => {
        cy.elements().remove();
        cy.add(elements);
      });

      const hasVisiblePositions = entities.some((entity) => positions[entity.id] !== undefined);
      const layoutRequested = resetTokenRef.current !== resetToken;
      if (!hasVisiblePositions || layoutRequested) {
        const nextPositions = buildClusteredRadialPositions({ entities, relations });
        cy.batch(() => {
          entities.forEach((entity) => {
            const node = cy.$id(String(entity.id));
            if (node.empty()) {
              return;
            }
            const next = nextPositions[entity.id];
            if (!next) {
              return;
            }
            node.position(next);
            callbacksRef.current.onNodePositionChange(entity.id, next);
          });
        });
        const nodeCollection = cy.nodes(".entity");
        if (nodeCollection.length > 0) {
          cy.fit(nodeCollection, 90);
        }
      }
      resetTokenRef.current = resetToken;
    }, [elements, entities, positions, relations, resetToken]);

    useEffect(() => {
      const cy = cyRef.current;
      if (!cy) {
        return;
      }
      applyInteractionClasses(cy, interactionState);
    }, [interactionState]);

    return (
      <div className="graphStudioCanvasWrap">
        <div
          ref={containerRef}
          className="graphCySurface"
          role="img"
          aria-label="Conversation graph whiteboard canvas"
        />
      </div>
    );
  }
);

export default ConversationGraphCanvas;
