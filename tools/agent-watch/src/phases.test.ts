import { describe, expect, it } from 'vitest';
import { parseManifest } from './manifest';
import { buildWorkflowNode, propagateActivity } from './model';
import type { SubagentInput } from './model';

const STALE = { liveWindowSeconds: 60, nowMs: 10_000_000 };

function agents(count: number, prefix = 'a'): SubagentInput[] {
  return Array.from({ length: count }, (_unused, index) => ({
    agentId: `${prefix}${index}`,
    meta: { agentType: 'workflow-subagent' },
    lines: [],
  }));
}

function manifestFor(spec: { id: string; phase: string; state?: string; label?: string }[]) {
  return parseManifest({
    runId: 'wf_test',
    workflowName: 'review-code',
    logs: ['review-code: 6 lenses, 30 candidate findings, 15 confirmed'],
    phases: [{ title: 'Review' }, { title: 'Verify' }],
    workflowProgress: spec.map((entry, index) => ({
      type: 'workflow_agent',
      agentId: entry.id,
      label: entry.label ?? `${entry.phase.toLowerCase()}:${index}`,
      phaseIndex: entry.phase === 'Review' ? 1 : 2,
      phaseTitle: entry.phase,
      state: entry.state ?? 'done',
    })),
  });
}

describe('buildWorkflowNode', () => {
  it('bands a flat fan-out into phase layers in declared order', () => {
    const spec = [
      ...agents(2, 'r').map((agent) => ({ id: agent.agentId, phase: 'Review' })),
      ...agents(5, 'v').map((agent) => ({ id: agent.agentId, phase: 'Verify' })),
    ];
    const node = buildWorkflowNode({
      runId: 'wf_test',
      journal: [],
      agents: [...agents(2, 'r'), ...agents(5, 'v')],
      manifest: manifestFor(spec),
    }, STALE);

    expect(node.children.map((child) => child.kind)).toEqual(['phase', 'phase']);
    expect(node.children.map((child) => child.label)).toEqual(['Review', 'Verify']);
    expect(node.children[0]?.children).toHaveLength(2);
    expect(node.children[1]?.children).toHaveLength(5);
    expect(node.children[1]?.sublabel).toBe('5 agents');
  });

  it('labels the run from the manifest and summarizes from its log line', () => {
    const node = buildWorkflowNode({
      runId: 'wf_test',
      journal: [],
      agents: agents(1, 'r'),
      manifest: manifestFor([{ id: 'r0', phase: 'Review' }]),
    }, STALE);
    expect(node.label).toBe('review-code');
    expect(node.sublabel).toContain('15 confirmed');
  });

  it('takes agent labels and status from the manifest rather than the prompt', () => {
    const node = buildWorkflowNode({
      runId: 'wf_test',
      journal: [],
      agents: [...agents(1, 'r'), ...agents(1, 'v')],
      manifest: manifestFor([
        { id: 'r0', phase: 'Review', label: 'review:correctness' },
        { id: 'v0', phase: 'Verify', state: 'progress', label: 'verify:auth.ts' },
      ]),
    }, STALE);

    const review = node.children[0]?.children[0];
    const verify = node.children[1]?.children[0];
    expect(review?.label).toBe('review:correctness');
    expect(verify?.label).toBe('verify:auth.ts');
    expect(verify?.status).toBe('running');
    expect(node.status).toBe('running');
  });

  it('marks a phase failed when one of its agents errored', () => {
    const node = buildWorkflowNode({
      runId: 'wf_test',
      journal: [],
      agents: agents(2, 'r'),
      manifest: manifestFor([
        { id: 'r0', phase: 'Review' },
        { id: 'r1', phase: 'Review', state: 'error' },
      ]),
    }, STALE);
    expect(node.children[0]?.status).toBe('error');
    expect(node.children[0]?.sublabel).toBe('2 agents · 1 failed');
  });

  it('stays flat when there is no manifest, falling back to the journal', () => {
    const node = buildWorkflowNode({
      runId: 'wf_test',
      journal: [
        { type: 'started', agentId: 'r0' },
        { type: 'started', agentId: 'r1' },
        { type: 'result', agentId: 'r0' },
      ],
      agents: agents(2, 'r'),
    }, STALE);

    expect(node.children.every((child) => child.kind === 'agent')).toBe(true);
    expect(node.sublabel).toBe('1/2 done');
    expect(node.children[1]?.status).toBe('running');
  });

  it('stays flat when the manifest declares a single phase', () => {
    const manifest = parseManifest({
      runId: 'wf_test',
      phases: [{ title: 'Only' }],
      workflowProgress: [{ type: 'workflow_agent', agentId: 'r0', phaseTitle: 'Only', state: 'done' }],
    });
    const node = buildWorkflowNode({ runId: 'wf_test', journal: [], agents: agents(1, 'r'), manifest }, STALE);
    expect(node.children[0]?.kind).toBe('agent');
  });
});

