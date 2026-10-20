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
  group?: { parentId: string; hidden: number; expanded: boolean };
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
  expanded?: ReadonlySet<string>;
  groupThreshold?: number;
}

export const DEFAULT_GROUP_THRESHOLD = 12;
const GROUP_PREFIX = 'group:';

export function groupIdFor(parentId: string): string {
  return `${GROUP_PREFIX}${parentId}`;
}

export function parentOfGroupId(groupId: string): string | undefined {
  return groupId.startsWith(GROUP_PREFIX) ? groupId.slice(GROUP_PREFIX.length) : undefined;
}

function collapse(root: AgentNode, options: LayoutOptions): AgentNode {
  const threshold = options.groupThreshold ?? DEFAULT_GROUP_THRESHOLD;
  const expanded = options.expanded ?? new Set<string>();

  const visit = (node: AgentNode): AgentNode => {
    const children = node.children.map(visit);
    if (children.length <= threshold || expanded.has(node.id)) {
      return { ...node, children };
    }
    const shown = children.slice(0, threshold);
    const hidden = children.length - shown.length;
    const running = children.filter((child) => child.status === 'running').length;
    const errored = children.filter((child) => child.status === 'error').length;
    shown.push({
      id: groupIdFor(node.id),
      kind: node.kind,
      label: `+${hidden} more`,
      sublabel: running > 0 ? `${running} running` : errored > 0 ? `${errored} failed` : undefined,
      status: running > 0 ? 'running' : errored > 0 ? 'error' : 'idle',
      events: [],
      children: [],
    });
    return { ...node, children: shown };
  };

  return visit(root);
}

export function layoutTree(root: AgentNode, options: LayoutOptions = {}): GraphLayout {
  const rooted = hierarchy<AgentNode>(collapse(root, options), (node) => node.children);
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

  const expandedSet = options.expanded ?? new Set<string>();
  const nodes: PositionedNode[] = descendants.map((node) => {
    const parentId = parentOfGroupId(node.data.id);
    return {
      id: node.data.id,
      kind: node.data.kind,
      status: node.data.status,
      label: node.data.label,
      sublabel: node.data.sublabel,
      eventCount: node.data.events.length,
      childCount: node.data.children.length,
      x: (node.y ?? 0) - minColumn,
      y: (node.x ?? 0) - minRow,
      ...(parentId
        ? { group: { parentId, hidden: 0, expanded: expandedSet.has(parentId) } }
        : {}),
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

  const full = layoutTree(virtualRoot, options);
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
