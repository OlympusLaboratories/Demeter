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
  const matched = WORKTREE_PATTERN.exec(cwd);
  if (matched?.[1]) return matched[1];
  let best: string | undefined;
  for (const root of knownRoots) {
    if (cwd === root || cwd.startsWith(`${root}/`)) {
      if (!best || root.length > best.length) best = root;
    }
  }
  return best;
}

export function labelForWorktree(root: string | undefined): string {
  if (!root) return 'main';
  const parts = root.split('/').filter((part) => part.length > 0);
  return parts[parts.length - 1] ?? 'main';
}

export interface RepoState {
  knownRoots: string[];
  branches: ReadonlySet<string>;
}

export type RemovalReason = 'worktree' | 'branch';

export function removalReasonFor(
  session: Pick<LoadedSession, 'cwd' | 'branch'>,
  state: RepoState,
): RemovalReason | undefined {
  if (state.knownRoots.length > 0) {
    const root = worktreeRootFor(session.cwd, state.knownRoots);
    if (root && !state.knownRoots.includes(root)) return 'worktree';
  }
  if (state.branches.size > 0 && session.branch && !state.branches.has(session.branch)) {
    return 'branch';
  }
  return undefined;
}

export function partitionSessions(
  sessions: LoadedSession[],
  state: RepoState,
): { live: LoadedSession[]; removed: LoadedSession[] } {
  const live: LoadedSession[] = [];
  const removed: LoadedSession[] = [];
  for (const session of sessions) {
    if (removalReasonFor(session, state)) removed.push(session);
    else live.push(session);
  }
  return { live, removed };
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
    if (session.tree.status === 'live' || session.tree.status === 'running') group.liveCount += 1;
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

export async function isInsideWorkTree(dir: string): Promise<boolean> {
  return (await git(dir, ['rev-parse', '--is-inside-work-tree'])) === 'true';
}

export async function branchNames(repoRoot: string): Promise<Set<string>> {
  const output = await git(repoRoot, ['branch', '--format=%(refname:short)']);
  if (!output) return new Set();
  return new Set(output.split('\n').map((line) => line.trim()).filter((line) => line.length > 0));
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

export interface GitProbe {
  isInsideWorkTree(dir: string): Promise<boolean>;
  worktreeRoots(repoRoot: string): Promise<string[]>;
  branchNames(repoRoot: string): Promise<Set<string>>;
}

export const liveGit: GitProbe = { isInsideWorkTree, worktreeRoots, branchNames };

export const GIT_FACT_TTL_MS = 15_000;
export const REPO_SHAPE_TTL_MS = 300_000;

interface Cached<T> {
  value: T;
  atMs: number;
}

export class GitFacts {
  private readonly entries = new Map<string, Cached<unknown>>();

  constructor(
    private readonly probe: GitProbe = liveGit,
    private readonly ttlMs: number = GIT_FACT_TTL_MS,
    private readonly now: () => number = Date.now,
    private readonly shapeTtlMs: number = REPO_SHAPE_TTL_MS,
  ) {}

  invalidate(): void {
    this.entries.clear();
  }

  isInsideWorkTree(dir: string): Promise<boolean> {
    return this.remember(`work:${dir}`, () => this.probe.isInsideWorkTree(dir), this.shapeTtlMs);
  }

  worktreeRoots(repoRoot: string): Promise<string[]> {
    return this.remember(`roots:${repoRoot}`, () => this.probe.worktreeRoots(repoRoot));
  }

  branchNames(repoRoot: string): Promise<Set<string>> {
    return this.remember(`branches:${repoRoot}`, () => this.probe.branchNames(repoRoot));
  }

  private async remember<T>(key: string, compute: () => Promise<T>, ttlMs = this.ttlMs): Promise<T> {
    const atMs = this.now();
    const hit = this.entries.get(key);
    if (hit && atMs - hit.atMs < ttlMs) return hit.value as T;
    const value = await compute();
    this.entries.set(key, { value, atMs });
    return value;
  }
}
