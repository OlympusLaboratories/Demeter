import { describe, expect, it } from 'vitest';
import { MIN_FOCUS_SCALE, MIN_HEIGHT_FRACTION, expansionBoxes, frameBox, siblingBoxes } from './focus';
import { MAX_ZOOM } from './zoom';
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

describe('expansionBoxes', () => {
  it('spans the children row, and keeps a wider box that reaches back to the parent', () => {
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

    expect(expansionBoxes(layout, 'p')).toEqual({
      row: { x: 266, y: 40, width: NODE_WIDTH, height: 160 + NODE_HEIGHT - 40 },
      withParent: { x: 0, y: 40, width: 266 + NODE_WIDTH, height: 160 + NODE_HEIGHT - 40 },
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

    expect(expansionBoxes(layout, 'p')?.row.height).toBe(NODE_HEIGHT);
  });

  it('has nothing to frame when the node is childless or absent', () => {
    const layout = layoutOf([{ id: 'p', x: 0, y: 0 }], []);
    expect(expansionBoxes(layout, 'p')).toBeUndefined();
    expect(expansionBoxes(layout, 'gone')).toBeUndefined();
    expect(siblingBoxes(layout, 'gone')).toBeUndefined();
  });
});

describe('siblingBoxes', () => {
  const layout = layoutOf(
    [
      { id: 's1', x: 0, y: 0 },
      { id: 's2', x: 0, y: 300 },
      { id: 'a', x: 266, y: 0 },
      { id: 'b', x: 266, y: 62 },
      { id: 'c', x: 266, y: 124 },
    ],
    [
      ['s1', 'a'],
      ['s1', 'b'],
      ['s1', 'c'],
    ],
  );

  it('frames the whole row the collapsed node sits in, not the node alone', () => {
    expect(siblingBoxes(layout, 'b')).toEqual({
      row: { x: 266, y: 0, width: NODE_WIDTH, height: 124 + NODE_HEIGHT },
      withParent: { x: 0, y: 0, width: 266 + NODE_WIDTH, height: 124 + NODE_HEIGHT },
      anchor: { x: 266, y: 62, width: NODE_WIDTH, height: NODE_HEIGHT },
    });
  });

  it('frames every session when the collapsed node is a root of the forest', () => {
    expect(siblingBoxes(layout, 's2')).toEqual({
      row: { x: 0, y: 0, width: NODE_WIDTH, height: 300 + NODE_HEIGHT },
      withParent: { x: 0, y: 0, width: NODE_WIDTH, height: 300 + NODE_HEIGHT },
      anchor: { x: 0, y: 300, width: NODE_WIDTH, height: NODE_HEIGHT },
    });
  });

  it('gives a lone root its own row rather than nothing', () => {
    const single = layoutOf([{ id: 'only', x: 0, y: 0 }], []);
    expect(siblingBoxes(single, 'only')?.row).toEqual({
      x: 0,
      y: 0,
      width: NODE_WIDTH,
      height: NODE_HEIGHT,
    });
  });
});

function rowOf(count: number, x = 266, y = 0) {
  const gap = 16;
  return { x, y, width: NODE_WIDTH, height: count * NODE_HEIGHT + (count - 1) * gap };
}

describe('frameBox', () => {
  it('magnifies a short row until it fills a third of the viewport', () => {
    for (const count of [2, 3]) {
      const box = rowOf(count);
      const frame = frameBox(box, canvas);

      expect(box.height * frame.k).toBeCloseTo(canvas.height * MIN_HEIGHT_FRACTION);
      expect(frame.k).toBeGreaterThan(1);
    }
  });

  it('leaves a row that already clears a third at its natural size', () => {
    const box = rowOf(4);
    const frame = frameBox(box, canvas);

    expect(frame.k).toBe(1);
    expect(box.height * frame.k).toBeGreaterThan(canvas.height * MIN_HEIGHT_FRACTION);
  });

  it('stops magnifying a lone node at the ceiling the wheel also stops at', () => {
    const frame = frameBox(rowOf(1), canvas);
    expect(frame.k).toBe(MAX_ZOOM);
  });

  it('never magnifies so far that the box stops fitting across', () => {
    const wide = { x: 0, y: 0, width: 456, height: NODE_HEIGHT };
    const frame = frameBox(wide, canvas);

    expect(wide.height * frame.k).toBeLessThan(canvas.height * MIN_HEIGHT_FRACTION);
    expect(wide.width * frame.k).toBeLessThanOrEqual(canvas.width - 56 + 0.001);
  });

  it('zooms out to show a tall row in full', () => {
    const box = { x: 0, y: 0, width: 400, height: 800 };
    const frame = frameBox(box, canvas);

    expect(frame.k).toBeCloseTo((canvas.height - 56) / 800);
    expect(frame.k).toBeGreaterThan(MIN_FOCUS_SCALE);
  });

  it('anchors a row too tall to read at the top instead of its middle', () => {
    const box = { x: 0, y: 500, width: 400, height: 5936 };
    const frame = frameBox(box, canvas);

    expect(frame.k).toBe(MIN_FOCUS_SCALE);
    expect(frame.ty + box.y * frame.k).toBeCloseTo(28);
  });

  it('centres on the parent too when the pair still fits across', () => {
    const box = rowOf(2);
    const context = { x: 0, y: 0, width: 456, height: box.height };
    const frame = frameBox(box, canvas, { context });

    expect(context.width * frame.k).toBeLessThanOrEqual(canvas.width - 56);
    expect(frame.tx + context.x * frame.k + (context.width * frame.k) / 2).toBeCloseTo(
      canvas.width / 2,
    );
  });

  it('drops the parent and centres the child when the pair no longer fits', () => {
    const box = rowOf(1);
    const context = { x: 0, y: 0, width: 456, height: box.height };
    const frame = frameBox(box, canvas, { context });

    expect(context.width * frame.k).toBeGreaterThan(canvas.width - 56);
    expect(frame.tx + box.x * frame.k + (box.width * frame.k) / 2).toBeCloseTo(canvas.width / 2);
  });

  it('keeps the node you clicked in view when its row is too tall to fit', () => {
    const row = { x: 266, y: 0, width: NODE_WIDTH, height: 5936 };
    const anchor = { x: 266, y: 3000, width: NODE_WIDTH, height: NODE_HEIGHT };
    const frame = frameBox(row, canvas, { anchor });

    const centre = frame.ty + anchor.y * frame.k + (anchor.height * frame.k) / 2;
    expect(centre).toBeCloseTo(canvas.height / 2);
  });

  it('still starts a too-tall expansion at its first child, with no anchor given', () => {
    const row = { x: 266, y: 0, width: NODE_WIDTH, height: 5936 };
    const frame = frameBox(row, canvas);

    expect(frame.ty + row.y * frame.k).toBeCloseTo(28);
  });

  it('survives a degenerate box', () => {
    const frame = frameBox({ x: 0, y: 0, width: 0, height: 0 }, canvas);
    expect(Number.isFinite(frame.k)).toBe(true);
    expect(Number.isFinite(frame.tx)).toBe(true);
    expect(Number.isFinite(frame.ty)).toBe(true);
  });
});
