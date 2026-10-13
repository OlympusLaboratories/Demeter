import * as fs from 'node:fs/promises';
import * as path from 'node:path';
import type { Logger } from './log';
import {
  aliasOutranks,
  isPathWithin,
  normalizeLabel,
  normalizePath,
  parseSessionTail,
  sessionAliases,
  splitTail,
  truncatedPrefix,
  type AliasKind,
  type WorktreeSource,
} from './resolve';

const TAIL_BYTES = 256 * 1024;
const DEEP_TAIL_BYTES = 4 * 1024 * 1024;
const TTL_MS = 5000;
const READ_CONCURRENCY = 16;

export interface SessionEntry {
  sessionId?: string;
  label: string;
  matchedVia: AliasKind;
  aliases: string[];
  worktreePath: string;
  source: WorktreeSource;
  mtimeMs: number;
  file: string;
}

export interface SkippedSession {
  file: string;
  reason: string;
}

async function readTail(file: string, bytes: number): Promise<{ text: string; partial: boolean }> {
  const handle = await fs.open(file, 'r');
  try {
    const { size } = await handle.stat();
    const start = Math.max(0, size - bytes);
    const length = size - start;
    if (length === 0) {
      return { text: '', partial: false };
    }
    const buffer = Buffer.alloc(length);
    await handle.read(buffer, 0, length, start);
    return { text: buffer.toString('utf8'), partial: start > 0 };
  } finally {
    await handle.close();
  }
}

function rankBeats(candidate: SessionEntry, incumbent: SessionEntry): boolean {
  if (candidate.worktreePath !== incumbent.worktreePath) {
    if (isPathWithin(incumbent.worktreePath, candidate.worktreePath)) {
      return true;
    }
    if (isPathWithin(candidate.worktreePath, incumbent.worktreePath)) {
      return false;
    }
  }
  if (candidate.matchedVia !== incumbent.matchedVia) {
    return aliasOutranks(candidate.matchedVia, incumbent.matchedVia);
  }
  return candidate.mtimeMs > incumbent.mtimeMs;
}

async function mapWithLimit<T, R>(
  items: T[],
  limit: number,
  fn: (item: T) => Promise<R>,
): Promise<R[]> {
  const results = new Array<R>(items.length);
  let cursor = 0;
  const workers = Array.from({ length: Math.min(limit, items.length) }, async () => {
    for (;;) {
      const index = cursor++;
      const item = items[index];
      if (index >= items.length || item === undefined) {
        return;
      }
      results[index] = await fn(item);
    }
  });
  await Promise.all(workers);
  return results;
}

export class SessionIndex {
  private byLabel = new Map<string, SessionEntry>();
  private worktrees = new Set<string>();
  private skipped: SkippedSession[] = [];
  private misses = new Set<string>();
  private builtAt = 0;
  private building: Promise<void> | undefined;

  constructor(
    private readonly projectsDir: () => string,
    private readonly log: Logger,
  ) {}

  async ensureFresh(force = false): Promise<void> {
    if (!force && Date.now() - this.builtAt < TTL_MS) {
      return;
    }
    if (this.building) {
      return this.building;
    }
    this.building = this.rebuild().finally(() => {
      this.building = undefined;
    });
    return this.building;
  }

  async lookupLabel(label: string): Promise<SessionEntry | undefined> {
    await this.ensureFresh();
    const hit = this.find(label);
    if (hit) {
      return hit;
    }
    if (this.misses.has(label)) {
      return undefined;
    }
    await this.ensureFresh(true);
    const retried = this.find(label);
    if (!retried) {
      this.misses.add(label);
    }
    return retried;
  }

