import * as vscode from 'vscode';

export class Logger {
  private readonly channel: vscode.OutputChannel;

  constructor() {
    this.channel = vscode.window.createOutputChannel('Claude Usage');
  }

  info(message: string): void {
    const stamp = new Date().toISOString().slice(11, 23);
    this.channel.appendLine(`${stamp} ${message}`);
  }

  show(): void {
    this.channel.show(true);
  }

  dispose(): void {
    this.channel.dispose();
  }
}
