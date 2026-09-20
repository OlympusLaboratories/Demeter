import * as fs from 'node:fs/promises';
import * as vscode from 'vscode';
import type { Logger } from './log';
import type { SessionIndex } from './sessionIndex';
import { normalizePath, resolveWorktreeForCwd } from './resolve';

const CLAUDE_VIEW_TYPE = 'claudeVSCodePanel';
const GUARD_MS = 150;

const GROUP_FOCUS_COMMANDS: Record<number, string> = {
  1: 'workbench.action.focusFirstEditorGroup',
  2: 'workbench.action.focusSecondEditorGroup',
  3: 'workbench.action.focusThirdEditorGroup',
  4: 'workbench.action.focusFourthEditorGroup',
  5: 'workbench.action.focusFifthEditorGroup',
  6: 'workbench.action.focusSixthEditorGroup',
  7: 'workbench.action.focusSeventhEditorGroup',
  8: 'workbench.action.focusEighthEditorGroup',
};

export type Direction = 'both' | 'tabToTerminal' | 'terminalToTab';

export function isClaudeTab(tab: vscode.Tab): boolean {
  const input = tab.input;
  return input instanceof vscode.TabInputWebview && input.viewType.includes(CLAUDE_VIEW_TYPE);
}

async function sessionWriteAgeMs(file: string): Promise<number | undefined> {
  try {
    const stats = await fs.stat(file);
    return Math.max(0, Date.now() - stats.mtimeMs);
  } catch {
    return undefined;
  }
}

export function claudeTabs(): vscode.Tab[] {
  return vscode.window.tabGroups.all.flatMap((group) => group.tabs.filter(isClaudeTab));
}

export class Syncer {
  private guard = 0;
  private deferred: 'tabs' | 'terminal' | undefined;
  private mru: vscode.Terminal[] = [];
  private lastKnownCwd = new WeakMap<vscode.Terminal, string>();
  private lastActive: { tab: vscode.Tab; label: string } | undefined;
  private tabTimer: NodeJS.Timeout | undefined;
  private terminalTimer: NodeJS.Timeout | undefined;
  private lastTerminalTouchAt = 0;
  private lastTabSwitchAt = 0;
  private pendingReveal: { tab: vscode.Tab; at: number } | undefined;

  constructor(
    private readonly index: SessionIndex,
    private readonly log: Logger,
  ) {
    const active = this.activeClaudeTab();
    if (active) {
      this.lastActive = { tab: active, label: active.label };
    }
    if (vscode.window.activeTerminal) {
      this.mru = [vscode.window.activeTerminal];
    }
  }

  private config() {
    const cfg = vscode.workspace.getConfiguration('worktreeSync');
    return {
      enabled: cfg.get<boolean>('enabled', true),
      direction: cfg.get<Direction>('direction', 'both'),
      debounceMs: cfg.get<number>('debounceMs', 50),
      revealSettleMs: cfg.get<number>('revealSettleMs', 250),
    };
  }

  noteTerminalActivated(terminal: vscode.Terminal): void {
    this.mru = [terminal, ...this.mru.filter((t) => t !== terminal)];
    this.cwdOf(terminal);
  }

  noteTerminalClosed(terminal: vscode.Terminal): void {
    this.mru = this.mru.filter((t) => t !== terminal);
  }

  cwdOf(terminal: vscode.Terminal): string | undefined {
    const live = terminal.shellIntegration?.cwd?.fsPath;
    if (live) {
      this.lastKnownCwd.set(terminal, live);
      return live;
    }
    const cached = this.lastKnownCwd.get(terminal);
    if (cached) {
      return cached;
    }
    const options = terminal.creationOptions as vscode.TerminalOptions;
    const configured = options?.cwd;
    if (typeof configured === 'string') {
      return configured;
    }
    if (configured) {
      return configured.fsPath;
    }
    return undefined;
  }

