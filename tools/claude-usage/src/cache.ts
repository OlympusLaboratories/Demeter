import * as fs from 'node:fs';
import * as fsp from 'node:fs/promises';
import * as os from 'node:os';
import * as path from 'node:path';
import { Meter } from './format';
import { UsageSnapshot } from './usage';

export interface CacheRecord {
  updatedAt: number;
  snapshot?: UsageSnapshot;
  source?: string;
  notice?: string;
  retryUntil?: number;
}

export function defaultCacheDir(
  platform: NodeJS.Platform = process.platform,
  env: NodeJS.ProcessEnv = process.env,
  home: string = os.homedir(),
): string {
  const override = env['CLAUDE_USAGE_CACHE_DIR'];
  if (override !== undefined && override.length > 0) {
    return override;
  }
  if (platform === 'darwin') {
    return path.join(home, 'Library', 'Caches', 'claude-usage');
  }
  if (platform === 'win32') {
    return path.join(env['LOCALAPPDATA'] ?? path.join(home, 'AppData', 'Local'), 'claude-usage');
  }
  return path.join(env['XDG_CACHE_HOME'] ?? path.join(home, '.cache'), 'claude-usage');
}

function isMeter(value: unknown): value is Meter {
  const meter = value as Record<string, unknown> | null;
  return (
    typeof meter === 'object' &&
    meter !== null &&
    typeof meter['id'] === 'string' &&
    typeof meter['group'] === 'string' &&
    typeof meter['label'] === 'string' &&
    typeof meter['percent'] === 'number'
  );
}

export function parseRecord(text: string): CacheRecord | undefined {
  let body: unknown;
  try {
    body = JSON.parse(text);
  } catch {
    return undefined;
  }
  if (typeof body !== 'object' || body === null) {
    return undefined;
  }
  const record = body as Record<string, unknown>;
  if (typeof record['updatedAt'] !== 'number') {
    return undefined;
  }
  const result: CacheRecord = { updatedAt: record['updatedAt'] as number };
  const snapshot = record['snapshot'] as Record<string, unknown> | undefined;
  if (snapshot && Array.isArray(snapshot['meters']) && snapshot['meters'].every(isMeter)) {
    result.snapshot = {
      meters: snapshot['meters'] as Meter[],
      fetchedAt: typeof snapshot['fetchedAt'] === 'number' ? (snapshot['fetchedAt'] as number) : result.updatedAt,
    };
  }
  if (typeof record['source'] === 'string') {
    result.source = record['source'] as string;
  }
  if (typeof record['notice'] === 'string') {
    result.notice = record['notice'] as string;
  }
  if (typeof record['retryUntil'] === 'number') {
    result.retryUntil = record['retryUntil'] as number;
  }
  return result;
}

export class UsageCache {
  private readonly file: string;
  private readonly lockFile: string;

  constructor(private readonly dir: string = defaultCacheDir()) {
    this.file = path.join(dir, 'usage.json');
    this.lockFile = path.join(dir, 'usage.lock');
  }

  async read(): Promise<CacheRecord | undefined> {
    try {
      return parseRecord(await fsp.readFile(this.file, 'utf8'));
    } catch {
      return undefined;
    }
  }

  async write(record: CacheRecord): Promise<void> {
    const temp = `${this.file}.${process.pid}.${Math.random().toString(36).slice(2)}.tmp`;
    try {
      await fsp.mkdir(this.dir, { recursive: true });
      await fsp.writeFile(temp, JSON.stringify(record), { mode: 0o600 });
      await fsp.rename(temp, this.file);
    } catch {
      await fsp.rm(temp, { force: true }).catch(() => undefined);
    }
  }

  private async clearStaleLock(staleMs: number): Promise<void> {
    try {
      const stats = await fsp.stat(this.lockFile);
      if (Date.now() - stats.mtimeMs > staleMs) {
        await fsp.rm(this.lockFile, { force: true });
      }
    } catch {
      return;
    }
  }

  async withLock<T>(staleMs: number, task: () => Promise<T>): Promise<T | undefined> {
    await fsp.mkdir(this.dir, { recursive: true }).catch(() => undefined);
    let handle: fsp.FileHandle | undefined;
    try {
      handle = await fsp.open(this.lockFile, 'wx');
    } catch {
      await this.clearStaleLock(staleMs);
      try {
        handle = await fsp.open(this.lockFile, 'wx');
      } catch {
        return undefined;
      }
    }
    try {
      await handle.write(String(process.pid));
      await handle.close();
      handle = undefined;
      return await task();
    } finally {
      await handle?.close().catch(() => undefined);
      await fsp.rm(this.lockFile, { force: true }).catch(() => undefined);
    }
  }

  watch(onChange: () => void): { dispose(): void } {
    let watcher: fs.FSWatcher | undefined;
    let timer: NodeJS.Timeout | undefined;
    try {
      fs.mkdirSync(this.dir, { recursive: true });
      watcher = fs.watch(this.dir, (_event, filename) => {
        if (filename !== null && !filename.toString().startsWith('usage.json')) {
          return;
        }
        if (timer) {
          clearTimeout(timer);
        }
        timer = setTimeout(onChange, 150);
      });
    } catch {
      watcher = undefined;
    }
    return {
      dispose() {
        if (timer) {
          clearTimeout(timer);
        }
        watcher?.close();
      },
    };
  }
}
