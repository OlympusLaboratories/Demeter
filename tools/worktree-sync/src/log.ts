import * as fs from 'node:fs';
import * as os from 'node:os';
import * as path from 'node:path';
import * as vscode from 'vscode';

function logFile(): string {
  return (
    process.env.WORKTREE_SYNC_LOG_FILE ??
    path.join(os.homedir(), '.claude', 'tools', 'worktree-sync.log')
  );
}

export class Logger {
  private readonly channel: vscode.OutputChannel;
  private fileBroken = false;

  constructor() {
    this.channel = vscode.window.createOutputChannel('Worktree Sync');
  }

  info(message: string): void {
    const stamp = new Date().toISOString().slice(11, 23);
    this.channel.appendLine(`${stamp} ${message}`);
    if (this.fileBroken) {
      return;
    }
    try {
      const file = logFile();
      fs.mkdirSync(path.dirname(file), { recursive: true });
      fs.appendFileSync(file, `${new Date().toISOString()} ${message}\n`);
    } catch {
      this.fileBroken = true;
    }
  }

  report(lines: string[]): void {
    this.channel.appendLine('');
    for (const line of lines) {
      this.channel.appendLine(line);
    }
    this.channel.show(true);
  }

  dispose(): void {
    this.channel.dispose();
  }
}