  async keyForTerminal(terminal: vscode.Terminal): Promise<string | undefined> {
    const cwd = this.cwdOf(terminal);
    if (!cwd) {
      return undefined;
    }
    await this.index.ensureFresh();
    return resolveWorktreeForCwd(cwd, this.index.knownWorktrees());
  }

  async keyForTab(tab: vscode.Tab): Promise<string | undefined> {
    const entry = await this.index.lookupLabel(tab.label);
    return entry?.worktreePath;
  }

  private describeTabState(): string {
    const activeColumn = vscode.window.tabGroups.activeTabGroup?.viewColumn;
    return vscode.window.tabGroups.all
      .map((group) => {
        const mark = group.viewColumn === activeColumn ? '*' : ' ';
        const active = group.activeTab;
        const kind = active ? (isClaudeTab(active) ? 'claude' : 'other') : 'none';
        return `${mark}col${group.viewColumn}=${active ? `"${active.label}"[${kind}]` : '(none)'}`;
      })
      .join('  ');
  }

  onTabsChanged(event?: { changed?: readonly vscode.Tab[] }): void {
    if (this.guard > 0) {
      this.deferred = 'tabs';
      return;
    }
    this.log.info(`tab event | ${this.describeTabState()}`);

    const pending = this.pendingReveal;
    if (pending) {
      if (this.activeClaudeTab() !== pending.tab) {
        this.pendingReveal = undefined;
      } else if (event?.changed?.includes(pending.tab)) {
        this.log.info(`"${pending.tab.label}" changed while still active — re-checking whether to follow it`);
        clearTimeout(this.tabTimer);
        this.tabTimer = setTimeout(() => {
          void this.syncTabToTerminal(pending.tab);
        }, this.config().debounceMs);
        return;
      }
    }

    const changed = this.diffTabs();
    const { enabled, direction, debounceMs } = this.config();
    if (!enabled || direction === 'terminalToTab' || !changed) {
      return;
    }
    clearTimeout(this.tabTimer);
    this.tabTimer = setTimeout(() => {
      void this.syncTabToTerminal(changed);
    }, debounceMs);
  }

  onActiveTerminalChanged(terminal: vscode.Terminal | undefined): void {
    if (!terminal) {
      return;
    }
    this.noteTerminalActivated(terminal);
    if (this.guard > 0) {
      this.deferred = 'terminal';
      return;
    }
    this.lastTerminalTouchAt = Date.now();
    const { enabled, direction, debounceMs } = this.config();
    if (!enabled || direction === 'tabToTerminal') {
      return;
    }
    clearTimeout(this.terminalTimer);
    this.terminalTimer = setTimeout(() => {
      void this.syncTerminalToTab(terminal);
    }, debounceMs);
  }

  private drainDeferred(): void {
    const deferred = this.deferred;
    this.deferred = undefined;
    if (deferred === 'tabs') {
      this.onTabsChanged();
      return;
    }
    if (deferred === 'terminal') {
      const active = vscode.window.activeTerminal;
      if (active) {
        this.onActiveTerminalChanged(active);
      }
    }
  }

  private activeClaudeTab(): vscode.Tab | undefined {
    const active = vscode.window.tabGroups.activeTabGroup?.activeTab;
    return active && isClaudeTab(active) ? active : undefined;
  }

  private diffTabs(): vscode.Tab | undefined {
    const current = this.activeClaudeTab();
    if (!current) {
      return undefined;
    }
    const previous = this.lastActive;
    this.lastActive = { tab: current, label: current.label };
    if (previous && previous.tab === current) {
      return undefined;
    }
    this.log.info(
      `active Claude tab changed: ${previous ? `"${previous.label}"` : '(none)'} → "${current.label}"`,
    );
    return current;
  }

  private async guarded(fn: () => void | Promise<void>): Promise<void> {
    this.guard++;
    try {
      await fn();
    } catch (error) {
      this.log.info(`sync action failed: ${String(error)}`);
    } finally {
      setTimeout(() => {
        this.guard = Math.max(0, this.guard - 1);
        if (this.guard === 0) {
          this.drainDeferred();
        }
      }, GUARD_MS);
    }
  }

