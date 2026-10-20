import { hierarchy, tree } from 'd3-hierarchy';
import type { AgentNode, NodeKind, NodeStatus } from './model';

export const NODE_WIDTH = 190;
export const NODE_HEIGHT = 46;
const ROW_GAP = 16;
const COLUMN_GAP = 76;

export interface PositionedNode {
  id: string;
  kind: NodeKind;
  status: NodeStatus;
  label: string;
  sublabel?: string;
  eventCount: number;
  childCount: number;
  x: number;
  y: number;
  hiddenChildren: number;
  expanded: boolean;
  totalChildren: number;
}

export interface PositionedEdge {
  from: string;
  to: string;
  fromX: number;
  fromY: number;
  toX: number;
  toY: number;
}

export interface GraphLayout {
  nodes: PositionedNode[];
  edges: PositionedEdge[];
  width: number;
  height: number;
}

export interface LayoutOptions {
  overrides?: ReadonlyMap<string, boolean>;
  autoCollapseThreshold?: number;
  initialDepth?: number;
}

export const DEFAULT_AUTO_COLLAPSE = 12;
export const DEFAULT_INITIAL_DEPTH = 1;

export function isExpanded(node: AgentNode, depth: number, options: LayoutOptions = {}): boolean {
  if (node.children.length === 0) return true;
  const override = options.overrides?.get(node.id);
  if (override !== undefined) return override;
  if (depth >= (options.initialDepth ?? DEFAULT_INITIAL_DEPTH)) return false;
  return node.children.length <= (options.autoCollapseThreshold ?? DEFAULT_AUTO_COLLAPSE);
}

interface Collapsed {
  node: AgentNode;
  hidden: number;
  expanded: boolean;
}

function collapse(root: AgentNode, options: LayoutOptions, into: Map<string, Collapsed>): AgentNode {
  const visit = (node: AgentNode, depth: number): AgentNode => {
    const expanded = isExpanded(node, depth, options);
    const children = expanded ? node.children.map((child) => visit(child, depth + 1)) : [];
    into.set(node.id, {
      node,
      hidden: expanded ? 0 : node.children.length,
      expanded,
    });
    return { ...node, children };
  };
  return visit(root, 0);
}

export function layoutTree(root: AgentNode, options: LayoutOptions = {}): GraphLayout {
  const flags = new Map<string, Collapsed>();
  const rooted = hierarchy<AgentNode>(collapse(root, options, flags), (node) => node.children);
  const layered = tree<AgentNode>()
    .nodeSize([NODE_HEIGHT + ROW_GAP, NODE_WIDTH + COLUMN_GAP])
    .separation(() => 1);
  layered(rooted);

  const descendants = rooted.descendants();
  let minRow = Number.POSITIVE_INFINITY;
  let minColumn = Number.POSITIVE_INFINITY;
  for (const node of descendants) {
    minRow = Math.min(minRow, node.x ?? 0);
    minColumn = Math.min(minColumn, node.y ?? 0);
  }
  if (!Number.isFinite(minRow)) minRow = 0;
  if (!Number.isFinite(minColumn)) minColumn = 0;

  const nodes: PositionedNode[] = descendants.map((node) => {
    const flag = flags.get(node.data.id);
    return {
      id: node.data.id,
      kind: node.data.kind,
      status: node.data.status,
      label: node.data.label,
      sublabel: node.data.sublabel,
      eventCount: node.data.events.length,
      childCount: node.data.children.length,
      totalChildren: flag?.node.children.length ?? node.data.children.length,
      hiddenChildren: flag?.hidden ?? 0,
      expanded: flag?.expanded ?? true,
      x: (node.y ?? 0) - minColumn,
      y: (node.x ?? 0) - minRow,
    };
  });

  const byId = new Map(nodes.map((node) => [node.id, node]));
  const edges: PositionedEdge[] = [];
  for (const node of descendants) {
    const parent = node.parent;
    if (!parent) continue;
    const from = byId.get(parent.data.id);
    const to = byId.get(node.data.id);
    if (!from || !to) continue;
    edges.push({
      from: from.id,
      to: to.id,
      fromX: from.x + NODE_WIDTH,
      fromY: from.y + NODE_HEIGHT / 2,
      toX: to.x,
      toY: to.y + NODE_HEIGHT / 2,
    });
  }

  let width = 0;
  let height = 0;
  for (const node of nodes) {
    width = Math.max(width, node.x + NODE_WIDTH);
    height = Math.max(height, node.y + NODE_HEIGHT);
  }

  return { nodes, edges, width, height };
}

const FOREST_ROOT_ID = '__forest__';

export function layoutForest(roots: AgentNode[], options: LayoutOptions = {}): GraphLayout {
  if (roots.length === 0) return { nodes: [], edges: [], width: 0, height: 0 };

  const virtualRoot: AgentNode = {
    id: FOREST_ROOT_ID,
    kind: 'session',
    label: '',
    status: 'idle',
    events: [],
    children: roots,
  };

  const full = layoutTree(virtualRoot, {
    ...options,
    initialDepth: (options.initialDepth ?? DEFAULT_INITIAL_DEPTH) + 1,
    overrides: new Map([[FOREST_ROOT_ID, true], ...(options.overrides ?? new Map())]),
  });
  const nodes = full.nodes.filter((node) => node.id !== FOREST_ROOT_ID);
  const edges = full.edges.filter((edge) => edge.from !== FOREST_ROOT_ID);

  let minX = Number.POSITIVE_INFINITY;
  let minY = Number.POSITIVE_INFINITY;
  for (const node of nodes) {
    minX = Math.min(minX, node.x);
    minY = Math.min(minY, node.y);
  }
  if (!Number.isFinite(minX)) minX = 0;
  if (!Number.isFinite(minY)) minY = 0;

  let width = 0;
  let height = 0;
  for (const node of nodes) {
    node.x -= minX;
    node.y -= minY;
    width = Math.max(width, node.x + NODE_WIDTH);
    height = Math.max(height, node.y + NODE_HEIGHT);
  }
  for (const edge of edges) {
    edge.fromX -= minX;
    edge.toX -= minX;
    edge.fromY -= minY;
    edge.toY -= minY;
  }

  return { nodes, edges, width, height };
}
