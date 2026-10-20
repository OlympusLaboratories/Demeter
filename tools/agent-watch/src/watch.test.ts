import * as fs from 'node:fs/promises';
import * as os from 'node:os';
import * as path from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { PathWatcher, debounce, signatureOf } from './watch';

const temps: string[] = [];

async function tempDir(): Promise<string> {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'agent-watch-watch-'));
  temps.push(dir);
  return dir;
}

afterEach(async () => {
  vi.useRealTimers();
  while (temps.length > 0) {
    const dir = temps.pop();
    if (dir) await fs.rm(dir, { recursive: true, force: true });
  }
});

describe('signatureOf', () => {
  it('reports missing rather than throwing', async () => {
    expect(await signatureOf('/definitely/not/here')).toBe('missing');
  });

  it('changes when a file grows', async () => {
    const dir = await tempDir();
    const file = path.join(dir, 'a.jsonl');
    await fs.writeFile(file, 'one\n');
    const before = await signatureOf(file);
    await fs.appendFile(file, 'two\n');
    expect(await signatureOf(file)).not.toBe(before);
  });
});

describe('PathWatcher', () => {
  it('detects an append by polling even when fs.watch cannot be used at all', async () => {
    const dir = await tempDir();
    const file = path.join(dir, 'a.jsonl');
    await fs.writeFile(file, 'one\n');

    const throwing = () => {
      const error = new Error('ENOSPC: System limit for number of file watchers reached');
      Object.assign(error, { code: 'ENOSPC' });
      throw error;
    };

    const onChange = vi.fn();
    const watcher = new PathWatcher(onChange, { watchFactory: throwing });
    await watcher.setTargets([file]);

    expect(await watcher.poll()).toBe(false);

    await fs.appendFile(file, 'two\n');
    expect(await watcher.poll()).toBe(true);

    watcher.dispose();
  });

  it('detects a new file appearing in a watched directory', async () => {
    const dir = await tempDir();
    const watcher = new PathWatcher(() => undefined, { watchFactory: () => ({ close: () => undefined }) });
    await watcher.setTargets([dir]);

    expect(await watcher.poll()).toBe(false);
    await fs.writeFile(path.join(dir, 'new.jsonl'), '{}\n');
    expect(await watcher.poll()).toBe(true);

    watcher.dispose();
  });

  it('reports a watched file that disappears', async () => {
    const dir = await tempDir();
    const file = path.join(dir, 'a.jsonl');
    await fs.writeFile(file, 'one\n');
    const watcher = new PathWatcher(() => undefined, { watchFactory: () => ({ close: () => undefined }) });
    await watcher.setTargets([file]);

    await fs.rm(file);
    expect(await watcher.poll()).toBe(true);

    watcher.dispose();
  });

  it('acts on a native watch event without waiting for the poll', async () => {
    const dir = await tempDir();
    const listeners: (() => void)[] = [];
    const onChange = vi.fn();
    const watcher = new PathWatcher(onChange, {
      watchFactory: (_target, listener) => {
        listeners.push(listener);
        return { close: () => undefined };
      },
    });
    await watcher.setTargets([dir]);

    await fs.writeFile(path.join(dir, 'new.jsonl'), 'x');
    listeners.forEach((listener) => listener());
    for (let tick = 0; tick < 50 && onChange.mock.calls.length === 0; tick += 1) {
      await new Promise((resolve) => setTimeout(resolve, 2));
    }
    expect(onChange).toHaveBeenCalledTimes(1);

    watcher.dispose();
  });

  it('ignores a native watch event that turns out to be nothing', async () => {
    const dir = await tempDir();
    const listeners: (() => void)[] = [];
    const onChange = vi.fn();
    const watcher = new PathWatcher(onChange, {
      watchFactory: (_target, listener) => {
        listeners.push(listener);
        return { close: () => undefined };
      },
    });
    await watcher.setTargets([dir]);

    for (let burst = 0; burst < 10; burst += 1) {
      listeners.forEach((listener) => listener());
      await new Promise((resolve) => setTimeout(resolve, 5));
    }

    expect(onChange).not.toHaveBeenCalled();
    watcher.dispose();
  });

  it('stops polling and releases handles on dispose', async () => {
    const dir = await tempDir();
    let closed = 0;
    const watcher = new PathWatcher(() => undefined, {
      watchFactory: () => ({ close: () => { closed += 1; } }),
    });
    await watcher.setTargets([dir]);
    watcher.start();
    watcher.dispose();

    expect(closed).toBe(1);
    await fs.writeFile(path.join(dir, 'x.jsonl'), '{}\n');
    expect(await watcher.poll()).toBe(false);
  });
});

