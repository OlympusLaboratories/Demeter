import { describe, expect, it } from 'vitest';
import { parseUsage } from './usage';

const modern = {
  five_hour: { utilization: 15.0, resets_at: '2026-09-23T05:00:00Z' },
  seven_day: { utilization: 50.0, resets_at: '2026-09-29T00:00:00Z' },
  limits: [
    { kind: 'session', group: 'session', percent: 15, severity: 'normal', resets_at: '2026-09-23T05:00:00Z', scope: null },
    { kind: 'weekly_all', group: 'weekly', percent: 50, severity: 'warning', resets_at: '2026-09-29T00:00:00Z', scope: null },
    {
      kind: 'weekly_scoped',
      group: 'weekly',
      percent: 3,
      severity: 'normal',
      resets_at: '2026-09-29T00:00:00Z',
      scope: { model: { id: null, display_name: 'Opus' }, surface: null },
    },
  ],
  spend: {
    used: { amount_minor: 10003, currency: 'USD', exponent: 2 },
    limit: { amount_minor: 10000, currency: 'USD', exponent: 2 },
    percent: 100,
    severity: 'critical',
    enabled: true,
  },
};

describe('parseUsage', () => {
  it('reads the session, weekly and per-model windows', () => {
    const snapshot = parseUsage(modern, 1_000)!;
    expect(snapshot.fetchedAt).toBe(1_000);
    expect(snapshot.meters.map((meter) => meter.id)).toEqual(['session', 'weekly', 'scoped:Opus', 'spend']);

    const session = snapshot.meters[0]!;
    expect(session.label).toBe('Session');
    expect(session.shortLabel).toBe('5h');
    expect(session.percent).toBe(15);
    expect(session.resetsAt).toBe(Date.parse('2026-09-23T05:00:00Z'));

    expect(snapshot.meters[1]!.severity).toBe('warning');
    expect(snapshot.meters[2]!.label).toBe('Opus');
  });

  it('carries the spend meter with a human readable detail', () => {
    const spend = parseUsage(modern, 0)!.meters.find((meter) => meter.group === 'spend')!;
    expect(spend.percent).toBe(100);
    expect(spend.severity).toBe('critical');
    expect(spend.detail).toContain('100.03');
    expect(spend.detail).toContain('100.00');
  });

  it('omits spend when extra usage is switched off', () => {
    const snapshot = parseUsage({ ...modern, spend: { ...modern.spend, enabled: false } }, 0)!;
    expect(snapshot.meters.some((meter) => meter.group === 'spend')).toBe(false);
  });

  it('falls back to the legacy fields when limits is missing', () => {
    const snapshot = parseUsage(
      {
        five_hour: { utilization: 12, resets_at: '2026-09-23T05:00:00Z' },
        seven_day: { utilization: 44, resets_at: '2026-09-29T00:00:00Z' },
        seven_day_opus: { utilization: 7, resets_at: '2026-09-29T00:00:00Z' },
      },
      0,
    )!;
    expect(snapshot.meters.map((meter) => meter.id)).toEqual(['session', 'weekly', 'scoped:Opus']);
    expect(snapshot.meters[1]!.percent).toBe(44);
  });

  it('skips unusable entries rather than inventing meters', () => {
    expect(parseUsage({ limits: [{ kind: 'session', percent: null }] }, 0)).toBeUndefined();
    expect(parseUsage({ limits: [] }, 0)).toBeUndefined();
    expect(parseUsage(null, 0)).toBeUndefined();
    expect(parseUsage('nope', 0)).toBeUndefined();
  });

  it('clamps percentages and tolerates unparseable reset stamps', () => {
    const snapshot = parseUsage({ limits: [{ kind: 'session', percent: 140, resets_at: 'soon' }] }, 0)!;
    expect(snapshot.meters[0]!.percent).toBe(100);
    expect(snapshot.meters[0]!.resetsAt).toBeUndefined();
  });

  it('names unlabelled scoped windows without colliding', () => {
    const snapshot = parseUsage(
      { limits: [{ kind: 'weekly_scoped', percent: 1 }, { kind: 'weekly_scoped', percent: 2 }] },
      0,
    )!;
    expect(snapshot.meters.map((meter) => meter.id)).toEqual(['scoped:scoped0', 'scoped:scoped1']);
  });
});
