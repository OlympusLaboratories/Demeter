import * as fs from 'node:fs';
import * as fsp from 'node:fs/promises';

export interface WatchHandle {
  close(): void;
}

export type WatchFactory = (target: string, listener: () => void) => WatchHandle;

export interface WatcherOptions {
  pollMs?: number;
  watchFactory?: WatchFactory;
}

const DEFAULT_POLL_MS = 2000;

export function nodeWatchFactory(target: string, listener: () => void): WatchHandle {
  const watcher = fs.watch(target, { persistent: false }, () => listener());
  return { close: () => watcher.close() };
}

function fnv1a(value: string): string {
  let hash = 0x811c9dc5;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 0x01000193) >>> 0;
  }
  return hash.toString(16);
}

export async function signatureOf(target: string): Promise<string> {
  let stats;
  try {
    stats = await fsp.stat(target);
  } catch {
    return 'missing';
  }

  if (!stats.isDirectory()) return `f:${Math.trunc(stats.mtimeMs)}:${stats.size}`;

  try {
    const entries = await fsp.readdir(target);
    entries.sort();
    return `d:${entries.length}:${fnv1a(entries.join('\u0000'))}`;
  } catch {
    return `d:${Math.trunc(stats.mtimeMs)}`;
  }
}

export class PathWatcher {
  private signatures = new Map<string, string>();
  private handles: WatchHandle[] = [];
  private timer: ReturnType<typeof setInterval> | undefined;
  private targets: string[] = [];
  private disposed = false;
  private polling = false;

  constructor(
    private readonly onChange: () => void,
    private readonly options: WatcherOptions = {},
  ) {}

  async setTargets(targets: string[]): Promise<void> {
    this.closeHandles();
    this.targets = [...new Set(targets)];
    this.signatures.clear();
    for (const target of this.targets) {
      this.signatures.set(target, await signatureOf(target));
    }
    this.attach();
  }

  private attach(): void {
    if (this.disposed) return;
    const factory = this.options.watchFactory ?? nodeWatchFactory;
    for (const target of this.targets) {
      try {
        this.handles.push(factory(target, () => this.verify()));
      } catch {
        continue;
      }
    }
  }

  private verify(): void {
    if (this.polling || this.disposed) return;
    this.polling = true;
    void this.poll()
      .then((changed) => {
        if (changed && !this.disposed) this.onChange();
      })
      .finally(() => {
        this.polling = false;
      });
  }

  start(): void {
    if (this.timer || this.disposed) return;
    if (this.handles.length === 0) this.attach();
    const interval = this.options.pollMs ?? DEFAULT_POLL_MS;
    this.timer = setInterval(() => this.verify(), interval);
    if (typeof this.timer === 'object' && 'unref' in this.timer) this.timer.unref();
  }

  stop(): void {
    if (this.timer) clearInterval(this.timer);
    this.timer = undefined;
    this.closeHandles();
  }

  get started(): boolean {
    return this.timer !== undefined;
  }

  async poll(): Promise<boolean> {
    let changed = false;
    for (const target of this.targets) {
      const next = await signatureOf(target);
      if (this.signatures.get(target) !== next) {
        this.signatures.set(target, next);
        changed = true;
      }
    }
    return changed;
  }

  private closeHandles(): void {
    for (const handle of this.handles) {
      try {
        handle.close();
      } catch {
        continue;
      }
    }
    this.handles = [];
  }

  dispose(): void {
    this.disposed = true;
    if (this.timer) clearInterval(this.timer);
    this.timer = undefined;
    this.closeHandles();
    this.signatures.clear();
    this.targets = [];
  }
}

export function debounce(fn: () => void, waitMs: number): { call(): void; cancel(): void } {
  let timer: ReturnType<typeof setTimeout> | undefined;
  return {
    call() {
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => {
        timer = undefined;
        fn();
      }, waitMs);
    },
    cancel() {
      if (timer) clearTimeout(timer);
      timer = undefined;
    },
  };
}
