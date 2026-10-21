import * as vscode from 'vscode';
import type { HostMessage, NodeDetail, ViewMessage } from './protocol';
import type { Store } from './store';
import { PathWatcher, debounce } from './watch';
import { isInAnyFolder } from './workspacePaths';

const VIEW_TYPE = 'agentWatch.graph';
const OPEN_SESSION_COMMAND = 'claude-vscode.editor.open';

export class AgentWatchPanel {
  private static current: AgentWatchPanel | undefined;

  static readonly viewType = VIEW_TYPE;

  static restore(
    context: vscode.ExtensionContext,
    store: Store,
    panel: vscode.WebviewPanel,
    preferredPath?: string,
  ): AgentWatchPanel {
    AgentWatchPanel.current?.dispose();
    panel.webview.options = {
      enableScripts: true,
      localResourceRoots: [vscode.Uri.joinPath(context.extensionUri, 'dist')],
    };
    AgentWatchPanel.current = new AgentWatchPanel(context, panel, store, preferredPath);
    return AgentWatchPanel.current;
  }

  static show(context: vscode.ExtensionContext, store: Store, preferredPath?: string): AgentWatchPanel {
    if (AgentWatchPanel.current) {
      const existing = AgentWatchPanel.current;
      existing.panel.reveal(existing.panel.viewColumn, false);
      void existing.refresh(preferredPath);
      return existing;
    }

    const panel = vscode.window.createWebviewPanel(
      VIEW_TYPE,
      'Agent Watch',
      vscode.ViewColumn.Active,
      {
        enableScripts: true,
        retainContextWhenHidden: true,
        localResourceRoots: [vscode.Uri.joinPath(context.extensionUri, 'dist')],
      },
    );

    AgentWatchPanel.current = new AgentWatchPanel(context, panel, store, preferredPath);
    return AgentWatchPanel.current;
  }

  private disposables: vscode.Disposable[] = [];
  private watcher: PathWatcher | undefined;
  private heartbeat: ReturnType<typeof setInterval> | undefined;
  private pending = debounce(() => undefined, 0);
  private refreshing = false;
  private queued = false;
  private disposed = false;
  private openNodeId: string | undefined;
  private openDetailRevision: string | undefined;

  private constructor(
    private readonly context: vscode.ExtensionContext,
    private readonly panel: vscode.WebviewPanel,
    private readonly store: Store,
    private preferredPath: string | undefined,
  ) {
    this.panel.iconPath = {
      light: vscode.Uri.joinPath(context.extensionUri, 'media', 'graph-light.svg'),
      dark: vscode.Uri.joinPath(context.extensionUri, 'media', 'graph-dark.svg'),
    };
    this.panel.webview.html = this.html();
    this.watcher = new PathWatcher(() => this.pending.call(), { pollMs: store.pollMs() });
    this.pending = debounce(() => {
      void this.reload();
    }, 300);
    this.panel.onDidDispose(() => this.dispose(), undefined, this.disposables);
    this.panel.onDidChangeViewState(
      () => this.syncWatcherToVisibility(),
      undefined,
      this.disposables,
    );
    this.panel.webview.onDidReceiveMessage(
      (message: ViewMessage) => {
        void this.handle(message);
      },
      undefined,
      this.disposables,
    );
  }

  private startHeartbeat(): void {
    if (this.heartbeat || this.disposed) return;
    this.heartbeat = setInterval(() => this.tick(), this.store.pollMs());
    if (typeof this.heartbeat === 'object' && 'unref' in this.heartbeat) this.heartbeat.unref();
  }

  private tick(): void {
    if (this.refreshing || this.disposed) return;
    void this.reload();
  }

  private stopHeartbeat(): void {
    if (this.heartbeat) clearInterval(this.heartbeat);
    this.heartbeat = undefined;
  }

  private syncWatcherToVisibility(): void {
    if (!this.watcher) return;
    if (this.panel.visible) {
      if (!this.watcher.started) {
        this.watcher.start();
        this.startHeartbeat();
        void this.reload();
      }
      return;
    }
    this.watcher.stop();
    this.stopHeartbeat();
  }

  async refresh(preferredPath?: string): Promise<void> {
    if (this.disposed) return;
    if (preferredPath) this.preferredPath = preferredPath;
    this.store.invalidateGit();
    this.postState(true);
    await this.reload();
  }

