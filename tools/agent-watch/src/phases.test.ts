import { describe, expect, it } from 'vitest';
import { parseManifest } from './manifest';
import { buildWorkflowNode } from './model';
import type { SubagentInput } from './model';

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
    });

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
    });
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
    });

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
    });
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
    });

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
    const node = buildWorkflowNode({ runId: 'wf_test', journal: [], agents: agents(1, 'r'), manifest });
    expect(node.children[0]?.kind).toBe('agent');
  });
});
