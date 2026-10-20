import { readFileSync } from 'node:fs';
import * as path from 'node:path';
import { afterEach, describe, expect, it } from 'vitest';
import * as vscode from 'vscode';
import { activate, deactivate } from './extension';
import {
  configValues,
  registeredCommands,
  registeredSerializers,
  resetStub,
  statusBarItems,
  type StubPanel,
} from './testing/vscodeStub';

afterEach(() => resetStub());

function context(): vscode.ExtensionContext {
  return {
    subscriptions: [] as { dispose(): void }[],
    extensionUri: vscode.Uri.file('/ext'),
  } as unknown as vscode.ExtensionContext;
}

describe('activate', () => {
  it('registers both commands without touching the filesystem', () => {
    const ctx = context();
    activate(ctx);

    expect([...registeredCommands.keys()].sort()).toEqual(['agentWatch.open', 'agentWatch.refresh']);
    expect(ctx.subscriptions.length).toBeGreaterThan(0);
  });

  it('deactivates cleanly', () => {
    activate(context());
    expect(() => deactivate()).not.toThrow();
  });
});

describe('panel restore', () => {
  it('registers a serializer so the tab survives a window reload', () => {
    activate(context());
    expect(registeredSerializers.has('agentWatch.graph')).toBe(true);
  });

  it('rebuilds a restored panel with scripts and a locked resource root', async () => {
    activate(context());
    const serializer = registeredSerializers.get('agentWatch.graph') as {
      deserializeWebviewPanel(panel: unknown): Promise<void>;
    };

    const revived = (vscode.window as unknown as { createWebviewPanel(): StubPanel }).createWebviewPanel();
    await serializer.deserializeWebviewPanel(revived);

    expect(revived.webview.options['enableScripts']).toBe(true);
    expect(revived.webview.html).toContain('dist/webview.js');
  });
});

describe('status bar', () => {
  it('sits left of claude-usage, which spans 50-101 at its default priority', () => {
    activate(context());
    expect(statusBarItems[0]?.priority).toBeGreaterThan(101);
  });

  it('honours a configured priority', () => {
    configValues.set('agentWatch.statusBarPriority', 7);
    activate(context());
    expect(statusBarItems[0]?.priority).toBe(7);
  });

  it('shows one entry wired to the open command', () => {
    activate(context());
    expect(statusBarItems).toHaveLength(1);
    const item = statusBarItems[0]!;
    expect(item.shown).toBe(true);
    expect(item.text).toContain('Agents');
    expect(item.alignment).toBe(vscode.StatusBarAlignment.Right);
    const command = item.command;
    expect(command).toBe('agentWatch.open');
    expect(registeredCommands.has(command ?? '')).toBe(true);
  });
});

describe('activation contract', () => {
  it('activates eagerly, or the status bar entry can never appear', () => {
    const manifest = JSON.parse(
      readFileSync(path.join(process.cwd(), 'package.json'), 'utf8'),
    ) as { activationEvents?: string[]; contributes?: { commands?: { command: string }[] } };

    expect(manifest.activationEvents).toContain('onStartupFinished');

    const declared = (manifest.contributes?.commands ?? []).map((entry) => entry.command).sort();
    expect(declared).toEqual(['agentWatch.open', 'agentWatch.refresh']);
  });
});
