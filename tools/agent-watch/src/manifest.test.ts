import { describe, expect, it } from 'vitest';
import { parseManifest, statusFromState } from './manifest';

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
