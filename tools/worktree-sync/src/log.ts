import * as vscode from 'vscode';

export class Logger {
  private readonly channel: vscode.OutputChannel;

  constructor() {
    this.channel = vscode.window.createOutputChannel('Worktree Sync');
  }

  info(message: string): void {
    const stamp = new Date().toISOString().slice(11, 23);
    this.channel.appendLine(`${stamp} ${message}`);
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
