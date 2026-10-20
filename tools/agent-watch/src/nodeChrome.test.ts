import { describe, expect, it } from 'vitest';
import {
  LABEL_BASELINE,
  LABEL_FONT,
  SUBLABEL_BASELINE,
  SUBLABEL_FONT,
  badgeBox,
  labelCapacity,
  nodeBounds,
  openBox,
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

describe('the open-chat button', () => {
  it('sits in the node, clear of the expand badge and the label row', () => {
    const box = openBox();
    const bounds = nodeBounds();

    expect(box.x).toBeGreaterThanOrEqual(bounds.x);
    expect(box.y).toBeGreaterThanOrEqual(bounds.y);
    expect(box.x + box.width).toBeLessThanOrEqual(bounds.x + bounds.width);
    expect(box.y + box.height).toBeLessThanOrEqual(bounds.y + bounds.height);
    expect(overlaps(box, badgeBox())).toBe(false);
    expect(overlaps(box, textRowBox(LABEL_BASELINE, LABEL_FONT))).toBe(false);
  });

  it('shortens the sublabel, which it does overlap, and leaves the label alone', () => {
    expect(sublabelCapacity({ open: true })).toBeLessThan(sublabelCapacity({}));
    expect(labelCapacity({ open: true })).toBe(labelCapacity({}));
    expect(overlaps(openBox(), textRowBox(SUBLABEL_BASELINE, SUBLABEL_FONT))).toBe(true);
  });

  it('shortens both rows when a session also has children to expand', () => {
    const both = { badge: true, open: true };
    expect(labelCapacity(both)).toBe(labelCapacity({ badge: true }));
    expect(sublabelCapacity(both)).toBeLessThan(sublabelCapacity({ badge: true }));
    expect(sublabelCapacity(both)).toBeGreaterThan(0);
  });
});
