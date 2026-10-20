import { NODE_HEIGHT, NODE_WIDTH } from './graphLayout';

export interface Box {
  x: number;
  y: number;
  width: number;
  height: number;
}

export const GLYPH_X = 10;
export const TEXT_X = 26;
export const LABEL_BASELINE = 19;
export const SUBLABEL_BASELINE = 34;
export const LABEL_FONT = 12;
export const SUBLABEL_FONT = 10.5;

const BADGE_WIDTH = 30;
const BADGE_HEIGHT = 16;
const BADGE_INSET = 4;
const TEXT_GAP = 6;
const AVERAGE_ADVANCE = 0.55;

export function badgeBox(): Box {
  return {
    x: NODE_WIDTH - BADGE_WIDTH - BADGE_INSET,
    y: BADGE_INSET,
    width: BADGE_WIDTH,
    height: BADGE_HEIGHT,
  };
}

export function textRowBox(baseline: number, fontSize: number): Box {
  return {
    x: TEXT_X,
    y: baseline - fontSize,
    width: NODE_WIDTH - TEXT_X - BADGE_INSET,
    height: fontSize + 2,
  };
}

export function overlaps(left: Box, right: Box): boolean {
  return (
    left.x < right.x + right.width &&
    right.x < left.x + left.width &&
    left.y < right.y + right.height &&
    right.y < left.y + left.height
  );
}

function charsForWidth(width: number, fontSize: number): number {
  return Math.max(4, Math.floor(width / (fontSize * AVERAGE_ADVANCE)));
}

export function labelCapacity(hasBadge: boolean): number {
  const badge = badgeBox();
  const limit = hasBadge ? badge.x - TEXT_GAP : NODE_WIDTH - BADGE_INSET;
  return charsForWidth(limit - TEXT_X, LABEL_FONT);
}

export function sublabelCapacity(hasBadge: boolean): number {
  const badge = badgeBox();
  const row = textRowBox(SUBLABEL_BASELINE, SUBLABEL_FONT);
  const clearsBadge = !hasBadge || row.y >= badge.y + badge.height;
  const limit = clearsBadge ? NODE_WIDTH - BADGE_INSET : badge.x - TEXT_GAP;
  return charsForWidth(limit - TEXT_X, SUBLABEL_FONT);
}

export function nodeBounds(): Box {
  return { x: 0, y: 0, width: NODE_WIDTH, height: NODE_HEIGHT };
}
