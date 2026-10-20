import * as fs from 'node:fs/promises';
import * as os from 'node:os';
import * as path from 'node:path';
import { afterEach, describe, expect, it } from 'vitest';
import * as vscode from 'vscode';
import { AgentWatchPanel } from './panel';
import { Store } from './store';
import { createdPanels, resetStub } from './testing/vscodeStub';
import type { HostMessage } from './protocol';

const temps: string[] = [];
const SESSION_ID = 'bbbbbbbb-1111-2222-3333-444444444444';

function transcriptPath(projects: string): string {
  return path.join(projects, '-tmp-repo', `${SESSION_ID}.jsonl`);
}

async function appendSaid(projects: string, text: string): Promise<void> {
  await fs.appendFile(
    transcriptPath(projects),
    `${JSON.stringify({ type: 'assistant', cwd: '/tmp/repo', message: { content: [{ type: 'text', text }] } })}\n`,
  );
}

async function fixtureProjects(): Promise<string> {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'agent-watch-panel-'));
  temps.push(root);
  const dir = path.join(root, 'projects', '-tmp-repo');
  await fs.mkdir(path.join(dir, SESSION_ID, 'subagents'), { recursive: true });
  await fs.writeFile(
    path.join(dir, `${SESSION_ID}.jsonl`),
    `${JSON.stringify({ type: 'user', cwd: '/tmp/repo', message: { content: [{ type: 'text', text: 'hi' }] } })}\n`,
  );
  return path.join(root, 'projects');
}

function store(projects: string): Store {
  return new Store({
    projectsDir: projects,
    liveWindowSeconds: 3600,
    recentDays: 3650,
    maxSessionsPerRepo: 12,
    pollSeconds: 2,
    statusBarPriority: 110,
    initialDepth: 1,
    zoomSensitivity: 1,
    hideDeletedWork: false,
  });
}

function context(): vscode.ExtensionContext {
  return {
    subscriptions: [] as { dispose(): void }[],
    extensionUri: vscode.Uri.file('/ext'),
  } as unknown as vscode.ExtensionContext;
}

function states(panel: (typeof createdPanels)[number]): HostMessage[] {
  return panel.webview.posted as HostMessage[];
}

afterEach(async () => {
  for (const panel of createdPanels) panel.onDidDispose.fire();
  resetStub();
  while (temps.length > 0) {
    const dir = temps.pop();
    if (dir) await fs.rm(dir, { recursive: true, force: true });
  }
});

