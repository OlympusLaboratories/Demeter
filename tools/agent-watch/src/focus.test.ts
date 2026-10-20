import { describe, expect, it } from 'vitest';
import {
  MAX_FOCUS_SCALE,
  MIN_FOCUS_SCALE,
  centerBox,
  expansionBox,
  frameBox,
  nodeBox,
} from './focus';
import { NODE_HEIGHT, NODE_WIDTH, type GraphLayout } from './graphLayout';

function layoutOf(rows: Array<{ id: string; x: number; y: number }>, edges: Array<[string, string]>): GraphLayout {
  return {
    nodes: rows.map((row) => ({
      id: row.id,
      kind: 'agent' as const,
      status: 'done' as const,
      label: row.id,
      eventCount: 0,
      childCount: 0,
      x: row.x,
      y: row.y,
      hiddenChildren: 0,
      expanded: true,
      totalChildren: 0,
    })),
    edges: edges.map(([from, to]) => ({ from, to, fromX: 0, fromY: 0, toX: 0, toY: 0 })),
    width: 0,
    height: 0,
  };
}

const canvas = { width: 1000, height: 600 };

describe('expansionBox', () => {
  it('spans the children row and reaches back to the parent', () => {
    const layout = layoutOf(
      [
        { id: 'p', x: 0, y: 100 },
        { id: 'c1', x: 266, y: 40 },
        { id: 'c2', x: 266, y: 160 },
      ],
      [
        ['p', 'c1'],
        ['p', 'c2'],
      ],
    );

    expect(expansionBox(layout, 'p')).toEqual({
      x: 0,
      y: 40,
      width: 266 + NODE_WIDTH,
      height: 160 + NODE_HEIGHT - 40,
    });
  });

  it('ignores children of some other parent', () => {
    const layout = layoutOf(
      [
        { id: 'p', x: 0, y: 0 },
        { id: 'q', x: 0, y: 400 },
        { id: 'mine', x: 266, y: 0 },
        { id: 'theirs', x: 266, y: 400 },
      ],
      [
        ['p', 'mine'],
        ['q', 'theirs'],
      ],
    );

    expect(expansionBox(layout, 'p')?.height).toBe(NODE_HEIGHT);
  });

  it('has nothing to frame when the node is childless or absent', () => {
    const layout = layoutOf([{ id: 'p', x: 0, y: 0 }], []);
    expect(expansionBox(layout, 'p')).toBeUndefined();
    expect(expansionBox(layout, 'gone')).toBeUndefined();
    expect(nodeBox(layout, 'gone')).toBeUndefined();
    expect(nodeBox(layout, 'p')).toEqual({ x: 0, y: 0, width: NODE_WIDTH, height: NODE_HEIGHT });
  });
});

describe('frameBox', () => {
  it('centers a row that fits, without magnifying past 100%', () => {
    const box = { x: 100, y: 200, width: 400, height: 120 };
    const frame = frameBox(box, canvas);

    expect(frame.k).toBe(MAX_FOCUS_SCALE);
    expect(frame.tx + box.x * frame.k + (box.width * frame.k) / 2).toBeCloseTo(canvas.width / 2);
    expect(frame.ty + box.y * frame.k + (box.height * frame.k) / 2).toBeCloseTo(canvas.height / 2);
  });

  it('zooms out to show a tall row in full', () => {
    const box = { x: 0, y: 0, width: 400, height: 800 };
    const frame = frameBox(box, canvas);

    expect(frame.k).toBeCloseTo((canvas.height - 56) / 800);
    expect(frame.k).toBeGreaterThan(MIN_FOCUS_SCALE);
    expect(box.height * frame.k).toBeLessThanOrEqual(canvas.height - 56 + 0.001);
  });

  it('anchors a row too tall to read at the top instead of its middle', () => {
    const box = { x: 0, y: 500, width: 400, height: 5936 };
    const frame = frameBox(box, canvas);

    expect(frame.k).toBe(MIN_FOCUS_SCALE);
    expect(frame.ty + box.y * frame.k).toBeCloseTo(28);
  });

  it('survives a degenerate box', () => {
    const frame = frameBox({ x: 0, y: 0, width: 0, height: 0 }, canvas);
    expect(Number.isFinite(frame.k)).toBe(true);
    expect(Number.isFinite(frame.tx)).toBe(true);
    expect(Number.isFinite(frame.ty)).toBe(true);
  });
});

describe('centerBox', () => {
  it('pans to the box without touching the zoom level', () => {
    const box = { x: 300, y: 900, width: NODE_WIDTH, height: NODE_HEIGHT };
    const frame = centerBox(box, canvas, 0.72);

    expect(frame.k).toBe(0.72);
    expect(frame.tx + box.x * 0.72 + (box.width * 0.72) / 2).toBeCloseTo(canvas.width / 2);
    expect(frame.ty + box.y * 0.72 + (box.height * 0.72) / 2).toBeCloseTo(canvas.height / 2);
  });
});
