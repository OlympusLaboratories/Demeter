import type { AgentNode } from './model';
import { type ProjectDir, scanProjects, withinDays } from './discovery';
import { type LoadedSession, loadSession, peekProjectPath } from './loader';
import { type WorktreeGroup, GitFacts, groupByWorktree, partitionSessions, repoRootFor } from './repos';
import { DEFAULT_AUTO_COLLAPSE, layoutForest } from './graphLayout';
import { TranscriptCache } from './tail';
import type { NodeDetail, RepoSummary, ViewState, WorktreeSummary } from './protocol';
import { FirstChildrenWatch } from './firstChildren';
import { isInAnyFolder } from './workspacePaths';

export interface StoreSettings {
  projectsDir: string;
  liveWindowSeconds: number;
  recentDays: number;
  maxSessionsPerRepo: number;
  pollSeconds: number;
  statusBarPriority: number;
  initialDepth: number;
  zoomSensitivity: number;
  hideDeletedWork: boolean;
  workspaceFolders: string[];
}

interface RepoEntry {
  project: ProjectDir;
  label: string;
  path?: string;
}

export class Store {
  private repos: RepoEntry[] = [];
  private groups: WorktreeGroup[] = [];
  private nodesById: Map<string, AgentNode> = new Map();
  private selectedRepo?: string;
  private selectedWorktree?: string;
  private readonly cache = new TranscriptCache();
  private targets: string[] = [];
  private overrides = new Map<string, boolean>();
  private renderedExpansion = new Map<string, boolean>();
  private removedCount = 0;
  private readonly git = new GitFacts();
  private readonly firstChildren = new FirstChildrenWatch();
  private workspaceSlug?: string;
  private workspaceFor?: string;
  private emptyRepos = new Set<string>();
  private onlyThisWindow = false;

  constructor(private settings: StoreSettings) {}

  updateSettings(settings: StoreSettings): void {
    this.settings = settings;
  }

  invalidateGit(): void {
    this.git.invalidate();
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
      if (this.settings.hideDeletedWork && !(resolved && (await this.git.isInsideWorkTree(resolved)))) continue;
      if (this.hidingOtherWindows() && !isInAnyFolder(this.settings.workspaceFolders, resolved)) continue;
      this.repos.push({ project, label: labelFor(resolved, project.slug), path: resolved });
    }

    if (preferredPath !== undefined && this.workspaceFor !== preferredPath) {
      this.workspaceFor = preferredPath;
      this.workspaceSlug = await this.matchRepo(preferredPath);
    } else if (this.workspaceSlug && !this.repos.some((repo) => repo.project.slug === this.workspaceSlug)) {
      this.workspaceSlug = await this.matchRepo(this.workspaceFor);
    }