  private async terminalsForKey(key: string): Promise<vscode.Terminal[]> {
    const matches: vscode.Terminal[] = [];
    for (const terminal of vscode.window.terminals) {
      if ((await this.keyForTerminal(terminal)) === key) {
        matches.push(terminal);
      }
    }
    return matches;
  }

  private mostRecent(terminals: vscode.Terminal[]): vscode.Terminal | undefined {
    for (const candidate of this.mru) {
      if (terminals.includes(candidate)) {
        return candidate;
      }
    }
    return terminals[0];
  }

  async syncTabToTerminal(tab: vscode.Tab, force = false): Promise<void> {
    if (!force && this.activeClaudeTab() !== tab) {
      this.log.info(`"${tab.label}" is no longer the active tab — not moving the terminal`);
      return;
    }
    const entry = await this.index.lookupLabel(tab.label);
    const key = entry?.worktreePath;
    if (!key) {
      this.log.info(`tab "${tab.label}" — no worktree resolved, skipping`);
      return;
    }
    const busyFor = await sessionWriteAgeMs(entry.file);
    const settleMs = this.config().revealSettleMs;
    const workingInTerminal = this.lastTerminalTouchAt > this.lastTabSwitchAt;
    const looksLikeReveal = busyFor !== undefined && busyFor < settleMs;
    if (looksLikeReveal && workingInTerminal && !force) {
      this.log.info(
        `tab "${tab.label}" became active ${Math.round(busyFor)}ms after its session last wrote ` +
          `and you were last working in a terminal — leaving the terminal alone ` +
          `(run "Worktree Sync: Follow Active Tab" to override)`,
      );
      this.pendingReveal = { tab, at: Date.now() };
      return;
    }
    this.pendingReveal = undefined;
    this.lastTabSwitchAt = Date.now();
    const matches = await this.terminalsForKey(key);
    const active = vscode.window.activeTerminal;
    if (active && matches.includes(active)) {
      return;
    }
    const target = this.mostRecent(matches);
    if (!target) {
      this.log.info(`tab "${tab.label}" → ${key} — no terminal open for that worktree`);
      return;
    }
    if (this.activeClaudeTab() !== tab) {
      this.log.info(`"${tab.label}" stopped being active while resolving — not moving the terminal`);
      return;
    }
    this.log.info(`tab "${tab.label}" → terminal in ${key}`);
    await this.guarded(() => {
      target.show(true);
    });
  }

  async syncTerminalToTab(terminal: vscode.Terminal): Promise<void> {
    const key = await this.keyForTerminal(terminal);
    if (!key) {
      this.log.info(`terminal ${terminal.name} — no worktree resolved, skipping`);
      return;
    }
    const tab = await this.findClaudeTabForKey(key);
    if (!tab) {
      this.log.info(`terminal in ${key} — no Claude tab for that worktree`);
      return;
    }
    if (tab.isActive) {
      return;
    }
    const focusCommand = GROUP_FOCUS_COMMANDS[tab.group.viewColumn];
    if (!focusCommand) {
      this.log.info(`tab "${tab.label}" is in view column ${tab.group.viewColumn} — cannot focus`);
      return;
    }
    const tabIndex = tab.group.tabs.indexOf(tab);
    if (tabIndex < 0) {
      return;
    }
    this.log.info(`terminal in ${key} → tab "${tab.label}"`);
    await this.guarded(async () => {
      await vscode.commands.executeCommand(focusCommand);
      await vscode.commands.executeCommand('workbench.action.openEditorAtIndex', tabIndex);
      await vscode.commands.executeCommand('workbench.action.terminal.focus');
    });
  }

