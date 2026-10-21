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
    statusBarPriority: config.get<number>('statusBarPriority') ?? 110,
    initialDepth: config.get<number>('initialDepth') ?? 1,
    zoomSensitivity: config.get<number>('zoomSensitivity') ?? 1,
    hideDeletedWork: config.get<boolean>('hideDeletedWork') ?? true,
    workspaceFolders: workspaceFolders(),
  };
}

function workspaceFolders(): string[] {
  return (vscode.workspace.workspaceFolders ?? []).map((folder) => folder.uri.fsPath);
}

function preferredWorkspacePath(): string | undefined {
  const folders = vscode.workspace.workspaceFolders;
  return folders && folders.length > 0 ? folders[0]?.uri.fsPath : undefined;
}

export function activate(context: vscode.ExtensionContext): void {
  const store = new Store(readSettings());

  const status = vscode.window.createStatusBarItem(
    vscode.StatusBarAlignment.Right,
    readSettings().statusBarPriority,
  );
  status.text = '$(type-hierarchy) Agents';
  status.tooltip = 'Agent Watch — show what Claude Code sessions and their agents are doing';
  status.command = 'agentWatch.open';
  status.show();
  context.subscriptions.push(status);

  context.subscriptions.push(
    vscode.workspace.onDidChangeConfiguration((event) => {
      if (event.affectsConfiguration('agentWatch')) store.updateSettings(readSettings());
    }),
  );

  if (typeof vscode.window.registerWebviewPanelSerializer === 'function') {
    context.subscriptions.push(
      vscode.window.registerWebviewPanelSerializer(AgentWatchPanel.viewType, {
        async deserializeWebviewPanel(panel: vscode.WebviewPanel) {
          const restored = AgentWatchPanel.restore(context, store, panel, preferredWorkspacePath());
          await restored.refresh();
        },
      }),
    );
  }

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
