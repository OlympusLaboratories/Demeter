import type { ContentBlock } from './transcript';

const SUMMARY_LIMIT = 140;

export function clip(value: string, limit = SUMMARY_LIMIT): string {
  const flat = value.replace(/\s+/g, ' ').trim();
  if (flat.length <= limit) return flat;
  return `${flat.slice(0, Math.max(0, limit - 1))}…`;
}

function text(input: Record<string, unknown> | undefined, key: string): string | undefined {
  const value = input?.[key];
  return typeof value === 'string' && value.length > 0 ? value : undefined;
}

function num(input: Record<string, unknown> | undefined, key: string): number | undefined {
  const value = input?.[key];
  return typeof value === 'number' ? value : undefined;
}

function basename(filePath: string): string {
  const parts = filePath.split('/');
  return parts[parts.length - 1] ?? filePath;
}

export function summarizeToolUse(name: string, input?: Record<string, unknown>): string {
  switch (name) {
    case 'Bash':
      return clip(text(input, 'command') ?? '');
    case 'Read': {
      const file = text(input, 'file_path');
      if (!file) return '';
      const offset = num(input, 'offset');
      const limit = num(input, 'limit');
      if (offset !== undefined && limit !== undefined) return `${basename(file)}:${offset}-${offset + limit}`;
      return basename(file);
    }
    case 'Edit':
    case 'Write':
    case 'NotebookEdit':
      return basename(text(input, 'file_path') ?? '');
    case 'Grep': {
      const pattern = text(input, 'pattern') ?? '';
      const glob = text(input, 'glob');
      return clip(glob ? `${pattern} in ${glob}` : pattern);
    }
    case 'Glob':
      return clip(text(input, 'pattern') ?? '');
    case 'Agent':
    case 'Task': {
      const description = text(input, 'description') ?? '';
      const kind = text(input, 'subagent_type');
      return clip(kind ? `${description} (${kind})` : description);
    }
    case 'WebFetch':
      return clip(text(input, 'url') ?? '');
    case 'WebSearch':
      return clip(text(input, 'query') ?? '');
    case 'Skill':
      return clip(text(input, 'skill') ?? '');
    default: {
      const firstString = Object.values(input ?? {}).find((value) => typeof value === 'string');
      return typeof firstString === 'string' ? clip(firstString) : '';
    }
  }
}

export function resultToText(content: unknown): string {
  if (typeof content === 'string') return content;
  if (Array.isArray(content)) {
    return content
      .map((entry) => {
        if (typeof entry === 'string') return entry;
        const block = entry as ContentBlock;
        if (typeof block?.text === 'string') return block.text;
        return '';
      })
      .filter((entry) => entry.length > 0)
      .join('\n');
  }
  if (content && typeof content === 'object') {
    const block = content as ContentBlock;
    if (typeof block.text === 'string') return block.text;
  }
  return '';
}

export function formatAge(ms: number): string {
  const seconds = Math.max(0, Math.round(ms / 1000));
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours}h`;
  return `${Math.round(hours / 24)}d`;
}
