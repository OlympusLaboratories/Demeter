import * as vscode from 'vscode';
import { Logger } from './log';

export const OPEN_CHAT_COMMAND = 'claude-vscode.editor.open';
export const LOCK_GROUP_COMMAND = 'workbench.action.lockEditorGroup';

function reason(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export async function openChatInLockedGroup(logger: Logger): Promise<void> {
  const available = new Set(await vscode.commands.getCommands(true));

  if (!available.has(OPEN_CHAT_COMMAND)) {
    logger.info(`${OPEN_CHAT_COMMAND} is not registered; this window has no Claude Code extension.`);
    void vscode.window.showWarningMessage(
      'The Claude Code extension is not available in this window, so there is no chat to open.',
    );
    return;
  }

  try {
    await vscode.commands.executeCommand(OPEN_CHAT_COMMAND);
  } catch (error) {
    logger.info(`Opening a Claude chat failed: ${reason(error)}`);
    void vscode.window.showWarningMessage(`Could not open a Claude chat: ${reason(error)}`);
    return;
  }

  if (!available.has(LOCK_GROUP_COMMAND)) {
    logger.info(`${LOCK_GROUP_COMMAND} is not registered; the chat opened in an unlocked group.`);
    return;
  }

  try {
    await vscode.commands.executeCommand(LOCK_GROUP_COMMAND);
  } catch (error) {
    logger.info(`Could not lock the group the chat opened in: ${reason(error)}`);
  }
}
