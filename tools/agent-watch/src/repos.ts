import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import type { LoadedSession } from './loader';

const run = promisify(execFile);

const WORKTREE_PATTERN = /^(.*\/\.claude\/worktrees\/[^/]+\/[^/]+)(?:\/|$)/;

export interface WorktreeGroup {
  key: string;
  label: string;
  sessions: LoadedSession[];
  liveCount: number;
}

export function worktreeRootFor(cwd: string | undefined, knownRoots: string[]): string | undefined {
  if (!cwd) return undefined;
  let best: string | undefined;
  for (const root of knownRoots) {
    if (cwd === root || cwd.startsWith(`${root}/`)) {
      if (!best || root.length > best.length) best = root;
    }
  }
  if (best) return best;
  const matched = WORKTREE_PATTERN.exec(cwd);
  return matched?.[1];
}

export function labelForWorktree(root: string | undefined): string {
  if (!root) return 'main';
  const parts = root.split('/').filter((part) => part.length > 0);
  return parts[parts.length - 1] ?? 'main';
}

export function groupByWorktree(sessions: LoadedSession[], knownRoots: string[]): WorktreeGroup[] {
  const groups = new Map<string, WorktreeGroup>();
  for (const session of sessions) {
    const root = worktreeRootFor(session.cwd, knownRoots);
    const key = root ?? 'main';
    const label = session.branch && root ? session.branch : labelForWorktree(root);
    let group = groups.get(key);
    if (!group) {
      group = { key, label, sessions: [], liveCount: 0 };
      groups.set(key, group);
    }
    group.sessions.push(session);
    if (session.tree.status === 'live') group.liveCount += 1;
  }

  const ordered = [...groups.values()];
  for (const group of ordered) {
    group.sessions.sort((left, right) => right.mtimeMs - left.mtimeMs);
  }
  ordered.sort((left, right) => {
    if (left.key === 'main') return -1;
    if (right.key === 'main') return 1;
    const leftNewest = left.sessions[0]?.mtimeMs ?? 0;
    const rightNewest = right.sessions[0]?.mtimeMs ?? 0;
    return rightNewest - leftNewest;
  });
  return ordered;
}

async function git(cwd: string, args: string[]): Promise<string | undefined> {
  try {
    const { stdout } = await run('git', args, { cwd, timeout: 5000 });
    return stdout.trim();
  } catch {
    return undefined;
  }
}

export async function repoRootFor(dir: string): Promise<string | undefined> {
  const commonDir = await git(dir, ['rev-parse', '--path-format=absolute', '--git-common-dir']);
  if (!commonDir) return undefined;
  return commonDir.replace(/\/\.git\/?$/, '').replace(/\/\.git$/, '');
}

export async function worktreeRoots(repoRoot: string): Promise<string[]> {
  const output = await git(repoRoot, ['worktree', 'list', '--porcelain']);
  if (!output) return [];
  const roots: string[] = [];
  for (const line of output.split('\n')) {
    if (line.startsWith('worktree ')) roots.push(line.slice('worktree '.length).trim());
  }
  return roots;
}
