import { describe, expect, it } from 'vitest';
import type { AgentNode, NodeStatus } from './model';
import { propagateActivity } from './model';
import { isActiveStatus, pruneInactive } from './activeOnly';

function node(id: string, status: NodeStatus, children: AgentNode[] = []): AgentNode {
  return { id, kind: 'agent', label: id, status, events: [], children };
}

function ids(roots: AgentNode[]): string[] {
  const out: string[] = [];
  const walk = (entry: AgentNode): void => {
    out.push(entry.id);
    for (const child of entry.children) walk(child);
  };
  for (const root of roots) walk(root);
  return out;
}

describe('isActiveStatus', () => {
  it('counts the two statuses the graph paints green and blue', () => {
    expect(isActiveStatus('live')).toBe(true);
    expect(isActiveStatus('running')).toBe(true);
    expect(isActiveStatus('done')).toBe(false);
    expect(isActiveStatus('idle')).toBe(false);
    expect(isActiveStatus('error')).toBe(false);
    expect(isActiveStatus(undefined)).toBe(false);
  });
});

describe('pruneInactive', () => {
  it('drops a session with nothing live or running in it', () => {
    const tree = node('session:a', 'done', [node('agent:1', 'done')]);
    propagateActivity(tree);

    const pruned = pruneInactive([tree]);

    expect(pruned.roots).toEqual([]);
    expect(pruned.hidden).toBe(2);
  });

  it('keeps the whole path from a live agent up to its session', () => {
    const tree = node('session:a', 'idle', [
      node('workflow:w', 'done', [node('agent:1', 'live'), node('agent:2', 'done')]),
      node('agent:3', 'done'),
    ]);
    propagateActivity(tree);

    const pruned = pruneInactive([tree]);

    expect(ids(pruned.roots)).toEqual(['session:a', 'workflow:w', 'agent:1']);
    expect(pruned.hidden).toBe(2);
  });

  it('keeps a failure and the path to it, since a hidden error reads as success', () => {
    const tree = node('session:a', 'done', [node('agent:1', 'error'), node('agent:2', 'done')]);
    propagateActivity(tree);

    const pruned = pruneInactive([tree]);

    expect(ids(pruned.roots)).toEqual(['session:a', 'agent:1']);
    expect(pruned.hidden).toBe(1);
  });

  it('leaves the loaded trees untouched, since the view is rebuilt from them every poll', () => {
    const tree = node('session:a', 'idle', [node('agent:1', 'live'), node('agent:2', 'done')]);
    propagateActivity(tree);

    pruneInactive([tree]);

    expect(tree.children).toHaveLength(2);
    expect(ids([tree])).toEqual(['session:a', 'agent:1', 'agent:2']);
  });

  it('keeps every session that has work in it and hides only the quiet ones', () => {
    const busy = node('session:a', 'live');
    const quiet = node('session:b', 'done', [node('agent:9', 'done')]);
    propagateActivity(busy);
    propagateActivity(quiet);

    const pruned = pruneInactive([busy, quiet]);

    expect(ids(pruned.roots)).toEqual(['session:a']);
    expect(pruned.hidden).toBe(2);
  });

  it('hides nothing when everything is working', () => {
    const tree = node('session:a', 'live', [node('agent:1', 'running')]);
    propagateActivity(tree);

    const pruned = pruneInactive([tree]);

    expect(ids(pruned.roots)).toEqual(['session:a', 'agent:1']);
    expect(pruned.hidden).toBe(0);
  });
});
