import type { Dirent } from 'node:fs';
import * as fs from 'node:fs/promises';
import * as path from 'node:path';
import type { ProjectDir, SessionFile } from './discovery';
import {
  type AgentNode,
  type JournalEntry,
  type SubagentInput,
  type WorkflowInput,
  buildSessionTree,
} from './model';
import { type SubagentMeta, firstCwd, latestBranch, latestCwd, parseJsonl } from './transcript';

const PEEK_BYTES = 65_536;

export interface LoadOptions {
  liveWindowSeconds: number;
  nowMs: number;
}

export interface LoadedSession {
  sessionId: string;
  transcriptPath: string;
  mtimeMs: number;
  cwd?: string;
  branch?: string;
  tree: AgentNode;
}

async function readText(filePath: string): Promise<string> {
  try {
    return await fs.readFile(filePath, 'utf8');
  } catch {
    return '';
  }
}

async function readJson<T>(filePath: string): Promise<T | undefined> {
  const text = await readText(filePath);
  if (!text) return undefined;
  try {
    return JSON.parse(text) as T;
  } catch {
    return undefined;
  }
}

export async function peekProjectPath(project: ProjectDir): Promise<string | undefined> {
  for (const session of project.sessions.slice(0, 3)) {
    let handle;
    try {
      handle = await fs.open(session.transcriptPath, 'r');
      const buffer = Buffer.alloc(PEEK_BYTES);
      const { bytesRead } = await handle.read(buffer, 0, PEEK_BYTES, 0);
      const lines = parseJsonl(buffer.subarray(0, bytesRead).toString('utf8'));
      const cwd = firstCwd(lines);
      if (cwd) return cwd;
    } catch {
      continue;
    } finally {
      await handle?.close().catch(() => undefined);
    }
  }
  return undefined;
}

async function loadSubagentDir(dir: string): Promise<SubagentInput[]> {
  let entries: Dirent[];
  try {
    entries = await fs.readdir(dir, { withFileTypes: true });
  } catch {
    return [];
  }

  const agents: SubagentInput[] = [];
  for (const entry of entries) {
    if (!entry.isFile() || !entry.name.startsWith('agent-') || !entry.name.endsWith('.jsonl')) continue;
    const agentId = entry.name.slice('agent-'.length, -'.jsonl'.length);
    const meta = (await readJson<SubagentMeta>(path.join(dir, `agent-${agentId}.meta.json`))) ?? {};
    const lines = parseJsonl(await readText(path.join(dir, entry.name)));
    agents.push({ agentId, meta, lines });
  }
  return agents;
}

async function loadWorkflows(subagentsDir: string): Promise<WorkflowInput[]> {
  const workflowsDir = path.join(subagentsDir, 'workflows');
  let entries: Dirent[];
  try {
    entries = await fs.readdir(workflowsDir, { withFileTypes: true });
  } catch {
    return [];
  }

  const workflows: WorkflowInput[] = [];
  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    const runDir = path.join(workflowsDir, entry.name);
    const journal = parseJsonl(await readText(path.join(runDir, 'journal.jsonl'))) as JournalEntry[];
    const agents = await loadSubagentDir(runDir);
    if (journal.length === 0 && agents.length === 0) continue;
    workflows.push({ runId: entry.name, journal, agents });
  }
  return workflows;
}

export async function loadSession(session: SessionFile, options: LoadOptions): Promise<LoadedSession> {
  const lines = parseJsonl(await readText(session.transcriptPath));
  const subagentsDir = path.join(
    path.dirname(session.transcriptPath),
    session.sessionId,
    'subagents',
  );
  const subagents = await loadSubagentDir(subagentsDir);
  const workflows = await loadWorkflows(subagentsDir);

  const tree = buildSessionTree({
    sessionId: session.sessionId,
    lines,
    mtimeMs: session.mtimeMs,
    subagents,
    workflows,
    liveWindowSeconds: options.liveWindowSeconds,
    nowMs: options.nowMs,
  });

  return {
    sessionId: session.sessionId,
    transcriptPath: session.transcriptPath,
    mtimeMs: session.mtimeMs,
    cwd: latestCwd(lines),
    branch: latestBranch(lines),
    tree,
  };
}
