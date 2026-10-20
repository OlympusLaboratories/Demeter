import type { AgentNode } from './model';
import { type ProjectDir, scanProjects, withinDays } from './discovery';
import { type LoadedSession, loadSession, peekProjectPath } from './loader';
import { type WorktreeGroup, groupByWorktree, repoRootFor, worktreeRoots } from './repos';
import { layoutForest, parentOfGroupId } from './graphLayout';
import { TranscriptCache } from './tail';
import type { NodeDetail, RepoSummary, ViewState, WorktreeSummary } from './protocol';

export interface StoreSettings {
  projectsDir: string;
  liveWindowSeconds: number;
  recentDays: number;
  maxSessionsPerRepo: number;
  pollSeconds: number;
}

interface RepoEntry {
  project: ProjectDir;
  label: string;
  path?: string;
}

export class Store {
  private repos: RepoEntry[] = [];
  private groups: WorktreeGroup[] = [];
  private nodesById = new Map<string, AgentNode>();
  private transcriptByNodeId = new Map<string, string>();
  private selectedRepo?: string;
  private selectedWorktree?: string;
  private readonly cache = new TranscriptCache();
  private targets: string[] = [];
  private expanded = new Set<string>();

  constructor(private settings: StoreSettings) {}

  updateSettings(settings: StoreSettings): void {
    this.settings = settings;
  }

  async discover(preferredPath?: string): Promise<void> {
    const projects = await scanProjects(this.settings.projectsDir);
    const nowMs = Date.now();
    const recent = projects.filter((project) =>
      withinDays(project.newestMtimeMs, this.settings.recentDays, nowMs),
    );
    const chosen = recent.length > 0 ? recent : projects.slice(0, 1);

    this.repos = [];
    for (const project of chosen) {
      const resolved = await peekProjectPath(project);
      this.repos.push({ project, label: labelFor(resolved, project.slug), path: resolved });
    }

    if (!this.selectedRepo || !this.repos.some((repo) => repo.project.slug === this.selectedRepo)) {
      this.selectedRepo = (await this.matchRepo(preferredPath)) ?? this.repos[0]?.project.slug;
    }
  }

  private async matchRepo(preferredPath?: string): Promise<string | undefined> {
    if (!preferredPath) return undefined;
    const root = (await repoRootFor(preferredPath)) ?? preferredPath;
    let best: RepoEntry | undefined;
    for (const repo of this.repos) {
      if (!repo.path) continue;
      if (repo.path === root || repo.path.startsWith(`${root}/`) || root.startsWith(`${repo.path}/`)) {
        if (!best || (repo.path.length > (best.path?.length ?? 0))) best = repo;
      }
    }
    return best?.project.slug;
  }

  async loadSelected(): Promise<void> {
    this.groups = [];
    this.nodesById.clear();
    this.transcriptByNodeId.clear();
    const repo = this.repos.find((entry) => entry.project.slug === this.selectedRepo);
    if (!repo) return;

    const nowMs = Date.now();
    const sessions: LoadedSession[] = [];
    const candidates = repo.project.sessions
      .filter((session) => withinDays(session.mtimeMs, this.settings.recentDays, nowMs))
      .slice(0, this.settings.maxSessionsPerRepo);

    for (const session of candidates) {
      sessions.push(
        await loadSession(session, {
          liveWindowSeconds: this.settings.liveWindowSeconds,
          nowMs,
          cache: this.cache,
        }),
      );
    }

    const roots = repo.path ? await worktreeRoots(repo.path) : [];
    this.groups = groupByWorktree(sessions, roots);
    this.targets = [repo.project.dir, ...sessions.flatMap((entry) => entry.watchPaths)];
    for (const group of this.groups) {
      for (const session of group.sessions) {
        index(session.tree, this.nodesById);
        this.transcriptByNodeId.set(session.tree.id, session.transcriptPath);
      }
    }
    for (const session of sessions) {
      for (const [nodeId, transcript] of session.transcriptsByNodeId) {
        this.transcriptByNodeId.set(nodeId, transcript);
      }
    }

    if (!this.selectedWorktree || !this.groups.some((group) => group.key === this.selectedWorktree)) {
      this.selectedWorktree = this.groups[0]?.key;
    }
  }

  watchTargets(): string[] {
    return this.targets;
  }

  pollMs(): number {
    return Math.max(1, this.settings.pollSeconds) * 1000;
  }

  selectRepo(slug: string): void {
    if (this.selectedRepo === slug) return;
    this.selectedRepo = slug;
    this.selectedWorktree = undefined;
    this.expanded.clear();
    this.cache.clear();
  }

  selectWorktree(key: string): void {
    this.selectedWorktree = key;
  }

  toggleGroup(groupId: string): boolean {
    const parentId = parentOfGroupId(groupId) ?? groupId;
    if (this.expanded.has(parentId)) this.expanded.delete(parentId);
    else this.expanded.add(parentId);
    return this.expanded.has(parentId);
  }

  transcriptFor(id: string): string | undefined {
    return this.transcriptByNodeId.get(id);
  }

  detail(id: string): NodeDetail | undefined {
    const node = this.nodesById.get(id);
    if (!node) return undefined;
    return {
      id: node.id,
      kind: node.kind,
      status: node.status,
      label: node.label,
      sublabel: node.sublabel,
      events: node.events,
      hasTranscript: this.transcriptByNodeId.has(node.id),
    };
  }

  view(loading: boolean, message?: string): ViewState {
    const liveCutoff = Date.now() - this.settings.liveWindowSeconds * 1000;
    const repos: RepoSummary[] = this.repos.map((entry) => ({
      slug: entry.project.slug,
      label: entry.label,
      liveCount: entry.project.sessions.filter((session) => session.mtimeMs >= liveCutoff).length,
      sessionCount: entry.project.sessions.length,
      newestMtimeMs: entry.project.newestMtimeMs,
    }));

    const worktrees: WorktreeSummary[] = this.groups.map((group) => ({
      key: group.key,
      label: group.label,
      liveCount: group.liveCount,
      sessionCount: group.sessions.length,
    }));

    const active = this.groups.find((group) => group.key === this.selectedWorktree);
    const graph = layoutForest((active?.sessions ?? []).map((session) => session.tree), {
      expanded: this.expanded,
    });

    return {
      loading,
      repos,
      selectedRepo: this.selectedRepo,
      worktrees,
      selectedWorktree: this.selectedWorktree,
      graph,
      message,
      watchedCount: this.targets.length,
      updatedAtMs: Date.now(),
      recentDays: this.settings.recentDays,
    };
  }
}

function labelFor(resolvedPath: string | undefined, slug: string): string {
  if (resolvedPath) {
    const parts = resolvedPath.split('/').filter((part) => part.length > 0);
    return parts[parts.length - 1] ?? slug;
  }
  return slug.replace(/^-/, '').split('-').pop() ?? slug;
}

function index(node: AgentNode, into: Map<string, AgentNode>): void {
  into.set(node.id, node);
  for (const child of node.children) index(child, into);
}
