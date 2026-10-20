import { describe, expect, it } from 'vitest';
import {
  GitFacts,
  type GitProbe,
  groupByWorktree,
  labelForWorktree,
  partitionSessions,
  removalReasonFor,
  worktreeRootFor,
} from './repos';
import type { LoadedSession } from './loader';
import type { AgentNode, NodeStatus } from './model';

function session(
  id: string,
  cwd: string,
  status: NodeStatus = 'done',
  mtimeMs = 0,
  branch?: string,
): LoadedSession {
  const tree: AgentNode = { id, kind: 'session', label: id, status, events: [], children: [] };
  return { sessionId: id, transcriptPath: `/t/${id}.jsonl`, mtimeMs, cwd, branch, tree, watchPaths: [] };
}

describe('worktreeRootFor', () => {
  it('matches the longest known worktree root rather than the first', () => {
    const roots = ['/repo', '/repo/.claude/worktrees/dylan/PLAT-1'];
    expect(worktreeRootFor('/repo/.claude/worktrees/dylan/PLAT-1/apps/portal', roots)).toBe(
      '/repo/.claude/worktrees/dylan/PLAT-1',
    );
  });

  it('falls back to the worktree path pattern when git roots are unavailable', () => {
    expect(worktreeRootFor('/repo/.claude/worktrees/dylan/PLAT-3138/apps/portal', [])).toBe(
      '/repo/.claude/worktrees/dylan/PLAT-3138',
    );
  });

  it('returns undefined for a plain checkout', () => {
    expect(worktreeRootFor('/repo/apps/iam', [])).toBeUndefined();
  });

  it('keeps a removed worktree out of the enclosing checkout it sits inside', () => {
    const roots = ['/repo', '/repo/.claude/worktrees/dylan/PLAT-1'];
    expect(worktreeRootFor('/repo/.claude/worktrees/dylan/GONE/apps/iam', roots)).toBe(
      '/repo/.claude/worktrees/dylan/GONE',
    );
  });
});

describe('removalReasonFor', () => {
  const state = {
    knownRoots: ['/repo', '/repo/.claude/worktrees/dylan/PLAT-1'],
    branches: new Set(['main', 'dylan/PLAT-1']),
  };

  it('keeps a session in a worktree git still lists', () => {
    expect(
      removalReasonFor({ cwd: '/repo/.claude/worktrees/dylan/PLAT-1', branch: 'dylan/PLAT-1' }, state),
    ).toBeUndefined();
  });

  it('drops a session whose worktree has been removed', () => {
    expect(
      removalReasonFor({ cwd: '/repo/.claude/worktrees/dylan/PLAT-9/apps/iam', branch: 'main' }, state),
    ).toBe('worktree');
  });

  it('drops a session left in the main checkout on a branch since deleted', () => {
    expect(removalReasonFor({ cwd: '/repo/apps/iam', branch: 'dylan/PLAT-9' }, state)).toBe('branch');
  });

  it('judges nothing when git told us nothing', () => {
    const blind = { knownRoots: [], branches: new Set<string>() };
    expect(
      removalReasonFor({ cwd: '/repo/.claude/worktrees/dylan/PLAT-9', branch: 'dylan/PLAT-9' }, blind),
    ).toBeUndefined();
  });

  it('keeps a session that recorded no branch at all', () => {
    expect(removalReasonFor({ cwd: '/repo/apps/iam', branch: undefined }, state)).toBeUndefined();
  });
});

describe('partitionSessions', () => {
  it('splits the sessions you still have from the ones you cleaned up', () => {
    const { live, removed } = partitionSessions(
      [
        session('keep', '/repo/apps/iam', 'done', 0, 'main'),
        session('gone-branch', '/repo/apps/iam', 'done', 0, 'dylan/PLAT-9'),
        session('gone-worktree', '/repo/.claude/worktrees/dylan/PLAT-9', 'done', 0, 'main'),
      ],
      { knownRoots: ['/repo'], branches: new Set(['main']) },
    );

    expect(live.map((entry) => entry.sessionId)).toEqual(['keep']);
    expect(removed.map((entry) => entry.sessionId)).toEqual(['gone-branch', 'gone-worktree']);
  });
});

