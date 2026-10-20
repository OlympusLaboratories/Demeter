import * as vscode from 'vscode';
import { AgentWatchPanel } from './panel';
import { claudeProjectsDir } from './paths';
import { Store, type StoreSettings } from './store';

function readSettings(): StoreSettings {
  const config = vscode.workspace.getConfiguration('agentWatch');
  return {
    projectsDir: claudeProjectsDir(config.get<string>('projectsDir')),
    liveWindowSeconds: config.get<number>('liveWindowSeconds') ?? 60,
    recentDays: config.get<number>('recentDays') ?? 7,
    maxSessionsPerRepo: config.get<number>('maxSessionsPerRepo') ?? 12,
    pollSeconds: config.get<number>('pollSeconds') ?? 2,
  };
}

function preferredWorkspacePath(): string | undefined {
  const folders = vscode.workspace.workspaceFolders;
  return folders && folders.length > 0 ? folders[0]?.uri.fsPath : undefined;
}

export function activate(context: vscode.ExtensionContext): void {
  const store = new Store(readSettings());

  context.subscriptions.push(
    vscode.workspace.onDidChangeConfiguration((event) => {
      if (event.affectsConfiguration('agentWatch')) store.updateSettings(readSettings());
    }),
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('agentWatch.open', () => {
      AgentWatchPanel.show(context, store, preferredWorkspacePath());
    }),
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('agentWatch.refresh', () => {
      const panel = AgentWatchPanel.show(context, store, preferredWorkspacePath());
      void panel.refresh();
    }),
  );
}

export function deactivate(): void {}
