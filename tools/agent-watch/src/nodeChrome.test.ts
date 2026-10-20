import { describe, expect, it } from 'vitest';
import {
  LABEL_BASELINE,
  LABEL_FONT,
  SUBLABEL_BASELINE,
  SUBLABEL_FONT,
  badgeBox,
  labelCapacity,
  nodeBounds,
  overlaps,
  sublabelCapacity,
  textRowBox,
} from './nodeChrome';

describe('node chrome geometry', () => {
  it('keeps the expand badge clear of the sublabel row', () => {
    expect(overlaps(badgeBox(), textRowBox(SUBLABEL_BASELINE, SUBLABEL_FONT))).toBe(false);
  });

  it('keeps the badge inside the node', () => {
    const badge = badgeBox();
    const node = nodeBounds();
    expect(badge.x).toBeGreaterThanOrEqual(0);
    expect(badge.y).toBeGreaterThanOrEqual(0);
    expect(badge.x + badge.width).toBeLessThanOrEqual(node.width);
    expect(badge.y + badge.height).toBeLessThanOrEqual(node.height);
  });

  it('shortens the label when a badge shares its row', () => {
    expect(labelCapacity(true)).toBeLessThan(labelCapacity(false));
    expect(overlaps(badgeBox(), textRowBox(LABEL_BASELINE, LABEL_FONT))).toBe(true);
  });

  it('gives the sublabel the full width, since the badge sits above it', () => {
    expect(sublabelCapacity(true)).toBe(sublabelCapacity(false));
  });

  it('never returns a capacity too small to show anything', () => {
    expect(labelCapacity(true)).toBeGreaterThanOrEqual(4);
    expect(sublabelCapacity(true)).toBeGreaterThanOrEqual(4);
  });
});