describe('labelForWorktree', () => {
  it('names the main checkout and uses the last segment for a worktree', () => {
    expect(labelForWorktree(undefined)).toBe('main');
    expect(labelForWorktree('/repo/.claude/worktrees/dylan/PLAT-1')).toBe('PLAT-1');
  });
});

describe('groupByWorktree', () => {
  it('separates worktree sessions from the main checkout and counts live ones', () => {
    const groups = groupByWorktree(
      [
        session('s1', '/repo'),
        session('s2', '/repo/.claude/worktrees/dylan/PLAT-1', 'live', 50),
        session('s3', '/repo/.claude/worktrees/dylan/PLAT-1/apps', 'done', 10),
      ],
      [],
    );

    expect(groups).toHaveLength(2);
    expect(groups[0]?.key).toBe('main');
    const worktree = groups[1];
    expect(worktree?.sessions).toHaveLength(2);
    expect(worktree?.liveCount).toBe(1);
    expect(worktree?.sessions[0]?.sessionId).toBe('s2');
  });

  it('groups a session by its latest cwd, not the project directory it is filed under', () => {
    const groups = groupByWorktree([session('s1', '/repo/.claude/worktrees/dylan/PLAT-3138')], []);
    expect(groups[0]?.key).toBe('/repo/.claude/worktrees/dylan/PLAT-3138');
  });
});

describe('GitFacts', () => {
  function counting(): GitProbe & { calls: number } {
    const probe = {
      calls: 0,
      async isInsideWorkTree(): Promise<boolean> {
        probe.calls += 1;
        return true;
      },
      async worktreeRoots(): Promise<string[]> {
        probe.calls += 1;
        return ['/repo'];
      },
      async branchNames(): Promise<Set<string>> {
        probe.calls += 1;
        return new Set(['main']);
      },
    };
    return probe;
  }

  it('asks git once per path and serves the poll from memory', async () => {
    const probe = counting();
    let clock = 0;
    const facts = new GitFacts(probe, 15_000, () => clock);

    for (let tick = 0; tick < 8; tick += 1) {
      await facts.isInsideWorkTree('/repo');
      await facts.branchNames('/repo');
      clock += 2_000;
    }

    expect(probe.calls).toBe(2);
  });

  it('asks again once the answer has gone stale', async () => {
    const probe = counting();
    let clock = 0;
    const facts = new GitFacts(probe, 15_000, () => clock);

    await facts.worktreeRoots('/repo');
    clock = 14_999;
    await facts.worktreeRoots('/repo');
    expect(probe.calls).toBe(1);

    clock = 15_000;
    await facts.worktreeRoots('/repo');
    expect(probe.calls).toBe(2);
  });

  it('holds on to whether a path is a repo far longer than its branches', async () => {
    const probe = counting();
    let clock = 0;
    const facts = new GitFacts(probe, 15_000, () => clock, 300_000);

    await facts.isInsideWorkTree('/repo');
    await facts.branchNames('/repo');
    expect(probe.calls).toBe(2);

    clock = 20_000;
    await facts.isInsideWorkTree('/repo');
    await facts.branchNames('/repo');
    expect(probe.calls).toBe(3);

    clock = 300_000;
    await facts.isInsideWorkTree('/repo');
    expect(probe.calls).toBe(4);
  });

  it('keeps separate answers for separate repos, and forgets them on demand', async () => {
    const probe = counting();
    const facts = new GitFacts(probe, 15_000, () => 0);

    await facts.isInsideWorkTree('/one');
    await facts.isInsideWorkTree('/two');
    expect(probe.calls).toBe(2);

    facts.invalidate();
    await facts.isInsideWorkTree('/one');
    expect(probe.calls).toBe(3);
  });
});
