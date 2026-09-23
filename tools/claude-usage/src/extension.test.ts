import * as fs from 'node:fs';
import * as os from 'node:os';
import * as path from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import * as stub from './testing/vscodeStub';
import { activate } from './extension';

function payload() {
  const soon = Date.now() + 80 * 60_000 + 30_000;
  const later = Date.now() + 5 * 86_400_000 + 30_000;
  return {
    limits: [
      { kind: 'session', percent: 32, severity: 'normal', resets_at: new Date(soon).toISOString() },
      { kind: 'weekly_all', percent: 53, severity: 'normal', resets_at: new Date(later).toISOString() },
    ],
  };
}

class FakeSecretStorage {
  private readonly entries = new Map<string, string>();
  get(key: string) {
    return Promise.resolve(this.entries.get(key));
  }
  store(key: string, value: string) {
    this.entries.set(key, value);
    return Promise.resolve();
  }
  delete(key: string) {
    this.entries.delete(key);
    return Promise.resolve();
  }
}

function makeContext() {
  return { subscriptions: [] as { dispose(): void }[], secrets: new FakeSecretStorage() };
}

function jsonResponse(body: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: () => null },
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(JSON.stringify(body)),
  };
}

function meterItems(): stub.StubStatusBarItem[] {
  return stub.visibleItems().filter((item) => !item.text.startsWith('$('));
}

function chipItem(): stub.StubStatusBarItem | undefined {
  return stub.visibleItems().find((item) => item.text.startsWith('$(history)') || item.text.startsWith('$(warning)'));
}

async function settle(): Promise<void> {
  for (let attempt = 0; attempt < 50; attempt += 1) {
    await new Promise((resolve) => setTimeout(resolve, 5));
    if (stub.visibleItems().some((item) => item.text.includes('%'))) {
      return;
    }
  }
}

let context: ReturnType<typeof makeContext>;
let cacheDir: string;

beforeEach(() => {
  stub.resetState();
  cacheDir = fs.mkdtempSync(path.join(os.tmpdir(), 'claude-usage-ext-'));
  process.env['CLAUDE_USAGE_CACHE_DIR'] = cacheDir;
  process.env['CLAUDE_CODE_OAUTH_TOKEN'] = 'test-token';
  context = makeContext();
});

afterEach(() => {
  for (const disposable of context.subscriptions) {
    disposable.dispose();
  }
  fs.rmSync(cacheDir, { recursive: true, force: true });
  delete process.env['CLAUDE_USAGE_CACHE_DIR'];
  delete process.env['CLAUDE_CODE_OAUTH_TOKEN'];
  vi.unstubAllGlobals();
});

