import { RESULT_LIMIT, clip, resultToText, summarizeToolUse } from './summarize';
import {
  type ContentBlock,
  type SubagentMeta,
  type TranscriptLine,
  blocksOf,
  isAgentSpawn,
  latestBranch,
  latestCwd,
} from './transcript';

export type NodeStatus = 'live' | 'running' | 'done' | 'error' | 'idle';
export type NodeKind = 'session' | 'agent' | 'workflow';

export interface AgentEvent {
  kind: 'text' | 'thinking' | 'tool';
  name?: string;
  summary?: string;
  detail?: string;
  result?: string;
  resultTruncated?: boolean;
  isError?: boolean;
  text?: string;
  thinkingChars?: number;
  timestamp?: string;
}

export interface AgentNode {
  id: string;
  kind: NodeKind;
  label: string;
  sublabel?: string;
  status: NodeStatus;
  events: AgentEvent[];
  children: AgentNode[];
  toolUseId?: string;
  spawnDepth?: number;
  cwd?: string;
  branch?: string;
}

export interface SubagentInput {
  agentId: string;
  meta: SubagentMeta;
  lines: TranscriptLine[];
}

export interface JournalEntry {
  type?: string;
  agentId?: string;
}

export interface WorkflowInput {
  runId: string;
  journal: JournalEntry[];
  agents: SubagentInput[];
}

export interface SessionInput {
  sessionId: string;
  lines: TranscriptLine[];
  mtimeMs: number;
  subagents: SubagentInput[];
  workflows: WorkflowInput[];
  liveWindowSeconds: number;
  nowMs: number;
}

export function buildEvents(lines: TranscriptLine[]): AgentEvent[] {
  const events: AgentEvent[] = [];
  const byToolUseId = new Map<string, AgentEvent>();

  for (const line of lines) {
    for (const block of blocksOf(line)) {
      if (block.type === 'text' && block.text) {
        events.push({ kind: 'text', text: clip(block.text, 400), timestamp: line.timestamp });
      } else if (block.type === 'thinking') {
        const thinking = block.thinking ?? '';
        events.push({
          kind: 'thinking',
          text: thinking.length > 0 ? clip(thinking, 4000) : undefined,
          thinkingChars: thinking.length,
          timestamp: line.timestamp,
        });
      } else if (block.type === 'tool_use') {
        const event: AgentEvent = {
          kind: 'tool',
          name: block.name ?? 'tool',
          summary: summarizeToolUse(block.name ?? '', block.input),
          detail: safeJson(block.input),
          timestamp: line.timestamp,
        };
        events.push(event);
        if (block.id) byToolUseId.set(block.id, event);
      } else if (block.type === 'tool_result' && block.tool_use_id) {
        const target = byToolUseId.get(block.tool_use_id);
        if (!target) continue;
        const full = resultToText(block.content);
        target.result = full.slice(0, RESULT_LIMIT);
        target.resultTruncated = full.length > RESULT_LIMIT;
        target.isError = block.is_error === true;
      }
    }
  }

  return events;
}

function safeJson(input: unknown): string | undefined {
  if (input === undefined) return undefined;
  try {
    return JSON.stringify(input, null, 2);
  } catch {
    return undefined;
  }
}

export function completedToolUseIds(lines: TranscriptLine[]): Set<string> {
  const done = new Set<string>();
  for (const line of lines) {
    for (const block of blocksOf(line)) {
      if (block.type === 'tool_result' && block.tool_use_id) done.add(block.tool_use_id);
    }
  }
  return done;
}

export function spawnDescriptions(lines: TranscriptLine[]): Map<string, string> {
  const labels = new Map<string, string>();
  for (const line of lines) {
    for (const block of blocksOf(line)) {
      if (!isAgentSpawn(block) || !block.id) continue;
      const description = block.input?.['description'];
      if (typeof description === 'string') labels.set(block.id, description);
    }
  }
  return labels;
}

const COMPUTED_TASK_MARKER = 'computed task]';
const HARNESS_PREFIX = '[Workflow harness';

function userText(line: TranscriptLine): string | undefined {
  const content = line.message?.content;
  return typeof content === 'string' ? content : blockText(content);
}

function firstMeaningfulLine(text: string): string | undefined {
  return text.split('\n').find((entry) => entry.trim().length > 0)?.trim();
}

function tighten(label: string): string {
  return label.replace(/^You are\s+/i, '').replace(/^(an?|the)\s+/i, '');
}

