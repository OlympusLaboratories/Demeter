import { describe, expect, it } from 'vitest';

import type { AgentNode } from './model';
import { newestActivityMs, pruneStale } from './staleness';

const NOW = 1_700_000_000_000;
const HOUR = 3_600_000;
const CUTOFF = NOW - 24 * HOUR;

function node(id: string, activityMs: number | undefined, children: AgentNode[] = []): AgentNode {
  return { id, kind: 'agent', label: id, status: 'done', events: [], children, activityMs };
}

function session(id: string, activityMs: number | undefined, children: AgentNode[] = []): AgentNode {
  return { id, kind: 'session', label: id, status: 'done', events: [], children, activityMs };
}

const ids = (roots: AgentNode[]): string[] =>
  roots.flatMap((root) => [root.id, ...ids(root.children)]);

describe('newestActivityMs', () => {
  it('takes the newest stamp anywhere in the subtree', () => {
    const tree = session('s', NOW - 5 * 24 * HOUR, [
      node('a1', NOW - 6 * 24 * HOUR),
      node('a2', NOW - HOUR, [node('a3', NOW - 9 * 24 * HOUR)]),
    ]);

    expect(newestActivityMs(tree)).toBe(NOW - HOUR);
  });

  it('answers zero when nothing in the subtree carries a stamp', () => {
    expect(newestActivityMs(session('s', undefined, [node('a1', undefined)]))).toBe(0);
  });

  it('reads through a node that carries no stamp of its own', () => {
    const workflow = node('workflow:w', undefined, [node('a1', NOW - 2 * HOUR)]);

    expect(newestActivityMs(session('s', NOW - 5 * 24 * HOUR, [workflow]))).toBe(NOW - 2 * HOUR);
  });
});

describe('pruneStale', () => {
  it('keeps a session inside the window', () => {
    const pruned = pruneStale([session('s', NOW - 2 * HOUR)], CUTOFF);

    expect(ids(pruned.roots)).toEqual(['s']);
    expect(pruned.hidden).toBe(0);
  });

  it('drops a session outside the window and counts every node it took with it', () => {
    const tree = session('s', NOW - 30 * HOUR, [node('a1', NOW - 40 * HOUR, [node('a2', NOW - 50 * HOUR)])]);

    const pruned = pruneStale([tree], CUTOFF);

    expect(pruned.roots).toEqual([]);
    expect(pruned.hidden).toBe(3);
  });

  it('keeps every child of a session that came back, however old the child is', () => {
    const tree = session('s', NOW - HOUR, [
      node('a1', NOW - 20 * 24 * HOUR),
      node('a2', undefined, [node('a3', NOW - 40 * 24 * HOUR)]),
    ]);

    const pruned = pruneStale([tree], CUTOFF);

    expect(ids(pruned.roots)).toEqual(['s', 'a1', 'a2', 'a3']);
    expect(pruned.hidden).toBe(0);
  });

  it('keeps a session whose own transcript is old but whose agent is recent', () => {
    const tree = session('s', NOW - 5 * 24 * HOUR, [node('a1', NOW - 3 * HOUR)]);

    const pruned = pruneStale([tree], CUTOFF);

    expect(ids(pruned.roots)).toEqual(['s', 'a1']);
    expect(pruned.hidden).toBe(0);
  });

  it('judges each root on its own and sums what it hid', () => {
    const busy = session('busy', NOW - HOUR, [node('b1', NOW - HOUR)]);
    const quiet = session('quiet', NOW - 30 * HOUR, [node('q1', NOW - 31 * HOUR)]);

    const pruned = pruneStale([busy, quiet], CUTOFF);

    expect(ids(pruned.roots)).toEqual(['busy', 'b1']);
    expect(pruned.hidden).toBe(2);
  });

  it('treats a timestamp from the future as fresh rather than hiding it', () => {
    const pruned = pruneStale([session('s', NOW + 10 * HOUR)], CUTOFF);

    expect(ids(pruned.roots)).toEqual(['s']);
  });

  it('hides a session carrying no timestamp at all', () => {
    const pruned = pruneStale([session('s', undefined)], CUTOFF);

    expect(pruned.roots).toEqual([]);
    expect(pruned.hidden).toBe(1);
  });

  it('returns the surviving subtrees untouched rather than copies that could be mutated apart', () => {
    const child = node('a1', NOW - HOUR);
    const tree = session('s', NOW - HOUR, [child]);

    const pruned = pruneStale([tree], CUTOFF);

    expect(pruned.roots[0]).toBe(tree);
    expect(pruned.roots[0]?.children[0]).toBe(child);
  });
});
