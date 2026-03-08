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
  positions: GraphNodePositionMap;
};

type BuildGraphInteractionStateInput = {
  entities: EntityRead[];
  relations: RelationWithEntitiesRead[];
  activeNodeId: number | null;
  selectedNodeId: number | null;
  highlightRelation: string;
};

type BuildClusteredRadialPositionsInput = {
  entities: EntityRead[];
  relations: RelationWithEntitiesRead[];
};

export type GraphInteractionState = {
  selectedNodeId: string | null;
  focusedNodeIds: Set<string> | null;
  labelEdgeIds: Set<string>;
  focusEdgeIds: Set<string>;
  highlightEdgeIds: Set<string>;
  dimmedEdgeIds: Set<string>;
};

const TYPE_PALETTE = [
  "#9adfcf",
  "#9dcdf0",
  "#c7b7ef",
  "#f0c2a2",
  "#c4e3a8",
  "#efb8cf",
  "#d8e3a8"
];

function normalizeTypeLabel(label: string): string {
  const cleaned = label.trim();
  return cleaned.length > 0 ? cleaned : "untyped";
}

function buildClusterId(typeLabel: string): string {
  const normalized = typeLabel.toLowerCase().replace(/[^a-z0-9]+/g, "-");
  return `cluster::${normalized || "untyped"}`;
}

function buildEdgeId(relationId: number): string {
  return `edge::${relationId}`;
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

function buildClusterWeightMap(
  entities: EntityRead[],
  relations: RelationWithEntitiesRead[]
): Map<string, number> {
  const degreeById = buildDegreeMap(relations);
  const weightByCluster = new Map<string, number>();
  entities.forEach((entity) => {
    const typeLabel = normalizeTypeLabel(entity.type_label);
    const clusterId = buildClusterId(typeLabel);
    const degreeWeight = degreeById.get(entity.id) ?? 0;
    const prior = weightByCluster.get(clusterId) ?? 0;
    weightByCluster.set(clusterId, prior + 1 + degreeWeight * 1.15);
  });
  return weightByCluster;
}

export function buildConversationGraphElements({
  entities,
  relations,
  positions
}: BuildConversationGraphElementsInput): ElementDefinition[] {
  const elements: ElementDefinition[] = [];
  const degreeById = buildDegreeMap(relations);

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
      pannable: true
    });
  });

  entities.forEach((entity) => {
    const typeLabel = normalizeTypeLabel(entity.type_label);
    const cluster = clusterByType.get(typeLabel);
    if (!cluster) {
      return;
    }
    const degree = degreeById.get(entity.id) ?? 0;
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
      classes: "entity",
      position: positions[entity.id]
    });
  });

  relations.forEach((relation) => {
    elements.push({
      data: {
        id: buildEdgeId(relation.id),
        source: String(relation.from_entity_id),
        target: String(relation.to_entity_id),
        relationType: relation.relation_type,
        confidence: relation.confidence,
        label: relation.relation_type
      },
      classes:
        relation.qualifiers_json && relation.qualifiers_json.suggested
          ? "relation suggested"
          : "relation"
    });
  });

  return elements;
}

export function buildGraphInteractionState({
  entities,
  relations,
  activeNodeId,
  selectedNodeId,
  highlightRelation
}: BuildGraphInteractionStateInput): GraphInteractionState {
  const cleanHighlight = highlightRelation.trim().toLowerCase();
  const entityIds = new Set(entities.map((entity) => entity.id));
  const filteredRelations = relations.filter(
    (relation) => entityIds.has(relation.from_entity_id) && entityIds.has(relation.to_entity_id)
  );
  const neighborsById = buildNeighborMap(filteredRelations);
  const focusSet = buildFocusSet(activeNodeId, neighborsById);

  const focusEdgeIds = new Set<string>();
  const highlightEdgeIds = new Set<string>();
  const labelEdgeIds = new Set<string>();
  const dimmedEdgeIds = new Set<string>();

  filteredRelations.forEach((relation) => {
    const edgeId = buildEdgeId(relation.id);
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

    if (touchesActive) {
      focusEdgeIds.add(edgeId);
    }
    if (isHighlighted) {
      highlightEdgeIds.add(edgeId);
    }
    if (showLabel) {
      labelEdgeIds.add(edgeId);
    }
    if (isDimmedByHighlight || isOutOfFocus) {
      dimmedEdgeIds.add(edgeId);
    }
  });

  return {
    selectedNodeId: selectedNodeId !== null ? String(selectedNodeId) : null,
    focusedNodeIds: focusSet ? new Set(Array.from(focusSet).map((id) => String(id))) : null,
    labelEdgeIds,
    focusEdgeIds,
    highlightEdgeIds,
    dimmedEdgeIds
  };
}