    if (!this.selectedRepo || !this.repos.some((repo) => repo.project.slug === this.selectedRepo)) {
      this.selectedRepo = this.workspaceSlug ?? this.repos[0]?.project.slug;
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

  async loadSelected(attempt = 0): Promise<void> {
    const repo = this.repos.find((entry) => entry.project.slug === this.selectedRepo);
    if (!repo) {
      this.groups = [];
      this.nodesById.clear();
      this.removedCount = 0;
      return;
    }

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

    const roots = repo.path ? await this.git.worktreeRoots(repo.path) : [];
    const branches =
      repo.path && this.settings.hideDeletedWork ? await this.git.branchNames(repo.path) : new Set<string>();
    const { live: kept, removed } = this.settings.hideDeletedWork
      ? partitionSessions(sessions, { knownRoots: roots, branches })
      : { live: sessions, removed: [] };
    const live = this.hidingOtherWindows()
      ? kept.filter((entry) => isInAnyFolder(this.settings.workspaceFolders, entry.cwd))
      : kept;
    const groups = groupByWorktree(live, roots);
    const nodesById = new Map<string, AgentNode>();
    for (const group of groups) {
      for (const session of group.sessions) index(session.tree, nodesById);
    }

    if (groups.length > 0) this.emptyRepos.delete(repo.project.slug);
    else {
      this.emptyRepos.add(repo.project.slug);
      const next = this.repos.find(
        (entry) => entry.project.slug !== repo.project.slug && !this.emptyRepos.has(entry.project.slug),
      );
      if (next && attempt < this.repos.length) {
        this.selectedRepo = next.project.slug;
        this.selectedWorktree = undefined;
        this.overrides.clear();
        this.firstChildren.clear();
        await this.loadSelected(attempt + 1);
        return;
      }
    }

    this.removedCount = removed.length;
    this.groups = groups;
    this.nodesById = nodesById;
    this.targets = [repo.project.dir, ...live.flatMap((entry) => entry.watchPaths)];

    if (!this.selectedWorktree || !this.groups.some((group) => group.key === this.selectedWorktree)) {
      this.selectedWorktree = this.groups[0]?.key;
    }

    const onScreen = new Map<string, AgentNode>();
    const shown = this.groups.find((group) => group.key === this.selectedWorktree);
    for (const session of shown?.sessions ?? []) index(session.tree, onScreen);

    const arrivals = this.firstChildren.claim(
      [...onScreen.values()].map((node) => ({ id: node.id, childCount: node.children.length })),
    );
    for (const id of arrivals) {
      const node = onScreen.get(id);
      if (!node || node.children.length > DEFAULT_AUTO_COLLAPSE) continue;
      if (!this.overrides.has(id)) this.overrides.set(id, true);
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
    this.emptyRepos.delete(slug);
    this.selectedRepo = slug;
    this.selectedWorktree = undefined;
    this.overrides.clear();
    this.firstChildren.clear();
    this.cache.clear();
  }

  selectWorktree(key: string): void {
    this.selectedWorktree = key;
  }

  private hidingOtherWindows(): boolean {
    return this.onlyThisWindow && this.settings.workspaceFolders.length > 0;
  }

  setOnlyThisWindow(value: boolean): void {
    if (this.onlyThisWindow === value) return;
    this.onlyThisWindow = value;
    this.emptyRepos.clear();
    this.selectedWorktree = undefined;
  }

  toggleAll(): void {
    const expandable = [...this.nodesById.values()].filter((node) => node.children.length > 0);
    const allOpen = expandable.every((node) => this.renderedExpansion.get(node.id) === true);
    for (const node of expandable) this.overrides.set(node.id, !allOpen);
  }

  toggleNode(id: string): boolean {
    const node = this.nodesById.get(id);
    if (!node || node.children.length === 0) return false;
    const current = this.renderedExpansion.get(id) ?? false;
    this.overrides.set(id, !current);
    return !current;
  }

  scopeKey(): string {
    return `${this.selectedRepo ?? ''}::${this.selectedWorktree ?? ''}`;
  }

  sessionTarget(id: string): { sessionId: string; cwd?: string } | undefined {
    const node = this.nodesById.get(id);
    if (!node || node.kind !== 'session') return undefined;
    return { sessionId: node.id.slice('session:'.length), cwd: node.cwd };
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
    };
  }

  view(loading: boolean, message?: string): ViewState {
    const liveCutoff = Date.now() - this.settings.liveWindowSeconds * 1000;
    const repos: RepoSummary[] = this.repos
      .map((entry) => ({
        slug: entry.project.slug,
        label: entry.label,
        isWorkspace: entry.project.slug === this.workspaceSlug,
        liveCount:
          entry.project.slug === this.selectedRepo
            ? this.groups.reduce((total, group) => total + group.liveCount, 0)
            : entry.project.sessions.filter((session) => session.activityMs >= liveCutoff).length,
        sessionCount: entry.project.sessions.length,
        newestMtimeMs: entry.project.newestMtimeMs,
      }))
      .filter((entry) => entry.slug === this.selectedRepo || !this.emptyRepos.has(entry.slug))
      .sort((left, right) => {
        if (left.isWorkspace !== right.isWorkspace) return left.isWorkspace ? -1 : 1;
        return right.newestMtimeMs - left.newestMtimeMs;
      });

    const worktrees: WorktreeSummary[] = this.groups.map((group) => ({
      key: group.key,
      label: group.label,
      liveCount: group.liveCount,
      sessionCount: group.sessions.length,
    }));

    const active = this.groups.find((group) => group.key === this.selectedWorktree);
    const graph = layoutForest((active?.sessions ?? []).map((session) => session.tree), {
      overrides: this.overrides,
      initialDepth: this.settings.initialDepth,
    });
    this.renderedExpansion = new Map(graph.nodes.map((node) => [node.id, node.expanded]));

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
      onlyThisWindow: this.onlyThisWindow,
      scopeKey: this.scopeKey(),
      zoomSensitivity: this.settings.zoomSensitivity,
      removedCount: this.removedCount,
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
