import { afterEach, describe, expect, it } from 'vitest';
import * as vscode from 'vscode';
import { activate, deactivate } from './extension';
import { registeredCommands, resetStub } from './testing/vscodeStub';

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