  private async reload(): Promise<void> {
    if (this.disposed) return;
    if (this.refreshing) {
      this.queued = true;
      return;
    }
    this.refreshing = true;
    try {
      do {
        this.queued = false;
        if (this.disposed) return;
        await this.store.discover(this.preferredPath);
        await this.store.loadSelected();
        await this.watcher?.setTargets(this.store.watchTargets());
        if (this.disposed) return;
        if (this.panel.visible) {
          this.watcher?.start();
          this.startHeartbeat();
        } else {
          this.watcher?.stop();
          this.stopHeartbeat();
        }
        this.postState(false);
      } while (this.queued);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      this.postState(false, message);
    } finally {
      this.refreshing = false;
    }
  }

  private async handle(message: ViewMessage): Promise<void> {
    switch (message.type) {
      case 'ready':
      case 'refresh':
        await this.refresh();
        return;
      case 'selectRepo':
        this.store.selectRepo(message.slug);
        this.openNodeId = undefined;
        this.openDetailRevision = undefined;
        this.postState(true);
        await this.reload();
        return;
      case 'selectWorktree':
        this.store.selectWorktree(message.key);
        this.openNodeId = undefined;
        this.openDetailRevision = undefined;
        this.postState(false);
        return;
      case 'selectNode': {
        const detail = this.store.detail(message.id);
        if (!detail) return;
        this.openNodeId = message.id;
        this.openDetailRevision = detailRevision(detail);
        this.post({ type: 'detail', detail, refreshed: false });
        return;
      }
      case 'closeDetail':
        this.openNodeId = undefined;
        this.openDetailRevision = undefined;
        return;
      case 'toggleNode':
        this.store.toggleNode(message.id);
        this.postState(false);
        return;
      case 'openSession':
        await this.openSession(message.id);
        return;
      case 'toggleAll':
        this.store.toggleAll();
        this.postState(false);
        return;
      case 'setOnlyThisWindow':
        this.store.setOnlyThisWindow(message.value);
        this.postState(true);
        await this.reload();
        return;
    }
  }

  private async openSession(id: string): Promise<void> {
    const target = this.store.sessionTarget(id);
    if (!target) return;

    const available = await vscode.commands.getCommands(true);
    if (!available.includes(OPEN_SESSION_COMMAND)) {
      void vscode.window.showWarningMessage(
        `Cannot open the chat: the Claude Code extension did not register ${OPEN_SESSION_COMMAND}. Check that it is installed and enabled.`,
      );
      return;
    }

    const folders = (vscode.workspace.workspaceFolders ?? []).map((folder) => folder.uri.fsPath);
    if (!isInAnyFolder(folders, target.cwd)) {
      const open = 'Open Folder in New Window';
      const where = target.cwd
        ? `That session ran in ${target.cwd}, outside this window.`
        : 'That session never recorded a working directory, so there is no way to tell which repo it belongs to.';
      const choice = await vscode.window.showWarningMessage(
        `${where} Resuming it here would attach it to this workspace instead.`,
        ...(target.cwd ? [open] : []),
      );
      if (choice === open && target.cwd) {
        await vscode.commands.executeCommand('vscode.openFolder', vscode.Uri.file(target.cwd), {
          forceNewWindow: true,
        });
      }
      return;
    }

    await vscode.commands.executeCommand(
      OPEN_SESSION_COMMAND,
      target.sessionId,
      undefined,
      vscode.ViewColumn.Beside,
    );
  }

  private post(message: HostMessage): void {
    if (this.disposed) return;
    void this.panel.webview.postMessage(message);
  }

  private postState(loading: boolean, message?: string): void {
    this.post({ type: 'state', state: this.store.view(loading, message) });
    if (loading || !this.openNodeId) return;
    const detail = this.store.detail(this.openNodeId);
    if (!detail) {
      this.openNodeId = undefined;
      this.openDetailRevision = undefined;
      this.post({ type: 'detailClosed' });
      return;
    }
    const revision = detailRevision(detail);
    if (revision === this.openDetailRevision) return;
    this.openDetailRevision = revision;
    this.post({ type: 'detail', detail, refreshed: true });
  }

