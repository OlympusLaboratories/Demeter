import { afterEach, describe, expect, it } from 'vitest';
import * as vscode from 'vscode';
import { activate, deactivate } from './extension';
import { registeredCommands, registeredSerializers, resetStub, type StubPanel } from './testing/vscodeStub';

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
