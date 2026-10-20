import { describe, expect, it } from 'vitest';
import { groupByWorktree, labelForWorktree, worktreeRootFor } from './repos';
import type { LoadedSession } from './loader';
import type { AgentNode, NodeStatus } from './model';

function session(id: string, cwd: string, status: NodeStatus = 'done', mtimeMs = 0): LoadedSession {
  const tree: AgentNode = { id, kind: 'session', label: id, status, events: [], children: [] };
  return { sessionId: id, transcriptPath: `/t/${id}.jsonl`, mtimeMs, cwd, tree };
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
