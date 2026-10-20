import type { GraphLayout } from './graphLayout';
import { NODE_HEIGHT, NODE_WIDTH } from './graphLayout';

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
}

export const FOCUS_PADDING = 28;
export const MIN_FOCUS_SCALE = 0.55;
export const MAX_FOCUS_SCALE = 1;

export function nodeBox(layout: GraphLayout, id: string): Box | undefined {
  const node = layout.nodes.find((entry) => entry.id === id);
  if (!node) return undefined;
  return { x: node.x, y: node.y, width: NODE_WIDTH, height: NODE_HEIGHT };
}

export function expansionBox(layout: GraphLayout, parentId: string): Box | undefined {
  const parent = layout.nodes.find((entry) => entry.id === parentId);
  if (!parent) return undefined;

  const childIds = new Set(
    layout.edges.filter((edge) => edge.from === parentId).map((edge) => edge.to),
  );
  const children = layout.nodes.filter((entry) => childIds.has(entry.id));
  if (children.length === 0) return undefined;

  let top = Number.POSITIVE_INFINITY;
  let bottom = Number.NEGATIVE_INFINITY;
  let right = Number.NEGATIVE_INFINITY;
  for (const child of children) {
    top = Math.min(top, child.y);
    bottom = Math.max(bottom, child.y + NODE_HEIGHT);
    right = Math.max(right, child.x + NODE_WIDTH);
  }

  return { x: parent.x, y: top, width: right - parent.x, height: bottom - top };
}

export function frameBox(box: Box, canvas: Canvas, options: FrameOptions = {}): Frame {
  const padding = options.padding ?? FOCUS_PADDING;
  const minScale = options.minScale ?? MIN_FOCUS_SCALE;
  const maxScale = options.maxScale ?? MAX_FOCUS_SCALE;

  const availableWidth = Math.max(canvas.width - padding * 2, 1);
  const availableHeight = Math.max(canvas.height - padding * 2, 1);
  const byWidth = box.width > 0 ? availableWidth / box.width : maxScale;
  const byHeight = box.height > 0 ? availableHeight / box.height : maxScale;
  const k = Math.min(Math.max(Math.min(byWidth, byHeight), minScale), maxScale);

  const scaledWidth = box.width * k;
  const scaledHeight = box.height * k;
  const tx =
    scaledWidth <= availableWidth ? (canvas.width - scaledWidth) / 2 - box.x * k : padding - box.x * k;
  const ty =
    scaledHeight <= availableHeight
      ? (canvas.height - scaledHeight) / 2 - box.y * k
      : padding - box.y * k;

  return { k, tx, ty };
}

export function centerBox(box: Box, canvas: Canvas, k: number): Frame {
  return {
    k,
    tx: (canvas.width - box.width * k) / 2 - box.x * k,
    ty: (canvas.height - box.height * k) / 2 - box.y * k,
  };
}