describe('activate', () => {
  it('renders one status bar item per visible window', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(jsonResponse(payload()))));
    activate(context as never);
    await settle();

    const texts = meterItems().map((item) => item.text);
    expect(texts).toHaveLength(2);
    expect(texts[0]).toMatch(/^Session [●○]{6} 32% 1h20m$/);
    expect(texts[1]).toMatch(/^Weekly [●○]{6} 53% 5d$/);
  });

  it('shows how long ago the reading was taken', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(jsonResponse(payload()))));
    activate(context as never);
    await settle();

    const chip = chipItem()!;
    expect(chip.text).toBe('$(history) now');
    expect(chip.color).toBeUndefined();
    expect(chip.priority).toBeLessThan(meterItems()[0]!.priority);
  });

  it('flags a backoff in the status bar, with the retry countdown', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(payload()))
      .mockResolvedValueOnce({
        ok: false,
        status: 429,
        headers: { get: (name: string) => (name.toLowerCase() === 'retry-after' ? '120' : null) },
        json: () => Promise.resolve({}),
        text: () => Promise.resolve(''),
      });
    vi.stubGlobal('fetch', fetchMock);
    activate(context as never);
    await settle();
    expect(chipItem()!.text).toBe('$(history) now');

    await stub.state.commands.get('claudeUsage.refresh')!();
    const chip = chipItem()!;
    expect(chip.text).toMatch(/^\$\(warning\) now · retry [12]m$/);
    expect((chip.color as stub.ThemeColor).id).toBe('charts.yellow');
    expect(meterItems()).toHaveLength(2);
  });

  it('uses the short labels when asked', async () => {
    stub.state.config['labelStyle'] = 'short';
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(jsonResponse(payload()))));
    activate(context as never);
    await settle();

    const texts = meterItems().map((item) => item.text);
    expect(texts[0]).toMatch(/^5h /);
    expect(texts[1]).toMatch(/^7d /);
  });

  it('can hide the age chip entirely', async () => {
    stub.state.config['age'] = 'never';
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(jsonResponse(payload()))));
    activate(context as never);
    await settle();

    expect(chipItem()).toBeUndefined();
    expect(meterItems()).toHaveLength(2);
  });

  it('sends the bearer token and the oauth beta header', async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(payload())));
    vi.stubGlobal('fetch', fetchMock);
    activate(context as never);
    await settle();

    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe('https://api.anthropic.com/api/oauth/usage');
    const headers = init.headers as Record<string, string>;
    expect(headers['Authorization']).toBe('Bearer test-token');
    expect(headers['anthropic-beta']).toBe('oauth-2025-04-20');
  });

  it('orders the meters left to right by descending priority', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(jsonResponse(payload()))));
    activate(context as never);
    await settle();

    const items = meterItems();
    expect(items[0]!.alignment).toBe(stub.StatusBarAlignment.Right);
    expect(items[0]!.priority).toBeGreaterThan(items[1]!.priority);
  });

  it('colours a window that crosses the warning threshold', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve(jsonResponse({ limits: [{ kind: 'session', percent: 96, severity: 'normal' }] }))),
    );
    activate(context as never);
    await settle();

    const item = meterItems()[0]!;
    expect((item.color as stub.ThemeColor).id).toBe('charts.red');
  });

  it('shows a sign-in affordance instead of meters when no token resolves', async () => {
    delete process.env['CLAUDE_CODE_OAUTH_TOKEN'];
    stub.state.config['credentials'] = 'browser';
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(jsonResponse(payload()))));
    activate(context as never);
    await new Promise((resolve) => setTimeout(resolve, 50));

    const items = stub.visibleItems();
    expect(items).toHaveLength(1);
    expect(items[0]!.text).toContain('Claude usage');
    expect(items[0]!.command).toBe('claudeUsage.signIn');
  });

  it('keeps showing the last reading when a refresh fails', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(payload()))
      .mockResolvedValueOnce(jsonResponse({ error: 'boom' }, 500));
    vi.stubGlobal('fetch', fetchMock);
    activate(context as never);
    await settle();

    await stub.state.commands.get('claudeUsage.refresh')!();
    const texts = meterItems().map((item) => item.text);
    expect(texts).toHaveLength(2);
    expect(texts[0]).toContain('32%');
  });

  it('makes one request for several windows sharing the cache', async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(payload())));
    vi.stubGlobal('fetch', fetchMock);

    const windows = [makeContext(), makeContext(), makeContext()];
    for (const each of windows) {
      activate(each as never);
    }
    await settle();
    await new Promise((resolve) => setTimeout(resolve, 200));

    expect(fetchMock).toHaveBeenCalledTimes(1);
    for (const each of windows) {
      for (const disposable of each.subscriptions) {
        disposable.dispose();
      }
    }
  });

  it('serves a second window from the cache without touching the network', async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(payload())));
    vi.stubGlobal('fetch', fetchMock);

    activate(context as never);
    await settle();
    expect(fetchMock).toHaveBeenCalledTimes(1);

    const second = makeContext();
    activate(second as never);
    await new Promise((resolve) => setTimeout(resolve, 150));

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const texts = meterItems().map((item) => item.text);
    expect(texts.filter((text) => text.includes('32%'))).toHaveLength(2);

    for (const disposable of second.subscriptions) {
      disposable.dispose();
    }
  });

  it('lets a manual refresh through even when the cache is warm', async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(payload())));
    vi.stubGlobal('fetch', fetchMock);
    activate(context as never);
    await settle();
    expect(fetchMock).toHaveBeenCalledTimes(1);

    await new Promise((resolve) => setTimeout(resolve, 20));
    await stub.state.commands.get('claudeUsage.refresh')!();
    expect(fetchMock.mock.calls.length).toBeGreaterThan(1);
  });

  it('registers the commands it contributes', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(jsonResponse(payload()))));
    activate(context as never);
    await settle();

    expect([...stub.state.commands.keys()].sort()).toEqual([
      'claudeUsage.pickBarStyle',
      'claudeUsage.refresh',
      'claudeUsage.showDetails',
      'claudeUsage.signIn',
      'claudeUsage.signOut',
    ]);
  });

  it('hides everything when the extension is switched off', async () => {
    stub.state.config['enabled'] = false;
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(jsonResponse(payload()))));
    activate(context as never);
    await new Promise((resolve) => setTimeout(resolve, 50));

    expect(stub.visibleItems()).toHaveLength(0);
  });
});