export function buildClusteredRadialPositions({
  entities,
  relations
}: BuildClusteredRadialPositionsInput): GraphNodePositionMap {
  const positions: GraphNodePositionMap = {};
  if (entities.length === 0) {
    return positions;
  }

  const clusters = new Map<string, { label: string; entityIds: number[] }>();
  entities.forEach((entity) => {
    const typeLabel = normalizeTypeLabel(entity.type_label);
    const clusterId = buildClusterId(typeLabel);
    const current = clusters.get(clusterId);
    if (current) {
      current.entityIds.push(entity.id);
      return;
    }
    clusters.set(clusterId, { label: typeLabel, entityIds: [entity.id] });
  });

  const weightByCluster = buildClusterWeightMap(entities, relations);
  const sortedClusters = Array.from(clusters.entries())
    .map(([clusterId, cluster]) => ({
      clusterId,
      label: cluster.label,
      entityIds: cluster.entityIds,
      weight: weightByCluster.get(clusterId) ?? cluster.entityIds.length
    }))
    .sort((left, right) => right.weight - left.weight);

  const clusterCenterById = new Map<string, GraphNodePosition>();
  const radialStart = -Math.PI / 2;
  const ringRadiusStep = 340;
  let ring = 1;
  let slotInRing = 0;
  let slotsThisRing = 6;

  sortedClusters.forEach((cluster, index) => {
    if (index === 0) {
      clusterCenterById.set(cluster.clusterId, { x: 0, y: 0 });
      return;
    }
    if (slotInRing >= slotsThisRing) {
      ring += 1;
      slotInRing = 0;
      slotsThisRing = 6 * ring;
    }
    const radius = ring * ringRadiusStep;
    const angle = radialStart + (slotInRing / slotsThisRing) * Math.PI * 2;
    clusterCenterById.set(cluster.clusterId, {
      x: Math.cos(angle) * radius,
      y: Math.sin(angle) * radius
    });
    slotInRing += 1;
  });

  const degreeById = buildDegreeMap(relations);
  const goldenAngle = Math.PI * (3 - Math.sqrt(5));

  sortedClusters.forEach((cluster) => {
    const center = clusterCenterById.get(cluster.clusterId) ?? { x: 0, y: 0 };
    const rankedEntityIds = [...cluster.entityIds].sort(
      (left, right) => (degreeById.get(right) ?? 0) - (degreeById.get(left) ?? 0)
    );

    rankedEntityIds.forEach((entityId, index) => {
      if (rankedEntityIds.length === 1) {
        positions[entityId] = { x: center.x, y: center.y };
        return;
      }
      const localRadius = 42 + Math.sqrt(index + 1) * 36;
      const angle = index * goldenAngle;
      positions[entityId] = {
        x: center.x + Math.cos(angle) * localRadius,
        y: center.y + Math.sin(angle) * localRadius
      };
    });
  });

  return positions;
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
      "background-opacity": 0.34,
      "border-color": "data(clusterColor)",
      "border-width": 1.9,
      "border-style": "solid",
      "shape": "round-rectangle",
      "padding": "50px",
      "text-valign": "top",
      "text-halign": "center",
      "text-margin-y": "-12px",
      "font-size": "11px",
      "font-weight": "700",
      "text-transform": "uppercase",
      "letter-spacing": "0.82px",
      "color": "#254745",
      "text-background-color": "rgba(255, 255, 255, 0.74)",
      "text-background-opacity": 1,
      "text-background-padding": "2px",
      "label": "data(label)",
      "z-index": 1
    }
  },
  {
    selector: "node.cluster.dragArmed",
    style: {
      "background-opacity": 0.44,
      "border-width": 2.8,
      "border-color": "#0f766e",
      "color": "#17403d"
    }
  },
  {
    selector: "node.cluster.dragging",
    style: {
      "background-opacity": 0.5,
      "border-width": 3.2,
      "border-color": "#c2410c",
      "color": "#5f270a"
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
      "line-color": "#7a9390",
      "target-arrow-color": "#7a9390",
      "target-arrow-shape": "triangle",
      "arrow-scale": 0.8,
      "line-cap": "round",
      "width": 1.4,
      opacity: 0.52,
      "font-size": "10px",
      "font-weight": "600",
      "text-background-color": "rgba(248, 252, 251, 0.9)",
      "text-background-opacity": 1,
      "text-background-shape": "round-rectangle",
      "text-background-padding": "3px",
      "text-border-color": "rgba(255, 255, 255, 0.95)",
      "text-border-width": 1,
      "text-events": "no",
      "text-rotation": "none",
      "text-margin-y": "-4px",
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
    selector: "edge.suggested",
    style: {
      "line-style": "dashed",
      "line-color": "#d97706",
      "target-arrow-color": "#d97706",
      "width": 2,
      opacity: 0.85
    }
  },
  {
    selector: "edge.focus",
    style: {
      "line-color": "#0d736a",
      "target-arrow-color": "#0d736a",
      "width": 2.3,
      opacity: 0.92
    }
  },
  {
    selector: "edge.highlight",
    style: {
      "line-color": "#c8511c",
      "target-arrow-color": "#c8511c",
      "width": 2.8,
      opacity: 1
    }
  },
  {
    selector: "edge.dimmed",
    style: {
      opacity: 0.1
    }
  }
];
