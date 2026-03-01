import type { ElementDefinition, LayoutOptions } from "cytoscape";

import type { EntityRead, RelationWithEntitiesRead } from "./api";

export type GraphNodePosition = {
  x: number;
  y: number;
};

export type GraphNodePositionMap = Record<number, GraphNodePosition>;

type BuildConversationGraphElementsInput = {
  entities: EntityRead[];
  relations: RelationWithEntitiesRead[];
  activeNodeId: number | null;
  selectedNodeId: number | null;
  highlightRelation: string;
  positions: GraphNodePositionMap;
};

const TYPE_PALETTE = [
  "#d7f3ef",
  "#dceefb",
  "#efe8fb",
  "#fbe9df",
  "#e7f3d9",
  "#f8e3eb",
  "#f0f1d9"
];

function normalizeTypeLabel(label: string): string {
  const cleaned = label.trim();
  return cleaned.length > 0 ? cleaned : "untyped";
}

function buildClusterId(typeLabel: string): string {
  const normalized = typeLabel.toLowerCase().replace(/[^a-z0-9]+/g, "-");
  return `cluster::${normalized || "untyped"}`;
}

function hashString(value: string): number {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash << 5) - hash + value.charCodeAt(index);
    hash |= 0;
  }
  return Math.abs(hash);
}

