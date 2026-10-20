import * as fs from 'node:fs/promises';
import * as path from 'node:path';

export interface ManifestAgent {
  agentId: string;
  label?: string;
  phaseIndex?: number;
  phaseTitle?: string;
  state?: string;
  model?: string;
  lastToolName?: string;
}

export interface WorkflowManifest {
  runId: string;
  workflowName?: string;
  status?: string;
  summary?: string;
  logs: string[];
  phases: string[];
  agents: Map<string, ManifestAgent>;
}

function str(value: unknown): string | undefined {
  return typeof value === 'string' && value.length > 0 ? value : undefined;
}

function num(value: unknown): number | undefined {
  return typeof value === 'number' ? value : undefined;
}

export function parseManifest(raw: unknown): WorkflowManifest | undefined {
  if (!raw || typeof raw !== 'object') return undefined;
  const record = raw as Record<string, unknown>;
  const runId = str(record['runId']);
  if (!runId) return undefined;

  const phases: string[] = [];
  const declared = record['phases'];
  if (Array.isArray(declared)) {
    for (const entry of declared) {
      const title = str((entry as Record<string, unknown>)?.['title']);
      if (title) phases.push(title);
    }
  }

  const agents = new Map<string, ManifestAgent>();
  const progress = record['workflowProgress'];
  if (Array.isArray(progress)) {
    for (const entry of progress) {
      const item = entry as Record<string, unknown>;
      if (item?.['type'] !== 'workflow_agent') continue;
      const agentId = str(item['agentId']);
      if (!agentId) continue;
      agents.set(agentId, {
        agentId,
        label: str(item['label']),
        phaseIndex: num(item['phaseIndex']),
        phaseTitle: str(item['phaseTitle']),
        state: str(item['state']),
        model: str(item['model']),
        lastToolName: str(item['lastToolName']),
      });
    }
  }

  const logs: string[] = [];
  const rawLogs = record['logs'];
  if (Array.isArray(rawLogs)) {
    for (const entry of rawLogs) {
      const line = str(entry);
      if (line) logs.push(line);
    }
  }

  return {
    runId,
    workflowName: str(record['workflowName']),
    status: str(record['status']),
    summary: str(record['summary']),
    logs,
    phases,
    agents,
  };
}

export function manifestPathFor(sessionDir: string, runId: string): string {
  return path.join(sessionDir, 'workflows', `${runId}.json`);
}

export function firstJsonValue(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    const end = endOfFirstObject(text);
    if (end === undefined) return undefined;
    try {
      return JSON.parse(text.slice(0, end));
    } catch {
      return undefined;
    }
  }
}

function endOfFirstObject(text: string): number | undefined {
  let depth = 0;
  let inString = false;
  let escaped = false;
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    if (inString) {
      if (escaped) escaped = false;
      else if (char === '\\') escaped = true;
      else if (char === '"') inString = false;
      continue;
    }
    if (char === '"') inString = true;
    else if (char === '{') depth += 1;
    else if (char === '}') {
      depth -= 1;
      if (depth === 0) return index + 1;
    }
  }
  return undefined;
}

export async function readManifest(sessionDir: string, runId: string): Promise<WorkflowManifest | undefined> {
  try {
    const text = await fs.readFile(manifestPathFor(sessionDir, runId), 'utf8');
    return parseManifest(firstJsonValue(text));
  } catch {
    return undefined;
  }
}

export function statusFromState(state: string | undefined): 'running' | 'done' | 'error' | undefined {
  switch (state) {
    case 'done':
      return 'done';
    case 'error':
      return 'error';
    case 'progress':
    case 'start':
    case 'queued':
      return 'running';
    default:
      return undefined;
  }
}
