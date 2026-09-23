import { describe, expect, it } from 'vitest';
import {
  BAR_STYLES,
  Meter,
  RenderOptions,
  escalate,
  formatAge,
  formatPercent,
  formatRemaining,
  freshness,
  meterText,
  renderBar,
  worstSeverity,
} from './format';

const options: RenderOptions = {
  labelStyle: 'long',
  barWidth: 6,
  barStyle: 'blocks',
  showReset: true,
  warnAtPercent: 75,
  criticalAtPercent: 90,
};

const meter: Meter = {
  id: 'session',
  group: 'session',
  label: 'Session',
  shortLabel: '5h',
  title: 'Current session (5 hours)',
  percent: 15,
  severity: 'normal',
  resetsAt: 0,
};

describe('renderBar', () => {
  it('fills proportionally', () => {
    expect(renderBar(50, 6, 'blocks')).toBe('███░░░');
  });

  it('shows one cell for any non-zero usage', () => {
    expect(renderBar(1, 6, 'blocks')).toBe('█░░░░░');
  });

  it('keeps one empty cell until the limit is actually reached', () => {
    expect(renderBar(99, 6, 'blocks')).toBe('█████░');
    expect(renderBar(100, 6, 'blocks')).toBe('██████');
  });

  it('is empty at zero usage and at zero width', () => {
    expect(renderBar(0, 6, 'blocks')).toBe('░░░░░░');
    expect(renderBar(50, 0, 'blocks')).toBe('');
  });

  it('draws every style with one glyph per cell and no mixing', () => {
    for (const style of BAR_STYLES) {
      const bar = renderBar(50, 6, style);
      expect([...bar]).toHaveLength(6);
      expect(new Set([...bar]).size).toBe(2);
    }
  });

  it('uses circles by default, which UI fonts actually carry', () => {
    expect(renderBar(50, 6, 'dots')).toBe('●●●○○○');
    expect(renderBar(50, 6, 'squares')).toBe('■■■□□□');
    expect(renderBar(50, 6, 'bars')).toBe('▮▮▮▯▯▯');
    expect(renderBar(50, 6, 'line')).toBe('━━━───');
  });

  it('falls back to circles for an unknown style', () => {
    expect(renderBar(50, 6, 'nonsense' as never)).toBe('●●●○○○');
  });

  it('clamps out-of-range percentages', () => {
    expect(renderBar(-10, 4, 'ascii')).toBe('----');
    expect(renderBar(140, 4, 'ascii')).toBe('####');
  });
});

describe('formatRemaining', () => {
  it('formats days, hours and minutes compactly', () => {
    expect(formatRemaining(6 * 86_400_000 + 3 * 3_600_000)).toBe('6d3h');
    expect(formatRemaining(6 * 86_400_000)).toBe('6d');
    expect(formatRemaining(7 * 3_600_000 + 58 * 60_000)).toBe('7h58m');
    expect(formatRemaining(2 * 3_600_000)).toBe('2h');
    expect(formatRemaining(42 * 60_000)).toBe('42m');
  });

  it('degrades gracefully near and past the reset', () => {
    expect(formatRemaining(30_000)).toBe('<1m');
    expect(formatRemaining(0)).toBe('now');
    expect(formatRemaining(-5_000)).toBe('now');
    expect(formatRemaining(Number.NaN)).toBe('now');
  });
});

describe('escalate', () => {
  it('raises severity once a threshold is crossed', () => {
    expect(escalate('normal', 50, 75, 90)).toBe('normal');
    expect(escalate('normal', 80, 75, 90)).toBe('warning');
    expect(escalate('normal', 95, 75, 90)).toBe('critical');
  });

  it('never lowers the severity the API reported', () => {
    expect(escalate('critical', 5, 75, 90)).toBe('critical');
    expect(escalate('warning', 5, 75, 90)).toBe('warning');
  });
});

describe('worstSeverity', () => {
  it('picks the most severe entry', () => {
    expect(worstSeverity(['normal', 'critical', 'warning'])).toBe('critical');
    expect(worstSeverity([])).toBe('normal');
  });
});

describe('meterText', () => {
  it('renders label, bar, percent and time to reset', () => {
    expect(meterText({ ...meter, resetsAt: 7 * 3_600_000 }, options, 0)).toBe('Session █░░░░░ 15% 7h');
  });

  it('uses the short label when asked', () => {
    expect(meterText(meter, { ...options, labelStyle: 'short', showReset: false }, 0)).toBe('5h █░░░░░ 15%');
  });

  it('drops the reset when it is switched off', () => {
    expect(meterText(meter, { ...options, showReset: false }, 0)).toBe('Session █░░░░░ 15%');
  });

  it('drops the bar at zero width', () => {
    expect(meterText(meter, { ...options, barWidth: 0, showReset: false }, 0)).toBe('Session 15%');
  });
});

describe('formatAge', () => {
  it('reads as fresh for the first few seconds', () => {
    expect(formatAge(0)).toBe('now');
    expect(formatAge(14_000)).toBe('now');
  });

  it('counts seconds, then falls back to the coarser units', () => {
    expect(formatAge(20_000)).toBe('20s');
    expect(formatAge(4 * 60_000)).toBe('4m');
    expect(formatAge(2 * 3_600_000)).toBe('2h');
  });
});

describe('freshness', () => {
  const now = 10_000_000;
  const pollMs = 60_000;

  it('shows the age when asked to show it always', () => {
    const chip = freshness({ updatedAt: now - 20_000, now, pollMs, mode: 'always' })!;
    expect(chip.text).toBe('$(history) 20s');
    expect(chip.severity).toBe('normal');
    expect(chip.stale).toBe(false);
  });

  it('stays hidden while fresh when asked to show only staleness', () => {
    expect(freshness({ updatedAt: now - 20_000, now, pollMs, mode: 'whenStale' })).toBeUndefined();
  });

  it('warns once the reading is well past its poll interval', () => {
    const chip = freshness({ updatedAt: now - 5 * 60_000, now, pollMs, mode: 'whenStale' })!;
    expect(chip.text).toBe('$(warning) 5m');
    expect(chip.severity).toBe('warning');
    expect(chip.stale).toBe(true);
  });

  it('shows the retry countdown while backing off', () => {
    const chip = freshness({
      updatedAt: now - 4 * 60_000,
      retryUntil: now + 2 * 60_000,
      now,
      pollMs,
      mode: 'always',
    })!;
    expect(chip.text).toBe('$(warning) 4m · retry 2m');
    expect(chip.severity).toBe('warning');
  });

  it('still reports a backoff that has never had a reading to go with it', () => {
    const chip = freshness({ retryUntil: now + 90_000, now, pollMs, mode: 'always' })!;
    expect(chip.text).toBe('$(warning) retry 1m');
  });

  it('drops an elapsed backoff back to a plain age', () => {
    const chip = freshness({ updatedAt: now - 20_000, retryUntil: now - 1, now, pollMs, mode: 'always' })!;
    expect(chip.text).toBe('$(history) 20s');
    expect(chip.severity).toBe('normal');
  });

  it('shows nothing at all when switched off, or before the first reading', () => {
    expect(freshness({ updatedAt: now, retryUntil: now + 60_000, now, pollMs, mode: 'never' })).toBeUndefined();
    expect(freshness({ now, pollMs, mode: 'always' })).toBeUndefined();
  });
});

describe('formatPercent', () => {
  it('rounds and clamps', () => {
    expect(formatPercent(14.6)).toBe('15%');
    expect(formatPercent(120)).toBe('100%');
  });
});
