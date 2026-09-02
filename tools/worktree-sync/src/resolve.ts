import * as path from 'node:path';

export type WorktreeSource = 'worktree-state' | 'relocated' | 'cwd';

export interface TailFacts {
  sessionId?: string;
  aiTitle?: string;
  customTitle?: string;
  worktreeName?: string;
  worktreePath?: string;
  source?: WorktreeSource;
}

const TITLE_MARKERS = ['"ai-title"', '"custom-title"', '"worktree-state"', '"relocated"'];

export function parseSessionTail(lines: string[]): TailFacts {
  const facts: TailFacts = {};
  let cwdFallback: string | undefined;
  let worktreeStateSeen = false;

  for (let i = lines.length - 1; i >= 0; i--) {
    const line = lines[i];
    if (!line) {
      continue;
    }
    const titleish = TITLE_MARKERS.some((marker) => line.includes(marker));
    if (!titleish && !(cwdFallback === undefined && line.includes('"cwd"'))) {
      continue;
    }

    let record: Record<string, unknown>;
    try {
      record = JSON.parse(line) as Record<string, unknown>;
    } catch {
      continue;
    }
    if (!record || typeof record !== 'object') {
      continue;
    }

    if (!facts.sessionId && typeof record.sessionId === 'string') {
      facts.sessionId = record.sessionId;
    }

    switch (record.type) {
      case 'ai-title': {
        const title = record.aiTitle;
        if (!facts.aiTitle && typeof title === 'string' && title.length > 0) {
          facts.aiTitle = title;
        }
        break;
      }
      case 'custom-title': {
        const title = record.customTitle;
        if (!facts.customTitle && typeof title === 'string' && title.length > 0) {
          facts.customTitle = title;
        }
        break;
      }
      case 'worktree-state': {
        if (facts.worktreePath || worktreeStateSeen) {
          break;
        }
        worktreeStateSeen = true;
        const session = record.worktreeSession as
          | { worktreePath?: unknown; worktreeName?: unknown }
          | null
          | undefined;
        const worktreePath = session?.worktreePath;
        if (typeof worktreePath === 'string' && worktreePath.length > 0) {
          facts.worktreePath = worktreePath;
          facts.source = 'worktree-state';
        }
        const worktreeName = session?.worktreeName;
        if (typeof worktreeName === 'string' && worktreeName.length > 0) {
          facts.worktreeName = worktreeName;
        }
        break;
      }
      case 'relocated': {
        const relocated = record.relocatedCwd;
        if (!facts.worktreePath && typeof relocated === 'string' && relocated.length > 0) {
          facts.worktreePath = relocated;
          facts.source = 'relocated';
        }
        break;
      }
      default: {
        const cwd = record.cwd;
        if (!cwdFallback && typeof cwd === 'string' && cwd.length > 0) {
          cwdFallback = cwd;
        }
      }
    }
  }

  if (!facts.worktreePath && cwdFallback) {
    facts.worktreePath = cwdFallback;
    facts.source = 'cwd';
  }

  return facts;
}

export type AliasKind = 'title' | 'name';

export interface Alias {
  value: string;
  kind: AliasKind;
}

export function sessionAliases(facts: TailFacts): Alias[] {
  const candidates: Alias[] = [
    { value: facts.customTitle ?? '', kind: 'title' },
    { value: facts.aiTitle ?? '', kind: 'title' },
    { value: facts.worktreeName ?? '', kind: 'name' },
    { value: facts.worktreePath ? path.basename(facts.worktreePath) : '', kind: 'name' },
  ];
  const seen = new Set<string>();
  const aliases: Alias[] = [];
  for (const alias of candidates) {
    if (alias.value.length === 0 || seen.has(alias.value)) {
      continue;
    }
    seen.add(alias.value);
    aliases.push(alias);
  }
  return aliases;
}

export function normalizePath(value: string): string {
  const expanded = value.startsWith('~')
    ? path.join(process.env.HOME ?? '', value.slice(1))
    : value;
  return path.resolve(expanded);
}

export function isPathWithin(parent: string, child: string): boolean {
  const from = normalizePath(parent);
  const to = normalizePath(child);
  if (from === to) {
    return true;
  }
  return to.startsWith(from.endsWith(path.sep) ? from : from + path.sep);
}

export function resolveWorktreeForCwd(
  cwd: string,
  knownWorktrees: Iterable<string>,
): string | undefined {
  let best: string | undefined;
  for (const candidate of knownWorktrees) {
    if (!isPathWithin(candidate, cwd)) {
      continue;
    }
    if (best === undefined || normalizePath(candidate).length > normalizePath(best).length) {
      best = candidate;
    }
  }
  return best;
}

export function splitTail(text: string, partial: boolean): string[] {
  const lines = text.split('\n');
  if (partial && lines.length > 0) {
    lines.shift();
  }
  return lines;
}
