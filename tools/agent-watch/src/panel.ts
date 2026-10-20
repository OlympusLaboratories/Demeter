import * as vscode from 'vscode';
import type { HostMessage, ViewMessage } from './protocol';
import type { Store } from './store';
import { PathWatcher, debounce } from './watch';

const VIEW_TYPE = 'agentWatch.graph';

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
      AgentWatchPanel.current.panel.reveal(vscode.ViewColumn.Active);
      void AgentWatchPanel.current.refresh(preferredPath);
      return AgentWatchPanel.current;
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
  private pending = debounce(() => undefined, 0);
  private refreshing = false;
  private queued = false;
  private openNodeId: string | undefined;

  private constructor(
    private readonly context: vscode.ExtensionContext,
    private readonly panel: vscode.WebviewPanel,
    private readonly store: Store,
    private preferredPath: string | undefined,
  ) {
    this.panel.webview.html = this.html();
    this.watcher = new PathWatcher(() => this.pending.call(), { pollMs: store.pollMs() });
    this.pending = debounce(() => {
      void this.reload();
    }, 300);
    this.panel.onDidDispose(() => this.dispose(), undefined, this.disposables);
    this.panel.webview.onDidReceiveMessage(
      (message: ViewMessage) => {
        void this.handle(message);
      },
      undefined,
      this.disposables,
    );
  }

  async refresh(preferredPath?: string): Promise<void> {
    if (preferredPath) this.preferredPath = preferredPath;
    this.postState(true);
    await this.reload();
  }

  private async reload(): Promise<void> {
    if (this.refreshing) {
      this.queued = true;
      return;
    }
    this.refreshing = true;
    try {
      do {
        this.queued = false;
        await this.store.discover(this.preferredPath);
        await this.store.loadSelected();
        await this.watcher?.setTargets(this.store.watchTargets());
        this.watcher?.start();
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
        this.postState(true);
        await this.reload();
        return;
      case 'selectWorktree':
        this.store.selectWorktree(message.key);
        this.openNodeId = undefined;
        this.postState(false);
        return;
      case 'selectNode': {
        const detail = this.store.detail(message.id);
        if (!detail) return;
        this.openNodeId = message.id;
        this.post({ type: 'detail', detail, refreshed: false });
        return;
      }
      case 'closeDetail':
        this.openNodeId = undefined;
        return;
      case 'revealTranscript': {
        const target = this.store.transcriptFor(message.id);
        if (target) await vscode.commands.executeCommand('revealFileInOS', vscode.Uri.file(target));
        return;
      }
      case 'toggleGroup':
        this.store.toggleGroup(message.id);
        this.postState(false);
        return;
    }
  }

  private post(message: HostMessage): void {
    void this.panel.webview.postMessage(message);
  }

  private postState(loading: boolean, message?: string): void {
    this.post({ type: 'state', state: this.store.view(loading, message) });
    if (loading || !this.openNodeId) return;
    const detail = this.store.detail(this.openNodeId);
    if (detail) this.post({ type: 'detail', detail, refreshed: true });
    else {
      this.openNodeId = undefined;
      this.post({ type: 'detailClosed' });
    }
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
  <div class="row" id="repos"></div>
  <div class="row" id="worktrees"></div>
  <div class="row status" id="status">
    <span class="spacer"></span>
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
      <div class="actions">
        <button id="reveal" class="hidden" type="button">Reveal transcript</button>
        <button id="modal-close" type="button">Close</button>
      </div>
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
    AgentWatchPanel.current = undefined;
    this.pending.cancel();
    this.watcher?.dispose();
    this.watcher = undefined;
    this.panel.dispose();
    for (const disposable of this.disposables) disposable.dispose();
    this.disposables = [];
  }
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
header#scope { padding: 8px 12px 4px; border-bottom: 1px solid var(--vscode-panel-border); display: flex; flex-direction: column; gap: 4px; }
.row { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
.chip { border: 1px solid var(--vscode-panel-border); background: transparent; color: var(--vscode-foreground); border-radius: 999px; padding: 2px 10px; cursor: pointer; font-size: 0.85em; }
.chip.selected { background: var(--vscode-button-background); color: var(--vscode-button-foreground); border-color: transparent; }
.chip .live { color: var(--vscode-charts-green); margin-left: 4px; }
.row.status { color: var(--vscode-descriptionForeground); font-size: 0.8em; gap: 10px; }
.row.status .dot { color: var(--vscode-charts-green); }
main { flex: 1; position: relative; overflow: hidden; }
#canvas { position: absolute; inset: 0; overflow: hidden; cursor: grab; }
#canvas.grabbing { cursor: grabbing; }
.row.status .spacer { flex: 1; }
svg { display: block; }
.node rect { fill: var(--vscode-editorWidget-background); stroke: var(--vscode-panel-border); stroke-width: 1.5; rx: 6; cursor: pointer; }
.node.live rect { stroke: var(--vscode-charts-green); stroke-width: 2.5; animation: pulse 1.8s ease-in-out infinite; }
@keyframes pulse { 0%, 100% { stroke-opacity: 1; } 50% { stroke-opacity: 0.35; } }
@media (prefers-reduced-motion: reduce) { .node.live rect { animation: none; } }
.node.running rect { stroke: var(--vscode-charts-blue); stroke-width: 2.5; }
.node.error rect { stroke: var(--vscode-errorForeground); stroke-width: 2.5; }
.node text { pointer-events: none; }
.node.grouped rect { stroke-dasharray: 4 3; fill: transparent; }
.node .label { fill: var(--vscode-foreground); font-size: 12px; }
.node .sublabel { fill: var(--vscode-descriptionForeground); font-size: 10.5px; }
.node .glyph { font-size: 12px; }
.node.live .glyph { fill: var(--vscode-charts-green); }
.node.running .glyph { fill: var(--vscode-charts-blue); }
.node.done .glyph { fill: var(--vscode-descriptionForeground); }
.node.error .glyph { fill: var(--vscode-errorForeground); }
path.edge { fill: none; stroke: var(--vscode-panel-border); stroke-width: 1.5; }
#empty { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; color: var(--vscode-descriptionForeground); text-align: center; padding: 24px; }
.hidden { display: none !important; }
#overlay { position: absolute; inset: 0; background: rgba(0,0,0,0.45); display: flex; align-items: center; justify-content: center; z-index: 10; }
#modal { background: var(--vscode-editorWidget-background); border: 1px solid var(--vscode-panel-border); border-radius: 8px; width: min(820px, 92vw); max-height: 82vh; display: flex; flex-direction: column; position: relative; }
#modal .actions { display: flex; gap: 6px; }
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
.event pre { background: var(--vscode-textCodeBlock-background); padding: 6px 8px; border-radius: 4px; overflow-x: auto; margin: 4px 0 0; white-space: pre-wrap; overflow-wrap: anywhere; }
.event.thinking .summary { font-style: italic; }
.event.err .tool { color: var(--vscode-errorForeground); }
`;
}