  private async findClaudeTabForKey(key: string): Promise<vscode.Tab | undefined> {
    const matches: vscode.Tab[] = [];
    for (const tab of claudeTabs()) {
      if ((await this.keyForTab(tab)) === key) {
        matches.push(tab);
      }
    }
    const alreadyActive = matches.find((tab) => tab.isActive);
    if (alreadyActive) {
      return alreadyActive;
    }
    if (matches.length > 1) {
      const labels = matches.map((tab) => `"${tab.label}"`).join(', ');
      this.log.info(`${key} maps to ${matches.length} Claude tabs (${labels}) — ambiguous, skipping`);
      return undefined;
    }
    return matches[0];
  }

  async followActiveTab(): Promise<void> {
    const tab = this.activeClaudeTab();
    if (!tab) {
      void vscode.window.showInformationMessage('Worktree Sync: no Claude tab is active.');
      return;
    }
    this.lastTabSwitchAt = Date.now();
    await this.syncTabToTerminal(tab, true);
  }

  async diagnostics(): Promise<string[]> {
    await this.index.ensureFresh(true);
    const lines: string[] = ['=== Worktree Sync diagnostics ==='];
    const { enabled, direction } = this.config();
    lines.push(`enabled: ${enabled}    direction: ${direction}`);

    lines.push('', '--- Claude tabs ---');
    const tabs = claudeTabs();
    if (tabs.length === 0) {
      lines.push('(none found — no webview tabs with viewType containing claudeVSCodePanel)');
    }
    for (const tab of tabs) {
      const entry = await this.index.lookupLabel(tab.label);
      const where = `col ${tab.group.viewColumn} idx ${tab.group.tabs.indexOf(tab)}`;
      if (entry) {
        lines.push(
          `  ${tab.isActive ? '*' : ' '} "${tab.label}" [${where}] → ${entry.worktreePath}`,
          `       matched on ${entry.matchedVia}, worktree via ${entry.source}, aliases: ${entry.aliases.map((a) => `"${a}"`).join(', ')}`,
        );
      } else {
        lines.push(
          `  ${tab.isActive ? '*' : ' '} "${tab.label}" [${where}] → UNRESOLVED (no session on disk with this title or worktree name)`,
        );
      }
    }

    const byKey = new Map<string, string[]>();
    for (const tab of tabs) {
      const key = await this.keyForTab(tab);
      if (key) {
        byKey.set(key, [...(byKey.get(key) ?? []), tab.label]);
      }
    }
    const ambiguous = [...byKey.entries()].filter(([, labels]) => labels.length > 1);
    if (ambiguous.length > 0) {
      lines.push('', '--- Ambiguous (terminal -> tab will skip these) ---');
      for (const [key, labels] of ambiguous) {
        lines.push(`  ${key}: ${labels.map((l) => `"${l}"`).join(', ')}`);
      }
    }

    lines.push('', '--- Terminals ---');
    if (vscode.window.terminals.length === 0) {
      lines.push('(none)');
    }
    for (const terminal of vscode.window.terminals) {
      const cwd = this.cwdOf(terminal);
      const active = terminal === vscode.window.activeTerminal ? '*' : ' ';
      if (!cwd) {
        lines.push(`  ${active} ${terminal.name} → NO CWD (shell integration not ready)`);
        continue;
      }
      const key = resolveWorktreeForCwd(cwd, this.index.knownWorktrees());
      lines.push(
        `  ${active} ${terminal.name} cwd=${cwd} → ${key ?? 'UNRESOLVED (cwd under no known worktree)'}`,
      );
    }

    lines.push('', '--- Known worktrees ---');
    for (const worktree of [...this.index.knownWorktrees()].sort()) {
      lines.push(`  ${worktree}`);
    }

    const skipped = this.index.skippedSessions();
    lines.push('', `--- Skipped sessions (${skipped.length}) ---`);
    for (const entry of skipped) {
      lines.push(`  ${normalizePath(entry.file)}: ${entry.reason}`);
    }

    return lines;
  }
}