export function deriveLabel(lines: TranscriptLine[]): string | undefined {
  let fallback: string | undefined;
  for (const line of lines) {
    if (line.type !== 'user') continue;
    const raw = userText(line);
    if (!raw) continue;

    const marker = raw.indexOf(COMPUTED_TASK_MARKER);
    if (marker >= 0) {
      const after = raw.slice(marker + COMPUTED_TASK_MARKER.length).split('\n').slice(1);
      const task = after.find((entry) => /^\s+\S/.test(entry));
      if (task) return tighten(task.trim());
    }

    if (!fallback && !raw.trimStart().startsWith(HARNESS_PREFIX)) {
      const candidate = firstMeaningfulLine(raw);
      if (candidate && !candidate.startsWith('<command-')) fallback = tighten(candidate);
    }
  }
  return fallback;
}

export function erroredToolUseIds(lines: TranscriptLine[]): Set<string> {
  const errored = new Set<string>();
  for (const line of lines) {
    for (const block of blocksOf(line)) {
      if (block.type === 'tool_result' && block.tool_use_id && block.is_error === true) {
        errored.add(block.tool_use_id);
      }
    }
  }
  return errored;
}

function blockText(content: ContentBlock[] | undefined): string | undefined {
  if (!Array.isArray(content)) return undefined;
  for (const block of content) {
    if (typeof block.text === 'string' && block.text.length > 0) return block.text;
  }
  return undefined;
}

function subagentNode(input: SubagentInput, running: boolean, errored = false): AgentNode {
  const events = buildEvents(input.lines);
  const label = input.meta.description ?? deriveLabel(input.lines) ?? input.agentId.slice(0, 8);
  return {
    id: `agent:${input.agentId}`,
    kind: 'agent',
    label: clip(label, 48),
    sublabel: input.meta.agentType,
    status: running ? 'running' : errored ? 'error' : 'done',
    events,
    children: [],
    toolUseId: input.meta.toolUseId,
    spawnDepth: input.meta.spawnDepth,
  };
}

export function spawnIdsIn(lines: TranscriptLine[]): Set<string> {
  const ids = new Set<string>();
  for (const line of lines) {
    for (const block of blocksOf(line)) {
      if (isAgentSpawn(block) && block.id) ids.add(block.id);
    }
  }
  return ids;
}

interface Owner {
  node: AgentNode;
  spawned: Set<string>;
  completed: Set<string>;
  errored: Set<string>;
}

export function buildSessionTree(input: SessionInput): AgentNode {
  const events = buildEvents(input.lines);
  const ageSeconds = (input.nowMs - input.mtimeMs) / 1000;
  const branch = latestBranch(input.lines);
  const root: AgentNode = {
    id: `session:${input.sessionId}`,
    kind: 'session',
    label: input.sessionId.slice(0, 8),
    sublabel: branch,
    status: ageSeconds <= input.liveWindowSeconds ? 'live' : 'done',
    events,
    children: [],
    cwd: latestCwd(input.lines),
    branch,
  };

  const owners: Owner[] = [
    {
      node: root,
      spawned: spawnIdsIn(input.lines),
      completed: completedToolUseIds(input.lines),
      errored: erroredToolUseIds(input.lines),
    },
  ];

  const ordered = [...input.subagents].sort(
    (left, right) => (left.meta.spawnDepth ?? 1) - (right.meta.spawnDepth ?? 1),
  );

  for (const candidate of ordered) {
    const toolUseId = candidate.meta.toolUseId;
    const owner = owners.find((entry) => toolUseId !== undefined && entry.spawned.has(toolUseId)) ?? owners[0];
    if (!owner) continue;
    const running = toolUseId !== undefined && !owner.completed.has(toolUseId);
    const errored = toolUseId !== undefined && owner.errored.has(toolUseId);
    const node = subagentNode(candidate, running, errored);
    owner.node.children.push(node);
    owners.push({
      node,
      spawned: spawnIdsIn(candidate.lines),
      completed: completedToolUseIds(candidate.lines),
      errored: erroredToolUseIds(candidate.lines),
    });
  }

  for (const workflow of input.workflows) {
    const started = new Set<string>();
    const finished = new Set<string>();
    for (const entry of workflow.journal) {
      if (!entry.agentId) continue;
      if (entry.type === 'started') started.add(entry.agentId);
      if (entry.type === 'result') finished.add(entry.agentId);
    }
    const children = workflow.agents.map((agent) =>
      subagentNode(agent, started.has(agent.agentId) && !finished.has(agent.agentId)),
    );
    const running = children.filter((child) => child.status === 'running').length;
    const total = Math.max(started.size, workflow.agents.length);
    root.children.push({
      id: `workflow:${workflow.runId}`,
      kind: 'workflow',
      label: workflow.runId,
      sublabel: `${finished.size}/${total} done`,
      status: running > 0 ? 'running' : 'done',
      events: [],
      children,
    });
  }

  return root;
}
