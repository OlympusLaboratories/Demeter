import { Meter } from './format';

export interface PacingOptions {
  activeMs: number;
  idleMs: number;
  unchanged: number;
  steadyAfter: number;
}

export function nextInterval({ activeMs, idleMs, unchanged, steadyAfter }: PacingOptions): number {
  if (unchanged < steadyAfter) {
    return activeMs;
  }
  const doublings = unchanged - steadyAfter + 1;
  const relaxed = activeMs * 2 ** Math.min(doublings, 16);
  return Math.min(Math.max(idleMs, activeMs), relaxed);
}

export function readingOf(meters: Meter[] | undefined): string {
  if (meters === undefined) {
    return '';
  }
  return meters.map((meter) => `${meter.id}:${meter.percent}`).join('|');
}

export const RESET_BUFFER_MS = 5_000;
export const MIN_DELAY_MS = 10_000;

export function pollDelay(options: {
  intervalMs: number;
  resetTimes: number[];
  now: number;
}): number {
  const { intervalMs, resetTimes, now } = options;
  let delay = intervalMs;
  for (const resetsAt of resetTimes) {
    const afterReset = resetsAt - now + RESET_BUFFER_MS;
    if (afterReset > 0 && afterReset < delay) {
      delay = afterReset;
    }
  }
  return Math.max(MIN_DELAY_MS, delay);
}

export function clockInterval(resetTimes: number[], now: number): number {
  const soonest = resetTimes
    .map((resetsAt) => resetsAt - now)
    .filter((remaining) => remaining > -60_000)
    .sort((a, b) => a - b)[0];
  return soonest !== undefined && soonest < 120_000 ? 1_000 : 10_000;
}