  private find(label: string): SessionEntry | undefined {
    const exact = this.byLabel.get(normalizeLabel(label));
    if (exact) {
      return exact;
    }
    const prefix = truncatedPrefix(label);
    if (prefix === undefined) {
      return undefined;
    }
    let best: SessionEntry | undefined;
    for (const [key, entry] of this.byLabel) {
      if (!key.startsWith(prefix)) {
        continue;
      }
      if (best && best.worktreePath !== entry.worktreePath) {
        return undefined;
      }
      if (!best || rankBeats(entry, best)) {
        best = entry;
      }
    }
    return best;
  }

  knownWorktrees(): Set<string> {
    return this.worktrees;
  }

  skippedSessions(): SkippedSession[] {
    return this.skipped;
  }

  entries(): SessionEntry[] {
    const byFile = new Map<string, SessionEntry>();
    for (const entry of this.byLabel.values()) {
      if (!byFile.has(entry.file)) {
        byFile.set(entry.file, entry);
      }
    }
    return [...byFile.values()];
  }

  private async listSessionFiles(root: string): Promise<string[]> {
    let dirents;
    try {
      dirents = await fs.readdir(root, { withFileTypes: true });
    } catch (error) {
      this.log.info(`cannot read projects dir ${root}: ${String(error)}`);
      return [];
    }
    const nested = await Promise.all(
      dirents
        .filter((entry) => entry.isDirectory())
        .map(async (entry) => {
          const dir = path.join(root, entry.name);
          try {
            const files = await fs.readdir(dir);
            return files.filter((f) => f.endsWith('.jsonl')).map((f) => path.join(dir, f));
          } catch {
            return [];
          }
        }),
    );
    return nested.flat();
  }

  private async rebuild(): Promise<void> {
    const started = Date.now();
    const root = normalizePath(this.projectsDir());
    const files = await this.listSessionFiles(root);

    const byLabel = new Map<string, SessionEntry>();
    const worktrees = new Set<string>();
    const skipped: SkippedSession[] = [];

    await mapWithLimit(files, READ_CONCURRENCY, async (file) => {
      let mtimeMs = 0;
      try {
        mtimeMs = (await fs.stat(file)).mtimeMs;
      } catch {
        return;
      }

      let facts;
      try {
        const shallow = await readTail(file, TAIL_BYTES);
        facts = parseSessionTail(splitTail(shallow.text, shallow.partial));
        const missingTitle = !facts.aiTitle && !facts.customTitle;
        if ((missingTitle || !facts.worktreePath) && shallow.partial) {
          const deep = await readTail(file, DEEP_TAIL_BYTES);
          facts = parseSessionTail(splitTail(deep.text, deep.partial));
        }
      } catch (error) {
        skipped.push({ file, reason: `read failed: ${String(error)}` });
        return;
      }

      if (!facts.worktreePath) {
        skipped.push({ file, reason: 'no worktree-state, relocated, or cwd record found' });
        return;
      }

      const aliases = sessionAliases(facts);
      if (aliases.length === 0) {
        skipped.push({
          file,
          reason: 'no ai-title, custom-title, worktree name, or last prompt to match a tab label against',
        });
        return;
      }

      const worktreePath = normalizePath(facts.worktreePath);
      worktrees.add(worktreePath);

      for (const alias of aliases) {
        const entry: SessionEntry = {
          sessionId: facts.sessionId,
          label: alias.value,
          matchedVia: alias.kind,
          aliases: aliases.map((a) => a.value),
          worktreePath,
          source: facts.source ?? 'cwd',
          mtimeMs,
          file,
        };
        const key = normalizeLabel(alias.value);
        const existing = byLabel.get(key);
        if (!existing || rankBeats(entry, existing)) {
          byLabel.set(key, entry);
        }
      }
    });

    this.byLabel = byLabel;
    this.worktrees = worktrees;
    this.skipped = skipped;
    this.misses.clear();
    this.builtAt = Date.now();
    this.log.info(
      `indexed ${files.length} session files in ${Date.now() - started}ms — ` +
        `${byLabel.size} labelled, ${worktrees.size} worktrees, ${skipped.length} skipped`,
    );
  }
}
