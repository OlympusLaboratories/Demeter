import * as vscode from 'vscode';
import { Logger } from './log';
import { SessionIndex } from './sessionIndex';
import { Syncer } from './sync';

export function activate(context: vscode.ExtensionContext): void {
  const log = new Logger();
  const index = new SessionIndex(
    () => vscode.workspace.getConfiguration('worktreeSync').get<string>('projectsDir', '~/.claude/projects'),
    log,
  );
  const syncer = new Syncer(index, log);

  log.info('activated');
  void index.ensureFresh(true);

  context.subscriptions.push(
    log,
    vscode.window.tabGroups.onDidChangeTabs(() => syncer.onTabsChanged()),
    vscode.window.tabGroups.onDidChangeTabGroups(() => syncer.onTabsChanged()),
    vscode.window.onDidChangeActiveTerminal((terminal) => syncer.onActiveTerminalChanged(terminal)),
    vscode.window.onDidChangeTerminalShellIntegration(({ terminal }) => syncer.cwdOf(terminal)),
    vscode.window.onDidCloseTerminal((terminal) => syncer.noteTerminalClosed(terminal)),

    vscode.commands.registerCommand('worktreeSync.toggle', async () => {
      const cfg = vscode.workspace.getConfiguration('worktreeSync');
      const next = !cfg.get<boolean>('enabled', true);
      await cfg.update('enabled', next, vscode.ConfigurationTarget.Global);
      void vscode.window.showInformationMessage(`Worktree Sync ${next ? 'enabled' : 'disabled'}`);
    }),

    vscode.commands.registerCommand('worktreeSync.diagnostics', async () => {
      log.report(await syncer.diagnostics());
    }),

    vscode.commands.registerCommand('worktreeSync.rebuildIndex', async () => {
      await index.ensureFresh(true);
      void vscode.window.showInformationMessage(
        `Worktree Sync: indexed ${index.entries().length} sessions across ${index.knownWorktrees().size} worktrees`,
      );
    }),
  );
}

export function deactivate(): void {}