function getTypeColor(typeLabel: string): string {
  return TYPE_PALETTE[hashString(typeLabel) % TYPE_PALETTE.length];
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function buildNeighborMap(relations: RelationWithEntitiesRead[]): Map<number, Set<number>> {
  const neighbors = new Map<number, Set<number>>();
  relations.forEach((relation) => {
    if (!neighbors.has(relation.from_entity_id)) {
      neighbors.set(relation.from_entity_id, new Set<number>());
    }
    if (!neighbors.has(relation.to_entity_id)) {
      neighbors.set(relation.to_entity_id, new Set<number>());
    }
    neighbors.get(relation.from_entity_id)?.add(relation.to_entity_id);
    neighbors.get(relation.to_entity_id)?.add(relation.from_entity_id);
  });
  return neighbors;
}

function buildDegreeMap(relations: RelationWithEntitiesRead[]): Map<number, number> {
  const degreeById = new Map<number, number>();
  relations.forEach((relation) => {
    degreeById.set(relation.from_entity_id, (degreeById.get(relation.from_entity_id) ?? 0) + 1);
    degreeById.set(relation.to_entity_id, (degreeById.get(relation.to_entity_id) ?? 0) + 1);
  });
  return degreeById;
}

function buildFocusSet(
  activeNodeId: number | null,
  neighborsById: Map<number, Set<number>>
): Set<number> | null {
  if (activeNodeId === null) {
    return null;
  }
  const focusSet = new Set<number>([activeNodeId]);
  neighborsById.get(activeNodeId)?.forEach((neighborId) => {
    focusSet.add(neighborId);
  });
  return focusSet;
}

export function buildConversationGraphElements({
  entities,
  relations,
  activeNodeId,
  selectedNodeId,
  highlightRelation,
  positions
}: BuildConversationGraphElementsInput): ElementDefinition[] {
  const elements: ElementDefinition[] = [];
  const cleanHighlight = highlightRelation.trim().toLowerCase();
  const degreeById = buildDegreeMap(relations);
  const neighborsById = buildNeighborMap(relations);
  const focusSet = buildFocusSet(activeNodeId, neighborsById);

  const clusterByType = new Map<string, { id: string; label: string; color: string }>();
  entities.forEach((entity) => {
    const typeLabel = normalizeTypeLabel(entity.type_label);
    if (clusterByType.has(typeLabel)) {
      return;
    }
    clusterByType.set(typeLabel, {
      id: buildClusterId(typeLabel),
      label: typeLabel,
      color: getTypeColor(typeLabel)
    });
  });

  clusterByType.forEach((cluster) => {
    elements.push({
      data: {
        id: cluster.id,
        label: cluster.label,
        clusterColor: cluster.color
      },
      classes: "cluster",
      selectable: false,
      grabbable: false,
      locked: true
    });
  });

  entities.forEach((entity) => {
    const typeLabel = normalizeTypeLabel(entity.type_label);
    const cluster = clusterByType.get(typeLabel);
    if (!cluster) {
      return;
    }
    const degree = degreeById.get(entity.id) ?? 0;
    const inFocus = focusSet ? focusSet.has(entity.id) : true;
    const classes = ["entity"];
    if (selectedNodeId === entity.id) {
      classes.push("selected");
    }
    if (focusSet && inFocus) {
      classes.push("focused");
    }
    if (focusSet && !inFocus) {
      classes.push("dimmed");
    }
    const label = entity.canonical_name || entity.display_name || `Entity ${entity.id}`;
    elements.push({
      data: {
        id: String(entity.id),
        parent: cluster.id,
        label,
        canonicalName: entity.canonical_name,
        typeLabel,
        degree,
        nodeColor: cluster.color,
        nodeSize: clamp(26 + degree * 2.1, 26, 46)
      },
      classes: classes.join(" "),
      position: positions[entity.id]
    });
  });

  relations.forEach((relation) => {
    const touchesActive =
      activeNodeId !== null &&
      (relation.from_entity_id === activeNodeId || relation.to_entity_id === activeNodeId);
    const isHighlighted =
      cleanHighlight.length > 0 && relation.relation_type.toLowerCase() === cleanHighlight;
    const showLabel = touchesActive || isHighlighted;
    const isDimmedByHighlight = cleanHighlight.length > 0 && !isHighlighted;
    const isOutOfFocus =
      focusSet !== null &&
      !(focusSet.has(relation.from_entity_id) && focusSet.has(relation.to_entity_id)) &&
      !touchesActive;

    const classes = ["relation"];
    if (touchesActive) {
      classes.push("focus");
    }
    if (isHighlighted) {
      classes.push("highlight");
    }
    if (showLabel) {
      classes.push("showLabel");
    }
    if (isDimmedByHighlight || isOutOfFocus) {
      classes.push("dimmed");
    }

    elements.push({
      data: {
        id: `edge::${relation.id}`,
        source: String(relation.from_entity_id),
        target: String(relation.to_entity_id),
        relationType: relation.relation_type,
        confidence: relation.confidence,
        label: relation.relation_type
      },
      classes: classes.join(" ")
    });
  });

  return elements;
}

export function buildCoseLayoutOptions(randomize: boolean): LayoutOptions {
  return {
    name: "cose",
    fit: false,
    padding: 60,
    // Keep layout synchronous to avoid renderer-frame races on rapid route changes/unmount.
    animate: false,
    nodeRepulsion: 120000,
    nodeOverlap: 18,
    idealEdgeLength: 148,
    edgeElasticity: 110,
    nestingFactor: 0.7,
    gravity: 0.22,
    numIter: 1200,
    componentSpacing: 140,
    randomize
  } as LayoutOptions;
}

export const conversationGraphStyles = [
  {
    selector: "core",
    style: {
      "selection-box-color": "#0f766e",
      "selection-box-opacity": 0.2,
      "active-bg-color": "#0f766e",
      "active-bg-opacity": 0.16,
      "active-bg-size": 18
    }
  },
  {
    selector: "node.cluster",
    style: {
      "background-color": "data(clusterColor)",
      "background-opacity": 0.2,
      "border-color": "data(clusterColor)",
      "border-width": 1,
      "border-style": "solid",
      "shape": "round-rectangle",
      "padding": "42px",
      "text-valign": "top",
      "text-halign": "center",
      "text-margin-y": "-10px",
      "font-size": "10px",
      "font-weight": "600",
      "text-transform": "uppercase",
      "letter-spacing": "0.7px",
      "color": "#4b5e5c",
      "label": "data(label)",
      "z-index": 0
    }
  },
  {
    selector: "node.entity",
    style: {
      "background-color": "data(nodeColor)",
      "border-width": 1.6,
      "border-color": "#0f766e",
      "width": "data(nodeSize)",
      "height": "data(nodeSize)",
      "label": "data(label)",
      "text-valign": "bottom",
      "text-halign": "center",
      "text-margin-y": "9px",
      "font-size": "11px",
      "font-weight": "500",
      "text-wrap": "wrap",
      "text-max-width": "124px",
      "color": "#102826",
      "z-index": 12,
      "transition-property": "border-width, border-color, opacity, background-color",
      "transition-duration": "130ms",
      "overlay-opacity": 0
    }
  },
  {
    selector: "node.entity.focused",
    style: {
      "border-width": 2.2,
      "border-color": "#0b5b56",
      "z-index": 18
    }
  },
  {
    selector: "node.entity.selected",
    style: {
      "border-width": 2.6,
      "border-color": "#c2410c",
      "background-color": "#fff2e8",
      "z-index": 24
    }
  },
  {
    selector: "node.entity.dimmed",
    style: {
      opacity: 0.25
    }
  },
  {
    selector: "edge",
    style: {
      "curve-style": "bezier",
      "line-color": "#6f8f8c",
      "target-arrow-color": "#6f8f8c",
      "target-arrow-shape": "triangle",
      "arrow-scale": 0.8,
      "line-cap": "round",
      "width": 1.6,
      opacity: 0.6,
      "font-size": "9px",
      "font-weight": "600",
      "text-background-color": "rgba(255, 255, 255, 0.94)",
      "text-background-opacity": 1,
      "text-background-shape": "round-rectangle",
      "text-background-padding": "2px",
      "text-events": "no",
      "text-rotation": "autorotate",
      label: "",
      "z-index": 8,
      "overlay-opacity": 0
    }
  },
  {
    selector: "edge.showLabel",
    style: {
      label: "data(label)"
    }
  },
  {
    selector: "edge.focus",
    style: {
      "line-color": "#0f766e",
      "target-arrow-color": "#0f766e",
      "width": 2.1,
      opacity: 0.9
    }
  },
  {
    selector: "edge.highlight",
    style: {
      "line-color": "#c2410c",
      "target-arrow-color": "#c2410c",
      "width": 2.4,
      opacity: 1
    }
  },
  {
    selector: "edge.dimmed",
    style: {
      opacity: 0.14
    }
  }
];
