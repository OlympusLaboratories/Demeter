import { describe, expect, it } from 'vitest';
import { Meter } from './format';
import { MIN_DELAY_MS, clockInterval, nextInterval, pollDelay, readingOf } from './pacing';

const base = { activeMs: 60_000, idleMs: 600_000, steadyAfter: 2 };

function meter(id: string, percent: number): Meter {
  return { id, group: 'session', label: id, shortLabel: id, title: id, percent, severity: 'normal' };
}

describe('nextInterval', () => {
  it('stays at the active rate while the numbers are still moving', () => {
    expect(nextInterval({ ...base, unchanged: 0 })).toBe(60_000);
    expect(nextInterval({ ...base, unchanged: 1 })).toBe(60_000);
  });

  it('backs off geometrically once the numbers go quiet', () => {
    expect(nextInterval({ ...base, unchanged: 2 })).toBe(120_000);
    expect(nextInterval({ ...base, unchanged: 3 })).toBe(240_000);
    expect(nextInterval({ ...base, unchanged: 4 })).toBe(480_000);
  });

  it('never relaxes past the idle ceiling', () => {
    expect(nextInterval({ ...base, unchanged: 5 })).toBe(600_000);
    expect(nextInterval({ ...base, unchanged: 500 })).toBe(600_000);
  });

  it('never returns less than the active rate, even if idle is set lower', () => {
    expect(nextInterval({ activeMs: 60_000, idleMs: 10_000, unchanged: 9, steadyAfter: 2 })).toBe(60_000);
  });

  it('keeps the active rate throughout when backing off is switched off', () => {
    expect(nextInterval({ ...base, idleMs: 60_000, unchanged: 99 })).toBe(60_000);
  });
});

describe('readingOf', () => {
  it('changes when any percentage moves', () => {
    expect(readingOf([meter('session', 10)])).not.toBe(readingOf([meter('session', 11)]));
  });

  it('is stable when nothing moves', () => {
    expect(readingOf([meter('session', 10), meter('weekly', 50)])).toBe(
      readingOf([meter('session', 10), meter('weekly', 50)]),
    );
  });

  it('treats a missing reading as its own thing', () => {
    expect(readingOf(undefined)).toBe('');
    expect(readingOf([])).toBe('');
  });
});

describe('pollDelay', () => {
  const now = 1_000_000;

  it('uses the pacing interval when no reset is near', () => {
    expect(pollDelay({ intervalMs: 600_000, resetTimes: [now + 3_600_000], now })).toBe(600_000);
  });

  it('never sleeps through a reset, however relaxed the pacing is', () => {
    expect(pollDelay({ intervalMs: 600_000, resetTimes: [now + 180_000], now })).toBe(185_000);
  });

  it('wakes just after the soonest of several resets', () => {
    const delay = pollDelay({
      intervalMs: 600_000,
      resetTimes: [now + 500_000, now + 90_000, now + 200_000],
      now,
    });
    expect(delay).toBe(95_000);
  });

  it('ignores resets that have already passed', () => {
    expect(pollDelay({ intervalMs: 600_000, resetTimes: [now - 10_000], now })).toBe(600_000);
  });

  it('keeps a floor so a reset on the nose cannot spin', () => {
    expect(pollDelay({ intervalMs: 600_000, resetTimes: [now + 1], now })).toBe(MIN_DELAY_MS);
    expect(pollDelay({ intervalMs: 1_000, resetTimes: [], now })).toBe(MIN_DELAY_MS);
  });

  it('leaves the interval alone when there are no resets at all', () => {
    expect(pollDelay({ intervalMs: 600_000, resetTimes: [], now })).toBe(600_000);
  });
});

describe('clockInterval', () => {
  const now = 1_000_000;

  it('ticks every second through the final two minutes', () => {
    expect(clockInterval([now + 90_000], now)).toBe(1_000);
    expect(clockInterval([now + 5_000], now)).toBe(1_000);
  });

  it('keeps ticking fast just after a reset lands', () => {
    expect(clockInterval([now - 5_000], now)).toBe(1_000);
  });

  it('relaxes when every reset is far away', () => {
    expect(clockInterval([now + 3_600_000], now)).toBe(10_000);
    expect(clockInterval([], now)).toBe(10_000);
  });

  it('follows the soonest reset, not the first listed', () => {
    expect(clockInterval([now + 3_600_000, now + 30_000], now)).toBe(1_000);
  });
});
