import * as fs from 'node:fs';
import * as fsp from 'node:fs/promises';
import * as os from 'node:os';
import * as path from 'node:path';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { UsageCache, defaultCacheDir, parseRecord } from './cache';

const snapshot = {
  fetchedAt: 1_000,
  meters: [
    { id: 'session', group: 'session' as const, label: 'Session', shortLabel: '5h', title: 'Session', percent: 32, severity: 'normal' as const },
  ],
};

let dir: string;

beforeEach(() => {
  dir = fs.mkdtempSync(path.join(os.tmpdir(), 'claude-usage-test-'));
});

afterEach(() => {
  fs.rmSync(dir, { recursive: true, force: true });
});

describe('defaultCacheDir', () => {
  it('uses a per-user location outside any one editor installation', () => {
    expect(defaultCacheDir('darwin', {}, '/Users/x')).toBe('/Users/x/Library/Caches/claude-usage');
    expect(defaultCacheDir('linux', {}, '/home/x')).toBe('/home/x/.cache/claude-usage');
    expect(defaultCacheDir('linux', { XDG_CACHE_HOME: '/c' }, '/home/x')).toBe('/c/claude-usage');
    expect(defaultCacheDir('win32', { LOCALAPPDATA: 'C:\\l' }, 'C:\\u')).toMatch(/^C:\\l[\\/]claude-usage$/);
  });

  it('honours an explicit override', () => {
    expect(defaultCacheDir('darwin', { CLAUDE_USAGE_CACHE_DIR: '/tmp/x' }, '/Users/x')).toBe('/tmp/x');
  });
});

describe('parseRecord', () => {
  it('round-trips a written record', () => {
    const parsed = parseRecord(JSON.stringify({ updatedAt: 5, snapshot, source: 'claudeCode' }))!;
    expect(parsed.updatedAt).toBe(5);
    expect(parsed.snapshot!.meters[0]!.percent).toBe(32);
    expect(parsed.source).toBe('claudeCode');
  });

  it('rejects anything it cannot trust', () => {
    expect(parseRecord('nope')).toBeUndefined();
    expect(parseRecord('null')).toBeUndefined();
    expect(parseRecord('{}')).toBeUndefined();
  });

  it('keeps the record but drops a malformed snapshot', () => {
    const parsed = parseRecord(JSON.stringify({ updatedAt: 5, snapshot: { meters: [{ nope: true }] } }))!;
    expect(parsed.updatedAt).toBe(5);
    expect(parsed.snapshot).toBeUndefined();
  });
});

describe('UsageCache', () => {
  it('shares a reading between two independent instances', async () => {
    const writer = new UsageCache(dir);
    const reader = new UsageCache(dir);
    await writer.write({ updatedAt: 42, snapshot, source: 'claudeCode' });
    const seen = await reader.read();
    expect(seen!.updatedAt).toBe(42);
    expect(seen!.snapshot!.meters[0]!.label).toBe('Session');
  });

  it('returns undefined when there is no cache yet', async () => {
    expect(await new UsageCache(dir).read()).toBeUndefined();
  });

  it('lets only one holder run the task at a time', async () => {
    const a = new UsageCache(dir);
    const b = new UsageCache(dir);
    let release: () => void;
    const held = new Promise<void>((resolve) => {
      release = resolve;
    });

    const first = a.withLock(60_000, async () => {
      await held;
      return 'fetched';
    });
    await new Promise((resolve) => setTimeout(resolve, 10));
    const second = await b.withLock(60_000, async () => 'should not run');
    expect(second).toBeUndefined();

    release!();
    expect(await first).toBe('fetched');
  });

  it('frees the lock again once the task finishes', async () => {
    const cache = new UsageCache(dir);
    expect(await cache.withLock(60_000, async () => 'one')).toBe('one');
    expect(await cache.withLock(60_000, async () => 'two')).toBe('two');
  });

  it('releases the lock even when the task throws', async () => {
    const cache = new UsageCache(dir);
    await expect(cache.withLock(60_000, async () => {
      throw new Error('boom');
    })).rejects.toThrow('boom');
    expect(await cache.withLock(60_000, async () => 'after')).toBe('after');
  });

  it('breaks a lock left behind by a crashed window', async () => {
    const cache = new UsageCache(dir);
    const lockFile = path.join(dir, 'usage.lock');
    await fsp.writeFile(lockFile, '99999');
    const old = Date.now() - 120_000;
    await fsp.utimes(lockFile, old / 1000, old / 1000);
    expect(await cache.withLock(60_000, async () => 'recovered')).toBe('recovered');
  });

  it('notifies a watcher when another instance writes', async () => {
    const watcher = new UsageCache(dir);
    const writer = new UsageCache(dir);
    let fired = 0;
    const subscription = watcher.watch(() => {
      fired += 1;
    });
    await new Promise((resolve) => setTimeout(resolve, 50));
    await writer.write({ updatedAt: 1, snapshot });
    for (let attempt = 0; attempt < 40 && fired === 0; attempt += 1) {
      await new Promise((resolve) => setTimeout(resolve, 50));
    }
    subscription.dispose();
    expect(fired).toBeGreaterThan(0);
  });
});
