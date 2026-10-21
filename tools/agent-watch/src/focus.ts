import type { GraphLayout, PositionedNode } from './graphLayout';
import { NODE_HEIGHT, NODE_WIDTH, rowHeight } from './graphLayout';
import { MAX_ZOOM } from './zoom';

export interface Box {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface Canvas {
  width: number;
  height: number;
}

export interface Frame {
  k: number;
  tx: number;
  ty: number;
}

export interface FrameOptions {
  padding?: number;
  minScale?: number;
  maxScale?: number;
  minHeightFraction?: number;
  maxMagnifiedRows?: number;
  context?: Box;
  anchor?: Box;
}

export const FOCUS_PADDING = 28;
export const MIN_FOCUS_SCALE = 0.55;
export const MIN_FIT_SCALE = 0.15;
export const MAX_FOCUS_SCALE = 1;
export const MIN_HEIGHT_FRACTION = 1 / 3;
export const MAX_MAGNIFIED_ROWS = 3;

export interface RowFrame {
  row: Box;
  withParent: Box;
  anchor?: Box;
}

function boxOf(nodes: PositionedNode[]): Box {
  let top = Number.POSITIVE_INFINITY;
  let bottom = Number.NEGATIVE_INFINITY;
  let left = Number.POSITIVE_INFINITY;
  let right = Number.NEGATIVE_INFINITY;
  for (const node of nodes) {
    top = Math.min(top, node.y);
    bottom = Math.max(bottom, node.y + NODE_HEIGHT);
    left = Math.min(left, node.x);
    right = Math.max(right, node.x + NODE_WIDTH);
  }
  return { x: left, y: top, width: right - left, height: bottom - top };
}

function framesFor(members: PositionedNode[], parent: PositionedNode | undefined): RowFrame {
  const row = boxOf(members);
  const withParent = parent
    ? { x: parent.x, y: row.y, width: row.x + row.width - parent.x, height: row.height }
    : row;
  return { row, withParent };
}

function childrenOf(layout: GraphLayout, parentId: string): PositionedNode[] {
  const ids = new Set(layout.edges.filter((edge) => edge.from === parentId).map((edge) => edge.to));
  return layout.nodes.filter((node) => ids.has(node.id));
}

export function expansionBoxes(layout: GraphLayout, parentId: string): RowFrame | undefined {
  const parent = layout.nodes.find((entry) => entry.id === parentId);
  if (!parent) return undefined;
  const children = childrenOf(layout, parentId);
  if (children.length === 0) return undefined;
  return framesFor(children, parent);
}

export function siblingBoxes(layout: GraphLayout, nodeId: string): RowFrame | undefined {
  const self = layout.nodes.find((entry) => entry.id === nodeId);
  if (!self) return undefined;
  const anchor = boxOf([self]);

  const parentId = layout.edges.find((edge) => edge.to === nodeId)?.from;
  if (parentId !== undefined) {
    const parent = layout.nodes.find((entry) => entry.id === parentId);
    return { ...framesFor(childrenOf(layout, parentId), parent), anchor };
  }

  const hasParent = new Set(layout.edges.map((edge) => edge.to));
  const roots = layout.nodes.filter((entry) => !hasParent.has(entry.id));
  return { ...framesFor(roots.length > 0 ? roots : [self], undefined), anchor };
}

export function scaleFor(box: Box, canvas: Canvas, options: FrameOptions = {}): number {
  const padding = options.padding ?? FOCUS_PADDING;
  const minScale = options.minScale ?? MIN_FOCUS_SCALE;
  const maxScale = options.maxScale ?? MAX_FOCUS_SCALE;
  if (box.height <= 0 || box.width <= 0) return maxScale;

  const byWidth = Math.max(canvas.width - padding * 2, 1) / box.width;
  const byHeight = Math.max(canvas.height - padding * 2, 1) / box.height;
  const fitted = Math.min(byWidth, byHeight, maxScale);

  const fraction = options.minHeightFraction ?? MIN_HEIGHT_FRACTION;
  const magnified = Math.max(box.height, rowHeight(options.maxMagnifiedRows ?? MAX_MAGNIFIED_ROWS));
  const toFillFraction = Math.min((canvas.height * fraction) / magnified, byWidth);

  return Math.min(Math.max(fitted, toFillFraction, minScale), MAX_ZOOM);
}

export function frameBox(box: Box, canvas: Canvas, options: FrameOptions = {}): Frame {
  const padding = options.padding ?? FOCUS_PADDING;
  const k = scaleFor(box, canvas, options);
  const availableWidth = Math.max(canvas.width - padding * 2, 1);
  const availableHeight = Math.max(canvas.height - padding * 2, 1);

  const context = options.context;
  const across = context && context.width * k <= availableWidth ? context : box;
  const scaledWidth = across.width * k;
  const scaledHeight = box.height * k;

  const tx =
    scaledWidth <= availableWidth
      ? (canvas.width - scaledWidth) / 2 - across.x * k
      : padding - across.x * k;
  const anchor = options.anchor;
  const ty =
    scaledHeight <= availableHeight
      ? (canvas.height - scaledHeight) / 2 - box.y * k
      : anchor
        ? (canvas.height - anchor.height * k) / 2 - anchor.y * k
        : padding - box.y * k;

  return { k, tx, ty };
}
