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
const OPEN_WIDTH = 18;
const OPEN_HEIGHT = 16;
const TEXT_GAP = 6;
const AVERAGE_ADVANCE = 0.55;

export interface Chrome {
  badge?: boolean;
  open?: boolean;
}

export function badgeBox(): Box {
  return {
    x: NODE_WIDTH - BADGE_WIDTH - BADGE_INSET,
    y: BADGE_INSET,
    width: BADGE_WIDTH,
    height: BADGE_HEIGHT,
  };
}

export function openBox(): Box {
  return {
    x: NODE_WIDTH - OPEN_WIDTH - BADGE_INSET,
    y: NODE_HEIGHT - OPEN_HEIGHT - BADGE_INSET,
    width: OPEN_WIDTH,
    height: OPEN_HEIGHT,
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

function limitFor(baseline: number, fontSize: number, chrome: Chrome): number {
  const row = textRowBox(baseline, fontSize);
  let limit = NODE_WIDTH - BADGE_INSET;
  for (const [present, box] of [
    [chrome.badge === true, badgeBox()],
    [chrome.open === true, openBox()],
  ] as Array<[boolean, Box]>) {
    if (present && overlaps(row, box)) limit = Math.min(limit, box.x - TEXT_GAP);
  }
  return limit;
}

export function labelCapacity(chrome: Chrome | boolean): number {
  const resolved = typeof chrome === 'boolean' ? { badge: chrome } : chrome;
  return charsForWidth(limitFor(LABEL_BASELINE, LABEL_FONT, resolved) - TEXT_X, LABEL_FONT);
}

export function sublabelCapacity(chrome: Chrome | boolean): number {
  const resolved = typeof chrome === 'boolean' ? { badge: chrome } : chrome;
  return charsForWidth(limitFor(SUBLABEL_BASELINE, SUBLABEL_FONT, resolved) - TEXT_X, SUBLABEL_FONT);
}

export function nodeBounds(): Box {
  return { x: 0, y: 0, width: NODE_WIDTH, height: NODE_HEIGHT };
}