describe('a run that was killed or failed', () => {
  function manifestWith(status: string, states: string[]) {
    return parseManifest({
      runId: 'wf_x',
      status,
      phases: [{ title: 'Review' }, { title: 'Verify' }],
      workflowProgress: states.map((state, index) => ({
        type: 'workflow_agent',
        agentId: `a${index}`,
        label: `lens-${index}`,
        phaseTitle: index === 0 ? 'Review' : 'Verify',
        state,
      })),
    });
  }

  it('is reported as failed even when its agents were stranded mid-flight', () => {
    const manifest = manifestWith('killed', ['progress', 'start']);
    const node = buildWorkflowNode(
      {
        runId: 'wf_x',
        journal: [],
        agents: [
          { agentId: 'a0', meta: {}, lines: [] },
          { agentId: 'a1', meta: {}, lines: [] },
        ],
        manifest,
      },
      STALE,
    );

    expect(node.status).toBe('error');
    expect(node.children.every((child) => child.status !== 'running')).toBe(true);
  });

  it('does not leave a stranded agent looking alive just because it was just written', () => {
    const manifest = manifestWith('failed', ['progress']);
    const node = buildWorkflowNode(
      {
        runId: 'wf_x',
        journal: [],
        agents: [{ agentId: 'a0', meta: {}, lines: [], mtimeMs: 9_999_999 }],
        manifest,
      },
      { liveWindowSeconds: 60, nowMs: 10_000_000 },
    );

    expect(node.status).toBe('error');
    expect(propagateActivity(node)).toBeUndefined();
  });
});

describe('a completed run', () => {
  it('does not leave an agent running forever because its journal result never landed', () => {
    const manifest = parseManifest({ runId: 'wf_z', status: 'completed', phases: [], workflowProgress: [] });
    const node = buildWorkflowNode(
      {
        runId: 'wf_z',
        journal: [{ type: 'started', agentId: 'ghost' }],
        agents: [{ agentId: 'ghost', meta: {}, lines: [] }],
        manifest,
      },
      STALE,
    );

    expect(node.children[0]?.status).toBe('done');
    expect(node.status).toBe('done');
  });

  it('still reports a run with no manifest from its journal', () => {
    const node = buildWorkflowNode(
      {
        runId: 'wf_w',
        journal: [{ type: 'started', agentId: 'live-one' }],
        agents: [{ agentId: 'live-one', meta: {}, lines: [] }],
      },
      STALE,
    );

    expect(node.status).toBe('running');
  });
});

describe('a phase whose members are working', () => {
  it('reads as live rather than flipping to error because one member failed', () => {
    const manifest = parseManifest({
      runId: 'wf_y',
      phases: [{ title: 'Review' }, { title: 'Verify' }],
      workflowProgress: [
        { type: 'workflow_agent', agentId: 'ok', phaseTitle: 'Review', state: 'progress' },
        { type: 'workflow_agent', agentId: 'bad', phaseTitle: 'Review', state: 'error' },
        { type: 'workflow_agent', agentId: 'other', phaseTitle: 'Verify', state: 'done' },
      ],
    });

    const node = buildWorkflowNode(
      {
        runId: 'wf_y',
        journal: [],
        agents: [
          { agentId: 'ok', meta: {}, lines: [], mtimeMs: 9_999_000 },
          { agentId: 'bad', meta: {}, lines: [] },
          { agentId: 'other', meta: {}, lines: [] },
        ],
        manifest,
      },
      { liveWindowSeconds: 60, nowMs: 10_000_000 },
    );

    const review = node.children.find((child) => child.label === 'Review');
    expect(review?.status).toBe('live');
    expect(review?.sublabel).toContain('1 failed');
  });
});