describe('AgentWatchPanel', () => {
  it('serves a nonce-locked CSP and loads only the bundled webview script', async () => {
    const projects = await fixtureProjects();
    AgentWatchPanel.show(context(), store(projects));
    const panel = createdPanels[0];

    expect(panel?.webview.html).toMatch(/script-src 'nonce-[A-Za-z0-9]{32}'/);
    expect(panel?.webview.html).toContain('/ext/dist/webview.js');
    expect(panel?.webview.html).toContain("default-src 'none'");
    expect(panel?.webview.html ?? '').not.toMatch(/<(?:script|link|img)[^>]+(?:src|href)="https?:/);
  });

  it('gives the webview the labelled scope rows it addresses by id', async () => {
    const projects = await fixtureProjects();
    AgentWatchPanel.show(context(), store(projects));
    const html = createdPanels[0]?.webview.html ?? '';

    for (const id of ['repo-row', 'repos', 'branch-row', 'worktrees']) {
      expect(html).toContain(`id="${id}"`);
    }
    expect(html).toMatch(/<span class="caption">repo<\/span>/);
    expect(html).toMatch(/<span class="caption">branch<\/span>/);
  });

  it('loads and posts a populated state on refresh', async () => {
    const projects = await fixtureProjects();
    const panel = AgentWatchPanel.show(context(), store(projects));
    await panel.refresh();

    const posted = states(createdPanels[0]!);
    const last = posted[posted.length - 1];
    expect(last?.type).toBe('state');
    if (last?.type !== 'state') throw new Error('expected a state message');
    expect(last.state.loading).toBe(false);
    expect(last.state.repos).toHaveLength(1);
    expect(last.state.graph.nodes).toHaveLength(1);
    expect(last.state.watchedCount).toBeGreaterThan(0);
  });

  it('answers a node selection with that node detail', async () => {
    const projects = await fixtureProjects();
    const panel = AgentWatchPanel.show(context(), store(projects));
    await panel.refresh();

    const stub = createdPanels[0]!;
    const posted = states(stub);
    const state = posted.find((message) => message.type === 'state' && message.state.graph.nodes.length > 0);
    if (state?.type !== 'state') throw new Error('expected a populated state');
    const nodeId = state.state.graph.nodes[0]!.id;

    stub.webview.onDidReceiveMessage.fire({ type: 'selectNode', id: nodeId });
    await new Promise((resolve) => setImmediate(resolve));

    const detail = states(stub).find((message) => message.type === 'detail');
    expect(detail?.type).toBe('detail');
    if (detail?.type !== 'detail') throw new Error('expected a detail message');
    expect(detail.detail.id).toBe(nodeId);
  });

  it('collapses concurrent reloads instead of stacking them', async () => {
    const projects = await fixtureProjects();
    const panel = AgentWatchPanel.show(context(), store(projects));

    await Promise.all([panel.refresh(), panel.refresh(), panel.refresh()]);

    const finished = states(createdPanels[0]!).filter(
      (message) => message.type === 'state' && !message.state.loading,
    );
    expect(finished.length).toBeLessThanOrEqual(3);
    expect(finished.length).toBeGreaterThan(0);
  });

  it('stops watching once the panel is disposed', async () => {
    const projects = await fixtureProjects();
    const panel = AgentWatchPanel.show(context(), store(projects));
    await panel.refresh();

    const stub = createdPanels[0]!;
    stub.onDidDispose.fire();

    const before = states(stub).length;
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(states(stub).length).toBe(before);
  });
});

describe('live detail', () => {
  it('pushes the open node detail again once its transcript grows, flagged as a refresh', async () => {
    const projects = await fixtureProjects();
    const panel = AgentWatchPanel.show(context(), store(projects));
    await panel.refresh();

    const stub = createdPanels[0]!;
    const state = states(stub).find((m) => m.type === 'state' && m.state.graph.nodes.length > 0);
    if (state?.type !== 'state') throw new Error('expected a populated state');
    const nodeId = state.state.graph.nodes[0]!.id;

    stub.webview.onDidReceiveMessage.fire({ type: 'selectNode', id: nodeId });
    await new Promise((resolve) => setImmediate(resolve));

    const first = states(stub).filter((m) => m.type === 'detail');
    expect(first).toHaveLength(1);
    expect(first[0]?.type === 'detail' && first[0].refreshed).toBe(false);

    await appendSaid(projects, 'a second thing the agent said');
    await panel.refresh();

    const all = states(stub).filter((m) => m.type === 'detail');
    expect(all.length).toBeGreaterThan(1);
    const latest = all[all.length - 1];
    if (latest?.type !== 'detail') throw new Error('expected a detail message');
    expect(latest.refreshed).toBe(true);
    expect(latest.detail.id).toBe(nodeId);
    expect(latest.detail.events.map((event) => event.text)).toContain('a second thing the agent said');
  });

  it('leaves an unchanged detail alone instead of re-posting it every refresh', async () => {
    const projects = await fixtureProjects();
    const panel = AgentWatchPanel.show(context(), store(projects));
    await panel.refresh();

    const stub = createdPanels[0]!;
    const state = states(stub).find((m) => m.type === 'state' && m.state.graph.nodes.length > 0);
    if (state?.type !== 'state') throw new Error('expected a populated state');

    stub.webview.onDidReceiveMessage.fire({ type: 'selectNode', id: state.state.graph.nodes[0]!.id });
    await new Promise((resolve) => setImmediate(resolve));

    await panel.refresh();
    await panel.refresh();

    expect(states(stub).filter((m) => m.type === 'detail')).toHaveLength(1);
  });

  it('stops pushing detail once the webview closes the modal', async () => {
    const projects = await fixtureProjects();
    const panel = AgentWatchPanel.show(context(), store(projects));
    await panel.refresh();

    const stub = createdPanels[0]!;
    const state = states(stub).find((m) => m.type === 'state' && m.state.graph.nodes.length > 0);
    if (state?.type !== 'state') throw new Error('expected a populated state');

    stub.webview.onDidReceiveMessage.fire({ type: 'selectNode', id: state.state.graph.nodes[0]!.id });
    await new Promise((resolve) => setImmediate(resolve));
    stub.webview.onDidReceiveMessage.fire({ type: 'closeDetail' });
    await new Promise((resolve) => setImmediate(resolve));

    const before = states(stub).filter((m) => m.type === 'detail').length;
    await panel.refresh();
    expect(states(stub).filter((m) => m.type === 'detail')).toHaveLength(before);
  });

  it('tells the webview to close when the open node disappears from the graph', async () => {
    const projects = await fixtureProjects();
    const panel = AgentWatchPanel.show(context(), store(projects));
    await panel.refresh();

    const stub = createdPanels[0]!;
    stub.webview.onDidReceiveMessage.fire({ type: 'selectNode', id: 'session:does-not-exist' });
    await new Promise((resolve) => setImmediate(resolve));
    expect(states(stub).some((m) => m.type === 'detail')).toBe(false);

    const state = states(stub).find((m) => m.type === 'state' && m.state.graph.nodes.length > 0);
    if (state?.type !== 'state') throw new Error('expected a populated state');
    stub.webview.onDidReceiveMessage.fire({ type: 'selectNode', id: state.state.graph.nodes[0]!.id });
    await new Promise((resolve) => setImmediate(resolve));

    stub.webview.onDidReceiveMessage.fire({ type: 'selectWorktree', key: 'nope' });
    await new Promise((resolve) => setImmediate(resolve));
    await panel.refresh();
    expect(states(stub).filter((m) => m.type === 'detail').length).toBeGreaterThan(0);
  });
});

describe('resource use', () => {
  it('polls only while the tab is visible', async () => {
    const projects = await fixtureProjects();
    const panel = AgentWatchPanel.show(context(), store(projects));
    await panel.refresh();

    const stub = createdPanels[0]!;
    const posted = () => states(stub).filter((m) => m.type === 'state').length;

    stub.visible = false;
    stub.onDidChangeViewState.fire();
    await new Promise((resolve) => setImmediate(resolve));
    const whileHidden = posted();

    await new Promise((resolve) => setTimeout(resolve, 30));
    expect(posted()).toBe(whileHidden);

    stub.visible = true;
    stub.onDidChangeViewState.fire();
    for (let tick = 0; tick < 50 && posted() === whileHidden; tick += 1) {
      await new Promise((resolve) => setTimeout(resolve, 10));
    }
    expect(posted()).toBeGreaterThan(whileHidden);
  });

  it('keeps refreshing while visible even when nothing on disk changes', async () => {
    const projects = await fixtureProjects();
    const panel = AgentWatchPanel.show(context(), store(projects));
    await panel.refresh();

    const stub = createdPanels[0]!;
    const posted = () => states(stub).filter((m) => m.type === 'state').length;
    const before = posted();

    for (let tick = 0; tick < 40 && posted() === before; tick += 1) {
      await new Promise((resolve) => setTimeout(resolve, 50));
    }

    expect(posted()).toBeGreaterThan(before);
  });

  it('reveals the existing tab instead of opening a second one', async () => {
    const projects = await fixtureProjects();
    const ctx = context();
    const shared = store(projects);

    const first = AgentWatchPanel.show(ctx, shared);
    await first.refresh();
    const second = AgentWatchPanel.show(ctx, shared);

    expect(createdPanels).toHaveLength(1);
    expect(second).toBe(first);
    const reveal = createdPanels[0]!.revealCalls.at(-1);
    expect(reveal?.column).toBe(1);
    expect(reveal?.preserveFocus).toBe(false);
  });

  it('stops polling entirely once the tab is closed', async () => {
    const projects = await fixtureProjects();
    const panel = AgentWatchPanel.show(context(), store(projects));
    await panel.refresh();

    const stub = createdPanels[0]!;
    stub.onDidDispose.fire();
    const before = states(stub).length;

    await new Promise((resolve) => setTimeout(resolve, 40));
    expect(states(stub).length).toBe(before);
  });
});