  private html(): string {
    const webview = this.panel.webview;
    const script = webview.asWebviewUri(vscode.Uri.joinPath(this.context.extensionUri, 'dist', 'webview.js'));
    const nonce = createNonce();
    return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource} 'unsafe-inline'; script-src 'nonce-${nonce}';">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Agent Watch</title>
<style>${styles()}</style>
</head>
<body>
<header id="scope">
  <div class="scope-row" id="repo-row"><span class="caption">repo</span><div class="chips" id="repos"></div></div>
  <div class="scope-row" id="branch-row"><span class="caption">branch</span><div class="chips" id="worktrees"></div></div>
  <div class="row status" id="status">
    <span id="status-text"></span>
    <span class="spacer"></span>
    <button class="chip" id="only-window" type="button" title="Show only sessions from the folder this window has open">this window</button>
    <button class="chip" id="expand-all" type="button" title="Expand or collapse every branch">expand all</button>
    <button class="chip" id="zoom-out" type="button">−</button>
    <span id="zoom-level">100%</span>
    <button class="chip" id="zoom-in" type="button">+</button>
    <button class="chip" id="fit" type="button">Fit</button>
  </div>
</header>
<main>
  <div id="canvas"><svg id="graph" xmlns="http://www.w3.org/2000/svg"></svg></div>
  <div id="empty" class="hidden"></div>
</main>
<div id="overlay" class="hidden">
  <section id="modal">
    <header>
      <h2 id="modal-title"></h2>
      <button id="modal-close" type="button">Close</button>
    </header>
    <div id="modal-body"></div>
    <button id="jump" class="hidden" type="button">↓ Jump to latest</button>
  </section>
</div>
<script nonce="${nonce}" src="${script.toString()}"></script>
</body>
</html>`;
  }

  private dispose(): void {
    this.disposed = true;
    AgentWatchPanel.current = undefined;
    this.pending.cancel();
    this.stopHeartbeat();
    this.watcher?.dispose();
    this.watcher = undefined;
    this.panel.dispose();
    for (const disposable of this.disposables) disposable.dispose();
    this.disposables = [];
  }
}

function detailRevision(detail: NodeDetail): string {
  let chars = 0;
  for (const event of detail.events) {
    chars += (event.text?.length ?? 0) + (event.result?.length ?? 0) + (event.detail?.length ?? 0);
  }
  return `${detail.id}|${detail.status}|${detail.events.length}|${chars}`;
}

function createNonce(): string {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  let value = '';
  for (let index = 0; index < 32; index += 1) {
    value += alphabet.charAt(Math.floor(Math.random() * alphabet.length));
  }
  return value;
}

function styles(): string {
  return `
:root { color-scheme: light dark; }
body { margin: 0; font-family: var(--vscode-font-family); font-size: var(--vscode-font-size); color: var(--vscode-foreground); background: var(--vscode-editor-background); height: 100vh; display: flex; flex-direction: column; }
header#scope { padding: 8px 12px 4px; border-bottom: 1px solid var(--vscode-panel-border); display: flex; flex-direction: column; gap: 5px; }
.row { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
.scope-row { display: grid; grid-template-columns: 3.6em 1fr; gap: 8px; align-items: start; }
.scope-row.hidden { display: none; }
.scope-row + .scope-row:not(.hidden) { border-top: 1px solid var(--vscode-panel-border); padding-top: 5px; }
.scope-row .caption { font-size: 0.68em; text-transform: uppercase; letter-spacing: 0.08em; color: var(--vscode-descriptionForeground); text-align: right; padding-top: 5px; user-select: none; }
.scope-row .chips { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; min-width: 0; }
.chip { border: 1px solid var(--vscode-panel-border); background: transparent; color: var(--vscode-foreground); border-radius: 999px; padding: 2px 10px; cursor: pointer; font-size: 0.85em; }
.chip.selected { background: var(--vscode-button-background); color: var(--vscode-button-foreground); border-color: transparent; }
.chip .live { color: var(--vscode-charts-green); margin-left: 4px; }
.chip.repo { border-radius: 4px; font-weight: 600; }
.chip.repo.home::before { content: ''; display: inline-block; width: 5px; height: 5px; border-radius: 50%; background: var(--vscode-focusBorder); margin-right: 6px; vertical-align: middle; }
.chip.repo.home.selected::before { background: var(--vscode-button-foreground); }
.chip.worktree { border-radius: 999px; }
.row.status { color: var(--vscode-descriptionForeground); font-size: 0.8em; gap: 10px; }
.row.status .dot { color: var(--vscode-charts-green); }
.row.status .chip.on { background: var(--vscode-button-background); color: var(--vscode-button-foreground); border-color: transparent; }
.row.status .hidden-count { color: var(--vscode-descriptionForeground); border-bottom: 1px dotted currentColor; cursor: help; }
main { flex: 1; position: relative; overflow: hidden; }
#canvas { position: absolute; inset: 0; overflow: hidden; cursor: grab; user-select: none; -webkit-user-select: none; }
#canvas.grabbing { cursor: grabbing; }
.row.status .spacer { flex: 1; }
.row.status #status-text { display: flex; gap: 10px; align-items: center; }
svg { display: block; }
.node rect { fill: var(--vscode-editorWidget-background); stroke: var(--vscode-panel-border); stroke-width: 1.5; rx: 6; cursor: pointer; }
.node.live rect { stroke: var(--vscode-charts-green); stroke-width: 2.5; animation: pulse 1.8s ease-in-out infinite; }
@keyframes pulse { 0%, 100% { stroke-opacity: 1; } 50% { stroke-opacity: 0.35; } }
@media (prefers-reduced-motion: reduce) { .node.live rect { animation: none; } }
.node.running rect { stroke: var(--vscode-charts-blue); stroke-width: 2.5; }
.node.error rect { stroke: var(--vscode-errorForeground); stroke-width: 2.5; }
.node text { pointer-events: none; }
.node.collapsed rect { stroke-dasharray: 5 3; }
.node .badge { cursor: pointer; }
.node .badge rect { fill: var(--vscode-badge-background); stroke: none; }
.node .badge text { fill: var(--vscode-badge-foreground); font-size: 11px; }
.node .badge:hover rect { fill: var(--vscode-button-background); }
.node .open-chat { cursor: pointer; }
.node .open-chat rect { fill: var(--vscode-badge-background); stroke: none; }
.node .open-chat text { fill: var(--vscode-badge-foreground); font-size: 11px; }
.node .open-chat:hover rect { fill: var(--vscode-button-background); }
.node .label { fill: var(--vscode-foreground); font-size: 12px; }
.node .sublabel { fill: var(--vscode-descriptionForeground); font-size: 10.5px; }
.node .glyph { font-size: 12px; }
.node.live .glyph { fill: var(--vscode-charts-green); }
.node.running .glyph { fill: var(--vscode-charts-blue); }
.node.done .glyph { fill: var(--vscode-descriptionForeground); }
.node.error .glyph { fill: var(--vscode-errorForeground); }
path.edge { fill: none; stroke: var(--vscode-panel-border); stroke-width: 1.5; }
path.edge.live { stroke: var(--vscode-charts-green); stroke-width: 2.5; }
path.edge.running { stroke: var(--vscode-charts-blue); stroke-width: 2.5; }
#empty { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; color: var(--vscode-descriptionForeground); text-align: center; padding: 24px; }
.hidden { display: none !important; }
#overlay { position: absolute; inset: 0; background: rgba(0,0,0,0.45); display: flex; align-items: center; justify-content: center; z-index: 10; }
#modal { background: var(--vscode-editorWidget-background); border: 1px solid var(--vscode-panel-border); border-radius: 8px; width: min(820px, 92vw); max-height: 82vh; display: flex; flex-direction: column; position: relative; }
#jump { position: absolute; bottom: 14px; left: 50%; transform: translateX(-50%); background: var(--vscode-button-background); color: var(--vscode-button-foreground); border: none; padding: 5px 12px; border-radius: 999px; cursor: pointer; box-shadow: 0 2px 8px rgba(0,0,0,0.35); }
#modal header { display: flex; justify-content: space-between; align-items: center; padding: 10px 14px; border-bottom: 1px solid var(--vscode-panel-border); }
#modal h2 { margin: 0; font-size: 1em; }
#modal button { background: var(--vscode-button-secondaryBackground); color: var(--vscode-button-secondaryForeground); border: none; padding: 4px 10px; border-radius: 4px; cursor: pointer; }
#modal-body { overflow: auto; padding: 10px 14px; }
#modal-body details { margin-top: 4px; }
#modal-body summary { cursor: pointer; color: var(--vscode-textLink-foreground); font-size: 0.85em; }
#modal-body details[open] summary { margin-bottom: 4px; }
.event { border-bottom: 1px solid var(--vscode-panel-border); padding: 6px 0; }
.event:last-child { border-bottom: none; }
.event .head { display: flex; gap: 8px; align-items: baseline; }
.event .tool { font-weight: 600; }
.event .summary { color: var(--vscode-descriptionForeground); overflow-wrap: anywhere; }
.event .summary.muted { opacity: 0.6; font-style: italic; }
.event pre { background: var(--vscode-textCodeBlock-background); padding: 6px 8px; border-radius: 4px; overflow-x: auto; margin: 4px 0 0; white-space: pre-wrap; overflow-wrap: anywhere; }
.event.thinking .summary { font-style: italic; }
.event.user { border-left: 2px solid var(--vscode-textLink-foreground); padding-left: 8px; }
.event.user .tool { color: var(--vscode-textLink-foreground); text-transform: uppercase; letter-spacing: 0.04em; font-size: 0.85em; }
.event.meta .tool { color: var(--vscode-descriptionForeground); font-weight: 500; }
.event button.more { margin-top: 4px; background: transparent; border: 1px solid var(--vscode-panel-border); color: var(--vscode-textLink-foreground); border-radius: 4px; padding: 1px 8px; cursor: pointer; font-size: 0.85em; font-family: inherit; }
.event button.more:hover { background: var(--vscode-toolbar-hoverBackground); }
.event.err .tool { color: var(--vscode-errorForeground); }
`;
}
