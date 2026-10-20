export interface ContentBlock {
  type?: string;
  text?: string;
  thinking?: string;
  signature?: string;
  name?: string;
  id?: string;
  input?: Record<string, unknown>;
  tool_use_id?: string;
  content?: unknown;
  is_error?: boolean;
}

export interface TranscriptLine {
  type?: string;
  sessionId?: string;
  timestamp?: string;
  cwd?: string;
  gitBranch?: string;
  version?: string;
  message?: { role?: string; content?: ContentBlock[] | string };
}

export interface SubagentMeta {
  agentType?: string;
  description?: string;
  toolUseId?: string;
  spawnDepth?: number;
}

export function parseJsonl(text: string): TranscriptLine[] {
  const lines: TranscriptLine[] = [];
  for (const raw of text.split('\n')) {
    const trimmed = raw.trim();
    if (!trimmed) continue;
    try {
      lines.push(JSON.parse(trimmed) as TranscriptLine);
    } catch {
      continue;
    }
  }
  return lines;
}

export function blocksOf(line: TranscriptLine): ContentBlock[] {
  const content = line.message?.content;
  return Array.isArray(content) ? content : [];
}

function lastDefined(lines: TranscriptLine[], pick: (line: TranscriptLine) => string | undefined): string | undefined {
  for (let index = lines.length - 1; index >= 0; index -= 1) {
    const line = lines[index];
    const value = line ? pick(line) : undefined;
    if (value) return value;
  }
  return undefined;
}

export function latestCwd(lines: TranscriptLine[]): string | undefined {
  return lastDefined(lines, (line) => line.cwd);
}

export function latestBranch(lines: TranscriptLine[]): string | undefined {
  return lastDefined(lines, (line) => line.gitBranch);
}

export function firstCwd(lines: TranscriptLine[]): string | undefined {
  for (const line of lines) {
    if (line.cwd) return line.cwd;
  }
  return undefined;
}

export function isAgentSpawn(block: ContentBlock): boolean {
  return block.type === 'tool_use' && (block.name === 'Agent' || block.name === 'Task');
}