describe('debounce', () => {
  it('collapses a burst into a single call', () => {
    vi.useFakeTimers();
    const fn = vi.fn();
    const debounced = debounce(fn, 100);

    debounced.call();
    debounced.call();
    debounced.call();
    expect(fn).not.toHaveBeenCalled();

    vi.advanceTimersByTime(100);
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it('can be cancelled before it fires', () => {
    vi.useFakeTimers();
    const fn = vi.fn();
    const debounced = debounce(fn, 100);
    debounced.call();
    debounced.cancel();
    vi.advanceTimersByTime(500);
    expect(fn).not.toHaveBeenCalled();
  });
});

describe('directory signatures', () => {
  it('changes when a file is added in the same millisecond as the baseline', async () => {
    for (let attempt = 0; attempt < 25; attempt += 1) {
      const dir = await tempDir();
      const before = await signatureOf(dir);
      await fs.writeFile(path.join(dir, `f${attempt}.jsonl`), '{}\n');
      expect(await signatureOf(dir)).not.toBe(before);
    }
  });

  it('changes when a file is renamed without changing the entry count', async () => {
    const dir = await tempDir();
    await fs.writeFile(path.join(dir, 'a.jsonl'), '{}\n');
    const before = await signatureOf(dir);
    await fs.rename(path.join(dir, 'a.jsonl'), path.join(dir, 'b.jsonl'));
    expect(await signatureOf(dir)).not.toBe(before);
  });

  it('does not change when a watched directory is untouched', async () => {
    const dir = await tempDir();
    await fs.writeFile(path.join(dir, 'a.jsonl'), '{}\n');
    expect(await signatureOf(dir)).toBe(await signatureOf(dir));
  });
});

describe('append detection', () => {
  it('fires for content appended to a watched file inside a watched directory', async () => {
    const dir = await tempDir();
    const file = path.join(dir, 'agent-a1.jsonl');
    await fs.writeFile(file, '{"type":"a"}\n');

    const watcher = new PathWatcher(() => undefined, { watchFactory: () => ({ close: () => undefined }) });
    await watcher.setTargets([dir, file]);

    expect(await watcher.poll()).toBe(false);
    await fs.appendFile(file, '{"type":"b"}\n');
    expect(await watcher.poll()).toBe(true);

    watcher.dispose();
  });
});

describe('pausing', () => {
  it('stops polling on stop and resumes on start, without stacking timers', async () => {
    const dir = await tempDir();
    let opened = 0;
    let closed = 0;
    const watcher = new PathWatcher(() => undefined, {
      pollMs: 10_000,
      watchFactory: () => {
        opened += 1;
        return { close: () => { closed += 1; } };
      },
    });
    await watcher.setTargets([dir]);
    expect(watcher.started).toBe(false);

    watcher.start();
    watcher.start();
    watcher.start();
    expect(watcher.started).toBe(true);

    watcher.stop();
    expect(watcher.started).toBe(false);
    expect(closed).toBe(opened);

    watcher.start();
    expect(watcher.started).toBe(true);
    watcher.dispose();
    expect(watcher.started).toBe(false);
  });

  it('keeps its baseline across a pause so nothing is missed while stopped', async () => {
    const dir = await tempDir();
    const file = path.join(dir, 'a.jsonl');
    await fs.writeFile(file, 'one\n');

    const watcher = new PathWatcher(() => undefined, { watchFactory: () => ({ close: () => undefined }) });
    await watcher.setTargets([file]);
    watcher.start();
    watcher.stop();

    await fs.appendFile(file, 'two\n');
    expect(await watcher.poll()).toBe(true);

    watcher.dispose();
  });
});
