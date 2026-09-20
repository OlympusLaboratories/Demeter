import * as fs from 'node:fs/promises';
import * as path from 'node:path';
import * as vscode from 'vscode';
import { Logger } from './log';
import { SessionIndex } from './sessionIndex';
import { newerInstalledVersion } from './staleBuild';
import { Syncer } from './sync';

const EXTENSION_ID = 'dylanlarrabee.worktree-sync';

async function warnIfStaleBuildIsRunning(log: Logger): Promise<void> {
  const self = vscode.extensions.getExtension(EXTENSION_ID);
  const running = self?.packageJSON?.version;
  if (typeof running !== 'string' || !self) {
    return;
  }
  let entries: string[];
  try {
    entries = await fs.readdir(path.dirname(self.extensionPath));
  } catch {
    return;
  }
  const newer = newerInstalledVersion(entries, EXTENSION_ID, running);
  if (!newer) {
    log.info(`running ${running} (newest installed)`);
    return;
  }
  log.info(`running ${running} but ${newer} is installed on disk — reload required`);
  const reload = 'Reload Window';
  const choice = await vscode.window.showWarningMessage(
    `Worktree Sync ${newer} is installed but this window is still running ${running}. ` +
      `Installing does not reload a running window.`,
    reload,
  );
  if (choice === reload) {
    await vscode.commands.executeCommand('workbench.action.reloadWindow');
  }
}

export function activate(context: vscode.ExtensionContext): void {
  const log = new Logger();
  const index = new SessionIndex(
    () => vscode.workspace.getConfiguration('worktreeSync').get<string>('projectsDir', '~/.claude/projects'),
    log,
  );
  const syncer = new Syncer(index, log);

  log.info('activated');
  void warnIfStaleBuildIsRunning(log);
  void index.ensureFresh(true);

  context.subscriptions.push(
    log,
    vscode.window.tabGroups.onDidChangeTabs((event) => syncer.onTabsChanged(event)),
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

    vscode.commands.registerCommand('worktreeSync.followActiveTab', async () => {
      await syncer.followActiveTab();
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
