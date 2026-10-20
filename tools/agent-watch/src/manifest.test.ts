import { describe, expect, it } from 'vitest';
import { isLive } from './model';
import { firstJsonValue, parseManifest, statusFromState } from './manifest';

const sample = {
  runId: 'wf_abc',
  workflowName: 'review-code',
  status: 'completed',
  logs: ['review-code: 6 lenses, 30 candidate findings, 15 confirmed'],
  phases: [{ title: 'Review' }, { title: 'Verify' }],
  workflowProgress: [
    { type: 'workflow_phase', index: 1, title: 'Review' },
    {
      type: 'workflow_agent',
      agentId: 'a1',
      label: 'review:correctness',
      phaseIndex: 1,
      phaseTitle: 'Review',
      state: 'done',
      model: 'claude-opus-5',
      lastToolName: 'StructuredOutput',
    },
    {
      type: 'workflow_agent',
      agentId: 'a2',
      label: 'verify:auth.ts',
      phaseIndex: 2,
      phaseTitle: 'Verify',
      state: 'progress',
    },
  ],
};

describe('parseManifest', () => {
  it('extracts phases, labels and per-agent state', () => {
    const manifest = parseManifest(sample);
    expect(manifest?.phases).toEqual(['Review', 'Verify']);
    expect(manifest?.agents.size).toBe(2);

    const first = manifest?.agents.get('a1');
    expect(first?.label).toBe('review:correctness');
    expect(first?.phaseTitle).toBe('Review');
    expect(first?.model).toBe('claude-opus-5');
    expect(manifest?.logs[0]).toContain('6 lenses');
  });

  it('ignores phase rows when collecting agents', () => {
    const manifest = parseManifest(sample);
    expect([...(manifest?.agents.keys() ?? [])]).toEqual(['a1', 'a2']);
  });

  it('rejects anything without a runId', () => {
    expect(parseManifest(undefined)).toBeUndefined();
    expect(parseManifest({})).toBeUndefined();
    expect(parseManifest({ workflowProgress: [] })).toBeUndefined();
  });

  it('tolerates a manifest with no progress or phases', () => {
    const manifest = parseManifest({ runId: 'wf_x' });
    expect(manifest?.phases).toEqual([]);
    expect(manifest?.agents.size).toBe(0);
    expect(manifest?.logs).toEqual([]);
  });
});

describe('statusFromState', () => {
  it('maps harness states onto node statuses', () => {
    expect(statusFromState('done')).toBe('done');
    expect(statusFromState('error')).toBe('error');
    expect(statusFromState('progress')).toBe('running');
    expect(statusFromState('start')).toBe('running');
    expect(statusFromState('something-new')).toBeUndefined();
    expect(statusFromState(undefined)).toBeUndefined();
  });
});

describe('firstJsonValue', () => {
  it('reads an ordinary document unchanged', () => {
    expect(firstJsonValue('{"runId":"wf_a","logs":[]}')).toEqual({ runId: 'wf_a', logs: [] });
  });

  it('recovers the first document when the harness wrote two without truncating', () => {
    const first = { runId: 'wf_a', status: 'completed' };
    const stale = { runId: 'wf_a', status: 'running' };
    const value = firstJsonValue(`${JSON.stringify(first)}${JSON.stringify(stale)}`);

    expect(value).toEqual(first);
  });

  it('is not fooled by braces inside strings', () => {
    const doc = { runId: 'wf_a', logs: ['a } b { c', 'escaped \\" quote }'] };
    expect(firstJsonValue(`${JSON.stringify(doc)}{"runId":"later"}`)).toEqual(doc);
  });

  it('gives up rather than guessing at a truncated document', () => {
    expect(firstJsonValue('{"runId":"wf_a","logs":[')).toBeUndefined();
    expect(firstJsonValue('not json at all')).toBeUndefined();
  });
});

describe('isLive', () => {
  const window = { liveWindowSeconds: 60, nowMs: 1_000_000 };

  it('counts a transcript written inside the window, and not one outside it', () => {
    expect(isLive(1_000_000, window)).toBe(true);
    expect(isLive(1_000_000 - 60_000, window)).toBe(true);
    expect(isLive(1_000_000 - 60_001, window)).toBe(false);
  });

  it('tolerates a little clock skew but refuses a timestamp from the future', () => {
    expect(isLive(1_000_000 + 59_000, window)).toBe(true);
    expect(isLive(Date.parse('2035-01-01T00:00:00Z'), window)).toBe(false);
  });

  it('is false when the file could not be stat-ed at all', () => {
    expect(isLive(undefined, window)).toBe(false);
  });
});
