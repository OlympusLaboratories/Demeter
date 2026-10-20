import type { GraphLayout } from './graphLayout';
import type { AgentEvent, NodeKind, NodeStatus } from './model';

export interface RepoSummary {
  slug: string;
  label: string;
  isWorkspace: boolean;
  liveCount: number;
  sessionCount: number;
  newestMtimeMs: number;
}

export interface WorktreeSummary {
  key: string;
  label: string;
  liveCount: number;
  sessionCount: number;
}

export interface NodeDetail {
  id: string;
  kind: NodeKind;
  status: NodeStatus;
  label: string;
  sublabel?: string;
  events: AgentEvent[];
}

export interface ViewState {
  loading: boolean;
  repos: RepoSummary[];
  selectedRepo?: string;
  worktrees: WorktreeSummary[];
  selectedWorktree?: string;
  graph: GraphLayout;
  message?: string;
  watchedCount: number;
  updatedAtMs: number;
  recentDays: number;
  scopeKey: string;
  zoomSensitivity: number;
  removedCount: number;
}

export type HostMessage =
  | { type: 'state'; state: ViewState }
  | { type: 'detail'; detail: NodeDetail; refreshed: boolean }
  | { type: 'detailClosed' };

export type ViewMessage =
  | { type: 'ready' }
  | { type: 'refresh' }
  | { type: 'selectRepo'; slug: string }
  | { type: 'selectWorktree'; key: string }
  | { type: 'selectNode'; id: string }
  | { type: 'toggleNode'; id: string }
  | { type: 'openSession'; id: string }
  | { type: 'closeDetail' };
